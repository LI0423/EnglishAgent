from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import uuid4
import json
import os
import random
import threading
import time
import math
import re
from datetime import datetime, timedelta

from ..deps import get_current_user
from ..db import (
    save_vocabulary,
    get_user_vocabulary,
    get_user_vocabulary_by_word,
    get_user_vocabulary_word_set,
    get_vocabulary_mastery_counts,
    get_vocabulary_page,
    delete_vocabulary,
    delete_vocabulary_bulk,
    get_due_vocabulary,
    get_vocabulary_by_id,
    review_vocabulary,
    get_vocabulary_stats,
    save_vocabulary_strategy_session,
    get_vocabulary_strategy_insights,
    save_vocabulary_learning_attempt,
    save_learning_event,
    save_mistake,
    get_user_mistakes,
)
from ..services.ielts_vocabulary_bank_service import (
    get_ielts_vocabulary_bank_by_head_word,
    get_ielts_vocabulary_bank_by_ids,
    get_ielts_vocabulary_bank_summary,
    list_ielts_vocabulary_bank,
    sample_word_definitions,
    LOW_VALUE_WORDS,
)
from ..services.ability_service import get_difficulty_recommendation, record_practice_result
from ..redis_client import clear_timed_state, get_timed_state, set_timed_state
from ..services.tts_service import get_tts_service

try:
    from models.generator_model import GeneratorModel
except Exception:  # pragma: no cover - keeps vocabulary routes usable without LLM deps
    GeneratorModel = None


router = APIRouter()
test_runtime: Dict[str, Dict[str, Any]] = {}
context_replay_runtime: Dict[str, Dict[str, Any]] = {}
_vocab_llm = None
_tts_service = get_tts_service()


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _primary_topic(word_row: Dict[str, Any]) -> str:
    """从 tags 解析 topic:xxx。

    旧实现把所有非黑名单 tag 当作话题返回，而词库词的 tags 形如
    ["ielts_bank", "difficulty:easy", "topic:work", ...] —— 会把 "ielts_bank" 当话题，
    导致喂给成长引擎的 topic 恒错。
    """
    for tag in word_row.get("tags") or []:
        text = str(tag or "").strip().lower()
        if text.startswith("topic:"):
            value = text.split(":", 1)[1].strip()
            if value and value != "general":
                return value
    return "general"


def _word_difficulty_tag(word_row: Dict[str, Any]) -> str:
    """vocabulary 表没有 difficulty 列，难度只能来自 difficulty:xxx 标签。"""
    for tag in word_row.get("tags") or []:
        text = str(tag or "").strip().lower()
        if text.startswith("difficulty:"):
            value = text.split(":", 1)[1].strip()
            if value:
                return value
    return "medium"


def _today_date_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_date_key(value: str = "") -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return _today_date_key()


def _seconds_until_next_day(date_key: str = "") -> int:
    safe_key = _normalize_date_key(date_key)
    try:
        day = datetime.strptime(safe_key, "%Y-%m-%d")
    except ValueError:
        day = datetime.now()
    next_day = day + timedelta(days=1)
    ttl = int((next_day - datetime.now()).total_seconds())
    return max(3600, ttl)


def _today_learning_status_key(user_id: str, date_key: str = "") -> str:
    safe_key = _normalize_date_key(date_key)
    return f"vocabulary:today_learning:completed:{user_id}:{safe_key}"


class WordCreate(BaseModel):
    word: str
    definition: str = ""
    examples: List[str] = []
    pronunciation: str = ""
    part_of_speech: str = ""
    tags: List[str] = []
    source_module: str = "manual"


class WordItem(BaseModel):
    id: str
    user_id: str
    word: str
    definition: str
    examples: List[str]
    pronunciation: str
    part_of_speech: str
    tags: List[str]
    source_module: str
    mastery_level: float
    last_reviewed_at: int
    next_review_date: int
    created_at: int


class LearnSessionRequest(BaseModel):
    strategy: str = "spaced"
    count: int = 10


class TodayLearnSessionRequest(BaseModel):
    count: int = 10
    topic: str = ""
    difficulty: str = ""


class TodayLearningStatusRequest(BaseModel):
    date_key: str = ""
    completed: bool = True


class TodayLearningStatusResponse(BaseModel):
    date_key: str
    completed: bool


class VocabularyWordAudioResponse(BaseModel):
    word: str
    audio_url: str
    cached: bool = False
    storage: str = ""
    backend: str = ""


class LearnSessionWordItem(WordItem):
    scheduler_score: float = 0.0
    scheduler_reason: str = ""


class LearnSessionResponse(BaseModel):
    session_id: str
    strategy: str
    words: List[LearnSessionWordItem]


class WordReviewResponse(BaseModel):
    next_review_date: int
    mastery_level: float


class LearningAttemptSubmitRequest(BaseModel):
    vocab_id: str
    session_id: str = ""
    strategy: str = "today_active_recall"
    recall_text: str = ""
    cloze_answer: str = ""
    output_sentence: str = ""
    self_rating: str = "fuzzy"  # unknown | fuzzy | known


class LearningAttemptSubmitResponse(BaseModel):
    next_review_date: int
    next_review_label: str = ""
    mastery_level: float
    mastery_delta: float
    quality_score: float
    recall_completed: bool
    cloze_correct: bool
    output_uses_word: bool
    feedback: str
    output_feedback: str = ""
    output_suggestion: str = ""


class BookSessionRequest(BaseModel):
    count: int = 10
    topic: str = ""
    difficulty: str = ""
    mode: str = "auto"  # auto | review | bank


class BookStudyWordItem(BaseModel):
    key: str
    word: str
    definition: str = ""
    examples: List[str] = []
    pronunciation: str = ""
    part_of_speech: str = ""
    tags: List[str] = []
    source_module: str = ""
    in_book: bool = False
    due: bool = False
    mastery_level: float = 0.0
    next_review_date: int = 0
    difficulty: str = ""
    topics: List[str] = []
    vocab_id: str = ""
    bank_word_id: str = ""


class BookSessionResponse(BaseModel):
    session_id: str
    mode: str
    due_count: int = 0
    new_count: int = 0
    words: List[BookStudyWordItem] = []


class BookGradeRequest(BaseModel):
    rating: str = "fuzzy"  # forgot | fuzzy | familiar
    # None → 按 rating 决定默认是否入本；True/False → 用户显式覆盖
    collect: Optional[bool] = None
    # 深度练习结果（不认识→再认 / 模糊→拼写）；None 表示未做练习
    practice_correct: Optional[bool] = None
    vocab_id: str = ""
    bank_word_id: str = ""
    word: str = ""
    definition: str = ""
    examples: List[str] = []
    pronunciation: str = ""
    part_of_speech: str = ""
    source_module: str = "ielts_bank"
    topic: str = ""
    difficulty: str = ""


class BookGradeResponse(BaseModel):
    vocab_id: str = ""
    in_book: bool = False
    collected: bool = False
    skipped: bool = False
    next_review_date: int = 0
    next_review_label: str = ""
    mastery_level: float = 0.0
    mastery_delta: float = 0.0


class BookCollectRequest(BaseModel):
    word: str
    definition: str = ""
    examples: List[str] = []
    pronunciation: str = ""
    part_of_speech: str = ""
    source_module: str = "manual"
    bank_word_id: str = ""
    context: str = ""


class BookCollectResponse(BaseModel):
    vocab_id: str
    word: str
    in_book: bool = True
    already: bool = False


class BookSeenRequest(BaseModel):
    word: str
    bank_word_id: str = ""
    source_module: str = "ielts_bank"
    action: str = "skip"  # skip | seen


class BookSeenResponse(BaseModel):
    ok: bool = True
    action: str = "skip"


class BookPracticeOption(BaseModel):
    definition: str
    correct: bool = False


class BookPracticeOptionsResponse(BaseModel):
    word: str
    options: List[BookPracticeOption] = []


class BookGroupItem(BaseModel):
    source_module: str
    label: str
    count: int = 0


class BookSummaryResponse(BaseModel):
    total: int = 0
    active_count: int = 0
    mastered_count: int = 0
    due_count: int = 0
    avg_mastery: float = 0.0
    groups: List[BookGroupItem] = []


class BookListItem(BaseModel):
    id: str
    word: str
    definition: str = ""
    pronunciation: str = ""
    part_of_speech: str = ""
    source_module: str = ""
    mastery_level: float = 0.0
    next_review_date: int = 0
    created_at: int = 0
    mastered: bool = False
    due: bool = False


class BookListResponse(BaseModel):
    total: int = 0
    items: List[BookListItem] = []


class BookBulkRemoveRequest(BaseModel):
    vocab_ids: List[str] = []


class BookBulkRemoveResponse(BaseModel):
    removed: int = 0


class WordExplainResponse(BaseModel):
    word: str
    found: bool = False
    in_book: bool = False
    vocab_id: str = ""
    bank_word_id: str = ""
    pronunciation: str = ""
    part_of_speech: str = ""
    definitions: List[str] = []
    examples: List[str] = []
    phrases: List[str] = []
    synonyms: List[str] = []
    related_words: List[str] = []
    difficulty: str = ""
    topics: List[str] = []
    context: str = ""


class WordExplainAskRequest(BaseModel):
    word: str = Field(..., max_length=64)
    question: str = Field(..., max_length=500)
    context: str = Field(default="", max_length=500)
    definition: str = Field(default="", max_length=300)
    history: List[Dict[str, str]] = []


class WordExplainAskResponse(BaseModel):
    answer: str
    llm: bool = False


class OutputPromptRequest(BaseModel):
    vocab_id: str
    topic: str = ""


class OutputPromptResponse(BaseModel):
    chinese_sentence: str


class VocabularyStatsResponse(BaseModel):
    total: int
    due_count: int
    avg_mastery: float
    by_source_module: dict


class VocabularyStrategyInsightItem(BaseModel):
    strategy: str
    session_count: int
    total_words: int
    total_due_words: int
    avg_scheduler_score: float
    avg_mastery: float
    reviewed_words_7d: int = 0
    review_events_7d: int = 0
    avg_mastery_gain_7d: float = 0.0
    wrong_count_7d: int = 0
    wrong_rate_7d: float = 0.0


class VocabTestGenerateRequest(BaseModel):
    mode: str = "multiple_choice"  # multiple_choice / spelling / fill_blank
    count: int = 5


class VocabTestQuestion(BaseModel):
    id: str
    prompt: str
    options: Optional[List[str]] = None
    answer_format: str = "text"


class VocabTestGenerateResponse(BaseModel):
    test_id: str
    mode: str
    questions: List[VocabTestQuestion]


class VocabTestAnswer(BaseModel):
    question_id: str
    answer: str


class VocabTestSubmitRequest(BaseModel):
    test_id: str
    answers: List[VocabTestAnswer]


class VocabTestSubmitResponse(BaseModel):
    total: int
    correct: int
    accuracy: float
    details: List[Dict[str, Any]]


class WrongReviewQueueRequest(BaseModel):
    word_ids: List[str]
    limit: int = 30


class WrongReviewQueueItem(WordItem):
    priority_score: float
    priority_reason: str


class ContextReplayGenerateRequest(BaseModel):
    count: int = 5
    source_module: Optional[str] = None
    topic: Optional[str] = None
    mode: str = "cloze"  # cloze | multiple_choice
    word_ids: List[str] = []


class ContextReplayQuestion(BaseModel):
    id: str
    word_id: str
    prompt: str
    answer_format: str = "text"
    options: Optional[List[str]] = None
    hint: Optional[str] = None


class ContextReplayGenerateResponse(BaseModel):
    session_id: str
    mode: str
    questions: List[ContextReplayQuestion]


class ContextReplaySubmitRequest(BaseModel):
    session_id: str
    answers: List[VocabTestAnswer]


class ContextReplaySubmitResponse(BaseModel):
    total: int
    correct: int
    accuracy: float
    details: List[Dict[str, Any]]


class ContextReplayRetryQueueItem(BaseModel):
    word_id: str
    word: str
    definition: str
    priority_score: float
    priority_reason: str
    wrong_count: int


class VocabularyScenarioWord(BaseModel):
    word: str
    definition: str
    example: str = ""


class VocabularyScenarioPack(BaseModel):
    module: str
    topic: str
    level: str
    words: List[VocabularyScenarioWord]
    learned_count: int = 0
    total_count: int = 0


class VocabularyScenarioImportRequest(BaseModel):
    module: str
    topic: str
    limit: int = 20
    source_module: str = "scenario_pack"


class VocabularyScenarioImportResponse(BaseModel):
    imported: int
    skipped_existing: int
    words: List[str]


class VocabularyAutoCollectRequest(BaseModel):
    text: str
    source_module: str = "reading"
    topic: str = "general"
    max_words: int = 20
    level: str = "intermediate"


class VocabularyAutoCollectResponse(BaseModel):
    imported: int
    skipped_existing: int
    words: List[str]
    word_ids: List[str]


class VocabularyBankItem(BaseModel):
    word_id: str
    word: str
    definition: str = ""
    definition_en: str = ""
    examples: List[str] = []
    phrases: List[str] = []
    pronunciation: str = ""
    part_of_speech: str = ""
    difficulty: str = "medium"
    topics: List[str] = []
    imported: bool = False


class VocabularyBankSummaryResponse(BaseModel):
    total: int
    difficulties: List[Dict[str, Any]]
    topics: List[Dict[str, Any]]


class VocabularyBankImportRequest(BaseModel):
    word_ids: List[str]
    source_module: str = "ielts_bank"


class VocabularyBankImportResponse(BaseModel):
    imported: int
    skipped_existing: int
    words: List[str]
    word_ids: List[str]


_COMMON_AFFIXES = (
    "pre",
    "post",
    "inter",
    "trans",
    "sub",
    "anti",
    "auto",
    "over",
    "under",
    "tion",
    "sion",
    "ment",
    "ness",
    "able",
    "ible",
    "ize",
    "ise",
    "ology",
)

_WORD_STOPWORDS = {
    "that", "this", "with", "from", "have", "will", "would", "there", "their", "about",
    "which", "while", "where", "when", "what", "could", "should", "into", "than", "your",
    "them", "they", "were", "been", "being", "does", "did", "done", "also", "very",
    "more", "most", "some", "such", "just", "over", "under", "many", "much", "then",
    "because", "through", "between", "across", "after", "before", "during", "without",
    "these", "those", "each", "other", "still", "make", "made", "take", "used", "using",
    "into", "onto", "upon", "ours", "ourselves", "yourself", "themselves",
}

SCENARIO_VOCAB_BANK: List[Dict[str, Any]] = [
    {
        "module": "listening",
        "topic": "accommodation",
        "level": "basic",
        "words": [
            {"word": "deposit", "definition": "押金", "example": "You need to pay a deposit before moving in."},
            {"word": "landlord", "definition": "房东", "example": "The landlord agreed to fix the heater."},
            {"word": "tenant", "definition": "租户", "example": "Each tenant has to sign the contract."},
            {"word": "utilities", "definition": "水电煤等公用事业费", "example": "Utilities are not included in the rent."},
        ],
    },
    {
        "module": "reading",
        "topic": "environment",
        "level": "intermediate",
        "words": [
            {"word": "emission", "definition": "排放", "example": "The policy aims to reduce carbon emissions."},
            {"word": "sustainable", "definition": "可持续的", "example": "Sustainable transport benefits urban life."},
            {"word": "biodiversity", "definition": "生物多样性", "example": "The forest has rich biodiversity."},
            {"word": "conservation", "definition": "保护", "example": "Conservation projects need long-term support."},
        ],
    },
    {
        "module": "writing",
        "topic": "education",
        "level": "intermediate",
        "words": [
            {"word": "curriculum", "definition": "课程体系", "example": "The curriculum should include practical skills."},
            {"word": "compulsory", "definition": "强制性的", "example": "Primary education is compulsory in many countries."},
            {"word": "allocate", "definition": "分配", "example": "Governments should allocate funds to schools."},
            {"word": "equity", "definition": "公平；均衡", "example": "Education equity remains a major concern."},
        ],
    },
    {
        "module": "speaking",
        "topic": "technology",
        "level": "advanced",
        "words": [
            {"word": "ubiquitous", "definition": "无处不在的", "example": "Smartphones are ubiquitous in modern life."},
            {"word": "innovative", "definition": "创新的", "example": "Innovative solutions can solve social problems."},
            {"word": "automation", "definition": "自动化", "example": "Automation changes the structure of employment."},
            {"word": "privacy", "definition": "隐私", "example": "People are concerned about online privacy."},
        ],
    },
]


def _word_has_affix(word: str) -> bool:
    w = (word or "").strip().lower()
    if len(w) < 5:
        return False
    return any(w.startswith(a) or w.endswith(a) for a in _COMMON_AFFIXES)


def _pick_words_by_strategy(words: List[dict], strategy: str, count: int) -> List[dict]:
    if not words:
        return []
    n = max(1, int(count))
    now = int(time.time())
    s = (strategy or "spaced").strip().lower()
    if s not in {"spaced", "root", "context", "mixed"}:
        s = "spaced"

    strategy_weights: Dict[str, Dict[str, float]] = {
        "spaced": {"due": 0.45, "weakness": 0.25, "stale": 0.15, "affix": 0.05, "context": 0.10},
        "root": {"due": 0.20, "weakness": 0.15, "stale": 0.10, "affix": 0.45, "context": 0.10},
        "context": {"due": 0.20, "weakness": 0.15, "stale": 0.10, "affix": 0.05, "context": 0.50},
        "mixed": {"due": 0.30, "weakness": 0.20, "stale": 0.15, "affix": 0.15, "context": 0.20},
    }
    weights = strategy_weights[s]

    ranked: List[dict] = []
    for w in words:
        mastery = max(0.0, min(1.0, float(w.get("mastery_level") or 0.0)))
        weakness = 1.0 - mastery
        next_review = int(w.get("next_review_date") or 0)
        last_reviewed = int(w.get("last_reviewed_at") or int(w.get("created_at") or now))
        due_signal = 0.0
        if next_review <= 0:
            due_signal = 1.0
        elif now >= next_review:
            overdue_days = max(0.0, (now - next_review) / 86400.0)
            due_signal = min(1.0, 0.6 + overdue_days / 3.0)
        else:
            remaining_days = max(0.0, (next_review - now) / 86400.0)
            due_signal = max(0.0, 0.35 - min(0.35, remaining_days / 10.0))
        stale_days = max(0.0, (now - last_reviewed) / 86400.0)
        stale_signal = min(1.0, stale_days / 7.0)
        affix_signal = 1.0 if _word_has_affix(str(w.get("word") or "")) else 0.0
        examples = w.get("examples") or []
        context_signal = 1.0 if len(examples) > 0 else 0.0

        score = (
            due_signal * weights["due"]
            + weakness * weights["weakness"]
            + stale_signal * weights["stale"]
            + affix_signal * weights["affix"]
            + context_signal * weights["context"]
        )
        score = round(float(score), 6)

        reason_bits: List[str] = []
        if due_signal >= 0.7:
            reason_bits.append("到期/逾期优先")
        if weakness >= 0.65:
            reason_bits.append("掌握度偏低")
        if s in {"root", "mixed"} and affix_signal >= 1:
            reason_bits.append("词根词缀命中")
        if s in {"context", "mixed"} and context_signal >= 1:
            reason_bits.append("语境例句丰富")
        if not reason_bits:
            reason_bits.append("综合调度")

        ranked.append(
            {
                **w,
                "scheduler_score": score,
                "scheduler_reason": "；".join(reason_bits),
            }
        )

    ranked.sort(
        key=lambda x: (
            -float(x.get("scheduler_score") or 0.0),
            float(x.get("mastery_level") or 0.0),
            int(x.get("next_review_date") or 0),
            str(x.get("word") or ""),
        )
    )
    return ranked[:n]


def _build_mcq_options(target: dict, candidates: List[dict]) -> List[str]:
    correct = str(target.get("definition") or "").strip()
    distractors = []
    for c in candidates:
        d = str(c.get("definition") or "").strip()
        if d and d != correct and d not in distractors:
            distractors.append(d)
    random.shuffle(distractors)
    options = [correct] + distractors[:3]
    random.shuffle(options)
    return options


def _forgetting_priority(word: dict, now_ts: int) -> tuple[float, str]:
    mastery = max(0.0, min(1.0, float(word.get("mastery_level") or 0.0)))
    created_at = int(word.get("created_at") or now_ts)
    last_reviewed = int(word.get("last_reviewed_at") or created_at)
    next_review = int(word.get("next_review_date") or (last_reviewed + 24 * 3600))
    elapsed = max(0, now_ts - last_reviewed)
    interval = max(3600, next_review - last_reviewed)

    retention = math.exp(-elapsed / interval) * (0.4 + 0.6 * mastery)
    overdue_ratio = max(0.0, (now_ts - next_review) / interval)

    priority = (1.0 - retention) + 0.8 * overdue_ratio + 0.5 * (1.0 - mastery)
    if overdue_ratio > 0.5:
        reason = "已明显过期复习"
    elif mastery < 0.35:
        reason = "掌握度较低"
    else:
        reason = "遗忘曲线预测高遗忘风险"
    return round(float(priority), 6), reason


def _normalize_word_input(token: str) -> str:
    """清洗「用户提交的单词」：保留非 ASCII（café / naïve / 3D），只去空白与首尾标点。

    `_normalize_word_token` 的正则是为「从句子抽 token」设计的，直接用于用户输入
    会把 café 变成 caf、3D 变成 d，导致查词与发音都错。
    """
    raw = " ".join(str(token or "").split())
    return raw.strip(".,;:!?\"'()[]{}").lower()


def _normalize_word_token(token: str) -> str:
    return re.sub(r"[^a-zA-Z\-']", "", str(token or "")).lower().strip("-'")


# 单词发音是同步调用付费 TTS，这里做一层按用户的滑动窗口限流，防止脚本刷接口。
# 音频本身由 tts_service 按内容哈希落盘缓存，重复单词不会重复合成。
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, List[float]] = {}
_TTS_RATE_LIMIT = max(1, int(os.environ.get("VOCABULARY_AUDIO_RATE_LIMIT", "60") or 60))
_TTS_RATE_WINDOW = max(1, int(os.environ.get("VOCABULARY_AUDIO_RATE_WINDOW_SECONDS", "60") or 60))
_LLM_RATE_LIMIT = max(1, int(os.environ.get("VOCABULARY_LLM_RATE_LIMIT", "30") or 30))
_LLM_RATE_WINDOW = max(1, int(os.environ.get("VOCABULARY_LLM_RATE_WINDOW_SECONDS", "60") or 60))


def _allow_rate_request(user_id: str, scope: str, limit: int, window: int) -> bool:
    now = time.time()
    safe_limit = max(1, int(limit or 1))
    safe_window = max(1, int(window or 1))
    key = f"{scope}:{str(user_id or 'anonymous')}"
    with _RATE_LOCK:
        bucket = [t for t in _RATE_BUCKETS.get(key, []) if now - t < safe_window]
        if len(bucket) >= safe_limit:
            _RATE_BUCKETS[key] = bucket
            return False
        bucket.append(now)
        _RATE_BUCKETS[key] = bucket
        if len(_RATE_BUCKETS) > 5000:
            # 防止长期运行下 key 无界增长：清理已过期的用户桶。
            for stale in [k for k, v in _RATE_BUCKETS.items() if not v or now - v[-1] > safe_window]:
                _RATE_BUCKETS.pop(stale, None)
        return True


def _allow_tts_request(user_id: str) -> bool:
    return _allow_rate_request(user_id, "tts", _TTS_RATE_LIMIT, _TTS_RATE_WINDOW)


def _allow_llm_request(user_id: str) -> bool:
    return _allow_rate_request(user_id, "llm", _LLM_RATE_LIMIT, _LLM_RATE_WINDOW)


def _extract_candidate_words(text: str, max_words: int = 20) -> List[str]:
    candidates: List[str] = []
    for raw in re.findall(r"\b[a-zA-Z][a-zA-Z\-']{3,}\b", text or ""):
        token = _normalize_word_token(raw)
        if not token:
            continue
        if token in _WORD_STOPWORDS:
            continue
        if token in candidates:
            continue
        candidates.append(token)
        if len(candidates) >= max_words:
            break
    return candidates


def _mask_word_in_sentence(sentence: str, word: str) -> str:
    s = str(sentence or "").strip()
    w = str(word or "").strip()
    if not s or not w:
        return s
    pattern = re.compile(rf"\b{re.escape(w)}\b", flags=re.IGNORECASE)
    if pattern.search(s):
        return pattern.sub("____", s, count=1)
    # 兜底：首个单词替换，避免空题面
    first = re.search(r"\b[a-zA-Z][a-zA-Z\-']*\b", s)
    if first:
        return s[: first.start()] + "____" + s[first.end() :]
    return f"____ ({w})"


def _build_context_prompt(word_row: Dict[str, Any]) -> str:
    word = str(word_row.get("word") or "").strip()
    examples = word_row.get("examples") or []
    if examples:
        sentence = str(examples[0] or "").strip()
        if sentence:
            return _mask_word_in_sentence(sentence, word)
    definition = str(word_row.get("definition") or "").strip()
    if definition:
        return f"In IELTS preparation, students should use ____ to express: {definition}"
    return f"Fill in the blank with one suitable IELTS word: ____ ({word})"


def _word_matches_learning_filters(word_row: Dict[str, Any], topic: str = "", difficulty: str = "") -> bool:
    tags = {str(t or "").strip().lower() for t in (word_row.get("tags") or [])}
    safe_topic = str(topic or "").strip().lower()
    safe_difficulty = str(difficulty or "").strip().lower()
    if safe_topic:
        topic_tags = {safe_topic, f"topic:{safe_topic}"}
        if tags.isdisjoint(topic_tags):
            return False
    if safe_difficulty:
        difficulty_tags = {safe_difficulty, f"difficulty:{safe_difficulty}"}
        if tags.isdisjoint(difficulty_tags):
            return False
    return True


def _contains_word(text: str, word: str) -> bool:
    target = str(word or "").strip()
    if not target:
        return False
    return bool(re.search(rf"\b{re.escape(target)}\b", str(text or ""), flags=re.IGNORECASE))


def _primary_chinese_definition(definition: str, word: str) -> str:
    raw = str(definition or "").strip()
    if not raw:
        return "这个概念"
    first = re.split(r"[;；,，、/]", raw)[0].strip()
    candidate = first or raw
    if re.search(r"[A-Za-z]", candidate):
        chinese_parts = re.findall(r"[\u4e00-\u9fff]+", raw)
        if chinese_parts:
            return chinese_parts[0]
        return "这个概念"
    return candidate


def _topic_zh(topic: str) -> str:
    mapping = {
        "accommodation": "住宿",
        "education": "教育",
        "environment": "环境",
        "technology": "科技",
        "health": "健康",
        "economy": "经济",
        "culture": "文化",
        "transport": "交通",
        "tourism": "旅游",
        "work": "工作",
        "career": "职业",
        "family": "家庭",
        "food": "饮食",
        "media": "媒体",
        "crime": "犯罪",
        "government": "政府",
        "housing": "住房",
        "general": "日常学习",
    }
    return mapping.get(str(topic or "").strip().lower(), str(topic or "").strip() or "日常学习")


def _fallback_output_prompt(word: str, definition: str, topic: str = "") -> str:
    meaning = _primary_chinese_definition(definition, word)
    topic_name = _topic_zh(topic)
    templates = [
        f"学校可以通过技术手段{meaning}真实的考试场景。",
        f"在{topic_name}话题中，学生需要学会准确表达“{meaning}”这个意思。",
        f"这项训练可以帮助学习者更自然地使用“{meaning}”相关表达。",
    ]
    return random.choice(templates)


def _extract_chinese_sentence(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.strip("\"'“” \n")
    for line in cleaned.splitlines():
        line = line.strip().strip("\"'“”")
        if line and not re.search(r"[A-Za-z]", line):
            return line
    return cleaned


def _get_vocab_llm():
    global _vocab_llm
    if _vocab_llm is not None:
        return _vocab_llm
    if GeneratorModel is None:
        return None
    try:
        _vocab_llm = GeneratorModel()
        return _vocab_llm
    except Exception:
        return None


def _generate_output_prompt_sentence(word_row: Dict[str, Any], topic: str = "") -> str:
    word = str(word_row.get("word") or "").strip()
    definition = str(word_row.get("definition") or "").strip()
    topic_name = _topic_zh(topic)
    fallback = _fallback_output_prompt(word, definition, topic)
    llm = _get_vocab_llm()
    if llm is None:
        return fallback
    prompt = f"""
你是雅思词汇训练题目生成器。请为用户生成一句完整中文句子，用于让用户翻译成英文。

要求：
- 必须是纯中文句子，不要出现任何英文单词、拼音、引号中的英文、解释、编号或 Markdown。
- 句子要自然，适合雅思或英语学习场景。
- 句子语义要能引导用户在英文翻译中使用目标词。
- 只输出一句中文，长度 12 到 35 个汉字。

目标英文词：{word}
中文含义：{definition or word}
话题：{topic_name}
"""
    try:
        _, raw = llm.communicate(prompt, temperature=0.7, max_tokens=80)
        sentence = _extract_chinese_sentence(raw)
        if sentence and not re.search(r"[A-Za-z]", sentence):
            return sentence
    except Exception:
        return fallback
    return fallback


def _extract_json_payload(raw: str) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _llm_assess_output_sentence(sentence: str, word: str, definition: str = "") -> Optional[Dict[str, str]]:
    text = str(sentence or "").strip()
    target = str(word or "").strip()
    if not text or not target:
        return None
    llm = _get_vocab_llm()
    if llm is None:
        return None
    prompt = f"""
你是雅思词汇造句批改老师。请审核用户英文句子是否自然、语法是否基本正确、目标词是否用得合适。

只输出 JSON，不要 Markdown，不要解释 JSON 外的内容。字段：
- output_feedback: 中文，1-2句，明确说明句子是否可用，以及最重要的一处修改建议；如果句子很好，也要说好在哪里。
- output_suggestion: 英文，给出一版更自然或修正后的句子。必须包含目标词。

目标词：{target}
目标词释义：{definition or target}
用户句子：{text}
"""
    try:
        _, raw = llm.communicate(prompt, temperature=0.2, max_tokens=220)
        data = _extract_json_payload(raw)
    except Exception:
        return None
    if not data:
        return None
    feedback = str(data.get("output_feedback") or "").strip()
    suggestion = str(data.get("output_suggestion") or "").strip()
    if not feedback:
        return None
    if suggestion and not _contains_word(suggestion, target):
        suggestion = ""
    return {
        "output_feedback": feedback[:220],
        "output_suggestion": suggestion[:260],
    }


def _assess_output_sentence(sentence: str, word: str, definition: str = "") -> Dict[str, str]:
    lines = [x.strip() for x in str(sentence or "").splitlines() if x.strip()]
    text = lines[-1] if lines else ""
    if not text:
        return {"output_feedback": "", "output_suggestion": ""}
    llm_assessment = _llm_assess_output_sentence(text, word, definition)
    if llm_assessment:
        return llm_assessment

    issues: List[str] = []
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not _contains_word(text, word):
        issues.append(f"句子里还没有自然使用 {word}")
    if len(tokens) < 5:
        issues.append("句子偏短，可以补充主语、动作或原因")
    if text and text[0].isalpha() and not text[0].isupper():
        issues.append("句首建议大写")
    if text and text[-1] not in ".!?":
        issues.append("句末建议补上标点")
    if re.search(r"\byours\s+[A-Za-z]", text, flags=re.IGNORECASE):
        issues.append("yours 后不能直接接名词，这里通常用 your")
    if re.search(r"\ba\s+[aeiouAEIOU]", text):
        issues.append("元音开头的单词前通常用 an")
    if re.search(r"\b(can|should|must|will|would|could|may|might)\s+to\s+", text, flags=re.IGNORECASE):
        issues.append("情态动词后直接接动词原形，不加 to")

    suggestion = ""
    if _contains_word(text, word):
        suggestion = text
    else:
        suggestion = f"It is important to use {word} accurately in IELTS writing."
    suggestion = suggestion[:1].upper() + suggestion[1:] if suggestion else ""
    if suggestion and suggestion[-1] not in ".!?":
        suggestion = f"{suggestion}."

    if not issues:
        return {
            "output_feedback": "句子基本通顺，目标词使用到位。",
            "output_suggestion": suggestion,
        }
    return {
        "output_feedback": "；".join(issues[:3]),
        "output_suggestion": suggestion,
    }


def _score_learning_attempt(word_row: Dict[str, Any], payload: LearningAttemptSubmitRequest) -> Dict[str, Any]:
    word = str(word_row.get("word") or "").strip()
    recall_text = str(payload.recall_text or "").strip()
    cloze_answer = str(payload.cloze_answer or "").strip()
    output_sentence = str(payload.output_sentence or "").strip()
    self_rating = str(payload.self_rating or "fuzzy").strip().lower()
    rating_score_map = {
        "unknown": 0.0,
        "forgot": 0.0,
        "fuzzy": 0.35,
        "hard": 0.35,
        "recalled": 0.58,
        "known": 0.76,
        "familiar": 0.76,
        "easy": 1.0,
    }
    rating_delta_map = {
        "unknown": -0.14,
        "forgot": -0.16,
        "fuzzy": -0.02,
        "hard": -0.02,
        "recalled": 0.06,
        "known": 0.14,
        "familiar": 0.14,
        "easy": 0.2,
    }
    if self_rating not in rating_score_map:
        self_rating = "fuzzy"

    recall_completed = len(recall_text) >= 2
    cloze_correct = bool(cloze_answer) and cloze_answer.lower() == word.lower()
    output_uses_word = _contains_word(output_sentence, word)
    output_assessment = _assess_output_sentence(
        output_sentence,
        word,
        str(word_row.get("definition") or ""),
    )

    rating_score = rating_score_map[self_rating]
    quality_score = (
        (0.22 if recall_completed else 0.0)
        + (0.28 if cloze_correct else 0.0)
        + (0.25 if output_uses_word else 0.0)
        + rating_score * 0.25
    )
    delta = rating_delta_map[self_rating]
    delta += 0.03 if recall_completed else -0.03
    if cloze_answer:
        delta += 0.06 if cloze_correct else -0.05
    if output_sentence:
        delta += 0.06 if output_uses_word else -0.04
    delta = max(-0.22, min(0.26, delta))

    feedback_bits = []
    if not recall_completed:
        feedback_bits.append("下次先尝试写出释义或搭配")
    if cloze_answer and not cloze_correct:
        feedback_bits.append("填空未命中目标词")
    if output_sentence and not output_uses_word:
        feedback_bits.append("造句中还没有自然使用目标词")
    if quality_score >= 0.75:
        feedback_bits.append("本轮掌握较好，复习间隔会适当拉长")
    elif quality_score <= 0.35:
        feedback_bits.append("本轮记忆较弱，会更快进入复习")
    else:
        feedback_bits.append("本轮处于巩固阶段")

    if quality_score <= 0.25:
        sm2_quality = 1
        next_review_label = "稍后会更快复习"
    elif quality_score <= 0.45:
        sm2_quality = 2
        next_review_label = "会进入短间隔巩固"
    elif quality_score <= 0.65:
        sm2_quality = 3
        next_review_label = "明天左右复习"
    elif quality_score <= 0.82:
        sm2_quality = 4
        next_review_label = "间隔会适当拉长"
    else:
        sm2_quality = 5
        next_review_label = "间隔会明显拉长"

    return {
        "recall_completed": recall_completed,
        "cloze_correct": cloze_correct,
        "output_uses_word": output_uses_word,
        "quality_score": round(quality_score, 4),
        "sm2_quality": sm2_quality,
        "mastery_delta": round(delta, 4),
        "next_review_label": next_review_label,
        "self_rating": self_rating,
        "feedback": "；".join(feedback_bits),
        **output_assessment,
    }


def _bank_row_to_item(row: Dict[str, Any], imported_words: set[str] | None = None) -> VocabularyBankItem:
    examples = row.get("examples") or []
    phrases = row.get("phrases") or []
    example_texts: List[str] = []
    if isinstance(examples, list):
        for item in examples[:3]:
            if isinstance(item, dict):
                english = str(item.get("english") or "").strip()
                chinese = str(item.get("chinese") or "").strip()
                text = " / ".join([x for x in [english, chinese] if x])
            else:
                text = str(item or "").strip()
            if text:
                example_texts.append(text)
    phrase_texts: List[str] = []
    if isinstance(phrases, list):
        for item in phrases[:5]:
            if isinstance(item, dict):
                phrase = str(item.get("phrase") or "").strip()
                chinese = str(item.get("chinese") or "").strip()
                text = " / ".join([x for x in [phrase, chinese] if x])
            else:
                text = str(item or "").strip()
            if text:
                phrase_texts.append(text)
    word = str(row.get("head_word") or "").strip()
    definition = str(row.get("definition_cn") or row.get("definition_en") or "").strip()
    topics = [str(x).strip() for x in (row.get("topics") or []) if str(x).strip()]
    imported = word.lower() in (imported_words or set())
    return VocabularyBankItem(
        word_id=str(row.get("word_id") or ""),
        word=word,
        definition=definition,
        definition_en=str(row.get("definition_en") or "").strip(),
        examples=example_texts,
        phrases=phrase_texts,
        pronunciation=str(row.get("uk_phone") or row.get("us_phone") or "").strip(),
        part_of_speech=str(row.get("part_of_speech") or "").strip(),
        difficulty=str(row.get("difficulty") or "medium").strip(),
        topics=topics,
        imported=imported,
    )


def _bank_row_to_vocab_data(row: Dict[str, Any], source_module: str = "ielts_bank") -> Dict[str, Any]:
    item = _bank_row_to_item(row)
    tags = [
        "ielts_bank",
        f"difficulty:{item.difficulty}",
        *(f"topic:{topic}" for topic in item.topics),
    ]
    if row.get("book_id"):
        tags.append(f"book:{row.get('book_id')}")
    if row.get("word_id"):
        tags.append(f"bank_word_id:{row.get('word_id')}")
    return {
        "word": item.word,
        "definition": item.definition,
        "examples": item.examples,
        "pronunciation": item.pronunciation,
        "part_of_speech": item.part_of_speech,
        "tags": tags,
        "source_module": source_module or "ielts_bank",
        "mastery_level": 0.0,
    }


# ── 词汇本学习闭环：3 档自评 + rating-driven 准入 ──────────────────────────
_BOOK_RATING_QUALITY = {
    "forgot": 1,
    "unknown": 1,
    "fuzzy": 2,
    "hard": 2,
    "recalled": 3,
    "familiar": 5,
    "known": 5,
    "easy": 5,
}
# 不认识 / 模糊 → 默认纳入词汇本；认识 → 默认不纳入（用户可手动加入）
_BOOK_DEFAULT_COLLECT_RATINGS = {"forgot", "unknown", "fuzzy", "hard"}

# 词汇本来源展示名
_BOOK_SOURCE_LABELS = {
    "ielts_bank": "词库",
    "manual": "手动添加",
    "reading": "阅读随文",
    "listening": "听力随文",
    "writing": "写作",
    "speaking": "口语",
    "translation": "翻译",
    "translation_search": "翻译",
    "auto_collect": "自动收录",
    "unknown": "其他",
}


def _book_quality(rating: str) -> int:
    return _BOOK_RATING_QUALITY.get(str(rating or "").strip().lower(), 3)


# 自评叠加一次深度练习后的最终 quality（答对上调、答错下调）
# 「模糊」本身不算通过（quality 2）；只有练习答对才升到 3。
_BOOK_PRACTICE_QUALITY = {
    ("forgot", True): 2,
    ("forgot", False): 1,
    ("fuzzy", True): 3,
    ("fuzzy", False): 2,
    ("familiar", True): 5,
    ("familiar", False): 2,
}


def _book_quality_with_practice(rating: str, practice_correct: Optional[bool]) -> int:
    if practice_correct is not None:
        key = (str(rating or "").strip().lower(), bool(practice_correct))
        if key in _BOOK_PRACTICE_QUALITY:
            return _BOOK_PRACTICE_QUALITY[key]
    return _book_quality(rating)


def _book_default_collect(rating: str) -> bool:
    return str(rating or "").strip().lower() in _BOOK_DEFAULT_COLLECT_RATINGS


def _book_collect_data(payload: Any) -> Dict[str, Any]:
    """优先用词库补齐词条信息，否则回落到前端传来的字段。"""
    bank_word_id = str(getattr(payload, "bank_word_id", "") or "").strip()
    if bank_word_id:
        rows = get_ielts_vocabulary_bank_by_ids([bank_word_id])
        if rows:
            source = str(getattr(payload, "source_module", "") or "ielts_bank")
            return _bank_row_to_vocab_data(rows[0], source_module=source)
    return {
        "word": str(getattr(payload, "word", "") or "").strip(),
        "definition": str(getattr(payload, "definition", "") or ""),
        "examples": list(getattr(payload, "examples", []) or []),
        "pronunciation": str(getattr(payload, "pronunciation", "") or ""),
        "part_of_speech": str(getattr(payload, "part_of_speech", "") or ""),
        "tags": [],
        "source_module": str(getattr(payload, "source_module", "") or "manual"),
        "mastery_level": 0.0,
    }


def _record_book_seen(
    user_id: str,
    word: str,
    bank_word_id: str = "",
    source_module: str = "",
    action: str = "skip",
    rating: str = "",
) -> None:
    """只记「见过」，不做任何掌握度 / SM2 变更。"""
    safe_word = str(word or "").strip()
    if not safe_word:
        return
    properties: Dict[str, Any] = {
        "word": safe_word.lower(),
        "bank_word_id": str(bank_word_id or ""),
        "source_module": str(source_module or ""),
        "action": str(action or "skip"),
    }
    if rating:
        properties["rating"] = str(rating)
    try:
        save_learning_event(
            str(uuid4()),
            str(user_id),
            {
                "event_type": "vocabulary_seen",
                "event_name": "vocabulary_seen",
                "properties": properties,
                "timestamp": int(time.time()),
            },
        )
    except Exception:
        return


def _vocab_row_to_study_item(row: Dict[str, Any], now: int) -> BookStudyWordItem:
    next_review = int(row.get("next_review_date") or 0)
    return BookStudyWordItem(
        key=f"vocab:{row.get('id')}",
        word=str(row.get("word") or ""),
        definition=str(row.get("definition") or ""),
        examples=row.get("examples") or [],
        pronunciation=str(row.get("pronunciation") or ""),
        part_of_speech=str(row.get("part_of_speech") or ""),
        tags=row.get("tags") or [],
        source_module=str(row.get("source_module") or ""),
        in_book=True,
        due=next_review <= now,
        mastery_level=float(row.get("mastery_level") or 0.0),
        next_review_date=next_review,
        vocab_id=str(row.get("id") or ""),
    )


def _bank_row_to_study_item(row: Dict[str, Any]) -> BookStudyWordItem:
    item = _bank_row_to_item(row)
    tags = [f"difficulty:{item.difficulty}", *(f"topic:{t}" for t in item.topics)]
    return BookStudyWordItem(
        key=f"bank:{item.word_id or item.word.strip().lower()}",
        word=item.word,
        definition=item.definition,
        examples=item.examples,
        pronunciation=item.pronunciation,
        part_of_speech=item.part_of_speech,
        tags=tags,
        source_module="ielts_bank",
        in_book=False,
        due=False,
        mastery_level=0.0,
        next_review_date=0,
        difficulty=item.difficulty,
        topics=item.topics,
        bank_word_id=item.word_id,
    )


def _lookup_word_facts(user_id: str, word: str) -> Dict[str, Any]:
    """先查用户词汇本，再查词库，组装「问老师」的结构化速览。"""
    normalized = _normalize_word_input(word)
    facts: Dict[str, Any] = {
        "word": normalized,
        "found": False,
        "in_book": False,
        "vocab_id": "",
        "bank_word_id": "",
        "pronunciation": "",
        "part_of_speech": "",
        "definitions": [],
        "examples": [],
        "phrases": [],
        "synonyms": [],
        "related_words": [],
        "difficulty": "",
        "topics": [],
    }
    if not normalized:
        return facts

    row = get_user_vocabulary_by_word(user_id, normalized)
    if row:
        definition = str(row.get("definition") or "").strip()
        facts.update({
            "word": str(row.get("word") or normalized),
            "found": True,
            "in_book": True,
            "vocab_id": str(row.get("id") or ""),
            "pronunciation": str(row.get("pronunciation") or ""),
            "part_of_speech": str(row.get("part_of_speech") or ""),
            "definitions": [definition] if definition else [],
            "examples": [str(x) for x in (row.get("examples") or [])][:3],
        })
        return facts

    raw = get_ielts_vocabulary_bank_by_head_word(normalized)
    if raw is None:
        # 精确未命中时再用 LIKE 兜底（处理词形/拼写差异）
        rows = list_ielts_vocabulary_bank(keyword=normalized, limit=8)
        match = next(
            (r for r in rows if str(r.get("head_word") or "").strip().lower() == normalized),
            None,
        )
        raw = dict(match) if match else None
    if raw:
        item = _bank_row_to_item(raw)
        definitions = [x for x in [item.definition, str(raw.get("definition_en") or "").strip()] if x]
        facts.update({
            "word": item.word or normalized,
            "found": True,
            "bank_word_id": item.word_id,
            "pronunciation": item.pronunciation,
            "part_of_speech": item.part_of_speech,
            "definitions": definitions,
            "examples": item.examples[:3],
            "phrases": item.phrases[:5],
            "synonyms": [str(x).strip() for x in (raw.get("synonyms") or []) if str(x).strip()][:6],
            "related_words": [str(x).strip() for x in (raw.get("related_words") or []) if str(x).strip()][:6],
            "difficulty": item.difficulty,
            "topics": item.topics,
        })
    return facts


@router.get("/bank", response_model=List[VocabularyBankItem])
async def list_bank_vocabulary(
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    imported_rows = get_user_vocabulary(current_user["id"], 5000)
    imported_words = {str(x.get("word") or "").strip().lower() for x in imported_rows}
    rows = list_ielts_vocabulary_bank(
        difficulty=difficulty or "",
        topic=topic or "",
        keyword=keyword or "",
        limit=limit,
    )
    return [_bank_row_to_item(row, imported_words=imported_words) for row in rows]


@router.get("/bank/summary", response_model=VocabularyBankSummaryResponse)
async def bank_vocabulary_summary(current_user: dict = Depends(get_current_user)):
    return VocabularyBankSummaryResponse(**get_ielts_vocabulary_bank_summary())


@router.post("/bank/import", response_model=VocabularyBankImportResponse)
async def import_bank_vocabulary(
    payload: VocabularyBankImportRequest,
    current_user: dict = Depends(get_current_user),
):
    requested_ids = list(dict.fromkeys(str(x or "").strip() for x in payload.word_ids if str(x or "").strip()))
    if not requested_ids:
        raise HTTPException(status_code=400, detail="No bank words selected")

    rows = get_ielts_vocabulary_bank_by_ids(requested_ids[:200])
    if not rows:
        raise HTTPException(status_code=404, detail="Vocabulary bank words not found")

    existing = get_user_vocabulary(current_user["id"], 5000)
    existing_by_word = {str(w.get("word", "")).strip().lower() for w in existing}

    imported_words: List[str] = []
    imported_ids: List[str] = []
    skipped_existing = 0
    for row in rows:
        word = str(row.get("head_word") or "").strip()
        if not word:
            continue
        if word.lower() in existing_by_word:
            skipped_existing += 1
            continue
        vocab_id = str(uuid4())
        save_vocabulary(
            vocab_id,
            current_user["id"],
            _bank_row_to_vocab_data(row, source_module=payload.source_module or "ielts_bank"),
        )
        existing_by_word.add(word.lower())
        imported_words.append(word)
        imported_ids.append(vocab_id)

    return VocabularyBankImportResponse(
        imported=len(imported_words),
        skipped_existing=skipped_existing,
        words=imported_words,
        word_ids=imported_ids,
    )


@router.get("/", response_model=List[WordItem])
async def list_vocabulary(
    limit: int = 100,
    source_module: Optional[str] = None,
    tag: Optional[str] = None,
    keyword: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    fetch_limit = max(100, min(2000, int(limit or 100) * 5))
    words = get_user_vocabulary(current_user["id"], fetch_limit)
    if source_module:
        source_module = source_module.strip().lower()
        words = [w for w in words if str(w.get("source_module", "")).strip().lower() == source_module]
    if tag:
        tag = tag.strip().lower()
        words = [w for w in words if tag in {str(t).strip().lower() for t in (w.get("tags") or [])}]
    if keyword:
        key = keyword.strip().lower()
        words = [
            w for w in words
            if key in str(w.get("word", "")).lower()
            or key in str(w.get("definition", "")).lower()
        ]
    words = words[: max(1, min(int(limit or 100), 1000))]
    return [WordItem(**w) for w in words]


@router.get("/due", response_model=List[WordItem])
async def list_due_vocabulary(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    rows = get_due_vocabulary(current_user["id"], limit)
    return [WordItem(**w) for w in rows]


@router.post("/add", response_model=WordItem)
async def add_word(
    payload: WordCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    vocab_id = str(uuid4())
    data = _model_dump(payload)
    data["mastery_level"] = 0.0
    save_vocabulary(vocab_id, user_id, data)
    created = get_user_vocabulary(user_id, 1)
    return WordItem(**created[0])


@router.post("/learn/session", response_model=LearnSessionResponse)
async def start_learning_session(
    payload: LearnSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    all_words = get_user_vocabulary(user_id, 500)
    selected = _pick_words_by_strategy(all_words, payload.strategy, payload.count)
    strategy_used = (payload.strategy or "spaced").strip().lower()
    if strategy_used not in {"spaced", "root", "context", "mixed"}:
        strategy_used = "spaced"
    save_vocabulary_strategy_session(user_id, strategy_used, selected)
    return LearnSessionResponse(
        session_id=str(uuid4()),
        strategy=strategy_used,
        words=[LearnSessionWordItem(**w) for w in selected],
    )


@router.post("/learn/today", response_model=LearnSessionResponse)
async def start_today_learning_session(
    payload: TodayLearnSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    clear_timed_state(_today_learning_status_key(str(user_id), _today_date_key()))
    count = max(1, min(int(payload.count or 10), 30))
    requested_difficulty = str(payload.difficulty or "").strip().lower()
    effective_difficulty = requested_difficulty or get_difficulty_recommendation(
        str(user_id),
        module="vocabulary",
    ).get("recommended_difficulty", "easy")
    all_words = get_user_vocabulary(user_id, 5000)
    filtered_words = [
        word for word in all_words
        if _word_matches_learning_filters(word, topic=payload.topic, difficulty=effective_difficulty)
    ]
    if not filtered_words and not requested_difficulty and not payload.topic:
        filtered_words = all_words
    selected_pool = filtered_words if (payload.topic or effective_difficulty) else all_words
    selected = _pick_words_by_strategy(selected_pool, "mixed", count)

    if len(selected) < count:
        existing_words = {str(w.get("word", "")).strip().lower() for w in all_words}
        bank_rows = list_ielts_vocabulary_bank(
            difficulty=effective_difficulty or "",
            topic=payload.topic or "",
            keyword="",
            limit=max(20, (count - len(selected)) * 6),
        )
        imported = 0
        for row in bank_rows:
            word = str(row.get("head_word") or "").strip()
            if not word or word.lower() in existing_words:
                continue
            save_vocabulary(
                str(uuid4()),
                user_id,
                _bank_row_to_vocab_data(row, source_module="ielts_bank"),
            )
            existing_words.add(word.lower())
            imported += 1
            if imported >= count - len(selected):
                break
        if imported:
            all_words = get_user_vocabulary(user_id, 5000)
            filtered_words = [
                word for word in all_words
                if _word_matches_learning_filters(word, topic=payload.topic, difficulty=effective_difficulty)
            ]
            if not filtered_words and not requested_difficulty and not payload.topic:
                filtered_words = all_words
            selected_pool = filtered_words if (payload.topic or effective_difficulty) else all_words
            selected = _pick_words_by_strategy(selected_pool, "mixed", count)

    save_vocabulary_strategy_session(user_id, "today_active_recall", selected)
    return LearnSessionResponse(
        session_id=str(uuid4()),
        strategy="today_active_recall",
        words=[LearnSessionWordItem(**w) for w in selected],
    )


@router.get("/learn/today/status", response_model=TodayLearningStatusResponse)
async def get_today_learning_status(
    date_key: str = "",
    current_user: dict = Depends(get_current_user),
):
    safe_date_key = _normalize_date_key(date_key)
    key = _today_learning_status_key(str(current_user["id"]), safe_date_key)
    return TodayLearningStatusResponse(
        date_key=safe_date_key,
        completed=get_timed_state(key) == "completed",
    )


@router.post("/learn/today/status", response_model=TodayLearningStatusResponse)
async def set_today_learning_status(
    payload: TodayLearningStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    safe_date_key = _normalize_date_key(payload.date_key)
    key = _today_learning_status_key(str(current_user["id"]), safe_date_key)
    if payload.completed:
        set_timed_state(key, "completed", _seconds_until_next_day(safe_date_key))
    else:
        clear_timed_state(key)
    return TodayLearningStatusResponse(date_key=safe_date_key, completed=payload.completed)


@router.post("/book/session", response_model=BookSessionResponse)
async def start_book_session(payload: BookSessionRequest, current_user: dict = Depends(get_current_user)):
    """词汇本学习：先取到期复习词，不足再补词库中尚未入本的新词。

    词库新词只作为「临时词」返回，**不会**自动写入词汇本 —— 是否入本由用户在评分时决定。
    """
    user_id = str(current_user["id"])
    now = int(time.time())
    count = max(1, min(int(payload.count or 10), 30))
    mode = str(payload.mode or "auto").strip().lower()
    if mode not in {"auto", "review", "bank"}:
        mode = "auto"

    words: List[BookStudyWordItem] = []
    due_count = 0

    if mode in {"auto", "review"}:
        due_rows = get_due_vocabulary(user_id, limit=count, now_ts=now)
        due_count = len(due_rows)
        words.extend(_vocab_row_to_study_item(row, now) for row in due_rows)

    if mode in {"auto", "bank"} and len(words) < count:
        in_book = get_user_vocabulary_word_set(user_id)
        requested_difficulty = str(payload.difficulty or "").strip().lower()
        effective_difficulty = requested_difficulty or get_difficulty_recommendation(
            user_id, module="vocabulary"
        ).get("recommended_difficulty", "easy")
        bank_rows = list_ielts_vocabulary_bank(
            difficulty=effective_difficulty or "",
            topic=payload.topic or "",
            keyword="",
            limit=max(20, (count - len(words)) * 6),
        )
        for row in bank_rows:
            word = str(row.get("head_word") or "").strip()
            if not word or word.lower() in in_book or word.lower() in LOW_VALUE_WORDS:
                continue
            words.append(_bank_row_to_study_item(row))
            in_book.add(word.lower())
            if len(words) >= count:
                break

    selected = words[:count]
    return BookSessionResponse(
        session_id=str(uuid4()),
        mode=mode,
        due_count=due_count,
        new_count=sum(1 for item in selected if not item.in_book),
        words=selected,
    )


@router.post("/book/grade", response_model=BookGradeResponse)
async def grade_book_word(payload: BookGradeRequest, current_user: dict = Depends(get_current_user)):
    """提交一次 3 档自评：按 rating 决定是否入本，并更新 SM2 / 能力曲线。"""
    user_id = str(current_user["id"])
    rating = str(payload.rating or "fuzzy").strip().lower()
    quality = _book_quality_with_practice(rating, payload.practice_correct)

    target = None
    if payload.vocab_id:
        row = get_vocabulary_by_id(payload.vocab_id)
        if row and str(row.get("user_id")) == user_id:
            target = row
    if target is None and payload.word:
        target = get_user_vocabulary_by_word(user_id, payload.word)

    collected = False
    if target is None:
        want_collect = _book_default_collect(rating) if payload.collect is None else bool(payload.collect)
        if want_collect:
            data = _book_collect_data(payload)
            if not str(data.get("word") or "").strip():
                raise HTTPException(status_code=400, detail="word is required")
            save_vocabulary(str(uuid4()), user_id, data)
            target = get_user_vocabulary_by_word(user_id, data["word"])
            collected = target is not None

    if target is None:
        # 不入本：只记「见过」，不产生掌握度。
        # 用独立 action 区分"认真评了但没入本"与真正点「跳过」，并保留 rating 信号。
        _record_book_seen(
            user_id,
            payload.word,
            payload.bank_word_id,
            payload.source_module,
            action="graded_not_collected",
            rating=rating,
        )
        return BookGradeResponse(in_book=False, collected=False, skipped=True)

    before_mastery = float(target.get("mastery_level") or 0.0)
    reviewed = review_vocabulary(str(target["id"]), quality=quality)
    if not reviewed:
        raise HTTPException(status_code=500, detail="Failed to review vocabulary")
    return BookGradeResponse(
        vocab_id=str(target["id"]),
        in_book=True,
        collected=collected,
        skipped=False,
        next_review_date=int(reviewed.get("next_review_date") or 0),
        next_review_label=str(reviewed.get("next_review_label") or ""),
        mastery_level=float(reviewed.get("mastery_level") or 0.0),
        mastery_delta=round(float(reviewed.get("mastery_level") or 0.0) - before_mastery, 4),
    )


@router.post("/book/collect", response_model=BookCollectResponse)
async def collect_book_word(payload: BookCollectRequest, current_user: dict = Depends(get_current_user)):
    """把一个词加入词汇本（划词浮层 / 手动收藏）。幂等：已在本中直接返回。"""
    user_id = str(current_user["id"])
    existing = get_user_vocabulary_by_word(user_id, payload.word)
    if existing:
        return BookCollectResponse(
            vocab_id=str(existing["id"]),
            word=str(existing.get("word") or payload.word),
            in_book=True,
            already=True,
        )
    data = _book_collect_data(payload)
    if not str(data.get("word") or "").strip():
        raise HTTPException(status_code=400, detail="word is required")
    save_vocabulary(str(uuid4()), user_id, data)
    row = get_user_vocabulary_by_word(user_id, data["word"])
    if not row:
        raise HTTPException(status_code=500, detail="Failed to collect word")
    return BookCollectResponse(
        vocab_id=str(row["id"]),
        word=str(row.get("word") or data["word"]),
        in_book=True,
        already=False,
    )


@router.delete("/book/collect/{vocab_id}")
async def uncollect_book_word(vocab_id: str, current_user: dict = Depends(get_current_user)):
    if not delete_vocabulary(vocab_id, str(current_user["id"])):
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    return {"ok": True, "vocab_id": vocab_id}


@router.post("/book/seen", response_model=BookSeenResponse)
async def mark_book_word_seen(payload: BookSeenRequest, current_user: dict = Depends(get_current_user)):
    action = str(payload.action or "skip").strip().lower()
    if action not in {"skip", "seen"}:
        action = "skip"
    _record_book_seen(
        str(current_user["id"]),
        payload.word,
        payload.bank_word_id,
        payload.source_module,
        action=action,
    )
    return BookSeenResponse(ok=True, action=action)


@router.get("/book/summary", response_model=BookSummaryResponse)
async def book_summary(current_user: dict = Depends(get_current_user)):
    """词汇本总览：总数 / 活跃 / 已掌握 / 到期 + 按来源分组。"""
    user_id = str(current_user["id"])
    stats = get_vocabulary_stats(user_id)
    counts = get_vocabulary_mastery_counts(user_id)
    groups: List[BookGroupItem] = []
    for source, count in (stats.get("by_source_module") or {}).items():
        key = str(source or "unknown")
        groups.append(BookGroupItem(
            source_module=key,
            label=_BOOK_SOURCE_LABELS.get(key, key),
            count=int(count or 0),
        ))
    groups.sort(key=lambda item: (-item.count, item.source_module))
    return BookSummaryResponse(
        total=int(stats.get("total") or 0),
        active_count=counts["active"],
        mastered_count=counts["mastered"],
        due_count=int(stats.get("due_count") or 0),
        avg_mastery=float(stats.get("avg_mastery") or 0.0),
        groups=groups,
    )


@router.get("/book/list", response_model=BookListResponse)
async def book_list(
    source: str = "",
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """词汇本分页列表，支持按来源分组与 active / mastered 筛选。"""
    page = get_vocabulary_page(
        str(current_user["id"]),
        source_module=source,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [
        BookListItem(
            id=str(item.get("id") or ""),
            word=str(item.get("word") or ""),
            definition=str(item.get("definition") or ""),
            pronunciation=str(item.get("pronunciation") or ""),
            part_of_speech=str(item.get("part_of_speech") or ""),
            source_module=str(item.get("source_module") or ""),
            mastery_level=float(item.get("mastery_level") or 0.0),
            next_review_date=int(item.get("next_review_date") or 0),
            created_at=int(item.get("created_at") or 0),
            mastered=bool(item.get("mastered")),
            due=bool(item.get("due")),
        )
        for item in page["items"]
    ]
    return BookListResponse(total=int(page["total"] or 0), items=items)


@router.post("/book/bulk-remove", response_model=BookBulkRemoveResponse)
async def book_bulk_remove(payload: BookBulkRemoveRequest, current_user: dict = Depends(get_current_user)):
    """批量移出词汇本（仅限本人数据）。"""
    # 去重 + 上限，避免超长 IN 列表触发 "too many SQL variables"
    ids = list(dict.fromkeys(
        str(x).strip() for x in (payload.vocab_ids or []) if str(x).strip()
    ))[:500]
    removed = delete_vocabulary_bulk(ids, str(current_user["id"]))
    return BookBulkRemoveResponse(removed=removed)


@router.get("/book/practice/options", response_model=BookPracticeOptionsResponse)
async def book_practice_options(
    word: str,
    definition: str = "",
    current_user: dict = Depends(get_current_user),
):
    """「不认识 → 再认」练习的 4 选 1 选项（1 正确 + 3 干扰）。"""
    safe_word = _normalize_word_input(word)
    correct = str(definition or "").strip()
    if not correct and safe_word:
        facts = _lookup_word_facts(str(current_user["id"]), safe_word)
        correct = next((str(x).strip() for x in (facts.get("definitions") or []) if str(x).strip()), "")
    if not correct:
        return BookPracticeOptionsResponse(word=safe_word, options=[])

    # 随机采样干扰项：固定取词库前 N 条会让所有题目共用同一组干扰项
    distractors = sample_word_definitions(exclude=correct, limit=3)
    if len(distractors) < 2:
        pool: List[str] = []
        for row in list_ielts_vocabulary_bank(keyword="", limit=60):
            text = str(row.get("definition_cn") or row.get("definition_en") or "").strip()
            if text and text != correct and text not in pool:
                pool.append(text)
        random.shuffle(pool)
        distractors = pool[:3]

    options: List[Dict[str, Any]] = [{"definition": correct, "correct": True}]
    options.extend({"definition": text, "correct": False} for text in distractors)
    random.shuffle(options)
    return BookPracticeOptionsResponse(
        word=safe_word,
        options=[BookPracticeOption(**item) for item in options],
    )


@router.get("/explain", response_model=WordExplainResponse)
async def explain_word(word: str, context: str = "", current_user: dict = Depends(get_current_user)):
    """「问老师」L0：直接用词库 / 词汇本数据给出结构化速览（零 LLM、零延迟）。"""
    safe_word = _normalize_word_input(word)
    if not safe_word:
        raise HTTPException(status_code=400, detail="word is required")
    facts = _lookup_word_facts(str(current_user["id"]), safe_word)
    return WordExplainResponse(context=str(context or "")[:500], **facts)


@router.post("/explain/ask", response_model=WordExplainAskResponse)
async def ask_about_word(payload: WordExplainAskRequest, current_user: dict = Depends(get_current_user)):
    """「问老师」L1：带着单词与语境追问，按需调用 LLM。"""
    word = str(payload.word or "").strip()
    question = str(payload.question or "").strip()
    if not word or not question:
        raise HTTPException(status_code=400, detail="word and question are required")
    if not _allow_llm_request(str(current_user["id"])):
        raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")
    llm = _get_vocab_llm()
    if llm is None:
        return WordExplainAskResponse(
            answer="老师暂时无法回答（模型未就绪），可以先看上面的释义和例句。",
            llm=False,
        )
    history_lines: List[str] = []
    for item in (payload.history or [])[-6:]:
        content = str((item or {}).get("content") or "").strip()
        if not content:
            continue
        role = "学生" if str((item or {}).get("role")) == "user" else "老师"
        history_lines.append(f"{role}：{content}")
    history_text = "\n".join(history_lines)
    context_text = str(payload.context or "").strip()
    prompt = f"""你是雅思词汇老师，请用中文简明回答学生关于单词「{word}」的问题。
要求：
- 紧扣这个词，必要时给出搭配、词形变化、近义辨析和例句。
- 例句用英文，讲解用中文。
- 控制在 200 字以内，不要使用 Markdown 标题。

单词：{word}
释义：{str(payload.definition or '').strip() or '（未知）'}
出现语境：{context_text or '（无）'}{("\n此前对话：\n" + history_text) if history_text else ''}
学生问题：{question}
"""
    try:
        _, raw = await run_in_threadpool(llm.communicate, prompt, temperature=0.4, max_tokens=400)
        answer = str(raw or "").strip()
    except Exception:
        answer = ""
    if not answer:
        return WordExplainAskResponse(answer="老师暂时没能给出回答，请稍后再试。", llm=False)
    return WordExplainAskResponse(answer=answer, llm=True)


@router.get("/audio/word", response_model=VocabularyWordAudioResponse)
async def get_vocabulary_word_audio(
    word: str,
    current_user: dict = Depends(get_current_user),
):
    safe_word = str(word or "").strip()
    if not safe_word:
        raise HTTPException(status_code=400, detail="word is required")
    normalized = _normalize_word_input(safe_word)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid word")
    if len(normalized) > 64:
        raise HTTPException(status_code=400, detail="Word too long")
    if not _allow_tts_request(str(current_user["id"])):
        raise HTTPException(status_code=429, detail="发音请求过于频繁，请稍后再试")
    try:
        result = _tts_service.synthesize_word_audio(word=normalized, lang="en-US", speed=0.86)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS生成失败: {exc}") from exc
    return VocabularyWordAudioResponse(
        word=normalized,
        audio_url=str(result.get("audio_url") or ""),
        cached=bool(result.get("cached", False)),
        storage=str(result.get("storage") or ""),
        backend=str(result.get("backend") or ""),
    )


@router.post("/{vocab_id}/review", response_model=WordReviewResponse)
async def mark_word_reviewed(
    vocab_id: str,
    mastery_delta: float = 0.15,
    quality: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    row = get_vocabulary_by_id(vocab_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    if str(row["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    reviewed = review_vocabulary(vocab_id, mastery_delta, quality=quality)
    if not reviewed:
        raise HTTPException(status_code=500, detail="Failed to review vocabulary")
    return WordReviewResponse(
        next_review_date=reviewed["next_review_date"],
        mastery_level=reviewed["mastery_level"],
    )


@router.post("/learn/submit", response_model=LearningAttemptSubmitResponse)
async def submit_learning_attempt(
    payload: LearningAttemptSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    row = get_vocabulary_by_id(payload.vocab_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    if str(row["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    scoring = await run_in_threadpool(_score_learning_attempt, row, payload)
    before_mastery = float(row["mastery_level"] or 0.0)
    reviewed = review_vocabulary(
        payload.vocab_id,
        scoring["mastery_delta"],
        quality=scoring["sm2_quality"],
    )
    if not reviewed:
        raise HTTPException(status_code=500, detail="Failed to review vocabulary")
    # review_vocabulary 在传入 quality 时会改用 SM2 口径的增量，
    # 因此返回与入库都必须使用真实发生的变化量，保证与 mastery_level 一致。
    applied_mastery_delta = round(float(reviewed["mastery_level"]) - before_mastery, 4)

    attempt_id = str(uuid4())
    save_vocabulary_learning_attempt(
        attempt_id,
        str(current_user["id"]),
        payload.vocab_id,
        {
            **scoring,
            "mastery_delta": applied_mastery_delta,
            "session_id": payload.session_id,
            "strategy": payload.strategy,
            "recall_text": payload.recall_text,
            "cloze_answer": payload.cloze_answer,
            "output_sentence": payload.output_sentence,
            "mastery_after": reviewed["mastery_level"],
            "next_review_date": reviewed["next_review_date"],
        },
    )
    record_practice_result(
        str(current_user["id"]),
        "vocabulary",
        {
            "overall": round(float(scoring["quality_score"]) * 10, 2),
            "vocabulary": round(float(scoring["quality_score"]) * 10, 2),
            "word": str(row.get("word") or ""),
        },
        difficulty=_word_difficulty_tag(row),
        topic=_primary_topic(row),
        practice_mode=str(payload.strategy or "smart"),
        source="vocabulary_learning",
    )
    return LearningAttemptSubmitResponse(
        next_review_date=reviewed["next_review_date"],
        next_review_label=str(reviewed.get("next_review_label") or scoring["next_review_label"]),
        mastery_level=reviewed["mastery_level"],
        mastery_delta=applied_mastery_delta,
        quality_score=scoring["quality_score"],
        recall_completed=scoring["recall_completed"],
        cloze_correct=scoring["cloze_correct"],
        output_uses_word=scoring["output_uses_word"],
        feedback=scoring["feedback"],
        output_feedback=scoring["output_feedback"],
        output_suggestion=scoring["output_suggestion"],
    )


@router.post("/learn/output-prompt", response_model=OutputPromptResponse)
async def generate_output_prompt(
    payload: OutputPromptRequest,
    current_user: dict = Depends(get_current_user),
):
    row = get_vocabulary_by_id(payload.vocab_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    if str(row["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    sentence = await run_in_threadpool(_generate_output_prompt_sentence, row, payload.topic)
    return OutputPromptResponse(chinese_sentence=sentence)


@router.get("/stats/summary", response_model=VocabularyStatsResponse)
async def vocabulary_summary(current_user: dict = Depends(get_current_user)):
    return VocabularyStatsResponse(**get_vocabulary_stats(current_user["id"]))


@router.get("/strategy/insights", response_model=List[VocabularyStrategyInsightItem])
async def vocabulary_strategy_insights(
    days: int = 14,
    current_user: dict = Depends(get_current_user),
):
    rows = get_vocabulary_strategy_insights(current_user["id"], days=days)
    return [VocabularyStrategyInsightItem(**x) for x in rows]


@router.get("/scenarios", response_model=List[VocabularyScenarioPack])
async def list_vocabulary_scenarios(
    module: Optional[str] = None,
    topic: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    learned_rows = get_user_vocabulary(current_user["id"], 2000)
    learned_words = {str(x.get("word", "")).strip().lower() for x in learned_rows}

    packs: List[VocabularyScenarioPack] = []
    for pack in SCENARIO_VOCAB_BANK:
        module_key = str(pack.get("module") or "").strip().lower()
        topic_key = str(pack.get("topic") or "").strip().lower()
        if module and module_key != module.strip().lower():
            continue
        if topic and topic_key != topic.strip().lower():
            continue
        words = [VocabularyScenarioWord(**x) for x in (pack.get("words") or [])]
        learned_count = sum(1 for x in words if x.word.strip().lower() in learned_words)
        packs.append(
            VocabularyScenarioPack(
                module=module_key,
                topic=topic_key,
                level=str(pack.get("level") or "intermediate"),
                words=words,
                learned_count=learned_count,
                total_count=len(words),
            )
        )
    return packs


@router.post("/scenarios/import", response_model=VocabularyScenarioImportResponse)
async def import_vocabulary_scenario(
    payload: VocabularyScenarioImportRequest,
    current_user: dict = Depends(get_current_user),
):
    module_key = payload.module.strip().lower()
    topic_key = payload.topic.strip().lower()
    target_pack = next(
        (
            p for p in SCENARIO_VOCAB_BANK
            if str(p.get("module", "")).strip().lower() == module_key
            and str(p.get("topic", "")).strip().lower() == topic_key
        ),
        None,
    )
    if not target_pack:
        raise HTTPException(status_code=404, detail="Scenario pack not found")

    existing = get_user_vocabulary(current_user["id"], 5000)
    existing_by_word = {str(w.get("word", "")).strip().lower() for w in existing}

    imported_words: List[str] = []
    skipped_existing = 0
    for item in (target_pack.get("words") or [])[: max(1, min(payload.limit, 200))]:
        word = str(item.get("word", "")).strip()
        if not word:
            continue
        key = word.lower()
        if key in existing_by_word:
            skipped_existing += 1
            continue
        save_vocabulary(
            str(uuid4()),
            current_user["id"],
            {
                "word": word,
                "definition": str(item.get("definition") or ""),
                "examples": [str(item.get("example") or "")] if item.get("example") else [],
                "pronunciation": "",
                "part_of_speech": "",
                "tags": ["scenario", module_key, topic_key],
                "source_module": payload.source_module or "scenario_pack",
                "mastery_level": 0.0,
            },
        )
        existing_by_word.add(key)
        imported_words.append(word)

    return VocabularyScenarioImportResponse(
        imported=len(imported_words),
        skipped_existing=skipped_existing,
        words=imported_words,
    )


@router.post("/collect", response_model=VocabularyAutoCollectResponse)
async def auto_collect_vocabulary(
    payload: VocabularyAutoCollectRequest,
    current_user: dict = Depends(get_current_user),
):
    text = (payload.text or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="Text too short for vocabulary collection")

    candidates = _extract_candidate_words(text, max_words=max(1, min(payload.max_words * 3, 300)))
    if not candidates:
        return VocabularyAutoCollectResponse(imported=0, skipped_existing=0, words=[])

    existing = get_user_vocabulary(current_user["id"], 5000)
    existing_by_word: Dict[str, str] = {}
    for w in existing:
        key = str(w.get("word", "")).strip().lower()
        wid = str(w.get("id") or "").strip()
        if key and wid:
            existing_by_word[key] = wid

    imported_words: List[str] = []
    selected_word_ids: List[str] = []
    skipped_existing = 0
    for token in candidates:
        if token in existing_by_word:
            skipped_existing += 1
            selected_word_ids.append(existing_by_word[token])
            continue
        vocab_id = str(uuid4())
        save_vocabulary(
            vocab_id,
            current_user["id"],
            {
                "word": token,
                "definition": "",
                "examples": [],
                "pronunciation": "",
                "part_of_speech": "",
                "tags": ["auto_collect", payload.topic.strip().lower() or "general"],
                "source_module": payload.source_module.strip().lower() or "reading",
                "mastery_level": 0.0,
            },
        )
        imported_words.append(token)
        existing_by_word[token] = vocab_id
        selected_word_ids.append(vocab_id)
        if len(imported_words) >= max(1, min(payload.max_words, 200)):
            break

    return VocabularyAutoCollectResponse(
        imported=len(imported_words),
        skipped_existing=skipped_existing,
        words=imported_words,
        word_ids=selected_word_ids,
    )


@router.post("/context/replay/generate", response_model=ContextReplayGenerateResponse)
async def generate_context_replay(
    payload: ContextReplayGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    count = max(1, min(int(payload.count or 5), 30))
    mode = (payload.mode or "cloze").strip().lower()
    if mode not in {"cloze", "multiple_choice"}:
        raise HTTPException(status_code=400, detail="Unsupported context replay mode")

    all_words = get_user_vocabulary(user_id, 3000)
    words = all_words
    word_ids = [str(wid).strip() for wid in (payload.word_ids or []) if str(wid).strip()]
    if word_ids:
        allowed = set(word_ids)
        words = [w for w in all_words if str(w.get("id")) in allowed]
    if payload.source_module:
        source_key = payload.source_module.strip().lower()
        words = [w for w in words if str(w.get("source_module", "")).strip().lower() == source_key]
    if payload.topic:
        topic_key = payload.topic.strip().lower()
        words = [
            w for w in words
            if topic_key in {str(t).strip().lower() for t in (w.get("tags") or [])}
        ]
    if not words:
        raise HTTPException(status_code=400, detail="No vocabulary found for context replay")

    selected = _pick_words_by_strategy(words, "spaced", count)
    if not selected:
        raise HTTPException(status_code=400, detail="No suitable words for context replay")

    questions: List[Dict[str, Any]] = []
    for w in selected:
        qid = str(uuid4())
        word = str(w.get("word") or "").strip()
        prompt = _build_context_prompt(w)
        answer_format = "text"
        options = None
        if mode == "multiple_choice":
            answer_format = "option"
            option_words = [word]
            distractors = []
            for item in words:
                candidate = str(item.get("word") or "").strip()
                if candidate and candidate.lower() != word.lower() and candidate not in distractors:
                    distractors.append(candidate)
            random.shuffle(distractors)
            option_words.extend(distractors[:3])
            random.shuffle(option_words)
            options = option_words
        questions.append(
            {
                "id": qid,
                "word_id": str(w.get("id")),
                "prompt": prompt,
                "answer_format": answer_format,
                "options": options,
                "hint": str(w.get("definition") or "").strip()[:120],
                "_answer": word,
                "_definition": str(w.get("definition") or "").strip(),
                "_example": str(((w.get("examples") or [""])[0] or "")).strip(),
            }
        )

    session_id = str(uuid4())
    context_replay_runtime[session_id] = {
        "user_id": str(user_id),
        "mode": mode,
        "questions": questions,
        "created_at": int(time.time()),
    }
    return ContextReplayGenerateResponse(
        session_id=session_id,
        mode=mode,
        questions=[
            ContextReplayQuestion(
                id=q["id"],
                word_id=q["word_id"],
                prompt=q["prompt"],
                answer_format=q["answer_format"],
                options=q["options"],
                hint=q["hint"],
            )
            for q in questions
        ],
    )


@router.post("/context/replay/submit", response_model=ContextReplaySubmitResponse)
async def submit_context_replay(
    payload: ContextReplaySubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    runtime = context_replay_runtime.get(payload.session_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Context replay session not found")
    if str(runtime.get("user_id")) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    answer_map = {str(a.question_id): str(a.answer or "").strip().lower() for a in payload.answers}
    details: List[Dict[str, Any]] = []
    correct = 0

    for q in runtime.get("questions", []):
        qid = str(q.get("id") or "")
        expected = str(q.get("_answer") or "").strip().lower()
        user_answer = answer_map.get(qid, "")
        is_correct = user_answer == expected
        if is_correct:
            correct += 1
            review_vocabulary(str(q.get("word_id")), 0.12)
        else:
            review_vocabulary(str(q.get("word_id")), -0.08)
            word_tag = f"word_id:{str(q.get('word_id') or '').strip()}"
            save_mistake(
                str(uuid4()),
                str(current_user["id"]),
                {
                    "module": "vocabulary",
                    "question_id": qid,
                    "question_type": "vocabulary_context_replay",
                    "error_type": "context_replay_wrong",
                    "content": str(q.get("prompt") or ""),
                    "user_answer": user_answer,
                    "correct_answer": str(q.get("_answer") or ""),
                    "explanation": f"Context replay expected word: {q.get('_answer')}",
                    "difficulty": "medium",
                    "tags": ["vocabulary_context_replay", str(runtime.get("mode") or "cloze"), word_tag],
                },
            )
        definition = str(q.get("_definition") or "").strip()
        example = str(q.get("_example") or "").strip()
        explanation = f"目标词：{q.get('_answer') or ''}"
        if definition:
            explanation += f"；释义：{definition}"
        if example:
            explanation += f"；例句：{example}"
        details.append(
            {
                "question_id": qid,
                "word_id": q.get("word_id"),
                "is_correct": is_correct,
                "expected_answer": q.get("_answer"),
                "user_answer": answer_map.get(qid, ""),
                "explanation": explanation,
            }
        )

    total = len(runtime.get("questions", []))
    accuracy = round((correct / total), 4) if total else 0.0
    record_practice_result(
        str(current_user["id"]),
        "vocabulary",
        {
            "overall": round(accuracy * 10, 2),
            "accuracy": round(accuracy * 10, 2),
            "vocabulary": round(accuracy * 10, 2),
        },
        difficulty="medium",
        topic=str(runtime.get("topic") or "general"),
        practice_mode=f"context_replay_{runtime.get('mode') or 'cloze'}",
        source="vocabulary_context_replay",
    )
    return ContextReplaySubmitResponse(total=total, correct=correct, accuracy=accuracy, details=details)


@router.get("/context/replay/retry-queue", response_model=List[ContextReplayRetryQueueItem])
async def get_context_replay_retry_queue(
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])
    now = int(time.time())
    mistakes = get_user_mistakes(
        user_id,
        module="vocabulary",
        limit=1000,
        question_type="vocabulary_context_replay",
    )
    if not mistakes:
        return []

    wrong_stats: Dict[str, Dict[str, Any]] = {}
    for m in mistakes:
        tags = m.get("tags") or []
        word_id = ""
        for t in tags:
            ts = str(t or "")
            if ts.startswith("word_id:"):
                word_id = ts.split("word_id:", 1)[1].strip()
                break
        if not word_id:
            continue
        item = wrong_stats.setdefault(
            word_id,
            {"wrong_count": 0, "latest_wrong_ts": 0},
        )
        item["wrong_count"] += 1
        item["latest_wrong_ts"] = max(item["latest_wrong_ts"], int(m.get("created_at") or 0))

    if not wrong_stats:
        return []

    words = get_user_vocabulary(user_id, 5000)
    words_by_id = {str(w.get("id")): w for w in words}

    queue: List[ContextReplayRetryQueueItem] = []
    for word_id, stat in wrong_stats.items():
        row = words_by_id.get(word_id)
        if not row:
            continue
        base_score, base_reason = _forgetting_priority(row, now)
        wrong_boost = min(1.5, 0.15 * int(stat["wrong_count"]))
        score = base_score + wrong_boost
        reason = f"{base_reason} + 语境错题 {stat['wrong_count']} 次"
        queue.append(
            ContextReplayRetryQueueItem(
                word_id=word_id,
                word=str(row.get("word") or ""),
                definition=str(row.get("definition") or ""),
                priority_score=round(float(score), 6),
                priority_reason=reason,
                wrong_count=int(stat["wrong_count"]),
            )
        )

    queue.sort(key=lambda x: (-float(x.priority_score), -int(x.wrong_count), x.word))
    return queue[: max(1, min(limit, 200))]


@router.post("/test/generate", response_model=VocabTestGenerateResponse)
async def generate_vocab_test(
    payload: VocabTestGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    words = get_user_vocabulary(user_id, 300)
    if not words:
        raise HTTPException(status_code=400, detail="Vocabulary list is empty")

    mode = (payload.mode or "multiple_choice").strip().lower()
    if mode not in {"multiple_choice", "spelling", "fill_blank"}:
        raise HTTPException(status_code=400, detail="Unsupported test mode")

    selected = _pick_words_by_strategy(words, "spaced", payload.count)
    questions: List[Dict[str, Any]] = []
    for w in selected:
        qid = str(uuid4())
        word = str(w.get("word") or "")
        definition = str(w.get("definition") or "")
        if mode == "multiple_choice":
            options = _build_mcq_options(w, words)
            prompt = f"选择单词 '{word}' 最匹配的释义："
            answer = definition
            answer_format = "option"
        elif mode == "spelling":
            prompt = f"根据释义拼写单词：{definition}"
            options = None
            answer = word
            answer_format = "text"
        else:
            example = ((w.get("examples") or [""])[0] or "").strip()
            base = example if example else definition
            prompt = f"填空：{base.replace(word, '____') if word and word in base else f'请填入与释义匹配的词：{definition}'}"
            options = None
            answer = word
            answer_format = "text"

        questions.append(
            {
                "id": qid,
                "prompt": prompt,
                "options": options,
                "answer_format": answer_format,
                "_answer": answer,
                "_word_id": w.get("id"),
                "_word": word,
            }
        )

    test_id = str(uuid4())
    test_runtime[test_id] = {
        "user_id": str(user_id),
        "mode": mode,
        "questions": questions,
        "created_at": int(time.time()),
    }
    return VocabTestGenerateResponse(
        test_id=test_id,
        mode=mode,
        questions=[
            VocabTestQuestion(
                id=q["id"],
                prompt=q["prompt"],
                options=q["options"],
                answer_format=q["answer_format"],
            )
            for q in questions
        ],
    )


@router.post("/test/submit", response_model=VocabTestSubmitResponse)
async def submit_vocab_test(
    payload: VocabTestSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    runtime = test_runtime.get(payload.test_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Vocabulary test not found")
    if str(runtime.get("user_id")) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    answer_map = {str(a.question_id): str(a.answer or "").strip().lower() for a in payload.answers}
    details = []
    correct = 0
    for q in runtime.get("questions", []):
        qid = str(q["id"])
        expected = str(q.get("_answer") or "").strip().lower()
        user_answer = answer_map.get(qid, "")
        is_correct = user_answer == expected
        if is_correct:
            correct += 1
        else:
            # 词汇测试答错自动沉淀到错题本，进入后续复习与提醒链路
            word_id = str(q.get("_word_id") or "").strip()
            tags = ["vocabulary_test", str(runtime.get("mode") or "unknown")]
            if word_id:
                tags.append(f"word_id:{word_id}")
            save_mistake(
                str(uuid4()),
                str(current_user["id"]),
                {
                    "module": "vocabulary",
                    "question_id": qid,
                    "question_type": "vocabulary_test",
                    "error_type": "vocabulary_test_wrong",
                    "content": str(q.get("prompt") or ""),
                    "user_answer": user_answer,
                    "correct_answer": str(q.get("_answer") or ""),
                    "explanation": "Vocabulary test incorrect answer.",
                    "difficulty": "medium",
                    "tags": tags,
                },
            )
        details.append(
            {
                "question_id": qid,
                "word_id": q.get("_word_id"),
                "word": q.get("_word"),
                "is_correct": is_correct,
                "expected_answer": q.get("_answer"),
                "user_answer": answer_map.get(qid, ""),
            }
        )

    total = len(runtime.get("questions", []))
    accuracy = round((correct / total), 4) if total else 0.0
    record_practice_result(
        str(current_user["id"]),
        "vocabulary",
        {
            "overall": round(accuracy * 10, 2),
            "accuracy": round(accuracy * 10, 2),
            "vocabulary": round(accuracy * 10, 2),
        },
        difficulty="medium",
        topic="general",
        practice_mode=f"test_{runtime.get('mode') or 'unknown'}",
        source="vocabulary_test",
    )
    return VocabTestSubmitResponse(
        total=total,
        correct=correct,
        accuracy=accuracy,
        details=details,
    )


@router.post("/wrong/review-queue", response_model=List[WrongReviewQueueItem])
async def get_wrong_review_queue(
    payload: WrongReviewQueueRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])
    now = int(time.time())
    requested_ids = [str(wid).strip() for wid in (payload.word_ids or []) if str(wid).strip()]
    if not requested_ids:
        return []

    unique_ids = list(dict.fromkeys(requested_ids))
    ranked: List[Dict[str, Any]] = []
    for vocab_id in unique_ids:
        row = get_vocabulary_by_id(vocab_id)
        if not row:
            continue
        if str(row.get("user_id")) != user_id:
            continue
        score, reason = _forgetting_priority(row, now)
        ranked.append(
            {
                **row,
                "priority_score": score,
                "priority_reason": reason,
            }
        )

    ranked.sort(
        key=lambda x: (
            -float(x.get("priority_score") or 0.0),
            float(x.get("mastery_level") or 0.0),
            int(x.get("next_review_date") or 0),
        )
    )
    limit = max(1, int(payload.limit or 30))
    return [WrongReviewQueueItem(**x) for x in ranked[:limit]]

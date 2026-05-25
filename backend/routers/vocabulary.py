from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import uuid4
import random
import time
import math
import re

from ..deps import get_current_user
from ..db import (
    save_vocabulary,
    get_user_vocabulary,
    get_due_vocabulary,
    get_vocabulary_by_id,
    review_vocabulary,
    get_vocabulary_stats,
    save_vocabulary_strategy_session,
    get_vocabulary_strategy_insights,
    save_vocabulary_learning_attempt,
    save_mistake,
    get_user_mistakes,
)
from ..services.ielts_vocabulary_bank_service import (
    get_ielts_vocabulary_bank_by_ids,
    get_ielts_vocabulary_bank_summary,
    list_ielts_vocabulary_bank,
)

try:
    from models.generator_model import GeneratorModel
except Exception:  # pragma: no cover - keeps vocabulary routes usable without LLM deps
    GeneratorModel = None


router = APIRouter()
test_runtime: Dict[str, Dict[str, Any]] = {}
context_replay_runtime: Dict[str, Dict[str, Any]] = {}
_vocab_llm = None


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


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


def _normalize_word_token(token: str) -> str:
    return re.sub(r"[^a-zA-Z\-']", "", str(token or "")).lower().strip("-'")


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


def _assess_output_sentence(sentence: str, word: str) -> Dict[str, str]:
    lines = [x.strip() for x in str(sentence or "").splitlines() if x.strip()]
    text = lines[-1] if lines else ""
    if not text:
        return {"output_feedback": "", "output_suggestion": ""}

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
    if self_rating not in {"unknown", "fuzzy", "known"}:
        self_rating = "fuzzy"

    recall_completed = len(recall_text) >= 2
    cloze_correct = bool(cloze_answer) and cloze_answer.lower() == word.lower()
    output_uses_word = _contains_word(output_sentence, word)
    output_assessment = _assess_output_sentence(output_sentence, word)

    rating_score = {"unknown": 0.0, "fuzzy": 0.5, "known": 1.0}[self_rating]
    quality_score = (
        (0.22 if recall_completed else 0.0)
        + (0.28 if cloze_correct else 0.0)
        + (0.25 if output_uses_word else 0.0)
        + rating_score * 0.25
    )
    delta = {"unknown": -0.14, "fuzzy": 0.04, "known": 0.14}[self_rating]
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

    current_mastery = max(0.0, min(1.0, float(word_row.get("mastery_level") or 0.0)))
    projected_mastery = max(0.0, min(1.0, current_mastery + delta))
    if quality_score <= 0.25:
        interval_seconds = 4 * 3600
        next_review_label = "约4小时后复习"
    elif quality_score <= 0.45:
        interval_seconds = 12 * 3600
        next_review_label = "约12小时后复习"
    elif quality_score <= 0.65:
        interval_seconds = 24 * 3600
        next_review_label = "明天复习"
    elif quality_score <= 0.82:
        interval_seconds = 3 * 24 * 3600
        next_review_label = "约3天后复习"
    elif projected_mastery >= 0.85:
        interval_seconds = 14 * 24 * 3600
        next_review_label = "约14天后复习"
    else:
        interval_seconds = 7 * 24 * 3600
        next_review_label = "约7天后复习"

    return {
        "recall_completed": recall_completed,
        "cloze_correct": cloze_correct,
        "output_uses_word": output_uses_word,
        "quality_score": round(quality_score, 4),
        "mastery_delta": round(delta, 4),
        "review_interval_seconds": interval_seconds,
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
    count = max(1, min(int(payload.count or 10), 30))
    all_words = get_user_vocabulary(user_id, 5000)
    filtered_words = [
        word for word in all_words
        if _word_matches_learning_filters(word, topic=payload.topic, difficulty=payload.difficulty)
    ]
    selected_pool = filtered_words if (payload.topic or payload.difficulty) else all_words
    selected = _pick_words_by_strategy(selected_pool, "mixed", count)

    if len(selected) < count:
        existing_words = {str(w.get("word", "")).strip().lower() for w in all_words}
        bank_rows = list_ielts_vocabulary_bank(
            difficulty=payload.difficulty or "",
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
                if _word_matches_learning_filters(word, topic=payload.topic, difficulty=payload.difficulty)
            ]
            selected_pool = filtered_words if (payload.topic or payload.difficulty) else all_words
            selected = _pick_words_by_strategy(selected_pool, "mixed", count)

    save_vocabulary_strategy_session(user_id, "today_active_recall", selected)
    return LearnSessionResponse(
        session_id=str(uuid4()),
        strategy="today_active_recall",
        words=[LearnSessionWordItem(**w) for w in selected],
    )


@router.post("/{vocab_id}/review", response_model=WordReviewResponse)
async def mark_word_reviewed(
    vocab_id: str,
    mastery_delta: float = 0.15,
    current_user: dict = Depends(get_current_user),
):
    row = get_vocabulary_by_id(vocab_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    if str(row["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    reviewed = review_vocabulary(vocab_id, mastery_delta)
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

    scoring = _score_learning_attempt(row, payload)
    reviewed = review_vocabulary(
        payload.vocab_id,
        scoring["mastery_delta"],
        review_interval_seconds=scoring["review_interval_seconds"],
    )
    if not reviewed:
        raise HTTPException(status_code=500, detail="Failed to review vocabulary")

    attempt_id = str(uuid4())
    save_vocabulary_learning_attempt(
        attempt_id,
        str(current_user["id"]),
        payload.vocab_id,
        {
            **scoring,
            "session_id": payload.session_id,
            "strategy": payload.strategy,
            "recall_text": payload.recall_text,
            "cloze_answer": payload.cloze_answer,
            "output_sentence": payload.output_sentence,
            "mastery_after": reviewed["mastery_level"],
            "next_review_date": reviewed["next_review_date"],
        },
    )
    return LearningAttemptSubmitResponse(
        next_review_date=reviewed["next_review_date"],
        next_review_label=scoring["next_review_label"],
        mastery_level=reviewed["mastery_level"],
        mastery_delta=scoring["mastery_delta"],
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
    sentence = _generate_output_prompt_sentence(row, payload.topic)
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

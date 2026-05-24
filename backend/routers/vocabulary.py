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
    save_mistake,
    get_user_mistakes,
)


router = APIRouter()
test_runtime: Dict[str, Dict[str, Any]] = {}
context_replay_runtime: Dict[str, Dict[str, Any]] = {}


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

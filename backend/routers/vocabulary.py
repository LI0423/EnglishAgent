from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import uuid4
import random
import time
import math

from ..deps import get_current_user
from ..db import (
    save_vocabulary,
    get_user_vocabulary,
    get_due_vocabulary,
    get_vocabulary_by_id,
    review_vocabulary,
    get_vocabulary_stats,
    save_mistake,
)


router = APIRouter()
test_runtime: Dict[str, Dict[str, Any]] = {}


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


class LearnSessionResponse(BaseModel):
    session_id: str
    strategy: str
    words: List[WordItem]


class WordReviewResponse(BaseModel):
    next_review_date: int
    mastery_level: float


class VocabularyStatsResponse(BaseModel):
    total: int
    due_count: int
    avg_mastery: float
    by_source_module: dict


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

    if s == "root":
        with_affix = [w for w in words if _word_has_affix(w.get("word", ""))]
        without_affix = [w for w in words if not _word_has_affix(w.get("word", ""))]
        random.shuffle(with_affix)
        random.shuffle(without_affix)
        ordered = with_affix + without_affix
        return ordered[:n]

    if s == "context":
        rich_context = [w for w in words if (w.get("examples") or [])]
        weak_context = [w for w in words if not (w.get("examples") or [])]
        random.shuffle(rich_context)
        random.shuffle(weak_context)
        ordered = rich_context + weak_context
        return ordered[:n]

    # default: spaced
    due = [w for w in words if int(w.get("next_review_date") or 0) <= now]
    not_due = [w for w in words if int(w.get("next_review_date") or 0) > now]
    due.sort(key=lambda w: (float(w.get("mastery_level") or 0.0), int(w.get("next_review_date") or 0)))
    not_due.sort(key=lambda w: (float(w.get("mastery_level") or 0.0), int(w.get("next_review_date") or 0)))
    ordered = due + not_due
    return ordered[:n]


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


@router.get("/", response_model=List[WordItem])
async def list_vocabulary(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    words = get_user_vocabulary(current_user["id"], limit)
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
    return LearnSessionResponse(
        session_id=str(uuid4()),
        strategy=payload.strategy,
        words=[WordItem(**w) for w in selected],
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
                    "tags": ["vocabulary_test", str(runtime.get("mode") or "unknown")],
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

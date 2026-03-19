import json
import os
import random
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import save_mistake
from ..deps import get_current_user

router = APIRouter()


class SynonymRecognitionRequest(BaseModel):
    text: str
    topic: str = "general"


class SynonymResult(BaseModel):
    original: str
    synonyms: List[str]
    context: str
    position: int


class SynonymRecognitionResponse(BaseModel):
    results: List[SynonymResult]
    summary: str


class DifficultyAnalysis(BaseModel):
    level: str
    reason: str


class PassageAnalysisRequest(BaseModel):
    text: str


class LongSentenceAnalysis(BaseModel):
    sentence: str
    original: str
    structure: Dict[str, Any]
    simplified: str
    explanation: str


class PassageAnalysisResponse(BaseModel):
    difficulty: DifficultyAnalysis
    synonym_count: int
    long_sentence_count: int
    key_topics: List[str]


class ReadingQuizQuestion(BaseModel):
    id: str
    prompt: str
    options: Optional[List[str]] = None
    question_type: str
    difficulty: str


class ReadingQuizGenerateRequest(BaseModel):
    count: int = 5
    difficulty: Optional[str] = None
    question_type: Optional[str] = None


class ReadingQuizGenerateResponse(BaseModel):
    quiz_id: str
    questions: List[ReadingQuizQuestion]


class ReadingQuizAnswer(BaseModel):
    question_id: str
    answer: str


class ReadingQuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: List[ReadingQuizAnswer]


class ReadingQuizSubmitResponse(BaseModel):
    total: int
    correct: int
    accuracy: float
    details: List[Dict[str, Any]]


class QuizVersionResponse(BaseModel):
    version: str
    source: str
    count: int


synonym_dict = {
    "important": ["significant", "crucial", "vital"],
    "improve": ["enhance", "boost", "advance"],
    "problem": ["issue", "challenge", "concern"],
    "solution": ["approach", "resolution", "answer"],
    "result": ["outcome", "consequence", "effect"],
}

DEFAULT_READING_QUESTION_BANK = [
    {
        "id": "rd_q_001",
        "prompt": "T/F/NG: The passage says all cities reduced pollution by 2020.",
        "answer": "false",
        "options": ["true", "false", "not given"],
        "question_type": "tfng",
        "difficulty": "basic",
        "explanation": "The text does not claim all cities reduced pollution.",
    },
    {
        "id": "rd_q_002",
        "prompt": "Which heading best matches paragraph 4?",
        "answer": "technology adoption",
        "options": ["economic decline", "technology adoption", "policy failure", "population ageing"],
        "question_type": "heading_matching",
        "difficulty": "intermediate",
        "explanation": "Paragraph 4 mainly discusses technology adoption.",
    },
    {
        "id": "rd_q_003",
        "prompt": "The author's attitude to the study is mostly:",
        "answer": "supportive",
        "options": ["critical", "supportive", "uncertain", "dismissive"],
        "question_type": "attitude",
        "difficulty": "intermediate",
        "explanation": "The author presents the study in a supportive tone.",
    },
    {
        "id": "rd_q_004",
        "prompt": "Which inference is best supported by the final paragraph?",
        "answer": "long-term monitoring is required",
        "options": [
            "current data is sufficient",
            "policy is unnecessary",
            "long-term monitoring is required",
            "technology solved all issues",
        ],
        "question_type": "inference",
        "difficulty": "advanced",
        "explanation": "The final paragraph stresses long-term monitoring.",
    },
]

READING_QUESTION_BANK: List[Dict[str, Any]] = []
READING_QUESTION_BANK_VERSION = "builtin-fallback"
READING_QUIZ_RUNTIME: Dict[str, Dict[str, Any]] = {}


def _question_bank_path() -> str:
    return os.environ.get(
        "READING_QUESTION_BANK_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "reading_question_bank.v1.json",
        ),
    )


def _load_reading_question_bank() -> None:
    global READING_QUESTION_BANK, READING_QUESTION_BANK_VERSION
    path = _question_bank_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        version = str(payload.get("version") or "unknown")
        questions = payload.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("invalid questions")

        loaded = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id") or "").strip()
            prompt = str(q.get("prompt") or "").strip()
            answer = str(q.get("answer") or "").strip()
            if not qid or not prompt or not answer:
                continue
            loaded.append(
                {
                    "id": qid,
                    "prompt": prompt,
                    "answer": answer,
                    "options": q.get("options"),
                    "question_type": str(q.get("question_type") or "general"),
                    "difficulty": str(q.get("difficulty") or "intermediate"),
                    "explanation": str(q.get("explanation") or ""),
                }
            )
        if not loaded:
            raise ValueError("empty loaded questions")
        READING_QUESTION_BANK = loaded
        READING_QUESTION_BANK_VERSION = version
    except Exception:
        READING_QUESTION_BANK = DEFAULT_READING_QUESTION_BANK
        READING_QUESTION_BANK_VERSION = "builtin-fallback"


_load_reading_question_bank()


@router.get("/quiz/version", response_model=QuizVersionResponse)
async def get_reading_quiz_version(current_user: dict = Depends(get_current_user)):
    source = "file" if READING_QUESTION_BANK_VERSION != "builtin-fallback" else "builtin"
    return QuizVersionResponse(version=READING_QUESTION_BANK_VERSION, source=source, count=len(READING_QUESTION_BANK))


@router.post("/quiz/generate", response_model=ReadingQuizGenerateResponse)
async def generate_reading_quiz(
    payload: ReadingQuizGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    count = max(1, min(int(payload.count or 5), 20))
    difficulty = (payload.difficulty or "").strip().lower()
    question_type = (payload.question_type or "").strip().lower()

    pool = READING_QUESTION_BANK
    if difficulty:
        pool = [q for q in pool if str(q.get("difficulty") or "").lower() == difficulty]
    if question_type:
        pool = [q for q in pool if str(q.get("question_type") or "").lower() == question_type]
    if not pool:
        raise HTTPException(status_code=400, detail="No reading quiz questions found for given filters")

    selected = pool[:] if len(pool) <= count else random.sample(pool, count)
    runtime_questions = []
    public_questions = []
    for q in selected:
        qid = str(uuid4())
        runtime_questions.append(
            {
                "id": qid,
                "prompt": q.get("prompt"),
                "options": q.get("options"),
                "question_type": q.get("question_type"),
                "difficulty": q.get("difficulty"),
                "_answer": q.get("answer"),
                "_explanation": q.get("explanation"),
            }
        )
        public_questions.append(
            ReadingQuizQuestion(
                id=qid,
                prompt=str(q.get("prompt") or ""),
                options=q.get("options"),
                question_type=str(q.get("question_type") or "general"),
                difficulty=str(q.get("difficulty") or "intermediate"),
            )
        )

    quiz_id = str(uuid4())
    READING_QUIZ_RUNTIME[quiz_id] = {
        "user_id": str(current_user["id"]),
        "questions": runtime_questions,
        "created_at": int(time.time()),
    }
    return ReadingQuizGenerateResponse(quiz_id=quiz_id, questions=public_questions)


@router.post("/quiz/submit", response_model=ReadingQuizSubmitResponse)
async def submit_reading_quiz(
    payload: ReadingQuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    runtime = READING_QUIZ_RUNTIME.get(payload.quiz_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Reading quiz not found")
    if str(runtime.get("user_id")) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    answer_map = {str(a.question_id): str(a.answer or "").strip().lower() for a in payload.answers}
    details = []
    correct = 0
    for q in runtime.get("questions", []):
        qid = str(q.get("id") or "")
        expected = str(q.get("_answer") or "").strip().lower()
        user_answer = answer_map.get(qid, "")
        is_correct = user_answer == expected
        if is_correct:
            correct += 1
        else:
            save_mistake(
                str(uuid4()),
                str(current_user["id"]),
                {
                    "module": "reading",
                    "question_id": qid,
                    "question_type": "reading_quiz",
                    "error_type": "reading_incorrect",
                    "content": str(q.get("prompt") or ""),
                    "user_answer": user_answer,
                    "correct_answer": str(q.get("_answer") or ""),
                    "explanation": str(q.get("_explanation") or "Reading quiz incorrect answer."),
                    "difficulty": str(q.get("difficulty") or "medium"),
                    "tags": ["reading_quiz", str(q.get("question_type") or "unknown")],
                },
            )
        details.append(
            {
                "question_id": qid,
                "question_type": q.get("question_type"),
                "is_correct": is_correct,
                "expected_answer": q.get("_answer"),
                "user_answer": answer_map.get(qid, ""),
            }
        )

    total = len(runtime.get("questions", []))
    accuracy = round((correct / total), 4) if total else 0.0
    return ReadingQuizSubmitResponse(total=total, correct=correct, accuracy=accuracy, details=details)


@router.post("/synonyms", response_model=SynonymRecognitionResponse)
async def recognize_synonyms(req: SynonymRecognitionRequest, current_user: dict = Depends(get_current_user)):
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    results = []
    words = req.text.split()
    processed_words = set()
    for i, word in enumerate(words):
        lowercase_word = word.strip().rstrip(".,;:?!").lower()
        if lowercase_word in synonym_dict and lowercase_word not in processed_words:
            synonyms = synonym_dict[lowercase_word]
            start = max(0, i - 3)
            end = min(len(words), i + 4)
            context = " ".join(words[start:end])
            position = req.text.find(word, req.text.find(" ".join(words[start:i])))

            results.append(
                SynonymResult(
                    original=word,
                    synonyms=synonyms,
                    context=context,
                    position=position,
                )
            )
            processed_words.add(lowercase_word)

    summary = f"Found {len(results)} groups of synonyms"
    return SynonymRecognitionResponse(results=results, summary=summary)


@router.post("/analyze", response_model=PassageAnalysisResponse)
async def analyze_passage(req: PassageAnalysisRequest, current_user: dict = Depends(get_current_user)):
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    total_words = len(req.text.split())
    sentences = req.text.split(".")
    avg_sentence_length = total_words / len(sentences) if sentences else 0

    if total_words < 300:
        difficulty = DifficultyAnalysis(level="basic", reason="Short passage with simple structure")
    elif avg_sentence_length > 20:
        difficulty = DifficultyAnalysis(level="advanced", reason="Long sentences and complex structure")
    else:
        difficulty = DifficultyAnalysis(level="intermediate", reason="Balanced passage length and sentence structure")

    synonym_count = 0
    for word in req.text.split():
        lowercase_word = word.strip().rstrip(".,;:?!").lower()
        if lowercase_word in synonym_dict:
            synonym_count += 1

    key_topics = ["general"]

    return PassageAnalysisResponse(
        difficulty=difficulty,
        synonym_count=synonym_count,
        long_sentence_count=sum(1 for s in sentences if len(s.split()) > 20),
        key_topics=key_topics,
    )


@router.post("/long-sentences", response_model=List[LongSentenceAnalysis])
async def analyze_long_sentences(req: PassageAnalysisRequest, current_user: dict = Depends(get_current_user)):
    if not req.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    sentences = [s.strip() for s in req.text.split(".") if s.strip()]
    long_sentences = [s for s in sentences if len(s.split()) > 20]
    results = []
    for sentence in long_sentences:
        words = sentence.split()
        structure = {
            "total_words": len(words),
            "clause_count": 1,
            "has_conjunction": any(w.lower() in ["and", "but", "because", "although"] for w in words),
        }
        if structure["has_conjunction"]:
            simplified = sentence.split("because")[0].split("although")[0].split("but")[0].strip() + "."
        else:
            simplified = sentence

        explanation = f"这是一个较长的句子，包含 {structure['total_words']} 个单词。"
        if structure["has_conjunction"]:
            explanation += " 它包含连词，建议拆分为多个短句理解。"

        results.append(
            LongSentenceAnalysis(
                sentence=sentence[:50] + "..." if len(sentence) > 50 else sentence,
                original=sentence,
                structure=structure,
                simplified=simplified,
                explanation=explanation,
            )
        )
    return results


@router.get("/common-synonyms")
async def get_common_synonyms(category: str = "general", current_user: dict = Depends(get_current_user)):
    if category != "general":
        return {"category": category, "synonyms": []}
    return {
        "category": category,
        "synonyms": [{"word": word, "synonyms": synonyms} for word, synonyms in synonym_dict.items()],
    }

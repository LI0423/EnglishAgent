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


class AudioFile(BaseModel):
    id: str
    title: str
    duration: float
    url: str
    transcript: Optional[str] = None
    difficulty: str = "intermediate"


class PlaybackStatus(BaseModel):
    audio_id: Optional[str] = None
    is_playing: bool = False
    current_time: float = 0.0
    speed: float = 1.0
    volume: float = 1.0
    total_duration: float = 0.0


class PlaybackControlRequest(BaseModel):
    audio_id: Optional[str] = None
    current_time: Optional[float] = None


class SpeedControlRequest(BaseModel):
    speed: float


class LibraryVersionResponse(BaseModel):
    version: str
    source: str
    count: int


class ListeningQuizQuestion(BaseModel):
    id: str
    audio_id: str
    prompt: str
    options: Optional[List[str]] = None
    question_type: str
    difficulty: str


class ListeningQuizGenerateRequest(BaseModel):
    count: int = 5
    difficulty: Optional[str] = None
    audio_id: Optional[str] = None


class ListeningQuizGenerateResponse(BaseModel):
    quiz_id: str
    questions: List[ListeningQuizQuestion]


class ListeningQuizAnswer(BaseModel):
    question_id: str
    answer: str


class ListeningQuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: List[ListeningQuizAnswer]


class ListeningQuizSubmitResponse(BaseModel):
    total: int
    correct: int
    accuracy: float
    details: List[Dict[str, Any]]


DEFAULT_AUDIO_LIBRARY = {
    "audio_001": {
        "id": "audio_001",
        "title": "IELTS Listening Practice Test 1 - Section 1",
        "duration": 600.0,
        "url": "http://example.com/audio001.mp3",
        "transcript": "This is a sample transcript...",
        "difficulty": "easy",
    },
    "audio_002": {
        "id": "audio_002",
        "title": "IELTS Listening Practice Test 1 - Section 2",
        "duration": 720.0,
        "url": "http://example.com/audio002.mp3",
        "transcript": "Another sample transcript...",
        "difficulty": "intermediate",
    },
    "audio_003": {
        "id": "audio_003",
        "title": "IELTS Listening Practice Test 2 - Section 3",
        "duration": 840.0,
        "url": "http://example.com/audio003.mp3",
        "transcript": "Advanced sample transcript...",
        "difficulty": "advanced",
    },
}

DEFAULT_LISTENING_QUESTION_BANK = [
    {
        "id": "lst_q_001",
        "audio_id": "audio_001",
        "prompt": "In Section 1, where will the student meet the tutor?",
        "answer": "library",
        "options": ["library", "cafeteria", "office", "hall"],
        "question_type": "multiple_choice",
        "difficulty": "easy",
        "explanation": "The location mentioned in the conversation is library.",
    },
    {
        "id": "lst_q_002",
        "audio_id": "audio_001",
        "prompt": "What time does the lecture start?",
        "answer": "9",
        "options": ["8", "9", "10", "11"],
        "question_type": "multiple_choice",
        "difficulty": "easy",
        "explanation": "The correct start time is 9.",
    },
    {
        "id": "lst_q_003",
        "audio_id": "audio_002",
        "prompt": "Which problem does the speaker mention first?",
        "answer": "budget",
        "options": ["schedule", "budget", "venue", "staff"],
        "question_type": "multiple_choice",
        "difficulty": "intermediate",
        "explanation": "Budget pressure is the first issue raised.",
    },
    {
        "id": "lst_q_004",
        "audio_id": "audio_003",
        "prompt": "The speaker's tone is best described as ____.",
        "answer": "cautiously optimistic",
        "options": ["frustrated", "neutral", "cautiously optimistic", "sarcastic"],
        "question_type": "multiple_choice",
        "difficulty": "advanced",
        "explanation": "The speaker is positive but still cautious.",
    },
]


player_states: Dict[str, Dict[str, Any]] = {}
AUDIO_QUIZ_RUNTIME: Dict[str, Dict[str, Any]] = {}
AUDIO_LIBRARY: Dict[str, Dict[str, Any]] = {}
AUDIO_LIBRARY_VERSION = "builtin-fallback"
LISTENING_QUESTION_BANK: List[Dict[str, Any]] = []
LISTENING_QUESTION_BANK_VERSION = "builtin-fallback"


def _library_path() -> str:
    return os.environ.get(
        "LISTENING_AUDIO_LIBRARY_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "listening_audio_library.v1.json",
        ),
    )


def _question_bank_path() -> str:
    return os.environ.get(
        "LISTENING_QUESTION_BANK_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "listening_question_bank.v1.json",
        ),
    )


def _load_audio_library() -> None:
    global AUDIO_LIBRARY, AUDIO_LIBRARY_VERSION
    path = _library_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        version = str(payload.get("version") or "unknown")
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("invalid files")

        loaded: Dict[str, Dict[str, Any]] = {}
        for item in files:
            if not isinstance(item, dict):
                continue
            audio_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip()
            duration = float(item.get("duration") or 0.0)
            url = str(item.get("url") or "").strip()
            if not audio_id or not title or duration <= 0 or not url:
                continue
            loaded[audio_id] = {
                "id": audio_id,
                "title": title,
                "duration": duration,
                "url": url,
                "transcript": item.get("transcript"),
                "difficulty": str(item.get("difficulty") or "intermediate"),
            }
        if not loaded:
            raise ValueError("empty loaded files")
        AUDIO_LIBRARY = loaded
        AUDIO_LIBRARY_VERSION = version
    except Exception:
        AUDIO_LIBRARY = DEFAULT_AUDIO_LIBRARY
        AUDIO_LIBRARY_VERSION = "builtin-fallback"


def _load_listening_question_bank() -> None:
    global LISTENING_QUESTION_BANK, LISTENING_QUESTION_BANK_VERSION
    path = _question_bank_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        version = str(payload.get("version") or "unknown")
        questions = payload.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("invalid questions")

        loaded: List[Dict[str, Any]] = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            question_id = str(q.get("id") or "").strip()
            audio_id = str(q.get("audio_id") or "").strip()
            prompt = str(q.get("prompt") or "").strip()
            answer = str(q.get("answer") or "").strip()
            if not question_id or not audio_id or not prompt or not answer:
                continue
            loaded.append(
                {
                    "id": question_id,
                    "audio_id": audio_id,
                    "prompt": prompt,
                    "answer": answer,
                    "options": q.get("options"),
                    "question_type": str(q.get("question_type") or "multiple_choice"),
                    "difficulty": str(q.get("difficulty") or "intermediate"),
                    "explanation": str(q.get("explanation") or ""),
                }
            )
        if not loaded:
            raise ValueError("empty loaded questions")
        LISTENING_QUESTION_BANK = loaded
        LISTENING_QUESTION_BANK_VERSION = version
    except Exception:
        LISTENING_QUESTION_BANK = DEFAULT_LISTENING_QUESTION_BANK
        LISTENING_QUESTION_BANK_VERSION = "builtin-fallback"


_load_audio_library()
_load_listening_question_bank()


@router.get("/library", response_model=List[AudioFile])
async def get_audio_library(current_user: dict = Depends(get_current_user)):
    return [AudioFile(**audio) for audio in AUDIO_LIBRARY.values()]


@router.get("/library/version", response_model=LibraryVersionResponse)
async def get_audio_library_version(current_user: dict = Depends(get_current_user)):
    source = "file" if AUDIO_LIBRARY_VERSION != "builtin-fallback" else "builtin"
    return LibraryVersionResponse(version=AUDIO_LIBRARY_VERSION, source=source, count=len(AUDIO_LIBRARY))


@router.get("/quiz/version", response_model=LibraryVersionResponse)
async def get_listening_quiz_version(current_user: dict = Depends(get_current_user)):
    source = "file" if LISTENING_QUESTION_BANK_VERSION != "builtin-fallback" else "builtin"
    return LibraryVersionResponse(
        version=LISTENING_QUESTION_BANK_VERSION,
        source=source,
        count=len(LISTENING_QUESTION_BANK),
    )


@router.post("/quiz/generate", response_model=ListeningQuizGenerateResponse)
async def generate_listening_quiz(
    payload: ListeningQuizGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    count = max(1, min(int(payload.count or 5), 20))
    difficulty = (payload.difficulty or "").strip().lower()
    audio_id = (payload.audio_id or "").strip()

    pool = LISTENING_QUESTION_BANK
    if difficulty:
        pool = [q for q in pool if str(q.get("difficulty") or "").lower() == difficulty]
    if audio_id:
        pool = [q for q in pool if str(q.get("audio_id") or "") == audio_id]
    if not pool:
        raise HTTPException(status_code=400, detail="No quiz questions found for given filters")

    selected = pool[:] if len(pool) <= count else random.sample(pool, count)
    runtime_questions = []
    public_questions = []
    for q in selected:
        qid = str(uuid4())
        runtime_questions.append(
            {
                "id": qid,
                "audio_id": q.get("audio_id"),
                "prompt": q.get("prompt"),
                "options": q.get("options"),
                "question_type": q.get("question_type"),
                "difficulty": q.get("difficulty"),
                "_answer": q.get("answer"),
                "_explanation": q.get("explanation"),
            }
        )
        public_questions.append(
            ListeningQuizQuestion(
                id=qid,
                audio_id=str(q.get("audio_id") or ""),
                prompt=str(q.get("prompt") or ""),
                options=q.get("options"),
                question_type=str(q.get("question_type") or "multiple_choice"),
                difficulty=str(q.get("difficulty") or "intermediate"),
            )
        )

    quiz_id = str(uuid4())
    AUDIO_QUIZ_RUNTIME[quiz_id] = {
        "user_id": str(current_user["id"]),
        "questions": runtime_questions,
        "created_at": int(time.time()),
    }
    return ListeningQuizGenerateResponse(quiz_id=quiz_id, questions=public_questions)


@router.post("/quiz/submit", response_model=ListeningQuizSubmitResponse)
async def submit_listening_quiz(
    payload: ListeningQuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    runtime = AUDIO_QUIZ_RUNTIME.get(payload.quiz_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Listening quiz not found")
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
                    "module": "listening",
                    "question_id": qid,
                    "question_type": "listening_quiz",
                    "error_type": "listening_incorrect",
                    "content": str(q.get("prompt") or ""),
                    "user_answer": user_answer,
                    "correct_answer": str(q.get("_answer") or ""),
                    "explanation": str(q.get("_explanation") or "Listening quiz incorrect answer."),
                    "difficulty": str(q.get("difficulty") or "medium"),
                    "tags": ["listening_quiz", str(q.get("question_type") or "unknown")],
                },
            )
        details.append(
            {
                "question_id": qid,
                "audio_id": q.get("audio_id"),
                "is_correct": is_correct,
                "expected_answer": q.get("_answer"),
                "user_answer": answer_map.get(qid, ""),
            }
        )

    total = len(runtime.get("questions", []))
    accuracy = round((correct / total), 4) if total else 0.0
    return ListeningQuizSubmitResponse(total=total, correct=correct, accuracy=accuracy, details=details)


@router.get("/file/{audio_id}", response_model=AudioFile)
async def get_audio_file(audio_id: str, current_user: dict = Depends(get_current_user)):
    if audio_id not in AUDIO_LIBRARY:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return AudioFile(**AUDIO_LIBRARY[audio_id])


@router.post("/start", response_model=PlaybackStatus)
async def start_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if not req.audio_id:
        raise HTTPException(status_code=400, detail="Audio ID required")
    if req.audio_id not in AUDIO_LIBRARY:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_info = AUDIO_LIBRARY[req.audio_id]
    player_states[user_id] = {
        "audio_id": req.audio_id,
        "is_playing": True,
        "current_time": req.current_time or 0.0,
        "speed": 1.0,
        "volume": 1.0,
        "total_duration": audio_info["duration"],
    }
    return PlaybackStatus(**player_states[user_id])


@router.post("/pause", response_model=PlaybackStatus)
async def pause_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        raise HTTPException(status_code=400, detail="No active playback")

    player_states[user_id]["is_playing"] = False
    if req.current_time is not None:
        player_states[user_id]["current_time"] = req.current_time
    return PlaybackStatus(**player_states[user_id])


@router.post("/resume", response_model=PlaybackStatus)
async def resume_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        raise HTTPException(status_code=400, detail="No playback to resume")

    player_states[user_id]["is_playing"] = True
    if req.current_time is not None:
        player_states[user_id]["current_time"] = req.current_time
    return PlaybackStatus(**player_states[user_id])


@router.post("/stop", response_model=PlaybackStatus)
async def stop_playback(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        raise HTTPException(status_code=400, detail="No active playback")

    player_states[user_id] = {
        "audio_id": None,
        "is_playing": False,
        "current_time": 0.0,
        "speed": 1.0,
        "volume": 1.0,
        "total_duration": 0.0,
    }
    return PlaybackStatus(**player_states[user_id])


@router.post("/set-speed", response_model=PlaybackStatus)
async def set_speed(req: SpeedControlRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        raise HTTPException(status_code=400, detail="No active playback")
    if not (0.5 <= req.speed <= 2.0):
        raise HTTPException(status_code=400, detail="Speed must be between 0.5x and 2.0x")

    player_states[user_id]["speed"] = req.speed
    return PlaybackStatus(**player_states[user_id])


@router.post("/set-position", response_model=PlaybackStatus)
async def set_position(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        raise HTTPException(status_code=400, detail="No active playback")
    if req.current_time is None:
        raise HTTPException(status_code=400, detail="Current time required")

    player_states[user_id]["current_time"] = req.current_time
    return PlaybackStatus(**player_states[user_id])


@router.get("/status", response_model=PlaybackStatus)
async def get_playback_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id not in player_states:
        return PlaybackStatus()
    return PlaybackStatus(**player_states[user_id])


@router.get("/segment/{audio_id}")
async def get_audio_segment(
    audio_id: str,
    start_time: float = 0.0,
    end_time: float = 30.0,
    current_user: dict = Depends(get_current_user),
):
    if audio_id not in AUDIO_LIBRARY:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_info = AUDIO_LIBRARY[audio_id]
    return {
        "audio_id": audio_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration": min(end_time - start_time, audio_info["duration"] - start_time),
        "url": f"{audio_info['url']}?start={start_time}&end={end_time}",
        "transcript": audio_info["transcript"][:100] if audio_info["transcript"] else None,
    }

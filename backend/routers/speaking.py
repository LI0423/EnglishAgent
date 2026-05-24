from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import uuid4
import time
import re
from ..deps import get_current_user
from ..db import (
    create_session as db_create_session,
    append_session_transcript,
    finish_session as db_finish_session,
    get_session as db_get_session,
    list_sessions as db_list_sessions,
)
from backend.utils.tracking import get_learning_tracker
from ..services.tts_service import get_tts_service


router = APIRouter()

SPEAKING_PRACTICE_RUNTIME: Dict[str, Dict[str, Any]] = {}
_tts_service = get_tts_service()


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", str(text or "").lower())


def _build_follow_up(part_index: int, user_text: str, turn_index: int) -> str:
    words = _tokenize(user_text)
    short_answer = len(words) < 12
    has_reason = any(w in {"because", "since", "therefore", "so"} for w in words)
    has_example = any(w in {"for", "example", "instance"} for w in words)
    if short_answer:
        return "Can you add one concrete example to support your answer?"
    if not has_reason:
        return "Why do you think so? Please explain your reason clearly."
    if not has_example:
        return "Could you share a specific personal experience related to this?"
    if part_index == 3:
        return "How might this trend change in the next 10 years?"
    if turn_index % 2 == 0:
        return "What challenges might people face in this situation?"
    return "What is the most important point you want the examiner to remember?"


def _build_feedback(user_text: str) -> Dict[str, str]:
    words = _tokenize(user_text)
    word_count = len(words)
    sentence_count = max(1, len(re.findall(r"[.!?]", str(user_text or ""))))
    avg_sentence_len = word_count / sentence_count

    content = "观点基本清晰。"
    if word_count < 10:
        content = "内容偏短，建议补充细节和例子。"
    elif word_count >= 25:
        content = "内容较充分，可进一步突出主观点。"

    language = "表达基本自然。"
    if avg_sentence_len < 7:
        language = "句子偏短，建议增加连接词形成更完整表达。"
    elif avg_sentence_len > 22:
        language = "句子略长，可拆分为更清晰的短句。"

    if re.search(r"\bvery\b", str(user_text or "").lower()):
        language += " 可尝试用 more specific adjectives 替换 very。"

    return {
        "content": content,
        "language": language,
    }


def _extract_review_from_text(transcript_text: str) -> Dict[str, Any]:
    tokens = _tokenize(transcript_text)
    unique = []
    for t in tokens:
        if len(t) >= 6 and t not in unique:
            unique.append(t)
    highlights = unique[:3] if unique else ["communication", "experience", "society"]

    replacements = []
    replacement_map = {
        "very good": "beneficial / valuable",
        "very important": "crucial / significant",
        "i think": "from my perspective",
    }
    lower_text = str(transcript_text or "").lower()
    for old, new in replacement_map.items():
        if old in lower_text:
            replacements.append({"from": old, "to": new})
    if not replacements:
        replacements = [
            {"from": "very good", "to": "beneficial"},
            {"from": "i think", "to": "from my perspective"},
            {"from": "a lot of", "to": "a wide range of"},
        ]

    drills = [
        "每次回答先给观点，再给原因，最后给一个例子（3句结构）。",
        "控制句长在 10-18 词，减少过长句导致的流利度下降。",
        "在回答中主动使用 because / however / for example 提升连贯性。",
    ]

    vocabulary_candidates = [
        {
            "word": w,
            "definition": "Word extracted from your speaking practice for reinforcement.",
            "examples": [f"I can use {w} in a clearer sentence next time."],
        }
        for w in highlights
    ]
    return {
        "highlights": highlights,
        "replacements": replacements,
        "drills": drills,
        "vocabulary_candidates": vocabulary_candidates,
    }


def _target_seconds_for_part(part_index: int, mode: str) -> int:
    if mode == "exam":
        if part_index == 2:
            return 120
        if part_index in {1, 3}:
            return 45
    if part_index == 2:
        return 75
    return 50


def _prep_seconds_for_part(part_index: int, mode: str) -> int:
    if mode == "exam" and part_index == 2:
        return 60
    return 0


def _pacing_feedback(spent_seconds: int, target_seconds: int) -> str:
    if target_seconds <= 0:
        return "本轮无计时目标。"
    if spent_seconds <= 0:
        return "未记录本轮用时，建议开启计时。"
    ratio = spent_seconds / max(target_seconds, 1)
    if ratio < 0.65:
        return "回答偏短，建议补充原因与例子。"
    if ratio > 1.35:
        return "回答偏长，建议先给结论再展开要点。"
    return "节奏合适，继续保持。"


class Part(BaseModel):
    index: int
    type: str  # part1|part2|part3
    prompt: str


class CreateSessionResponse(BaseModel):
    sessionId: str
    topic: str
    parts: List[Part]


class SessionSummary(BaseModel):
    id: str
    topic: Optional[str] = None
    created_at: Optional[int] = None
    transcript_id: Optional[str] = None


@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(limit: int = 20, offset: int = 0, current_user: dict = Depends(get_current_user)):
    rows = db_list_sessions(user_id=str(current_user["id"]), limit=limit, offset=offset)
    return [SessionSummary(id=r.get("id"), topic=r.get("topic"), created_at=r.get("created_at"), transcript_id=r.get("transcript_id")) for r in rows]


class SessionDetail(BaseModel):
    id: str
    topic: Optional[str] = None
    parts: List[Part] = []
    transcript_text: Optional[str] = None
    transcript_id: Optional[str] = None
    created_at: Optional[int] = None


@router.get("/session/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str, current_user: dict = Depends(get_current_user)):
    row = db_get_session(session_id, user_id=str(current_user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    parts = [Part(index=p.get("idx"), type=str(p.get("type")), prompt=str(p.get("prompt"))) for p in row.get("parts", [])]
    return SessionDetail(
        id=row.get("id"),
        topic=row.get("topic"),
        parts=parts,
        transcript_text=row.get("transcript_text"),
        transcript_id=row.get("transcript_id"),
        created_at=row.get("created_at"),
    )


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(current_user: dict = Depends(get_current_user)):
    session_id = str(uuid4())
    parts = [
        Part(index=1, type="part1", prompt="Do you work or study?"),
        Part(index=2, type="part2", prompt="Describe a book you recently read."),
        Part(index=3, type="part3", prompt="How do books influence society?"),
    ]
    db_create_session(session_id, "General", [_model_dump(p) for p in parts], user_id=str(current_user["id"]))
    SPEAKING_PRACTICE_RUNTIME[session_id] = {
        "mode": "coach",
        "part_index": 1,
        "turn_index": 0,
        "history": [],
        "created_at": int(time.time()),
    }

    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "speaking_session_create",
        {"topic": "General", "part_count": len(parts)},
    )
    learning_tracker.track_event(
        current_user["id"],
        "study_session_started",
        {
            "session_id": session_id,
            "module": "speaking",
            "duration": 0,
            "completed": False,
            "score": 0,
            "activities": ["session_started"],
            "metadata": {
                "topic": "General",
                "parts": [p.type for p in parts],
            },
        },
    )
    return CreateSessionResponse(sessionId=session_id, topic="General", parts=parts)


class StartPartResponse(BaseModel):
    ok: bool
    partIndex: int
    prompt: str = ""
    promptAudioUrl: Optional[str] = None
    prepSeconds: int = 0
    targetAnswerSeconds: int = 45
    examClockStartedAt: int = 0


@router.post("/session/{session_id}/part/{part_index}/start", response_model=StartPartResponse)
async def start_part(
    session_id: str,
    part_index: int,
    with_audio: bool = False,
    voice: str = "F1",
    lang: str = "en",
    current_user: dict = Depends(get_current_user),
):
    row = db_get_session(session_id, user_id=str(current_user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if part_index not in {1, 2, 3}:
        raise HTTPException(status_code=400, detail="Invalid part index")

    parts = row.get("parts", [])
    prompt = ""
    for p in parts:
        if int(p.get("idx") or 0) == part_index:
            prompt = str(p.get("prompt") or "")
            break
    state = SPEAKING_PRACTICE_RUNTIME.setdefault(
        session_id,
        {"mode": "coach", "part_index": part_index, "turn_index": 0, "history": [], "created_at": int(time.time())},
    )
    state["part_index"] = part_index
    state["turn_index"] = 0
    mode = str(state.get("mode") or "coach")
    state["part_started_at"] = int(time.time())
    state["part_prep_seconds"] = _prep_seconds_for_part(part_index, mode)
    state["part_target_seconds"] = _target_seconds_for_part(part_index, mode)
    prompt_audio_url = None
    if with_audio and prompt:
        try:
            prompt_audio_url = str(
                _tts_service.synthesize(text=prompt, lang=lang, voice=voice, speed=1.0).get("audio_url") or ""
            )
        except Exception:
            prompt_audio_url = None

    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "speaking_part_start",
        {"session_id": session_id, "part_index": part_index},
    )
    return StartPartResponse(
        ok=True,
        partIndex=part_index,
        prompt=prompt,
        promptAudioUrl=prompt_audio_url,
        prepSeconds=int(state.get("part_prep_seconds") or 0),
        targetAnswerSeconds=int(state.get("part_target_seconds") or 45),
        examClockStartedAt=int(state.get("part_started_at") or 0),
    )


class AudioChunk(BaseModel):
    textPartial: Optional[str] = None
    audioUrl: Optional[str] = None


class AudioIngestResponse(BaseModel):
    asrPartial: Optional[str] = None
    timestamps: Optional[list] = None


@router.post("/session/{session_id}/audio", response_model=AudioIngestResponse)
async def ingest_audio(session_id: str, chunk: AudioChunk, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id, user_id=str(current_user["id"])):
        raise HTTPException(status_code=404, detail="Session not found")
    if chunk.textPartial:
        append_session_transcript(session_id, chunk.textPartial, user_id=str(current_user["id"]))
    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "speaking_audio_ingest",
        {"session_id": session_id, "has_text": bool(chunk.textPartial)},
    )
    return AudioIngestResponse(asrPartial=chunk.textPartial, timestamps=None)


class SpeakingTurnRequest(BaseModel):
    userText: str
    mode: str = "coach"  # coach|exam
    partIndex: Optional[int] = None
    spentSeconds: Optional[int] = None
    withAudio: bool = False
    voice: str = "F1"
    lang: str = "en"


class SpeakingTurnResponse(BaseModel):
    ok: bool
    mode: str
    partIndex: int
    turnIndex: int
    examinerPrompt: str
    followUpQuestion: str
    shouldMoveNextPart: bool
    feedback: Dict[str, str]
    spentSeconds: int = 0
    targetSeconds: int = 45
    pacingFeedback: str = ""
    examinerPromptAudioUrl: Optional[str] = None
    followUpAudioUrl: Optional[str] = None


@router.post("/session/{session_id}/turn", response_model=SpeakingTurnResponse)
async def submit_turn(session_id: str, payload: SpeakingTurnRequest, current_user: dict = Depends(get_current_user)):
    row = db_get_session(session_id, user_id=str(current_user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    text = str(payload.userText or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="userText is required")

    mode = "exam" if str(payload.mode or "").lower() == "exam" else "coach"
    state = SPEAKING_PRACTICE_RUNTIME.setdefault(
        session_id,
        {"mode": mode, "part_index": 1, "turn_index": 0, "history": [], "created_at": int(time.time())},
    )
    state["mode"] = mode
    if payload.partIndex in {1, 2, 3}:
        state["part_index"] = int(payload.partIndex)
    part_index = int(state.get("part_index") or 1)

    parts = row.get("parts", [])
    examiner_prompt = ""
    for p in parts:
        if int(p.get("idx") or 0) == part_index:
            examiner_prompt = str(p.get("prompt") or "")
            break
    if not examiner_prompt:
        examiner_prompt = "Please continue with your answer."

    state["turn_index"] = int(state.get("turn_index") or 0) + 1
    turn_index = int(state["turn_index"])
    target_seconds = _target_seconds_for_part(part_index, mode)
    spent_seconds = int(payload.spentSeconds or 0)
    if spent_seconds <= 0:
        part_started_at = int(state.get("part_started_at") or int(time.time()))
        spent_seconds = max(1, int(time.time()) - part_started_at)

    append_session_transcript(
        session_id,
        f"[P{part_index}-T{turn_index}] {text}",
        user_id=str(current_user["id"]),
    )

    follow_up = _build_follow_up(part_index=part_index, user_text=text, turn_index=turn_index)
    feedback = _build_feedback(text)
    if mode == "exam":
        max_turn = 1 if part_index == 2 else 2
    else:
        max_turn = 3
    should_move = turn_index >= max_turn
    pacing_feedback = _pacing_feedback(spent_seconds, target_seconds)
    examiner_prompt_audio_url = None
    follow_up_audio_url = None
    if bool(payload.withAudio):
        try:
            examiner_prompt_audio_url = str(
                _tts_service.synthesize(
                    text=examiner_prompt,
                    lang=payload.lang,
                    voice=payload.voice,
                    speed=1.0,
                ).get("audio_url")
                or ""
            )
            follow_up_audio_url = str(
                _tts_service.synthesize(
                    text=follow_up,
                    lang=payload.lang,
                    voice=payload.voice,
                    speed=1.0,
                ).get("audio_url")
                or ""
            )
        except Exception:
            examiner_prompt_audio_url = None
            follow_up_audio_url = None

    state["history"].append(
        {
            "part_index": part_index,
            "turn_index": turn_index,
            "user_text": text,
            "word_count": len(_tokenize(text)),
            "spent_seconds": spent_seconds,
            "target_seconds": target_seconds,
            "on_time": spent_seconds <= int(target_seconds * 1.2),
            "follow_up": follow_up,
            "feedback": feedback,
            "pacing_feedback": pacing_feedback,
            "timestamp": int(time.time()),
        }
    )

    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "speaking_turn_submit",
        {"session_id": session_id, "part_index": part_index, "turn_index": turn_index, "mode": mode},
    )
    return SpeakingTurnResponse(
        ok=True,
        mode=mode,
        partIndex=part_index,
        turnIndex=turn_index,
        examinerPrompt=examiner_prompt,
        followUpQuestion=follow_up,
        shouldMoveNextPart=should_move,
        feedback=feedback,
        spentSeconds=spent_seconds,
        targetSeconds=target_seconds,
        pacingFeedback=pacing_feedback,
        examinerPromptAudioUrl=examiner_prompt_audio_url,
        followUpAudioUrl=follow_up_audio_url,
    )


class SpeakingSummaryResponse(BaseModel):
    sessionId: str
    mode: str
    highlights: List[str]
    replacements: List[Dict[str, str]]
    drills: List[str]
    vocabularyCandidates: List[Dict[str, Any]]
    transcriptWordCount: int
    partStats: List[Dict[str, Any]] = []
    timingSummary: Dict[str, Any] = {}
    bandHints: Dict[str, float] = {}


@router.post("/session/{session_id}/summary", response_model=SpeakingSummaryResponse)
async def summarize_session(session_id: str, current_user: dict = Depends(get_current_user)):
    row = db_get_session(session_id, user_id=str(current_user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    transcript_text = str(row.get("transcript_text") or "").strip()
    extracted = _extract_review_from_text(transcript_text)
    runtime = SPEAKING_PRACTICE_RUNTIME.get(session_id, {})
    mode = str(runtime.get("mode") or "coach")
    history = list(runtime.get("history") or [])

    part_stats: List[Dict[str, Any]] = []
    total_spent = 0
    on_time_turns = 0
    for pidx in [1, 2, 3]:
        rows = [x for x in history if int(x.get("part_index") or 0) == pidx]
        if not rows:
            continue
        turns = len(rows)
        spent = sum(int(x.get("spent_seconds") or 0) for x in rows)
        words = sum(int(x.get("word_count") or 0) for x in rows)
        on_time = sum(1 for x in rows if bool(x.get("on_time")))
        target = int(rows[0].get("target_seconds") or _target_seconds_for_part(pidx, mode))
        total_spent += spent
        on_time_turns += on_time
        part_stats.append(
            {
                "part_index": pidx,
                "turns": turns,
                "avg_words": round(words / max(turns, 1), 1),
                "avg_spent_seconds": round(spent / max(turns, 1), 1),
                "target_seconds": target,
                "on_time_rate": round(on_time / max(turns, 1), 3),
            }
        )

    timing_summary = {
        "total_spent_seconds": total_spent,
        "total_turns": len(history),
        "on_time_turns": on_time_turns,
        "late_turns": max(len(history) - on_time_turns, 0),
    }
    transcript_words = len(_tokenize(transcript_text))
    band_hints = {
        "fc_hint": round(5.0 + min(2.0, transcript_words / 180.0), 2),
        "lr_hint": round(5.0 + min(2.0, len(set(_tokenize(transcript_text))) / 120.0), 2),
        "gr_hint": round(5.0 + (0.8 if transcript_words >= 120 else 0.2), 2),
        "pr_hint": round(5.5 + (0.5 if on_time_turns >= max(1, len(history) // 2) else 0.0), 2),
    }
    return SpeakingSummaryResponse(
        sessionId=session_id,
        mode=mode,
        highlights=[str(x) for x in extracted["highlights"]],
        replacements=[{"from": str(x.get("from") or ""), "to": str(x.get("to") or "")} for x in extracted["replacements"]],
        drills=[str(x) for x in extracted["drills"]],
        vocabularyCandidates=list(extracted["vocabulary_candidates"]),
        transcriptWordCount=transcript_words,
        partStats=part_stats,
        timingSummary=timing_summary,
        bandHints=band_hints,
    )


class FinishResponse(BaseModel):
    transcriptId: str


@router.post("/session/{session_id}/finish", response_model=FinishResponse)
async def finish_session(session_id: str, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id, user_id=str(current_user["id"])):
        raise HTTPException(status_code=404, detail="Session not found")
    transcript_id = str(uuid4())
    db_finish_session(session_id, transcript_id, user_id=str(current_user["id"]))

    learning_tracker = get_learning_tracker()
    learning_tracker.track_study_session(
        current_user["id"],
        {
            "session_id": session_id,
            "module": "speaking",
            "duration": 0,
            "completed": True,
            "score": 0,
            "activities": ["session_completed"],
            "metadata": {
                "transcript_id": transcript_id,
                "practice_turns": len(SPEAKING_PRACTICE_RUNTIME.get(session_id, {}).get("history", [])),
                "mode": SPEAKING_PRACTICE_RUNTIME.get(session_id, {}).get("mode", "coach"),
            },
        },
    )
    learning_tracker.track_feature_usage(
        current_user["id"],
        "speaking_session_finish",
        {"session_id": session_id, "transcript_id": transcript_id},
    )
    return FinishResponse(transcriptId=transcript_id)

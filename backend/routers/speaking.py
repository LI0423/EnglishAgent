from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
import time
from ..state import store, Session as Sess, Part as SessPart
from ..deps import get_current_user
from ..db import create_session as db_create_session, append_session_transcript, finish_session as db_finish_session, get_session as db_get_session
from ..db import list_sessions as db_list_sessions
from backend.utils.tracking import get_learning_tracker


router = APIRouter()

def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

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
        id=row.get("id"), topic=row.get("topic"), parts=parts,
        transcript_text=row.get("transcript_text"), transcript_id=row.get("transcript_id"), created_at=row.get("created_at")
    )


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(current_user: dict = Depends(get_current_user)):
    session_id = str(uuid4())
    parts = [
        Part(index=1, type="part1", prompt="Do you work or study?"),
        Part(index=2, type="part2", prompt="Describe a book you recently read."),
        Part(index=3, type="part3", prompt="How do books influence society?")
    ]
    # persist to DB
    db_create_session(session_id, "General", [_model_dump(p) for p in parts], user_id=str(current_user["id"]))
    
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪会话创建
    learning_tracker.track_feature_usage(
        current_user['id'], 
        "speaking_session_create",
        {"topic": "General", "part_count": len(parts)}
    )
    
    # 跟踪学习会话开始
    session_data = {
        "session_id": session_id,
        "module": "speaking",
        "duration": 0,
        "completed": False,
        "score": 0,
        "activities": ["session_started"],
        "metadata": {
            "topic": "General",
            "parts": [p.type for p in parts]
        }
    }
    learning_tracker.track_event(current_user['id'], "study_session_started", session_data)
    
    return CreateSessionResponse(sessionId=session_id, topic="General", parts=parts)


class StartPartResponse(BaseModel):
    ok: bool
    partIndex: int


@router.post("/session/{session_id}/part/{part_index}/start", response_model=StartPartResponse)
async def start_part(session_id: str, part_index: int, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id, user_id=str(current_user["id"])):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user['id'], 
        "speaking_part_start",
        {"session_id": session_id, "part_index": part_index}
    )
    
    return StartPartResponse(ok=True, partIndex=part_index)


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
    
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪音频上传
    learning_tracker.track_feature_usage(
        current_user['id'], 
        "speaking_audio_ingest",
        {"session_id": session_id, "has_text": bool(chunk.textPartial)}
    )
    
    return AudioIngestResponse(asrPartial=chunk.textPartial, timestamps=None)


class FinishResponse(BaseModel):
    transcriptId: str


@router.post("/session/{session_id}/finish", response_model=FinishResponse)
async def finish_session(session_id: str, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id, user_id=str(current_user["id"])):
        raise HTTPException(status_code=404, detail="Session not found")
    transcript_id = str(uuid4())
    db_finish_session(session_id, transcript_id, user_id=str(current_user["id"]))
    
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪会话完成
    session_data = {
        "session_id": session_id,
        "module": "speaking",
        "duration": 0,  # 后续可添加时间统计
        "completed": True,
        "score": 0,  # 后续可添加评分
        "activities": ["session_completed"],
        "metadata": {
            "transcript_id": transcript_id
        }
    }
    learning_tracker.track_study_session(current_user['id'], session_data)
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user['id'], 
        "speaking_session_finish",
        {"session_id": session_id, "transcript_id": transcript_id}
    )
    
    return FinishResponse(transcriptId=transcript_id)

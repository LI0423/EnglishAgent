from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from ..state import store, Session as Sess, Part as SessPart
from ..deps import get_current_user
from ..db import create_session as db_create_session, append_session_transcript, finish_session as db_finish_session, get_session as db_get_session
from ..db import list_sessions as db_list_sessions


router = APIRouter()

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
    topic: str | None = None
    created_at: int | None = None
    transcript_id: str | None = None


@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(limit: int = 20, offset: int = 0, current_user: dict = Depends(get_current_user)):
    rows = db_list_sessions(limit=limit, offset=offset)
    return [SessionSummary(id=r.get("id"), topic=r.get("topic"), created_at=r.get("created_at"), transcript_id=r.get("transcript_id")) for r in rows]


class SessionDetail(BaseModel):
    id: str
    topic: str | None = None
    parts: List[Part] = []
    transcript_text: str | None = None
    transcript_id: str | None = None
    created_at: int | None = None


@router.get("/session/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str, current_user: dict = Depends(get_current_user)):
    row = db_get_session(session_id)
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
    db_create_session(session_id, "General", [p.dict() for p in parts])
    return CreateSessionResponse(sessionId=session_id, topic="General", parts=parts)


class StartPartResponse(BaseModel):
    ok: bool
    partIndex: int


@router.post("/session/{session_id}/part/{part_index}/start", response_model=StartPartResponse)
async def start_part(session_id: str, part_index: int, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return StartPartResponse(ok=True, partIndex=part_index)


class AudioChunk(BaseModel):
    textPartial: Optional[str] = None
    audioUrl: Optional[str] = None


class AudioIngestResponse(BaseModel):
    asrPartial: Optional[str] = None
    timestamps: Optional[list] = None


@router.post("/session/{session_id}/audio", response_model=AudioIngestResponse)
async def ingest_audio(session_id: str, chunk: AudioChunk, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    if chunk.textPartial:
        append_session_transcript(session_id, chunk.textPartial)
    return AudioIngestResponse(asrPartial=chunk.textPartial, timestamps=None)


class FinishResponse(BaseModel):
    transcriptId: str


@router.post("/session/{session_id}/finish", response_model=FinishResponse)
async def finish_session(session_id: str, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    transcript_id = str(uuid4())
    db_finish_session(session_id, transcript_id)
    return FinishResponse(transcriptId=transcript_id)



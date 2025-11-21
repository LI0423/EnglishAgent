from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from ..db import get_conn

router = APIRouter(prefix="/history", tags=["history"])

class Session(BaseModel):
    id: str
    topic: Optional[str]
    type: str
    date: datetime
    score: float
    status: str
    duration: int
    accuracy: float

@router.get("/sessions", response_model=List[Session])
def get_recent_sessions(limit: int = 10):
    conn = get_conn()
    try:
        cur = conn.execute("""
            SELECT s.id, s.topic, s.type, s.status, s.duration, s.accuracy, s.created_at, sc.overall as score
            FROM sessions s
            LEFT JOIN scores sc ON s.id = sc.session_id
            ORDER BY s.created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        
        sessions = []
        for row in rows:
            session_dict = dict(row)
            
            # Convert created_at (Unix timestamp) to datetime with timezone
            session_dict["date"] = datetime.fromtimestamp(session_dict["created_at"], timezone.utc)
            
            # Ensure score is a float, defaulting to 0.0 if null
            session_dict["score"] = float(session_dict["score"]) if session_dict["score"] is not None else 0.0
            
            # Append to sessions list
            sessions.append(Session(**session_dict))
        
        return sessions
    finally:
        conn.close()
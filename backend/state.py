from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Part:
    index: int
    type: str
    prompt: str


@dataclass
class Session:
    session_id: str
    topic: str
    parts: List[Part]
    transcript_text: str = ""
    transcript_id: Optional[str] = None


@dataclass
class Transcript:
    transcript_id: str
    session_id: str
    text: str


@dataclass
class Score:
    FC: float
    LR: float
    GR: float
    PR: float
    overall: float


class InMemoryStore:
    def __init__(self) -> None:
        self.sessions: Dict[str, Session] = {}
        self.transcripts: Dict[str, Transcript] = {}
        self.session_to_transcript: Dict[str, str] = {}
        self.session_scores: Dict[str, Score] = {}


store = InMemoryStore()



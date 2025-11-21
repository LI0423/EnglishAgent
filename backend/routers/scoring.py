from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from ..state import store, Score as StoredScore
from ..deps import get_current_user
from ..db import get_transcript, save_score


router = APIRouter()


class ScoringRequest(BaseModel):
    transcriptId: str
    audioUrl: Optional[str] = None
    meta: Optional[dict] = None


class Score(BaseModel):
    FC: float  # Fluency & Coherence
    LR: float  # Lexical Resource
    GR: float  # Grammatical Range & Accuracy
    PR: float  # Pronunciation


class Highlight(BaseModel):
    start: float
    end: float
    note: str


class ActionItem(BaseModel):
    type: str
    before: str
    after: str
    examples: List[str] = []
    practiceLink: Optional[str] = None


class ScoringResponse(BaseModel):
    scores: Score
    overall: float
    rationales: List[str]
    actionItems: List[ActionItem]
    highlights: List[Highlight]


@router.post("/speaking", response_model=ScoringResponse)
async def score_speaking(req: ScoringRequest, current_user: dict = Depends(get_current_user)):
    # Validate transcript exists
    tr = get_transcript(req.transcriptId)
    if not tr:
        raise HTTPException(status_code=404, detail="Transcript not found")
    # Simple heuristic scoring based on length
    text = tr.get("text") or ""
    num_words = len(text.split()) if text else 0
    base = 5.5
    bonus = min(num_words / 80.0, 1.5)  # up to +1.5 for longer answers
    fc = round(base + bonus, 1)
    lr = round(base + min(num_words / 120.0, 1.0), 1)
    gr = round(base + 0.3, 1)
    pr = round(base + 0.5, 1)
    scores = Score(FC=fc, LR=lr, GR=gr, PR=pr)
    overall = round((scores.FC + scores.LR + scores.GR + scores.PR) / 4, 1)
    # persist score by session
    session_id = tr.get("session_id")
    save_score(str(session_id), scores.FC, scores.LR, scores.GR, scores.PR, overall)
    return ScoringResponse(
        scores=scores,
        overall=overall,
        rationales=["Good fluency with occasional hesitation.", "Vocabulary is adequate but could be more varied."],
        actionItems=[
            ActionItem(type="lexical", before="very good", after="excellent/outstanding", examples=["an outstanding example"]),
            ActionItem(type="cohesion", before="and then", after="moreover/furthermore", examples=["Furthermore, this suggests..."])
        ],
        highlights=[Highlight(start=12.3, end=18.7, note="Long pause and fillers")] 
    )



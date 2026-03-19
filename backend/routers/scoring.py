from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from ..deps import get_current_user
from ..db import get_transcript_for_user, save_mistake, save_score
from agent_core import speaking_agent


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
    tr = get_transcript_for_user(req.transcriptId, str(current_user["id"]))
    if not tr:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Get transcript text
    text = tr.get("text") or ""
    if not text:
        raise HTTPException(status_code=400, detail="Transcript text is empty")
    
    # Use AI agent for scoring
    evaluation = speaking_agent.evaluate_speaking(text, req.audioUrl)
    
    # Create response model
    scores = Score(
        FC=evaluation["scores"]["FC"],
        LR=evaluation["scores"]["LR"],
        GR=evaluation["scores"]["GR"],
        PR=evaluation["scores"]["PR"]
    )
    
    # Convert action items to response model
    action_items = []
    for item in evaluation["actionItems"]:
        action_items.append(ActionItem(
            type=item["type"],
            before=item["before"],
            after=item["after"],
            examples=item["examples"]
        ))
    
    # Convert highlights to response model
    highlights = []
    for highlight in evaluation["highlights"]:
        highlights.append(Highlight(
            start=highlight["start"],
            end=highlight["end"],
            note=highlight["note"]
        ))
    
    # Persist score by session
    session_id = tr.get("session_id")
    save_score(str(session_id), scores.FC, scores.LR, scores.GR, scores.PR, evaluation["overall"])

    # 低分维度自动沉淀到错题本，进入复习链路
    score_map = {"FC": scores.FC, "LR": scores.LR, "GR": scores.GR, "PR": scores.PR}
    for dim, value in score_map.items():
        if float(value) < 6.5:
            save_mistake(
                str(uuid4()),
                str(current_user["id"]),
                {
                    "module": "speaking",
                    "question_id": str(session_id),
                    "question_type": "speaking_assessment",
                    "error_type": f"low_{dim.lower()}",
                    "content": f"Speaking assessment dimension {dim} below target.",
                    "user_answer": str(value),
                    "correct_answer": ">=6.5",
                    "explanation": f"{dim} score is {value}. Review action items and practice drills.",
                    "difficulty": "intermediate",
                    "tags": ["speaking_assessment", dim],
                },
            )

    return ScoringResponse(
        scores=scores,
        overall=evaluation["overall"],
        rationales=evaluation["rationales"],
        actionItems=action_items,
        highlights=highlights
    )


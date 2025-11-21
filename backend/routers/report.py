from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from ..state import store
from ..deps import get_current_user
from ..db import get_session as db_get_session, get_score as db_get_score


router = APIRouter()


class Report(BaseModel):
    summary: str
    scores: dict
    suggestions: List[str]
    plan7d: dict


@router.get("/{session_id}", response_model=Report)
async def get_report(session_id: str, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    score = db_get_score(session_id)
    scores = {"FC": score.get('FC'), "LR": score.get('LR'), "GR": score.get('GR'), "PR": score.get('PR'), "overall": score.get('overall')} if score else {}
    # basic suggestions based on missing score
    suggestions: List[str] = []
    if not score:
        suggestions.append("No score yet. Finish session and request scoring.")
    else:
        if score.FC < 6.5:
            suggestions.append("Increase fluency by reducing pauses; practice 2-min monologues.")
        if score.LR < 6.5:
            suggestions.append("Expand topic-specific vocabulary and use varied synonyms.")
        if score.GR < 6.5:
            suggestions.append("Use more complex sentences and check subject-verb agreement.")
        if score.PR < 6.5:
            suggestions.append("Practice stress and intonation; shadow native materials.")

    plan7d = {
        "day1": ["fluency drill: 5-min monologue"],
        "day2": ["linking words practice"],
        "day3": ["topic vocab pack: education"],
        "day4": ["pronunciation: stress & intonation"],
        "day5": ["grammar range: complex sentences"],
        "day6": ["mock part2"],
        "day7": ["mock part3 + review"],
    }
    return Report(
        summary=f"Report for session {session_id}",
        scores=scores,
        suggestions=suggestions or ["Good job! Keep practicing."],
        plan7d=plan7d,
    )



from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import get_current_user
from backend.services.ability_service import get_difficulty_recommendation


router = APIRouter()


class DifficultyRecommendationResponse(BaseModel):
    module: str
    recommended_difficulty: str
    label: str
    reason: str
    confidence: float
    sample_count: int
    average_score: Optional[float] = None
    trend: str
    source: str


@router.get("/recommendation", response_model=DifficultyRecommendationResponse)
async def recommendation(module: str = "translation", current_user: dict = Depends(get_current_user)):
    return get_difficulty_recommendation(str(current_user["id"]), module=module)

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import get_current_user
from backend.services.ability_service import get_difficulty_recommendation
from backend.services.growth_recommendation_service import get_growth_recommendations


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


class GrowthRecommendationItem(BaseModel):
    id: str
    module: str
    module_label: str
    title: str
    description: str
    reason: str
    priority: int
    route: str
    practice_mode: str
    recommended_difficulty: str
    difficulty_label: str
    confidence: float


@router.get("/recommendation", response_model=DifficultyRecommendationResponse)
def recommendation(module: str = "translation", current_user: dict = Depends(get_current_user)):
    return get_difficulty_recommendation(str(current_user["id"]), module=module)


@router.get("/growth/recommendations", response_model=List[GrowthRecommendationItem])
def growth_recommendations(limit: int = 5, current_user: dict = Depends(get_current_user)):
    return get_growth_recommendations(str(current_user["id"]), limit=limit)

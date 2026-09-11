from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import get_current_user
from backend.services.dashboard_service import complete_smart_learning_task, get_checkin_calendar, get_dashboard_overview
from backend.services.learning_event_service import get_growth_insights, get_today_learning_plan


router = APIRouter()


class SmartTaskCompleteRequest(BaseModel):
    task_id: str


@router.get("/overview")
def overview(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    return get_dashboard_overview(
        user_id=str(current_user["id"]),
        username=str(current_user.get("username") or ""),
    )


@router.get("/checkin-calendar")
async def checkin_calendar(
    month: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    return get_checkin_calendar(user_id=str(current_user["id"]), month=month)


@router.get("/today-learning-plan")
async def today_learning_plan(
    limit: int = 6,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    return get_today_learning_plan(user_id=str(current_user["id"]), limit=limit)


@router.get("/growth-insights")
async def growth_insights(
    limit: int = 8,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    return get_growth_insights(user_id=str(current_user["id"]), limit=limit)


@router.post("/today-learning-plan/complete")
async def complete_today_learning_task(
    payload: SmartTaskCompleteRequest,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    return complete_smart_learning_task(
        user_id=str(current_user["id"]),
        task_id=str(payload.task_id or ""),
    )

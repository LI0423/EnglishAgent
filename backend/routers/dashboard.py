from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from backend.services.dashboard_service import get_checkin_calendar, get_dashboard_overview


router = APIRouter()


@router.get("/overview")
async def overview(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
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

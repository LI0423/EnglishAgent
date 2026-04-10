from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from ..state import store
from ..deps import get_current_user
from ..db import (
    get_session as db_get_session,
    get_score as db_get_score,
    get_plan_execution_health,
    get_plan_intervention_status,
    get_plan_calibration_logs,
    get_learning_plan,
    get_latest_user_plan,
)


router = APIRouter()


class Report(BaseModel):
    summary: str
    scores: dict
    suggestions: List[str]
    plan7d: dict


class PlanHealthReport(BaseModel):
    plan_id: str
    days: int
    health_level: str
    streak_days: int
    task_completion_rate: float
    day_completion_rate: float
    task_done: int
    task_total: int
    scheduled_days: int
    completed_days: int
    daily_minutes: int
    focus_modules: List[str]
    daily_trend: List[dict]
    module_stats: List[dict]


class PlanCalibrationLogItem(BaseModel):
    id: str
    plan_id: str
    source: str
    before_daily_minutes: Optional[int] = None
    after_daily_minutes: Optional[int] = None
    before_focus_modules: List[str] = []
    after_focus_modules: List[str] = []
    note: str = ""
    created_at: int


class PlanInterventionStatusReport(BaseModel):
    plan_id: str
    days: int
    intervention_total: int
    intervention_done: int
    intervention_completion_rate: float
    latest_batch_id: str
    latest_batch_created_at: int
    batch_count: int
    daily_trend: List[dict]
    module_stats: List[dict]


@router.get("/plan/health", response_model=PlanHealthReport)
async def get_current_plan_health(
    plan_id: Optional[str] = None,
    days: int = 14,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    target_plan = get_learning_plan(plan_id) if plan_id else get_latest_user_plan(user_id)
    if not target_plan:
        return PlanHealthReport(
            plan_id="",
            days=max(1, min(90, int(days))),
            health_level="unknown",
            streak_days=0,
            task_completion_rate=0.0,
            day_completion_rate=0.0,
            task_done=0,
            task_total=0,
            scheduled_days=0,
            completed_days=0,
            daily_minutes=0,
            focus_modules=[],
            daily_trend=[],
            module_stats=[],
        )
    if str(target_plan.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    health = get_plan_execution_health(str(target_plan["id"]), days=days)
    return PlanHealthReport(
        plan_id=str(target_plan["id"]),
        days=int(health.get("days") or days),
        health_level=str(health.get("health_level") or "unknown"),
        streak_days=int(health.get("streak_days") or 0),
        task_completion_rate=float(health.get("task_completion_rate") or 0.0),
        day_completion_rate=float(health.get("day_completion_rate") or 0.0),
        task_done=int(health.get("task_done") or 0),
        task_total=int(health.get("task_total") or 0),
        scheduled_days=int(health.get("scheduled_days") or 0),
        completed_days=int(health.get("completed_days") or 0),
        daily_minutes=int(target_plan.get("daily_minutes") or 0),
        focus_modules=[str(x) for x in (target_plan.get("focus_modules") or [])],
        daily_trend=list(health.get("daily_trend") or []),
        module_stats=list(health.get("module_stats") or []),
    )


@router.get("/plan/calibrations", response_model=List[PlanCalibrationLogItem])
async def get_current_plan_calibrations(
    plan_id: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    target_plan = get_learning_plan(plan_id) if plan_id else get_latest_user_plan(user_id)
    if not target_plan:
        return []
    if str(target_plan.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    logs = get_plan_calibration_logs(str(target_plan["id"]), limit=max(1, min(100, int(limit))))
    return [
        PlanCalibrationLogItem(
            id=str(x.get("id")),
            plan_id=str(x.get("plan_id")),
            source=str(x.get("source") or "manual"),
            before_daily_minutes=x.get("before_daily_minutes"),
            after_daily_minutes=x.get("after_daily_minutes"),
            before_focus_modules=[str(v) for v in (x.get("before_focus_modules") or [])],
            after_focus_modules=[str(v) for v in (x.get("after_focus_modules") or [])],
            note=str(x.get("note") or ""),
            created_at=int(x.get("created_at") or 0),
        )
        for x in logs
    ]


@router.get("/plan/intervention-status", response_model=PlanInterventionStatusReport)
async def get_current_plan_intervention_status(
    plan_id: Optional[str] = None,
    days: int = 14,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    target_plan = get_learning_plan(plan_id) if plan_id else get_latest_user_plan(user_id)
    if not target_plan:
        return PlanInterventionStatusReport(
            plan_id="",
            days=max(1, min(90, int(days))),
            intervention_total=0,
            intervention_done=0,
            intervention_completion_rate=0.0,
            latest_batch_id="",
            latest_batch_created_at=0,
            batch_count=0,
            daily_trend=[],
            module_stats=[],
        )
    if str(target_plan.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    status = get_plan_intervention_status(str(target_plan["id"]), days=days)
    return PlanInterventionStatusReport(
        plan_id=str(target_plan["id"]),
        days=int(status.get("days") or days),
        intervention_total=int(status.get("intervention_total") or 0),
        intervention_done=int(status.get("intervention_done") or 0),
        intervention_completion_rate=float(status.get("intervention_completion_rate") or 0.0),
        latest_batch_id=str(status.get("latest_batch_id") or ""),
        latest_batch_created_at=int(status.get("latest_batch_created_at") or 0),
        batch_count=int(status.get("batch_count") or 0),
        daily_trend=list(status.get("daily_trend") or []),
        module_stats=list(status.get("module_stats") or []),
    )


@router.get("/{session_id}", response_model=Report)
async def get_report(session_id: str, current_user: dict = Depends(get_current_user)):
    if not db_get_session(session_id, user_id=str(current_user["id"])):
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

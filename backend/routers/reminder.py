from datetime import datetime, timedelta, time as dtime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import uuid
from ..deps import get_current_user
from ..db import (
    create_reminder,
    create_reminder_audit_log,
    create_reminder_preference_history,
    get_reminder,
    get_reminder_preference_history_by_id,
    get_user_reminder_preference_history,
    get_user_reminder_analytics,
    get_user_reminder_audit_logs,
    get_user_reminders,
    update_reminder_status,
    delete_reminder,
    get_reminder_preferences,
    set_reminder_preferences,
    get_learning_plan,
    get_daily_tasks_by_plan,
    get_plan_execution_health,
    get_plan_intervention_status,
    has_recent_reminder,
)


router = APIRouter()


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


class ReminderCreate(BaseModel):
    type: str = "task"
    title: str
    content: str
    scheduled_at: int
    channel: str = "app"
    metadata: Dict[str, Any] = {}


class Reminder(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    content: str
    scheduled_at: int
    sent_at: Optional[int] = None
    status: str
    channel: str
    metadata: Dict[str, Any]
    created_at: int


class ReminderStatusUpdate(BaseModel):
    status: str


class ReminderBatchStatusUpdateRequest(BaseModel):
    reminder_ids: List[str]
    status: str


class ReminderBatchStatusUpdateResponse(BaseModel):
    total: int
    updated: int
    skipped: int
    failed: int
    updated_ids: List[str]
    skipped_ids: List[str]
    failed_ids: List[str]


class ReminderBatchDeleteRequest(BaseModel):
    reminder_ids: List[str]


class ReminderBatchDeleteResponse(BaseModel):
    total: int
    deleted: int
    skipped: int
    failed: int
    deleted_ids: List[str]
    skipped_ids: List[str]
    failed_ids: List[str]


class QuietHours(BaseModel):
    start: str
    end: str


class ReminderPreferences(BaseModel):
    enabled: bool = True
    channels: List[str] = ["app"]
    preferred_times: List[str] = []
    quiet_hours: Optional[QuietHours] = None
    strategy_config: Dict[str, Any] = {}


class ReminderPreferencesResponse(BaseModel):
    user_id: str
    enabled: bool
    channels: List[str]
    preferred_times: List[str]
    quiet_hours: Optional[QuietHours] = None
    strategy_config: Dict[str, Any] = {}
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class ReminderPreferencePresetItem(BaseModel):
    key: str
    name: str
    description: str
    config: ReminderPreferences


class ReminderPreferencePresetApplyRequest(BaseModel):
    preset_key: str


class ReminderPreferenceRollbackRequest(BaseModel):
    history_id: str


class ReminderPreferenceHistoryItem(BaseModel):
    id: str
    source: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    meta: Dict[str, Any] = {}
    created_at: int


class PlanReminderSuggestionItem(BaseModel):
    source: str
    title: str
    content: str
    scheduled_at: int
    priority: str = "medium"
    channel: str = "app"
    metadata: Dict[str, Any] = {}


class PlanReminderSuggestionResponse(BaseModel):
    plan_id: str
    days: int
    health_level: str
    pending_today_count: int
    overdue_count: int
    intervention_pending_count: int
    recommended_count: int
    items: List[PlanReminderSuggestionItem]


class PlanReminderApplyRequest(BaseModel):
    plan_id: str
    days: int = 14
    selected_sources: Optional[List[str]] = None
    preferred_channel: str = "app"
    dedupe_lookback_hours: int = 12


class PlanReminderApplyResponse(BaseModel):
    plan_id: str
    days: int
    created: int
    skipped: int
    reminder_ids: List[str]
    skipped_sources: List[str]


class ReminderAnalyticsBucket(BaseModel):
    key: str
    count: int


class ReminderTrendPoint(BaseModel):
    day: str
    created: int
    sent: int
    failed: int
    merged: int


class ReminderAnalyticsResponse(BaseModel):
    days: int
    total: int
    status_counts: List[ReminderAnalyticsBucket]
    type_counts: List[ReminderAnalyticsBucket]
    source_counts: List[ReminderAnalyticsBucket]
    trend: List[ReminderTrendPoint]


class ReminderAuditLogItem(BaseModel):
    id: str
    reminder_id: str
    action: str
    detail: Dict[str, Any] = {}
    created_at: int


def _write_audit(user_id: str, reminder_id: str, action: str, detail: Optional[Dict[str, Any]] = None):
    create_reminder_audit_log(
        str(uuid.uuid4()),
        user_id=str(user_id),
        reminder_id=str(reminder_id),
        action=str(action),
        detail=dict(detail or {}),
    )


REMINDER_PREFERENCE_PRESETS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "name": "平衡学习",
        "description": "常规提醒，兼顾节奏与打扰控制。",
        "config": {
            "enabled": True,
            "channels": ["app"],
            "preferred_times": ["09:00", "20:30"],
            "quiet_hours": {"start": "23:00", "end": "07:00"},
            "strategy_config": {
                "frequency_window_hours": 3,
                "max_reminders_per_window": 2,
                "preferred_tolerance_minutes": 90,
                "merge_similar_enabled": True,
                "high_priority_bypass_cap": False,
            },
        },
    },
    "high_focus": {
        "name": "冲刺高频",
        "description": "高强度备考，允许更高提醒频率。",
        "config": {
            "enabled": True,
            "channels": ["app"],
            "preferred_times": ["08:00", "12:30", "18:30", "21:30"],
            "quiet_hours": {"start": "00:00", "end": "06:30"},
            "strategy_config": {
                "frequency_window_hours": 2,
                "max_reminders_per_window": 3,
                "preferred_tolerance_minutes": 60,
                "merge_similar_enabled": False,
                "high_priority_bypass_cap": True,
            },
        },
    },
    "gentle": {
        "name": "低打扰恢复",
        "description": "减少提醒密度，更适合恢复期学习。",
        "config": {
            "enabled": True,
            "channels": ["app"],
            "preferred_times": ["10:00", "21:00"],
            "quiet_hours": {"start": "22:30", "end": "08:00"},
            "strategy_config": {
                "frequency_window_hours": 6,
                "max_reminders_per_window": 1,
                "preferred_tolerance_minutes": 120,
                "merge_similar_enabled": True,
                "high_priority_bypass_cap": False,
            },
        },
    },
}


def _default_preferences_snapshot(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": str(user_id),
        "enabled": True,
        "channels": ["app"],
        "preferred_times": [],
        "quiet_hours": {},
        "strategy_config": {},
    }


def _normalize_preferences_snapshot(user_id: str, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = dict(raw or _default_preferences_snapshot(user_id))
    return {
        "user_id": str(user_id),
        "enabled": bool(data.get("enabled", True)),
        "channels": list(data.get("channels") or ["app"]),
        "preferred_times": list(data.get("preferred_times") or []),
        "quiet_hours": dict(data.get("quiet_hours") or {}),
        "strategy_config": dict(data.get("strategy_config") or {}),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _response_from_preferences_snapshot(snapshot: Dict[str, Any]) -> ReminderPreferencesResponse:
    quiet_hours = None
    if snapshot.get("quiet_hours"):
        quiet_hours = QuietHours(**snapshot["quiet_hours"])
    return ReminderPreferencesResponse(
        user_id=str(snapshot.get("user_id") or ""),
        enabled=bool(snapshot.get("enabled", True)),
        channels=list(snapshot.get("channels") or ["app"]),
        preferred_times=list(snapshot.get("preferred_times") or []),
        quiet_hours=quiet_hours,
        strategy_config=dict(snapshot.get("strategy_config") or {}),
        created_at=snapshot.get("created_at"),
        updated_at=snapshot.get("updated_at"),
    )


@router.post("/", response_model=Reminder)
async def create_reminder_endpoint(
    reminder_data: ReminderCreate,
    current_user: dict = Depends(get_current_user)
):
    """创建新的提醒"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 生成提醒ID
    reminder_id = str(uuid.uuid4())
    
    # 创建提醒数据
    reminder_info = {
        "type": reminder_data.type,
        "title": reminder_data.title,
        "content": reminder_data.content,
        "scheduled_at": reminder_data.scheduled_at,
        "channel": reminder_data.channel,
        "metadata": reminder_data.metadata,
        "status": "pending"
    }
    
    create_reminder(reminder_id, user_id, reminder_info)
    _write_audit(
        user_id=str(user_id),
        reminder_id=reminder_id,
        action="create",
        detail={"type": reminder_data.type, "channel": reminder_data.channel},
    )
    
    # 获取创建的提醒
    created_reminder = get_reminder(reminder_id)
    if not created_reminder:
        raise HTTPException(status_code=500, detail="Failed to create reminder")
    
    return Reminder(
        id=created_reminder["id"],
        user_id=created_reminder["user_id"],
        type=created_reminder["type"],
        title=created_reminder["title"],
        content=created_reminder["content"],
        scheduled_at=created_reminder["scheduled_at"],
        sent_at=created_reminder["sent_at"],
        status=created_reminder["status"],
        channel=created_reminder["channel"],
        metadata=created_reminder["metadata"],
        created_at=created_reminder["created_at"]
    )


def _next_scheduled_at(preferences: Optional[Dict[str, Any]], now_ts: Optional[int] = None) -> int:
    now = int(now_ts or time.time())
    preferred_times = list((preferences or {}).get("preferred_times") or [])
    if not preferred_times:
        return now + 5 * 60

    now_dt = datetime.fromtimestamp(now)
    candidates: List[int] = []
    for entry in preferred_times[:6]:
        try:
            hour_str, minute_str = str(entry).split(":")
            hour = max(0, min(23, int(hour_str)))
            minute = max(0, min(59, int(minute_str)))
            target = datetime.combine(now_dt.date(), dtime(hour=hour, minute=minute))
            if target.timestamp() <= now:
                target = target + timedelta(days=1)
            candidates.append(int(target.timestamp()))
        except Exception:
            continue
    if not candidates:
        return now + 5 * 60
    return min(candidates)


def _build_plan_reminder_suggestions(
    *,
    plan_id: str,
    user_id: str,
    days: int,
    channel: str,
    now_ts: Optional[int] = None,
) -> PlanReminderSuggestionResponse:
    safe_days = max(3, min(30, int(days or 14)))
    now = int(now_ts or time.time())
    start_of_today_ts = int(datetime.combine(datetime.now().date(), dtime.min).timestamp())

    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if str(plan.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    health = get_plan_execution_health(plan_id, days=safe_days)
    intervention = get_plan_intervention_status(plan_id, days=safe_days)
    rows = get_daily_tasks_by_plan(plan_id)

    pending_today_count = 0
    overdue_count = 0
    intervention_pending_count = 0
    for daily in rows:
        daily_ts = int(daily.get("date") or 0)
        tasks = list(daily.get("tasks") or [])
        for task in tasks:
            if bool(task.get("completed")):
                continue
            if daily_ts < start_of_today_ts:
                overdue_count += 1
            elif daily_ts == start_of_today_ts:
                pending_today_count += 1
            if str(task.get("kind") or "") == "intervention" and daily_ts <= start_of_today_ts + 2 * 86400:
                intervention_pending_count += 1

    preferences = get_reminder_preferences(user_id)
    scheduled_at = _next_scheduled_at(preferences, now_ts=now)
    health_level = str(health.get("health_level") or "unknown")
    items: List[PlanReminderSuggestionItem] = []

    source_prefix = f"plan:{plan_id}"
    if overdue_count > 0:
        items.append(
            PlanReminderSuggestionItem(
                source=f"{source_prefix}:overdue_backlog",
                title="计划逾期任务提醒",
                content=f"你有 {overdue_count} 个计划任务已逾期，建议先完成最早的 1-2 项。",
                scheduled_at=scheduled_at,
                priority="high",
                channel=channel,
                metadata={
                    "source": f"{source_prefix}:overdue_backlog",
                    "plan_id": plan_id,
                    "overdue_count": overdue_count,
                },
            )
        )
    if pending_today_count > 0:
        items.append(
            PlanReminderSuggestionItem(
                source=f"{source_prefix}:today_pending",
                title="今日计划待办提醒",
                content=f"今日还有 {pending_today_count} 个计划任务未完成，建议按模块优先级逐个完成。",
                scheduled_at=scheduled_at,
                priority="medium",
                channel=channel,
                metadata={
                    "source": f"{source_prefix}:today_pending",
                    "plan_id": plan_id,
                    "pending_today_count": pending_today_count,
                },
            )
        )
    if intervention_pending_count > 0:
        items.append(
            PlanReminderSuggestionItem(
                source=f"{source_prefix}:intervention_followup",
                title="干预任务跟进提醒",
                content=f"你有 {intervention_pending_count} 个干预任务待处理，建议先完成补救任务再做常规任务。",
                scheduled_at=scheduled_at,
                priority="high",
                channel=channel,
                metadata={
                    "source": f"{source_prefix}:intervention_followup",
                    "plan_id": plan_id,
                    "intervention_pending_count": intervention_pending_count,
                },
            )
        )
    if health_level in {"watch", "at_risk"}:
        minute_hint = int(plan.get("daily_minutes") or 90)
        items.append(
            PlanReminderSuggestionItem(
                source=f"{source_prefix}:health_guard",
                title="学习节奏校准提醒",
                content=(
                    f"当前计划健康等级为 {health_level}，建议今天优先完成核心任务，"
                    f"并检查每日目标时长（当前 {minute_hint} 分钟）。"
                ),
                scheduled_at=scheduled_at,
                priority="medium" if health_level == "watch" else "high",
                channel=channel,
                metadata={
                    "source": f"{source_prefix}:health_guard",
                    "plan_id": plan_id,
                    "health_level": health_level,
                    "task_completion_rate": float(health.get("task_completion_rate") or 0.0),
                    "intervention_completion_rate": float(intervention.get("intervention_completion_rate") or 0.0),
                },
            )
        )

    return PlanReminderSuggestionResponse(
        plan_id=plan_id,
        days=safe_days,
        health_level=health_level,
        pending_today_count=pending_today_count,
        overdue_count=overdue_count,
        intervention_pending_count=intervention_pending_count,
        recommended_count=len(items),
        items=items,
    )


@router.get("/plan/suggestions", response_model=PlanReminderSuggestionResponse)
async def get_plan_reminder_suggestions(
    plan_id: str,
    days: int = 14,
    preferred_channel: str = "app",
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    channel = str(preferred_channel or "app").strip().lower() or "app"
    if channel not in {"app", "email", "sms"}:
        channel = "app"
    return _build_plan_reminder_suggestions(
        plan_id=plan_id,
        user_id=user_id,
        days=days,
        channel=channel,
    )


@router.post("/plan/apply", response_model=PlanReminderApplyResponse)
async def apply_plan_reminders(
    payload: PlanReminderApplyRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    suggestions = _build_plan_reminder_suggestions(
        plan_id=str(payload.plan_id),
        user_id=user_id,
        days=int(payload.days or 14),
        channel=str(payload.preferred_channel or "app").strip().lower() or "app",
    )
    selected_sources = set(str(x) for x in (payload.selected_sources or []))
    source_whitelist = selected_sources if selected_sources else None
    lookback_seconds = max(1, int(payload.dedupe_lookback_hours or 12)) * 3600

    created = 0
    skipped = 0
    reminder_ids: List[str] = []
    skipped_sources: List[str] = []
    for item in suggestions.items:
        if source_whitelist is not None and item.source not in source_whitelist:
            skipped += 1
            skipped_sources.append(item.source)
            continue
        if has_recent_reminder(user_id, "plan_execution", item.source, lookback_seconds=lookback_seconds):
            skipped += 1
            skipped_sources.append(item.source)
            continue

        reminder_id = str(uuid.uuid4())
        create_reminder(
            reminder_id,
            user_id,
            {
                "type": "plan_execution",
                "title": item.title,
                "content": item.content,
                "scheduled_at": int(item.scheduled_at),
                "status": "pending",
                "channel": item.channel,
                "metadata": dict(item.metadata or {"source": item.source, "plan_id": payload.plan_id}),
            },
        )
        _write_audit(
            user_id=user_id,
            reminder_id=reminder_id,
            action="plan_apply_create",
            detail={"plan_id": payload.plan_id, "source": item.source},
        )
        created += 1
        reminder_ids.append(reminder_id)

    return PlanReminderApplyResponse(
        plan_id=str(payload.plan_id),
        days=max(3, min(30, int(payload.days or 14))),
        created=created,
        skipped=skipped,
        reminder_ids=reminder_ids,
        skipped_sources=skipped_sources,
    )


@router.get("/", response_model=List[Reminder])
async def get_reminders(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """获取用户的提醒列表"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    reminders = get_user_reminders(user_id, status)
    return [
        Reminder(
            id=reminder["id"],
            user_id=reminder["user_id"],
            type=reminder["type"],
            title=reminder["title"],
            content=reminder["content"],
            scheduled_at=reminder["scheduled_at"],
            sent_at=reminder["sent_at"],
            status=reminder["status"],
            channel=reminder["channel"],
            metadata=reminder["metadata"],
            created_at=reminder["created_at"]
        )
        for reminder in reminders
    ]


@router.post("/batch/status", response_model=ReminderBatchStatusUpdateResponse)
async def batch_update_status(
    payload: ReminderBatchStatusUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    reminder_ids = [str(x).strip() for x in (payload.reminder_ids or []) if str(x).strip()]
    if not reminder_ids:
        raise HTTPException(status_code=400, detail="reminder_ids不能为空")

    updated_ids: List[str] = []
    skipped_ids: List[str] = []
    failed_ids: List[str] = []

    for reminder_id in reminder_ids:
        try:
            reminder = get_reminder(reminder_id)
            if not reminder or str(reminder.get("user_id")) != user_id:
                skipped_ids.append(reminder_id)
                continue
            sent_at = int(time.time()) if payload.status == "sent" else None
            update_reminder_status(reminder_id, payload.status, sent_at)
            _write_audit(
                user_id=user_id,
                reminder_id=reminder_id,
                action="batch_status_update",
                detail={"from": reminder.get("status"), "to": payload.status},
            )
            updated_ids.append(reminder_id)
        except Exception:
            failed_ids.append(reminder_id)

    return ReminderBatchStatusUpdateResponse(
        total=len(reminder_ids),
        updated=len(updated_ids),
        skipped=len(skipped_ids),
        failed=len(failed_ids),
        updated_ids=updated_ids,
        skipped_ids=skipped_ids,
        failed_ids=failed_ids,
    )


@router.post("/batch/delete", response_model=ReminderBatchDeleteResponse)
async def batch_delete_reminders(
    payload: ReminderBatchDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    reminder_ids = [str(x).strip() for x in (payload.reminder_ids or []) if str(x).strip()]
    if not reminder_ids:
        raise HTTPException(status_code=400, detail="reminder_ids不能为空")

    deleted_ids: List[str] = []
    skipped_ids: List[str] = []
    failed_ids: List[str] = []

    for reminder_id in reminder_ids:
        try:
            reminder = get_reminder(reminder_id)
            if not reminder or str(reminder.get("user_id")) != user_id:
                skipped_ids.append(reminder_id)
                continue
            _write_audit(
                user_id=user_id,
                reminder_id=reminder_id,
                action="batch_delete",
                detail={"status": reminder.get("status"), "source": (reminder.get("metadata") or {}).get("source")},
            )
            delete_reminder(reminder_id)
            deleted_ids.append(reminder_id)
        except Exception:
            failed_ids.append(reminder_id)

    return ReminderBatchDeleteResponse(
        total=len(reminder_ids),
        deleted=len(deleted_ids),
        skipped=len(skipped_ids),
        failed=len(failed_ids),
        deleted_ids=deleted_ids,
        skipped_ids=skipped_ids,
        failed_ids=failed_ids,
    )


@router.get("/analytics/summary", response_model=ReminderAnalyticsResponse)
async def get_reminder_analytics_summary(
    days: int = 14,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    data = get_user_reminder_analytics(user_id, days=max(1, min(90, int(days))))
    return ReminderAnalyticsResponse(
        days=int(data.get("days") or days),
        total=int(data.get("total") or 0),
        status_counts=[
            ReminderAnalyticsBucket(key=str(x.get("status") or ""), count=int(x.get("count") or 0))
            for x in list(data.get("status_counts") or [])
        ],
        type_counts=[
            ReminderAnalyticsBucket(key=str(x.get("type") or ""), count=int(x.get("count") or 0))
            for x in list(data.get("type_counts") or [])
        ],
        source_counts=[
            ReminderAnalyticsBucket(key=str(x.get("source") or ""), count=int(x.get("count") or 0))
            for x in list(data.get("source_counts") or [])
        ],
        trend=[
            ReminderTrendPoint(
                day=str(x.get("day") or ""),
                created=int(x.get("created") or 0),
                sent=int(x.get("sent") or 0),
                failed=int(x.get("failed") or 0),
                merged=int(x.get("merged") or 0),
            )
            for x in list(data.get("trend") or [])
        ],
    )


@router.get("/audit/logs", response_model=List[ReminderAuditLogItem])
async def get_reminder_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    rows = get_user_reminder_audit_logs(
        user_id,
        limit=max(1, min(500, int(limit))),
        action=action.strip() if isinstance(action, str) and action.strip() else None,
    )
    return [
        ReminderAuditLogItem(
            id=str(x.get("id") or ""),
            reminder_id=str(x.get("reminder_id") or ""),
            action=str(x.get("action") or ""),
            detail=dict(x.get("detail") or {}),
            created_at=int(x.get("created_at") or 0),
        )
        for x in rows
    ]


@router.get("/{reminder_id}", response_model=Reminder)
async def get_reminder_endpoint(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取提醒详情"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    reminder = get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    # 验证提醒属于当前用户
    if reminder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return Reminder(
        id=reminder["id"],
        user_id=reminder["user_id"],
        type=reminder["type"],
        title=reminder["title"],
        content=reminder["content"],
        scheduled_at=reminder["scheduled_at"],
        sent_at=reminder["sent_at"],
        status=reminder["status"],
        channel=reminder["channel"],
        metadata=reminder["metadata"],
        created_at=reminder["created_at"]
    )


@router.put("/{reminder_id}/status")
async def update_status(
    reminder_id: str,
    status_update: ReminderStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新提醒状态"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证提醒存在且属于当前用户
    reminder = get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if reminder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # 如果状态变为已发送，记录发送时间
    sent_at = int(time.time()) if status_update.status == "sent" else None
    update_reminder_status(reminder_id, status_update.status, sent_at)
    _write_audit(
        user_id=str(user_id),
        reminder_id=str(reminder_id),
        action="status_update",
        detail={"from": reminder.get("status"), "to": status_update.status},
    )
    
    return {"message": "Reminder status updated successfully", "status": status_update.status}


@router.delete("/{reminder_id}")
async def delete_reminder_endpoint(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除提醒"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证提醒存在且属于当前用户
    reminder = get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if reminder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    _write_audit(
        user_id=str(user_id),
        reminder_id=str(reminder_id),
        action="delete",
        detail={"status": reminder.get("status"), "source": (reminder.get("metadata") or {}).get("source")},
    )
    delete_reminder(reminder_id)
    return {"message": "Reminder deleted successfully"}


@router.get("/preferences/me", response_model=ReminderPreferencesResponse)
async def get_preferences(
    current_user: dict = Depends(get_current_user)
):
    """获取当前用户的提醒偏好设置"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))
    return _response_from_preferences_snapshot(snapshot)


@router.get("/preferences/presets", response_model=List[ReminderPreferencePresetItem])
async def get_preference_presets(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    rows: List[ReminderPreferencePresetItem] = []
    for key, item in REMINDER_PREFERENCE_PRESETS.items():
        rows.append(
            ReminderPreferencePresetItem(
                key=key,
                name=str(item.get("name") or key),
                description=str(item.get("description") or ""),
                config=ReminderPreferences(**dict(item.get("config") or {})),
            )
        )
    return rows


@router.get("/preferences/history", response_model=List[ReminderPreferenceHistoryItem])
async def get_preferences_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    rows = get_user_reminder_preference_history(str(user_id), limit=max(1, min(100, int(limit))))
    return [
        ReminderPreferenceHistoryItem(
            id=str(item.get("id") or ""),
            source=str(item.get("source") or ""),
            before=dict(item.get("before_config") or {}),
            after=dict(item.get("after_config") or {}),
            meta=dict(item.get("meta") or {}),
            created_at=int(item.get("created_at") or 0),
        )
        for item in rows
    ]


@router.put("/preferences/me", response_model=ReminderPreferencesResponse)
async def update_preferences(
    preferences: ReminderPreferences,
    current_user: dict = Depends(get_current_user)
):
    """更新当前用户的提醒偏好设置"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    user_id = str(user_id)
    before_snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))

    # 构建偏好设置数据
    preferences_data = {
        "enabled": 1 if preferences.enabled else 0,
        "channels": preferences.channels,
        "preferred_times": preferences.preferred_times,
        "quiet_hours": _model_dump(preferences.quiet_hours) if preferences.quiet_hours else {},
        "strategy_config": dict(preferences.strategy_config or {}),
    }
    
    set_reminder_preferences(user_id, preferences_data)

    # 获取更新后的偏好设置
    updated_preferences = get_reminder_preferences(user_id)
    if not updated_preferences:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    after_snapshot = _normalize_preferences_snapshot(user_id, updated_preferences)
    create_reminder_preference_history(
        str(uuid.uuid4()),
        user_id=user_id,
        source="manual_update",
        before_config=before_snapshot,
        after_config=after_snapshot,
        meta={"changed_by": "user"},
    )
    _write_audit(
        user_id=user_id,
        reminder_id="preferences",
        action="preference_update",
        detail={
            "source": "manual_update",
            "enabled": bool(after_snapshot.get("enabled")),
            "channels": list(after_snapshot.get("channels") or []),
        },
    )
    return _response_from_preferences_snapshot(after_snapshot)


@router.post("/preferences/apply-preset", response_model=ReminderPreferencesResponse)
async def apply_preference_preset(
    payload: ReminderPreferencePresetApplyRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    preset_key = str(payload.preset_key or "").strip()
    preset = REMINDER_PREFERENCE_PRESETS.get(preset_key)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    before_snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))
    preset_config = dict(preset.get("config") or {})
    set_reminder_preferences(
        user_id,
        {
            "enabled": 1 if bool(preset_config.get("enabled", True)) else 0,
            "channels": list(preset_config.get("channels") or ["app"]),
            "preferred_times": list(preset_config.get("preferred_times") or []),
            "quiet_hours": dict(preset_config.get("quiet_hours") or {}),
            "strategy_config": dict(preset_config.get("strategy_config") or {}),
        },
    )
    after_snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))
    create_reminder_preference_history(
        str(uuid.uuid4()),
        user_id=user_id,
        source=f"preset:{preset_key}",
        before_config=before_snapshot,
        after_config=after_snapshot,
        meta={"preset_key": preset_key, "preset_name": str(preset.get("name") or preset_key)},
    )
    _write_audit(
        user_id=user_id,
        reminder_id="preferences",
        action="preference_preset_apply",
        detail={"preset_key": preset_key},
    )
    return _response_from_preferences_snapshot(after_snapshot)


@router.post("/preferences/rollback", response_model=ReminderPreferencesResponse)
async def rollback_preferences(
    payload: ReminderPreferenceRollbackRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    history_id = str(payload.history_id or "").strip()
    if not history_id:
        raise HTTPException(status_code=400, detail="history_id不能为空")
    history = get_reminder_preference_history_by_id(history_id, user_id=user_id)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    before_snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))
    target_snapshot = _normalize_preferences_snapshot(user_id, dict(history.get("before_config") or {}))
    set_reminder_preferences(
        user_id,
        {
            "enabled": 1 if bool(target_snapshot.get("enabled", True)) else 0,
            "channels": list(target_snapshot.get("channels") or ["app"]),
            "preferred_times": list(target_snapshot.get("preferred_times") or []),
            "quiet_hours": dict(target_snapshot.get("quiet_hours") or {}),
            "strategy_config": dict(target_snapshot.get("strategy_config") or {}),
        },
    )
    after_snapshot = _normalize_preferences_snapshot(user_id, get_reminder_preferences(user_id))
    create_reminder_preference_history(
        str(uuid.uuid4()),
        user_id=user_id,
        source="rollback",
        before_config=before_snapshot,
        after_config=after_snapshot,
        meta={"history_id": history_id, "rollback_source": str(history.get("source") or "")},
    )
    _write_audit(
        user_id=user_id,
        reminder_id="preferences",
        action="preference_rollback",
        detail={"history_id": history_id},
    )
    return _response_from_preferences_snapshot(after_snapshot)

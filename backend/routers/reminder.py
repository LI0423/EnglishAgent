from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import uuid
from ..deps import get_current_user
from ..db import (
    create_reminder,
    get_reminder,
    get_user_reminders,
    update_reminder_status,
    delete_reminder,
    get_reminder_preferences,
    set_reminder_preferences
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


class QuietHours(BaseModel):
    start: str
    end: str


class ReminderPreferences(BaseModel):
    enabled: bool = True
    channels: List[str] = ["app"]
    preferred_times: List[str] = []
    quiet_hours: Optional[QuietHours] = None


class ReminderPreferencesResponse(BaseModel):
    user_id: str
    enabled: bool
    channels: List[str]
    preferred_times: List[str]
    quiet_hours: Optional[QuietHours] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


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
    
    preferences = get_reminder_preferences(user_id)
    if not preferences:
        # 返回默认偏好设置
        return ReminderPreferencesResponse(
            user_id=user_id,
            enabled=True,
            channels=["app"],
            preferred_times=[],
            quiet_hours=None
        )
    
    # 转换为响应格式
    quiet_hours = None
    if preferences.get("quiet_hours"):
        quiet_hours = QuietHours(**preferences["quiet_hours"])
    
    return ReminderPreferencesResponse(
        user_id=preferences["user_id"],
        enabled=bool(preferences["enabled"]),
        channels=preferences["channels"],
        preferred_times=preferences["preferred_times"],
        quiet_hours=quiet_hours,
        created_at=preferences.get("created_at"),
        updated_at=preferences.get("updated_at")
    )


@router.put("/preferences/me", response_model=ReminderPreferencesResponse)
async def update_preferences(
    preferences: ReminderPreferences,
    current_user: dict = Depends(get_current_user)
):
    """更新当前用户的提醒偏好设置"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 构建偏好设置数据
    preferences_data = {
        "enabled": 1 if preferences.enabled else 0,
        "channels": preferences.channels,
        "preferred_times": preferences.preferred_times,
        "quiet_hours": _model_dump(preferences.quiet_hours) if preferences.quiet_hours else {}
    }
    
    set_reminder_preferences(user_id, preferences_data)
    
    # 获取更新后的偏好设置
    updated_preferences = get_reminder_preferences(user_id)
    if not updated_preferences:
        raise HTTPException(status_code=500, detail="Failed to update preferences")
    
    # 转换为响应格式
    quiet_hours = None
    if updated_preferences.get("quiet_hours"):
        quiet_hours = QuietHours(**updated_preferences["quiet_hours"])
    
    return ReminderPreferencesResponse(
        user_id=updated_preferences["user_id"],
        enabled=bool(updated_preferences["enabled"]),
        channels=updated_preferences["channels"],
        preferred_times=updated_preferences["preferred_times"],
        quiet_hours=quiet_hours,
        created_at=updated_preferences.get("created_at"),
        updated_at=updated_preferences.get("updated_at")
    )

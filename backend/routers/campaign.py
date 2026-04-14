from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from uuid import uuid4
import time

from ..deps import get_current_user
from ..db import (
    is_admin_user,
    create_growth_campaign,
    update_growth_campaign_status,
    get_growth_campaign,
    list_growth_campaigns,
    join_growth_campaign,
    get_growth_campaign_participant,
    add_growth_campaign_event,
    advance_growth_campaign_progress,
    list_growth_campaign_participants,
    get_growth_campaign_stats,
    create_gamification_event,
)

router = APIRouter()

CampaignType = Literal["challenge", "checkin", "competition"]


def _is_admin(user: dict) -> bool:
    return is_admin_user(str(user["id"]), str(user.get("username") or ""))


class CampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field("", max_length=1000)
    campaign_type: CampaignType = "challenge"
    start_at: int
    end_at: int
    reward_points: int = Field(0, ge=0, le=1000)
    target: int = Field(1, ge=1, le=1000)
    auto_start: bool = True


class CampaignItem(BaseModel):
    id: str
    title: str
    description: str
    campaign_type: str
    status: str
    start_at: int
    end_at: int
    reward_points: int
    target: int
    created_by: str


class CampaignJoinResponse(BaseModel):
    campaign_id: str
    user_id: str
    status: str
    progress: int
    target: int


class CampaignEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=80)
    value: int = Field(1, ge=1, le=100)
    metadata: Dict[str, Any] = {}


@router.post("/campaigns", response_model=CampaignItem, tags=["campaign"])
async def create_campaign(req: CampaignCreateRequest, current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    if int(req.end_at) <= int(req.start_at):
        raise HTTPException(status_code=400, detail="end_at must be greater than start_at")
    now = int(time.time())
    status = "active" if req.auto_start and int(req.start_at) <= now else "scheduled"
    cid = str(uuid4())
    create_growth_campaign(
        cid,
        created_by=str(current_user["id"]),
        title=req.title.strip(),
        description=req.description.strip(),
        campaign_type=req.campaign_type,
        status=status,
        start_at=int(req.start_at),
        end_at=int(req.end_at),
        reward_points=int(req.reward_points),
        rules={"target": int(req.target), "auto_reward": True},
    )
    row = get_growth_campaign(cid) or {}
    rules = row.get("rules_json") or {}
    return CampaignItem(
        id=cid,
        title=str(row.get("title") or req.title.strip()),
        description=str(row.get("description") or req.description.strip()),
        campaign_type=str(row.get("campaign_type") or req.campaign_type),
        status=str(row.get("status") or status),
        start_at=int(row.get("start_at") or req.start_at),
        end_at=int(row.get("end_at") or req.end_at),
        reward_points=int(row.get("reward_points") or req.reward_points),
        target=int(rules.get("target") or req.target),
        created_by=str(row.get("created_by") or current_user["id"]),
    )


@router.post("/campaigns/{campaign_id}/status", tags=["campaign"])
async def set_campaign_status(campaign_id: str, status: Literal["scheduled", "active", "ended"], current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    ok = update_growth_campaign_status(campaign_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"ok": True, "campaign_id": campaign_id, "status": status}


@router.get("/campaigns", response_model=List[CampaignItem], tags=["campaign"])
async def get_campaigns(status: str = "", current_user: dict = Depends(get_current_user)):
    rows = list_growth_campaigns(status=status, limit=100)
    items: list[CampaignItem] = []
    for x in rows:
        rules = x.get("rules_json") or {}
        items.append(
            CampaignItem(
                id=str(x["id"]),
                title=str(x.get("title") or ""),
                description=str(x.get("description") or ""),
                campaign_type=str(x.get("campaign_type") or "challenge"),
                status=str(x.get("status") or "scheduled"),
                start_at=int(x.get("start_at") or 0),
                end_at=int(x.get("end_at") or 0),
                reward_points=int(x.get("reward_points") or 0),
                target=int(rules.get("target") or 1),
                created_by=str(x.get("created_by") or ""),
            )
        )
    return items


@router.post("/campaigns/{campaign_id}/join", response_model=CampaignJoinResponse, tags=["campaign"])
async def join_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = get_growth_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if str(campaign.get("status")) != "active":
        raise HTTPException(status_code=400, detail="Campaign is not active")
    rules = campaign.get("rules_json") or {}
    target = max(1, int(rules.get("target") or 1))
    row = join_growth_campaign(campaign_id, str(current_user["id"]), target=target)
    return CampaignJoinResponse(
        campaign_id=str(row.get("campaign_id") or campaign_id),
        user_id=str(row.get("user_id") or current_user["id"]),
        status=str(row.get("status") or "joined"),
        progress=int(row.get("progress") or 0),
        target=int(row.get("target") or target),
    )


@router.post("/campaigns/{campaign_id}/event", response_model=CampaignJoinResponse, tags=["campaign"])
async def report_campaign_event(campaign_id: str, req: CampaignEventRequest, current_user: dict = Depends(get_current_user)):
    campaign = get_growth_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    participant = get_growth_campaign_participant(campaign_id, str(current_user["id"]))
    if not participant:
        raise HTTPException(status_code=403, detail="Please join campaign first")
    if str(participant.get("status")) == "completed":
        return CampaignJoinResponse(
            campaign_id=campaign_id,
            user_id=str(current_user["id"]),
            status="completed",
            progress=int(participant.get("progress") or 0),
            target=int(participant.get("target") or 1),
        )

    add_growth_campaign_event(
        str(uuid4()),
        campaign_id=campaign_id,
        user_id=str(current_user["id"]),
        event_type=req.event_type.strip(),
        value=int(req.value),
        metadata=req.metadata or {},
    )
    row = advance_growth_campaign_progress(campaign_id=campaign_id, user_id=str(current_user["id"]), delta=int(req.value))
    if str(row.get("status")) == "completed":
        reward = max(0, int(campaign.get("reward_points") or 0))
        if reward > 0:
            create_gamification_event(
                str(uuid4()),
                user_id=str(current_user["id"]),
                source="campaign_complete",
                source_id=campaign_id,
                points=reward,
                note=f"完成活动：{campaign.get('title')}",
                metadata={"campaign_id": campaign_id, "campaign_type": campaign.get("campaign_type")},
            )
    return CampaignJoinResponse(
        campaign_id=str(row.get("campaign_id") or campaign_id),
        user_id=str(row.get("user_id") or current_user["id"]),
        status=str(row.get("status") or "joined"),
        progress=int(row.get("progress") or 0),
        target=int(row.get("target") or 1),
    )


@router.get("/campaigns/{campaign_id}/participants", tags=["campaign"])
async def campaign_participants(campaign_id: str, current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    rows = list_growth_campaign_participants(campaign_id, limit=300)
    return rows


@router.get("/campaigns/{campaign_id}/stats", tags=["campaign"])
async def campaign_stats(campaign_id: str, current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    campaign = get_growth_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    stats = get_growth_campaign_stats(campaign_id)
    return {"campaign_id": campaign_id, "title": campaign.get("title"), **stats}


@router.get("/campaigns/{campaign_id}/me", response_model=Optional[CampaignJoinResponse], tags=["campaign"])
async def campaign_me(campaign_id: str, current_user: dict = Depends(get_current_user)):
    row = get_growth_campaign_participant(campaign_id, str(current_user["id"]))
    if not row:
        return None
    return CampaignJoinResponse(
        campaign_id=str(row.get("campaign_id") or campaign_id),
        user_id=str(row.get("user_id") or current_user["id"]),
        status=str(row.get("status") or "joined"),
        progress=int(row.get("progress") or 0),
        target=int(row.get("target") or 1),
    )

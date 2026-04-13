from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import uuid4
import hashlib

from ..deps import get_current_user
from ..db import (
    create_gamification_event,
    create_gamification_achievement,
    create_gamification_redemption,
    get_gamification_total_points,
    list_gamification_events,
    list_gamification_achievements,
    list_gamification_redemptions,
    list_gamification_leaderboard,
    get_user_profile,
)

router = APIRouter()


CATALOG = [
    {"item_code": "coupon_peer_boost", "item_name": "互评加速卡", "cost_points": 30},
    {"item_code": "coupon_ai_hint", "item_name": "AI提示增强包", "cost_points": 50},
]
CATALOG_MAP = {x["item_code"]: x for x in CATALOG}


def _calc_level(total_points: int) -> str:
    if total_points >= 300:
        return "diamond"
    if total_points >= 150:
        return "gold"
    if total_points >= 60:
        return "silver"
    return "bronze"


def _user_alias(user_id: str) -> str:
    suffix = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()[:6].upper()
    return f"学员#{suffix}"


def _sync_achievements(user_id: str) -> None:
    events = list_gamification_events(user_id=user_id, limit=500)
    total_points = get_gamification_total_points(user_id=user_id)
    profile = get_user_profile(user_id)
    streak_days = int((profile or {}).get("learning_streak_days") or 0)

    writing_review_count = sum(1 for e in events if str(e.get("source") or "") == "writing_peer_review")

    candidates = []
    if total_points >= 1:
        candidates.append(("first_points", "积分入门", "获得首次积分", "🌟"))
    if total_points >= 100:
        candidates.append(("points_100", "积分进阶", "累计积分达到100分", "🚀"))
    if writing_review_count >= 3:
        candidates.append(("peer_reviewer_3", "互评贡献者", "完成3次作文互评", "🧠"))
    if writing_review_count >= 10:
        candidates.append(("peer_reviewer_10", "互评导师", "完成10次作文互评", "🏅"))
    if streak_days >= 7:
        candidates.append(("streak_7", "坚持一周", "连续学习达到7天", "🔥"))
    if len(events) >= 20:
        candidates.append(("event_20", "活跃学习者", "累计积分事件达到20条", "🎯"))

    for code, title, desc, icon in candidates:
        create_gamification_achievement(
            str(uuid4()),
            user_id=user_id,
            code=code,
            title=title,
            description=desc,
            icon=icon,
            metadata={"total_points": total_points, "event_count": len(events)},
        )


class GamificationEventItem(BaseModel):
    id: str
    source: str
    source_id: str
    points: int
    note: str
    metadata: Dict[str, Any]
    created_at: int


class AchievementItem(BaseModel):
    id: str
    code: str
    title: str
    description: str
    icon: str
    unlocked_at: int


class GamificationOverview(BaseModel):
    user_id: str
    total_points: int
    level: str
    event_count: int
    achievement_count: int
    available_catalog: List[Dict[str, Any]]


class LeaderboardItem(BaseModel):
    rank: int
    user_id: str
    user_alias: str
    total_points: int
    event_count: int


class RedemptionRequest(BaseModel):
    item_code: str


class RedemptionResponse(BaseModel):
    redemption_id: str
    item_code: str
    item_name: str
    cost_points: int
    total_points: int
    message: str


@router.get("/gamification/overview", response_model=GamificationOverview, tags=["gamification"])
async def get_overview(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    _sync_achievements(user_id)
    total_points = get_gamification_total_points(user_id)
    events = list_gamification_events(user_id, limit=500)
    achievements = list_gamification_achievements(user_id, limit=200)
    return GamificationOverview(
        user_id=user_id,
        total_points=total_points,
        level=_calc_level(total_points),
        event_count=len(events),
        achievement_count=len(achievements),
        available_catalog=CATALOG,
    )


@router.get("/gamification/events", response_model=List[GamificationEventItem], tags=["gamification"])
async def get_events(limit: int = 50, current_user: dict = Depends(get_current_user)):
    rows = list_gamification_events(str(current_user["id"]), limit=max(1, min(200, int(limit))))
    return [
        GamificationEventItem(
            id=str(x["id"]),
            source=str(x.get("source") or ""),
            source_id=str(x.get("source_id") or ""),
            points=int(x.get("points") or 0),
            note=str(x.get("note") or ""),
            metadata=dict(x.get("metadata") or {}),
            created_at=int(x.get("created_at") or 0),
        )
        for x in rows
    ]


@router.get("/gamification/achievements", response_model=List[AchievementItem], tags=["gamification"])
async def get_achievements(limit: int = 50, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    _sync_achievements(user_id)
    rows = list_gamification_achievements(user_id, limit=max(1, min(200, int(limit))))
    return [
        AchievementItem(
            id=str(x["id"]),
            code=str(x.get("code") or ""),
            title=str(x.get("title") or ""),
            description=str(x.get("description") or ""),
            icon=str(x.get("icon") or "🏅"),
            unlocked_at=int(x.get("unlocked_at") or 0),
        )
        for x in rows
    ]


@router.get("/gamification/leaderboard", response_model=List[LeaderboardItem], tags=["gamification"])
async def get_leaderboard(limit: int = 20, current_user: dict = Depends(get_current_user)):
    rows = list_gamification_leaderboard(limit=max(1, min(100, int(limit))))
    return [
        LeaderboardItem(
            rank=idx + 1,
            user_id=str(x.get("user_id") or ""),
            user_alias=_user_alias(str(x.get("user_id") or "")),
            total_points=int(x.get("total_points") or 0),
            event_count=int(x.get("event_count") or 0),
        )
        for idx, x in enumerate(rows)
    ]


@router.post("/gamification/redeem", response_model=RedemptionResponse, tags=["gamification"])
async def redeem_item(req: RedemptionRequest, current_user: dict = Depends(get_current_user)):
    item = CATALOG_MAP.get(str(req.item_code or ""))
    if not item:
        raise HTTPException(status_code=404, detail="Redeem item not found")

    user_id = str(current_user["id"])
    balance = get_gamification_total_points(user_id)
    cost = int(item["cost_points"])
    if balance < cost:
        raise HTTPException(status_code=400, detail="Not enough points")

    redemption_id = str(uuid4())
    create_gamification_redemption(
        redemption_id,
        user_id=user_id,
        item_code=str(item["item_code"]),
        item_name=str(item["item_name"]),
        cost_points=cost,
        metadata={"source": "gamification_redeem_api"},
    )
    create_gamification_event(
        str(uuid4()),
        user_id=user_id,
        source="gamification_redeem",
        source_id=redemption_id,
        points=-cost,
        note=f"兑换：{item['item_name']}",
        metadata={"item_code": item["item_code"], "cost_points": cost},
    )
    _sync_achievements(user_id)
    latest_points = get_gamification_total_points(user_id)
    return RedemptionResponse(
        redemption_id=redemption_id,
        item_code=str(item["item_code"]),
        item_name=str(item["item_name"]),
        cost_points=cost,
        total_points=latest_points,
        message="兑换成功",
    )


@router.get("/gamification/redemptions", tags=["gamification"])
async def get_redemptions(limit: int = 30, current_user: dict = Depends(get_current_user)):
    return list_gamification_redemptions(str(current_user["id"]), limit=max(1, min(200, int(limit))))

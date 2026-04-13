from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4
import hashlib

from ..deps import get_current_user
from ..db import (
    create_study_group,
    get_study_group,
    list_study_groups,
    list_user_study_groups,
    get_study_group_member,
    join_study_group,
    create_study_group_checkin,
    list_study_group_checkins,
    list_study_group_leaderboard,
    create_gamification_event,
)

router = APIRouter()


def _alias(user_id: str) -> str:
    suffix = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()[:6].upper()
    return f"组员#{suffix}"


class StudyGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    description: str = Field("", max_length=500)
    is_public: bool = True
    max_members: int = Field(20, ge=2, le=200)


class StudyGroupItem(BaseModel):
    id: str
    name: str
    description: str
    is_public: bool
    max_members: int
    member_count: int
    created_at: int
    owner_alias: str


class GroupMemberItem(BaseModel):
    user_id: str
    user_alias: str
    role: str
    checkin_streak: int
    total_checkins: int
    last_checkin_at: int


class GroupCheckinRequest(BaseModel):
    note: str = Field("", max_length=200)
    score: int = Field(1, ge=1, le=5)


class GroupCheckinItem(BaseModel):
    id: str
    group_id: str
    user_id: str
    user_alias: str
    note: str
    score: int
    created_at: int


@router.post("/groups", response_model=StudyGroupItem)
async def create_group(req: StudyGroupCreateRequest, current_user: dict = Depends(get_current_user)):
    gid = str(uuid4())
    uid = str(current_user["id"])
    create_study_group(
        gid,
        owner_user_id=uid,
        name=req.name.strip(),
        description=req.description.strip(),
        is_public=req.is_public,
        max_members=req.max_members,
    )
    create_gamification_event(
        str(uuid4()),
        user_id=uid,
        source="study_group_create",
        source_id=gid,
        points=3,
        note="创建学习小组",
        metadata={"name": req.name.strip()},
    )
    item = get_study_group(gid)
    return StudyGroupItem(
        id=gid,
        name=str(item.get("name") if item else req.name.strip()),
        description=str(item.get("description") if item else req.description.strip()),
        is_public=bool(item.get("is_public")) if item else req.is_public,
        max_members=int(item.get("max_members") if item else req.max_members),
        member_count=int(item.get("member_count") if item else 1),
        created_at=int(item.get("created_at") if item else 0),
        owner_alias=_alias(uid),
    )


@router.get("/groups", response_model=List[StudyGroupItem])
async def get_groups(limit: int = 30, offset: int = 0, current_user: dict = Depends(get_current_user)):
    rows = list_study_groups(public_only=True, limit=max(1, min(100, int(limit))), offset=max(0, int(offset)))
    return [
        StudyGroupItem(
            id=str(x["id"]),
            name=str(x.get("name") or ""),
            description=str(x.get("description") or ""),
            is_public=bool(x.get("is_public")),
            max_members=int(x.get("max_members") or 20),
            member_count=int(x.get("member_count") or 0),
            created_at=int(x.get("created_at") or 0),
            owner_alias=_alias(str(x.get("owner_user_id") or "")),
        )
        for x in rows
    ]


@router.get("/groups/me", response_model=List[StudyGroupItem])
async def get_my_groups(limit: int = 30, current_user: dict = Depends(get_current_user)):
    rows = list_user_study_groups(str(current_user["id"]), limit=max(1, min(100, int(limit))))
    return [
        StudyGroupItem(
            id=str(x["id"]),
            name=str(x.get("name") or ""),
            description=str(x.get("description") or ""),
            is_public=bool(x.get("is_public")),
            max_members=int(x.get("max_members") or 20),
            member_count=int(x.get("member_count") or 0),
            created_at=int(x.get("created_at") or 0),
            owner_alias=_alias(str(x.get("owner_user_id") or "")),
        )
        for x in rows
    ]


@router.post("/groups/{group_id}/join")
async def join_group(group_id: str, current_user: dict = Depends(get_current_user)):
    uid = str(current_user["id"])
    group = get_study_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    try:
        member = join_study_group(group_id, uid, role="member")
    except ValueError as exc:
        if str(exc) == "group_full":
            raise HTTPException(status_code=400, detail="Group is full") from exc
        raise HTTPException(status_code=400, detail="Join failed") from exc

    create_gamification_event(
        str(uuid4()),
        user_id=uid,
        source="study_group_join",
        source_id=f"{group_id}:{uid}",
        points=1,
        note="加入学习小组",
        metadata={"group_id": group_id},
    )
    return {
        "group_id": group_id,
        "user_id": uid,
        "role": str(member.get("role") or "member"),
        "message": "加入成功",
    }


@router.get("/groups/{group_id}/leaderboard", response_model=List[GroupMemberItem])
async def get_group_leaderboard(group_id: str, limit: int = 20, current_user: dict = Depends(get_current_user)):
    group = get_study_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    rows = list_study_group_leaderboard(group_id, limit=max(1, min(100, int(limit))))
    return [
        GroupMemberItem(
            user_id=str(x.get("user_id") or ""),
            user_alias=_alias(str(x.get("user_id") or "")),
            role=str(x.get("role") or "member"),
            checkin_streak=int(x.get("checkin_streak") or 0),
            total_checkins=int(x.get("total_checkins") or 0),
            last_checkin_at=int(x.get("last_checkin_at") or 0),
        )
        for x in rows
    ]


@router.post("/groups/{group_id}/checkin", response_model=GroupCheckinItem)
async def checkin_group(group_id: str, req: GroupCheckinRequest, current_user: dict = Depends(get_current_user)):
    uid = str(current_user["id"])
    member = get_study_group_member(group_id, uid)
    if not member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    cid = str(uuid4())
    try:
        row = create_study_group_checkin(
            cid,
            group_id=group_id,
            user_id=uid,
            note=req.note.strip(),
            score=req.score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Checkin failed") from exc

    create_gamification_event(
        str(uuid4()),
        user_id=uid,
        source="study_group_checkin",
        source_id=f"{group_id}:{int(row.get('created_at') or 0) // 86400}",
        points=2,
        note="学习小组打卡",
        metadata={"group_id": group_id, "score": req.score},
    )

    return GroupCheckinItem(
        id=str(row.get("id") or cid),
        group_id=str(row.get("group_id") or group_id),
        user_id=uid,
        user_alias=_alias(uid),
        note=str(row.get("note") or req.note.strip()),
        score=int(row.get("score") or req.score),
        created_at=int(row.get("created_at") or 0),
    )


@router.get("/groups/{group_id}/checkins", response_model=List[GroupCheckinItem])
async def get_group_checkins(group_id: str, limit: int = 100, current_user: dict = Depends(get_current_user)):
    group = get_study_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    rows = list_study_group_checkins(group_id, limit=max(1, min(300, int(limit))))
    return [
        GroupCheckinItem(
            id=str(x.get("id") or ""),
            group_id=str(x.get("group_id") or group_id),
            user_id=str(x.get("user_id") or ""),
            user_alias=_alias(str(x.get("user_id") or "")),
            note=str(x.get("note") or ""),
            score=int(x.get("score") or 1),
            created_at=int(x.get("created_at") or 0),
        )
        for x in rows
    ]

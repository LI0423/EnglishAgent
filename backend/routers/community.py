from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from uuid import uuid4
import hashlib
import time

from ..deps import get_current_user
from ..db import (
    create_community_post,
    get_community_post,
    add_community_post_view,
    list_community_posts,
    create_community_comment,
    list_community_comments,
    get_community_comment,
    set_community_vote,
    get_user_community_summary,
    create_gamification_event,
)

router = APIRouter()

PostType = Literal["discussion", "question", "share"]

_BLOCKED_TERMS = {"spam", "广告", "引流", "加vx", "赌博", "刷单"}


def _contains_blocked_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(term in lower for term in _BLOCKED_TERMS)


def _user_alias(user_id: str) -> str:
    suffix = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()[:6].upper()
    return f"同学#{suffix}"


class CommunityPostCreateRequest(BaseModel):
    post_type: PostType = "discussion"
    title: str = Field(..., min_length=4, max_length=120)
    content: str = Field(..., min_length=10, max_length=4000)
    tags: List[str] = []
    is_anonymous: bool = False


class CommunityPostItem(BaseModel):
    id: str
    post_type: str
    title: str
    content: str
    tags: List[str]
    status: str
    is_anonymous: bool
    author_alias: str
    upvotes: int
    downvotes: int
    comment_count: int
    view_count: int
    created_at: int
    updated_at: int


class CommunityPostCreateResponse(BaseModel):
    post_id: str
    status: str
    message: str


class CommunityCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=2, max_length=1000)
    is_anonymous: bool = False


class CommunityCommentItem(BaseModel):
    id: str
    post_id: str
    content: str
    status: str
    is_anonymous: bool
    author_alias: str
    upvotes: int
    downvotes: int
    created_at: int


class CommunityVoteRequest(BaseModel):
    vote: Literal[-1, 0, 1]


class CommunityVoteResponse(BaseModel):
    upvotes: int
    downvotes: int


class CommunitySummaryResponse(BaseModel):
    post_count: int
    comment_count: int
    vote_count: int


@router.post("/posts", response_model=CommunityPostCreateResponse)
async def create_post(req: CommunityPostCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    post_id = str(uuid4())
    merged_text = f"{req.title}\n{req.content}"
    status = "pending_review" if _contains_blocked_text(merged_text) else "published"
    create_community_post(
        post_id,
        user_id=user_id,
        post_type=req.post_type,
        title=req.title.strip(),
        content=req.content.strip(),
        tags=req.tags,
        status=status,
        is_anonymous=req.is_anonymous,
    )

    if status == "published":
        create_gamification_event(
            str(uuid4()),
            user_id=user_id,
            source="community_post",
            source_id=post_id,
            points=3,
            note="发布社区帖子",
            metadata={"post_type": req.post_type},
        )

    return CommunityPostCreateResponse(
        post_id=post_id,
        status=status,
        message="发布成功，等待互动" if status == "published" else "内容进入审核队列，请稍后查看",
    )


@router.get("/posts", response_model=List[CommunityPostItem])
async def get_posts(
    post_type: Optional[PostType] = None,
    keyword: str = "",
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    rows = list_community_posts(
        post_type=str(post_type) if post_type else None,
        status="published",
        keyword=keyword,
        limit=max(1, min(100, int(limit))),
        offset=max(0, int(offset)),
    )
    return [
        CommunityPostItem(
            id=str(x["id"]),
            post_type=str(x.get("post_type") or "discussion"),
            title=str(x.get("title") or ""),
            content=str(x.get("content") or ""),
            tags=list(x.get("tags") or []),
            status=str(x.get("status") or "published"),
            is_anonymous=bool(x.get("is_anonymous")),
            author_alias=("匿名同学" if bool(x.get("is_anonymous")) else _user_alias(str(x.get("user_id") or ""))),
            upvotes=int(x.get("upvotes") or 0),
            downvotes=int(x.get("downvotes") or 0),
            comment_count=int(x.get("comment_count") or 0),
            view_count=int(x.get("view_count") or 0),
            created_at=int(x.get("created_at") or 0),
            updated_at=int(x.get("updated_at") or 0),
        )
        for x in rows
    ]


@router.get("/posts/{post_id}", response_model=CommunityPostItem)
async def get_post_detail(post_id: str, current_user: dict = Depends(get_current_user)):
    post = get_community_post(post_id)
    if not post or str(post.get("status")) != "published":
        raise HTTPException(status_code=404, detail="Post not found")
    add_community_post_view(post_id)
    post = get_community_post(post_id) or post
    return CommunityPostItem(
        id=str(post["id"]),
        post_type=str(post.get("post_type") or "discussion"),
        title=str(post.get("title") or ""),
        content=str(post.get("content") or ""),
        tags=list(post.get("tags") or []),
        status=str(post.get("status") or "published"),
        is_anonymous=bool(post.get("is_anonymous")),
        author_alias=("匿名同学" if bool(post.get("is_anonymous")) else _user_alias(str(post.get("user_id") or ""))),
        upvotes=int(post.get("upvotes") or 0),
        downvotes=int(post.get("downvotes") or 0),
        comment_count=int(post.get("comment_count") or 0),
        view_count=int(post.get("view_count") or 0),
        created_at=int(post.get("created_at") or 0),
        updated_at=int(post.get("updated_at") or 0),
    )


@router.post("/posts/{post_id}/comments", response_model=CommunityCommentItem)
async def create_comment(post_id: str, req: CommunityCommentCreateRequest, current_user: dict = Depends(get_current_user)):
    post = get_community_post(post_id)
    if not post or str(post.get("status")) != "published":
        raise HTTPException(status_code=404, detail="Post not found")

    status = "pending_review" if _contains_blocked_text(req.content) else "published"
    comment_id = str(uuid4())
    create_community_comment(
        comment_id,
        post_id=post_id,
        user_id=str(current_user["id"]),
        content=req.content.strip(),
        status=status,
        is_anonymous=req.is_anonymous,
    )

    if status == "published":
        create_gamification_event(
            str(uuid4()),
            user_id=str(current_user["id"]),
            source="community_comment",
            source_id=comment_id,
            points=1,
            note="发布社区评论",
            metadata={"post_id": post_id},
        )

    return CommunityCommentItem(
        id=comment_id,
        post_id=post_id,
        content=req.content.strip(),
        status=status,
        is_anonymous=req.is_anonymous,
        author_alias=("匿名同学" if req.is_anonymous else _user_alias(str(current_user["id"]))),
        upvotes=0,
        downvotes=0,
        created_at=int(time.time()),
    )


@router.get("/posts/{post_id}/comments", response_model=List[CommunityCommentItem])
async def get_comments(post_id: str, limit: int = 100, current_user: dict = Depends(get_current_user)):
    post = get_community_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    rows = list_community_comments(post_id=post_id, status="published", limit=max(1, min(200, int(limit))))
    return [
        CommunityCommentItem(
            id=str(x["id"]),
            post_id=str(x.get("post_id") or post_id),
            content=str(x.get("content") or ""),
            status=str(x.get("status") or "published"),
            is_anonymous=bool(x.get("is_anonymous")),
            author_alias=("匿名同学" if bool(x.get("is_anonymous")) else _user_alias(str(x.get("user_id") or ""))),
            upvotes=int(x.get("upvotes") or 0),
            downvotes=int(x.get("downvotes") or 0),
            created_at=int(x.get("created_at") or 0),
        )
        for x in rows
    ]


@router.post("/posts/{post_id}/vote", response_model=CommunityVoteResponse)
async def vote_post(post_id: str, req: CommunityVoteRequest, current_user: dict = Depends(get_current_user)):
    post = get_community_post(post_id)
    if not post or str(post.get("status")) != "published":
        raise HTTPException(status_code=404, detail="Post not found")
    stat = set_community_vote(
        str(uuid4()),
        user_id=str(current_user["id"]),
        target_type="post",
        target_id=post_id,
        vote=int(req.vote),
    )
    return CommunityVoteResponse(upvotes=int(stat["upvotes"]), downvotes=int(stat["downvotes"]))


@router.post("/comments/{comment_id}/vote", response_model=CommunityVoteResponse)
async def vote_comment(comment_id: str, req: CommunityVoteRequest, current_user: dict = Depends(get_current_user)):
    comment = get_community_comment(comment_id)
    if not comment or str(comment.get("status")) != "published":
        raise HTTPException(status_code=404, detail="Comment not found")
    stat = set_community_vote(
        str(uuid4()),
        user_id=str(current_user["id"]),
        target_type="comment",
        target_id=comment_id,
        vote=int(req.vote),
    )
    return CommunityVoteResponse(upvotes=int(stat["upvotes"]), downvotes=int(stat["downvotes"]))


@router.get("/me/summary", response_model=CommunitySummaryResponse)
async def get_my_community_summary(current_user: dict = Depends(get_current_user)):
    data = get_user_community_summary(str(current_user["id"]))
    return CommunitySummaryResponse(
        post_count=int(data.get("post_count") or 0),
        comment_count=int(data.get("comment_count") or 0),
        vote_count=int(data.get("vote_count") or 0),
    )

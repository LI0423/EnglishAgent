from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Literal
from uuid import uuid4

from ..deps import get_current_user
from ..db import (
    is_admin_user,
    get_admin_overview_metrics,
    get_admin_retention_metrics,
    get_admin_payment_funnel_metrics,
    get_admin_entitlement_efficiency,
    get_admin_campaign_conversion_metrics,
    list_pending_community_posts,
    list_pending_community_comments,
    moderate_community_post,
    moderate_community_comment,
    create_admin_audit_log,
    list_payment_orders_admin,
    list_entitlement_ledger_admin,
)

router = APIRouter()


def _ensure_admin(current_user: dict) -> dict:
    if not is_admin_user(str(current_user["id"]), str(current_user.get("username") or "")):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users_7d: int
    total_orders: int
    paid_orders: int
    paid_amount_cents: int
    pending_posts: int
    pending_comments: int
    writing_ai_review_balance_sum: int
    writing_ai_review_granted_sum: int
    writing_ai_review_consumed_sum: int


class ModerateRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = ""


class AdminRetentionResponse(BaseModel):
    cohort_days: int
    new_users: int
    d1_retention_rate: float
    d7_retention_rate: float
    cohorts: List[Dict[str, Any]]


class AdminFunnelResponse(BaseModel):
    days: int
    inferred_exposure: bool
    exposure_users: int
    order_users: int
    paid_users: int
    order_count: int
    paid_count: int
    paid_amount_cents: int
    exposure_to_order_rate: float
    order_to_paid_rate: float
    exposure_to_paid_rate: float


class AdminEntitlementEfficiencyResponse(BaseModel):
    days: int
    feature_summary: List[Dict[str, Any]]
    source_breakdown: List[Dict[str, Any]]


class AdminCampaignConversionResponse(BaseModel):
    days: int
    campaign_count: int
    participant_total: int
    completed_total: int
    avg_completion_rate: float
    reward_cost_points_total: int
    campaigns: List[Dict[str, Any]]


@router.get("/admin/overview", response_model=AdminOverviewResponse, tags=["admin"])
async def admin_overview(current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    data = get_admin_overview_metrics()
    return AdminOverviewResponse(
        total_users=int(data.get("total_users") or 0),
        active_users_7d=int(data.get("active_users_7d") or 0),
        total_orders=int(data.get("total_orders") or 0),
        paid_orders=int(data.get("paid_orders") or 0),
        paid_amount_cents=int(data.get("paid_amount_cents") or 0),
        pending_posts=int(data.get("pending_posts") or 0),
        pending_comments=int(data.get("pending_comments") or 0),
        writing_ai_review_balance_sum=int(data.get("writing_ai_review_balance_sum") or 0),
        writing_ai_review_granted_sum=int(data.get("writing_ai_review_granted_sum") or 0),
        writing_ai_review_consumed_sum=int(data.get("writing_ai_review_consumed_sum") or 0),
    )


@router.get("/admin/reports/retention", response_model=AdminRetentionResponse, tags=["admin"])
async def admin_report_retention(cohort_days: int = 14, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    data = get_admin_retention_metrics(cohort_days=max(3, min(60, int(cohort_days))))
    return AdminRetentionResponse(
        cohort_days=int(data.get("cohort_days") or 14),
        new_users=int(data.get("new_users") or 0),
        d1_retention_rate=float(data.get("d1_retention_rate") or 0.0),
        d7_retention_rate=float(data.get("d7_retention_rate") or 0.0),
        cohorts=list(data.get("cohorts") or []),
    )


@router.get("/admin/reports/funnel", response_model=AdminFunnelResponse, tags=["admin"])
async def admin_report_funnel(days: int = 30, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    data = get_admin_payment_funnel_metrics(days=max(7, min(120, int(days))))
    return AdminFunnelResponse(
        days=int(data.get("days") or 30),
        inferred_exposure=bool(data.get("inferred_exposure")),
        exposure_users=int(data.get("exposure_users") or 0),
        order_users=int(data.get("order_users") or 0),
        paid_users=int(data.get("paid_users") or 0),
        order_count=int(data.get("order_count") or 0),
        paid_count=int(data.get("paid_count") or 0),
        paid_amount_cents=int(data.get("paid_amount_cents") or 0),
        exposure_to_order_rate=float(data.get("exposure_to_order_rate") or 0.0),
        order_to_paid_rate=float(data.get("order_to_paid_rate") or 0.0),
        exposure_to_paid_rate=float(data.get("exposure_to_paid_rate") or 0.0),
    )


@router.get("/admin/reports/entitlement-efficiency", response_model=AdminEntitlementEfficiencyResponse, tags=["admin"])
async def admin_report_entitlement_efficiency(
    feature_code: str = "",
    days: int = 30,
    current_user: dict = Depends(get_current_user),
):
    _ensure_admin(current_user)
    data = get_admin_entitlement_efficiency(feature_code=feature_code, days=max(7, min(120, int(days))))
    return AdminEntitlementEfficiencyResponse(
        days=int(data.get("days") or 30),
        feature_summary=list(data.get("feature_summary") or []),
        source_breakdown=list(data.get("source_breakdown") or []),
    )


@router.get("/admin/reports/campaign-conversion", response_model=AdminCampaignConversionResponse, tags=["admin"])
async def admin_report_campaign_conversion(days: int = 30, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    data = get_admin_campaign_conversion_metrics(days=max(7, min(180, int(days))))
    return AdminCampaignConversionResponse(
        days=int(data.get("days") or 30),
        campaign_count=int(data.get("campaign_count") or 0),
        participant_total=int(data.get("participant_total") or 0),
        completed_total=int(data.get("completed_total") or 0),
        avg_completion_rate=float(data.get("avg_completion_rate") or 0.0),
        reward_cost_points_total=int(data.get("reward_cost_points_total") or 0),
        campaigns=list(data.get("campaigns") or []),
    )


@router.get("/admin/moderation/posts", tags=["admin"])
async def admin_pending_posts(limit: int = 50, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    return list_pending_community_posts(limit=max(1, min(200, int(limit))))


@router.get("/admin/moderation/comments", tags=["admin"])
async def admin_pending_comments(limit: int = 100, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    return list_pending_community_comments(limit=max(1, min(300, int(limit))))


@router.post("/admin/moderation/posts/{post_id}", tags=["admin"])
async def admin_moderate_post(post_id: str, req: ModerateRequest, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    status = "published" if req.action == "approve" else "rejected"
    ok = moderate_community_post(post_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    create_admin_audit_log(
        str(uuid4()),
        admin_user_id=str(current_user["id"]),
        action=f"moderate_post:{req.action}",
        target_type="community_post",
        target_id=str(post_id),
        detail=str(req.reason or ""),
        metadata={"status": status},
    )
    return {"ok": True, "post_id": post_id, "status": status}


@router.post("/admin/moderation/comments/{comment_id}", tags=["admin"])
async def admin_moderate_comment(comment_id: str, req: ModerateRequest, current_user: dict = Depends(get_current_user)):
    _ensure_admin(current_user)
    status = "published" if req.action == "approve" else "rejected"
    ok = moderate_community_comment(comment_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="Comment not found")
    create_admin_audit_log(
        str(uuid4()),
        admin_user_id=str(current_user["id"]),
        action=f"moderate_comment:{req.action}",
        target_type="community_comment",
        target_id=str(comment_id),
        detail=str(req.reason or ""),
        metadata={"status": status},
    )
    return {"ok": True, "comment_id": comment_id, "status": status}


@router.get("/admin/orders", tags=["admin"])
async def admin_orders(
    status: str = "",
    user_id: str = "",
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    _ensure_admin(current_user)
    return list_payment_orders_admin(status=status, user_id=user_id, limit=max(1, min(300, int(limit))))


@router.get("/admin/entitlements/ledger", tags=["admin"])
async def admin_entitlement_ledger(
    user_id: str = "",
    feature_code: str = "",
    limit: int = 200,
    current_user: dict = Depends(get_current_user),
):
    _ensure_admin(current_user)
    return list_entitlement_ledger_admin(
        user_id=user_id,
        feature_code=feature_code,
        limit=max(1, min(500, int(limit))),
    )

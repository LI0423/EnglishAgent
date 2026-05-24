import csv
import io
from uuid import uuid4
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..deps import get_current_user
from ..db import (
    get_user_mistakes,
    get_due_mistakes,
    get_mistake_by_id,
    review_mistake,
    get_mistake_stats,
    get_mistake_analysis,
    get_mistake_clusters,
    get_mistake_hotspots,
    get_mistake_module_comparison,
    get_mistake_recommendations,
    get_mistake_weekly_focus_plan,
    get_mistake_review_effectiveness,
    get_mistake_trends,
    get_prioritized_mistake_review_queue,
    save_mistake,
)


router = APIRouter()


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


class MistakeCreate(BaseModel):
    module: str
    question_id: str
    question_type: str = "general"
    error_type: str = "general"
    content: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = "medium"
    tags: List[str] = []


class MistakeItem(BaseModel):
    id: str
    module: str
    question_id: str
    question_type: str
    error_type: str
    content: str
    user_answer: str
    correct_answer: str
    explanation: str
    difficulty: str
    tags: List[str]
    created_at: int
    last_reviewed_at: Optional[int] = None
    next_review_date: Optional[int] = None
    mastery_level: float = 0.0


class ReviewResponse(BaseModel):
    next_review_date: int
    mastery_level: float


class MistakeAnalysisResponse(BaseModel):
    total: int
    due_count: int
    avg_mastery: float
    by_error_type: dict
    by_difficulty: dict
    by_question_type: dict
    by_error_and_question_type: dict
    vocabulary_test_wrong_count: int
    vocabulary_test_wrong_ratio: float


class MistakeImportPayload(BaseModel):
    items: List[MistakeCreate]


class MistakeImportResponse(BaseModel):
    imported: int


class MistakeReviewQueueItem(MistakeItem):
    priority_score: float
    priority_reason: str
    expected_mastery_gain: float
    projected_mastery_after_review: float


class MistakeClusterItem(BaseModel):
    module: str
    question_type: str
    error_type: str
    difficulty: str
    count: int
    avg_mastery: float
    due_count: int
    latest_created_at: int
    risk_score: float


class BatchReviewRequest(BaseModel):
    mistake_ids: List[str]
    mastery_delta: float = 0.2


class BatchReviewResponse(BaseModel):
    requested: int
    reviewed: int
    skipped: int
    failed_ids: List[str] = []


class MistakeTrendItem(BaseModel):
    date: str
    day_start: int
    created_count: int
    reviewed_count: int
    due_snapshot: int


class MistakeReviewEffectivenessItem(BaseModel):
    date: str
    day_start: int
    review_count: int
    avg_mastery_before: float
    avg_mastery_after: float
    avg_mastery_gain: float


class MistakeHotspotItem(BaseModel):
    module: str
    error_type: str
    count: int
    due_count: int
    avg_mastery: float
    risk_score: float


class MistakeRecommendationItem(BaseModel):
    rank: int
    module: str
    error_type: str
    risk_score: float
    mistake_count: int
    due_count: int
    avg_mastery: float
    action: str


class MistakeModuleComparisonItem(BaseModel):
    module: str
    count: int
    due_count: int
    avg_mastery: float
    unique_error_types: int
    risk_index: float


class WeeklyFocusAllocationItem(BaseModel):
    module: str
    percent: int
    minutes: int
    reason: str


class WeeklyFocusBlockItem(BaseModel):
    block: int
    module: str
    minutes: int


class MistakeWeeklyFocusPlanResponse(BaseModel):
    focus_module: str
    total_daily_minutes: int
    module_allocations: List[WeeklyFocusAllocationItem]
    daily_blocks: List[WeeklyFocusBlockItem]
    summary: str


@router.post("/", response_model=MistakeItem)
async def create_mistake(
    payload: MistakeCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    mistake_id = str(uuid4())
    save_mistake(mistake_id, user_id, _model_dump(payload))
    created = get_mistake_by_id(mistake_id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create mistake")
    return MistakeItem(**created)


@router.get("/", response_model=List[MistakeItem])
async def list_mistakes(
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    error_type: Optional[str] = None,
    created_from: Optional[int] = None,
    created_to: Optional[int] = None,
    next_review_from: Optional[int] = None,
    next_review_to: Optional[int] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    rows = get_user_mistakes(
        current_user["id"],
        module,
        limit,
        question_type=question_type,
        error_type=error_type,
        created_from=created_from,
        created_to=created_to,
        next_review_from=next_review_from,
        next_review_to=next_review_to,
    )
    return [MistakeItem(**r) for r in rows]


@router.get("/due", response_model=List[MistakeItem])
async def list_due_mistakes(
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    rows = get_due_mistakes(current_user["id"], module, limit, question_type=question_type)
    return [MistakeItem(**r) for r in rows]


@router.get("/export")
async def export_mistakes(
    format: Literal["json", "csv"] = "json",
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    error_type: Optional[str] = None,
    limit: int = 1000,
    current_user: dict = Depends(get_current_user),
):
    rows = get_user_mistakes(
        current_user["id"],
        module,
        max(1, min(limit, 5000)),
        question_type=question_type,
        error_type=error_type,
    )
    if format == "json":
        return {"count": len(rows), "items": rows}

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "module",
            "question_id",
            "question_type",
            "error_type",
            "content",
            "user_answer",
            "correct_answer",
            "explanation",
            "difficulty",
            "tags",
            "mastery_level",
            "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.get("id", ""),
                r.get("module", ""),
                r.get("question_id", ""),
                r.get("question_type", ""),
                r.get("error_type", ""),
                r.get("content", ""),
                r.get("user_answer", ""),
                r.get("correct_answer", ""),
                r.get("explanation", ""),
                r.get("difficulty", ""),
                "|".join(r.get("tags") or []),
                r.get("mastery_level", 0.0),
                r.get("created_at", 0),
            ]
        )
    csv_content = buf.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mistakes_export.csv"},
    )


@router.post("/import", response_model=MistakeImportResponse)
async def import_mistakes(
    payload: MistakeImportPayload,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    imported = 0
    for item in payload.items:
        data = _model_dump(item)
        data["tags"] = list(dict.fromkeys(data.get("tags") or []))
        save_mistake(str(uuid4()), user_id, data)
        imported += 1
    return MistakeImportResponse(imported=imported)


@router.post("/{mistake_id}/review", response_model=ReviewResponse)
async def mark_reviewed(
    mistake_id: str,
    mastery_delta: float = 0.2,
    current_user: dict = Depends(get_current_user),
):
    mistake = get_mistake_by_id(mistake_id)
    if not mistake:
        raise HTTPException(status_code=404, detail="Mistake not found")
    if mistake["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    reviewed = review_mistake(mistake_id, mastery_delta)
    if not reviewed:
        raise HTTPException(status_code=500, detail="Failed to review mistake")
    return ReviewResponse(
        next_review_date=reviewed["next_review_date"],
        mastery_level=reviewed["mastery_level"],
    )


@router.post("/review/batch", response_model=BatchReviewResponse)
async def batch_review(
    payload: BatchReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    ids = [str(x).strip() for x in (payload.mistake_ids or []) if str(x).strip()]
    unique_ids = list(dict.fromkeys(ids))
    reviewed = 0
    skipped = 0
    failed_ids: List[str] = []
    for mistake_id in unique_ids:
        mistake = get_mistake_by_id(mistake_id)
        if not mistake:
            skipped += 1
            failed_ids.append(mistake_id)
            continue
        if mistake["user_id"] != current_user["id"]:
            skipped += 1
            failed_ids.append(mistake_id)
            continue
        result = review_mistake(mistake_id, payload.mastery_delta)
        if result:
            reviewed += 1
        else:
            failed_ids.append(mistake_id)
    return BatchReviewResponse(
        requested=len(unique_ids),
        reviewed=reviewed,
        skipped=skipped,
        failed_ids=failed_ids,
    )


@router.get("/stats/summary")
async def summary(current_user: dict = Depends(get_current_user)):
    return get_mistake_stats(current_user["id"])


@router.get("/analysis", response_model=MistakeAnalysisResponse)
async def analysis(current_user: dict = Depends(get_current_user)):
    return MistakeAnalysisResponse(**get_mistake_analysis(current_user["id"]))


@router.get("/review-queue", response_model=List[MistakeReviewQueueItem])
async def prioritized_review_queue(
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    next_review_from: Optional[int] = None,
    next_review_to: Optional[int] = None,
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    rows = get_prioritized_mistake_review_queue(
        current_user["id"],
        module=module,
        question_type=question_type,
        next_review_from=next_review_from,
        next_review_to=next_review_to,
        limit=limit,
    )
    return [MistakeReviewQueueItem(**r) for r in rows]


@router.get("/clusters", response_model=List[MistakeClusterItem])
async def clusters(
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_clusters(
        current_user["id"],
        module=module,
        question_type=question_type,
        limit=limit,
    )
    return [MistakeClusterItem(**r) for r in rows]


@router.get("/trends", response_model=List[MistakeTrendItem])
async def trends(
    days: int = 7,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_trends(
        current_user["id"],
        days=days,
        module=module,
        question_type=question_type,
    )
    return [MistakeTrendItem(**r) for r in rows]


@router.get("/review-effectiveness", response_model=List[MistakeReviewEffectivenessItem])
async def review_effectiveness(
    days: int = 7,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_review_effectiveness(
        current_user["id"],
        days=days,
        module=module,
        question_type=question_type,
    )
    return [MistakeReviewEffectivenessItem(**r) for r in rows]


@router.get("/hotspots", response_model=List[MistakeHotspotItem])
async def hotspots(
    days: int = 14,
    module: Optional[str] = None,
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_hotspots(
        current_user["id"],
        days=days,
        module=module,
        limit=limit,
    )
    return [MistakeHotspotItem(**r) for r in rows]


@router.get("/recommendations", response_model=List[MistakeRecommendationItem])
async def recommendations(
    days: int = 14,
    module: Optional[str] = None,
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_recommendations(
        current_user["id"],
        days=days,
        module=module,
        limit=limit,
    )
    return [MistakeRecommendationItem(**r) for r in rows]


@router.get("/module-comparison", response_model=List[MistakeModuleComparisonItem])
async def module_comparison(
    days: int = 14,
    current_user: dict = Depends(get_current_user),
):
    rows = get_mistake_module_comparison(
        current_user["id"],
        days=days,
    )
    return [MistakeModuleComparisonItem(**r) for r in rows]


@router.get("/weekly-focus", response_model=MistakeWeeklyFocusPlanResponse)
async def weekly_focus(
    days: int = 14,
    total_daily_minutes: int = 90,
    current_user: dict = Depends(get_current_user),
):
    plan = get_mistake_weekly_focus_plan(
        current_user["id"],
        days=days,
        total_daily_minutes=max(30, min(int(total_daily_minutes or 90), 240)),
    )
    return MistakeWeeklyFocusPlanResponse(**plan)

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
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    rows = get_user_mistakes(current_user["id"], module, limit, question_type=question_type)
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
    limit: int = 1000,
    current_user: dict = Depends(get_current_user),
):
    rows = get_user_mistakes(
        current_user["id"],
        module,
        max(1, min(limit, 5000)),
        question_type=question_type,
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


@router.get("/stats/summary")
async def summary(current_user: dict = Depends(get_current_user)):
    return get_mistake_stats(current_user["id"])


@router.get("/analysis", response_model=MistakeAnalysisResponse)
async def analysis(current_user: dict = Depends(get_current_user)):
    return MistakeAnalysisResponse(**get_mistake_analysis(current_user["id"]))

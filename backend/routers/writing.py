from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import re
import time
from uuid import uuid4
from ..deps import get_current_user
from ..db import (
    save_mistake,
    create_writing_submission,
    list_user_writing_submissions,
    claim_writing_submission_for_review,
    get_writing_submission,
    create_writing_peer_review,
    list_reviews_for_submission,
    list_received_writing_reviews,
)
from ..services.mistake_taxonomy import normalize_writing_dim_error_type, normalize_writing_feedback_error_type
from backend.utils.tracking import get_learning_tracker

router = APIRouter()

# Task 1 图表类型字面量
Task1Type = Literal["chart", "graph", "table", "diagram"]

class Task1WritingRequest(BaseModel):
    """Task 1 写作请求模型"""
    text: str = Field(..., min_length=10, description="写作内容")
    chart_type: Task1Type = Field(..., description="图表类型")
    topic: str = Field(..., description="写作主题")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")

class Task1FeedbackItem(BaseModel):
    """写作反馈项"""
    category: str  # structure/content/vocabulary/grammar
    severity: str  # low/medium/high
    message: str  # 反馈内容
    suggestion: str  # 改进建议
    position: Optional[int] = None  # 在文本中的位置

class Task1Analysis(BaseModel):
    """Task 1 写作分析结果"""
    structure_score: int  # 结构分数 (0-10)
    content_score: int     # 内容分数 (0-10)
    vocabulary_score: int  # 词汇分数 (0-10)
    grammar_score: int     # 语法分数 (0-10)
    total_score: int       # 总分 (0-40)
    feedback: List[Task1FeedbackItem]
    common_mistakes: List[str]
    improvement_tips: List[str]

class Task1Practice(BaseModel):
    """Task 1 练习记录"""
    id: int
    user_id: int
    text: str
    chart_type: Task1Type
    topic: str
    keywords: Optional[List[str]]
    analysis: Optional[Task1Analysis]
    created_at: str
    updated_at: str

class Task1CommonStructure(BaseModel):
    """Task 1 常用结构"""
    type: str
    example: str
    explanation: str

# 模拟的Task 1常用结构
task1_structures = [
    {
        "type": "introduction",
        "example": "The line graph illustrates changes in the number of people using smartphones in the UK from 2010 to 2020.",
        "explanation": "引言部分，介绍图表类型、主题和时间范围"
    },
    {
        "type": "overview",
        "example": "Overall, smartphone usage increased significantly over the period, with the highest growth occurring between 2015 and 2018.",
        "explanation": "概述部分，总结主要趋势或变化"
    },
    {
        "type": "detail",
        "example": "In 2010, approximately 30% of the population used smartphones, rising steadily to 70% by 2015.",
        "explanation": "细节部分，提供具体数据和变化"
    },
    {
        "type": "comparison",
        "example": "While urban areas saw faster growth, rural regions also experienced a notable increase in smartphone adoption.",
        "explanation": "比较部分，对比不同类别或时间段"
    }
]

# 模拟的Task 1常用词汇
task1_vocabulary = {
    "trend": ["increase", "decrease", "rise", "fall", "fluctuate", "stabilize"],
    "comparison": ["while", "whereas", "by contrast", "similarly", "in comparison"],
    "quantity": ["approximately", "around", "about", "just over", "slightly under"],
    "time": ["over the period", "between...and...", "from...to...", "by the end of", "during"]
}


def _calc_overall_band(tr_score: float, cc_score: float, lr_score: float, gra_score: float) -> float:
    return round((float(tr_score) + float(cc_score) + float(lr_score) + float(gra_score)) / 4.0, 2)


def _calc_review_quality_tier(comment_text: str, strengths: str, improvements: str) -> str:
    text = f"{comment_text} {strengths} {improvements}".strip()
    words = len(re.findall(r"[A-Za-z\u4e00-\u9fff]+", text))
    if words >= 60:
        return "advanced"
    if words >= 25:
        return "standard"
    return "basic"

# 基础语法检查规则
grammar_rules = {
    "capitalization": r"^(\s*[a-z])",  # 句子开头小写
    "missing_punctuation": r"[a-zA-Z0-9]\s*$",  # 句子结尾缺少标点
    "common_misspellings": {
        "teh": "the",
        "wtih": "with",
        "becuase": "because",
        "thier": "their",
        "your": "you're",
        "its": "it's"
    }  # 常见拼写错误
}

def check_basic_grammar(text: str) -> tuple[List[Dict[str, Any]], int]:
    """基础语法检查"""
    errors = []
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    
    # 检查句子开头大写
    for i, sentence in enumerate(sentences):
        if sentence and sentence[0].islower():
            position = text.find(sentence)
            errors.append({
                "category": "grammar",
                "severity": "low",
                "message": "句子开头应为大写字母",
                "suggestion": f"将 '{sentence[0]}' 改为 '{sentence[0].upper()}'",
                "position": position
            })
    
    # 检查句子结尾标点
    for i, sentence in enumerate(sentences):
        if sentence and not sentence[-1] in '.!?':
            position = text.find(sentence) + len(sentence) - 1
            errors.append({
                "category": "grammar",
                "severity": "low",
                "message": "句子结尾缺少适当标点",
                "suggestion": "添加句号、问号或感叹号",
                "position": position
            })
    
    # 检查常见拼写错误
    for wrong, correct in grammar_rules["common_misspellings"].items():
        start_pos = 0
        while True:
            pos = text.lower().find(wrong, start_pos)
            if pos == -1:
                break
            # 确保不是其他单词的一部分
            if (pos == 0 or not text[pos-1].isalnum()) and (pos + len(wrong) == len(text) or not text[pos+len(wrong)].isalnum()):
                errors.append({
                    "category": "grammar",
                    "severity": "low",
                    "message": f"可能的拼写错误：'{wrong}'",
                    "suggestion": f"改为 '{correct}'",
                    "position": pos
                })
            start_pos = pos + 1
    
    # 计算语法分数（基础版）
    base_score = 10
    for error in errors:
        base_score -= 0.5  # 每个错误扣0.5分
    grammar_score = max(5, round(base_score))  # 最低5分
    
    return errors, grammar_score

@router.post("/task1/analyze", response_model=Task1Analysis)
async def analyze_task1_writing(req: Task1WritingRequest, current_user: dict = Depends(get_current_user)):
    """分析Task 1 (Academic)写作内容"""
    if not req.text:
        raise HTTPException(status_code=400, detail="写作内容不能为空")

    # 简单的结构分析
    sentences = [s.strip() for s in req.text.split('.') if s.strip()]
    has_introduction = any("illustrates" in s.lower() or "shows" in s.lower() for s in sentences[:2])
    has_overview = any("overall" in s.lower() or "in summary" in s.lower() for s in sentences[:3])

    # 评分（基础版，后续可升级为AI模型）
    structure_score = 7 if has_introduction and has_overview else 5
    content_score = 8 if len(sentences) > 5 else 6
    vocabulary_score = 7 if any(word in req.text.lower() for word in task1_vocabulary["trend"] + task1_vocabulary["comparison"]) else 5
    
    # 基础语法检查
    grammar_errors, grammar_score = check_basic_grammar(req.text)

    total_score = (structure_score + content_score + vocabulary_score + grammar_score) * 2  # 换算成0-40分制

    # 生成反馈
    feedback = []
    
    # 添加语法错误反馈
    for error in grammar_errors:
        feedback.append(Task1FeedbackItem(**error))
    if not has_introduction:
        feedback.append(Task1FeedbackItem(
            category="structure",
            severity="medium",
            message="缺少引言部分",
            suggestion="建议在开头明确说明图表类型、主题和时间范围",
            position=0
        ))
    if not has_overview:
        feedback.append(Task1FeedbackItem(
            category="structure",
            severity="medium",
            message="缺少概述部分",
            suggestion="建议在引言后添加一个段落总结主要趋势",
            position=0
        ))

    # 常见错误和改进建议
    common_mistakes = []
    improvement_tips = []

    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪练习完成
    exercise_data = {
        "exercise_id": f"writing_task1_{current_user['id']}_{int(time.time())}",
        "type": "writing_task1",
        "difficulty": "medium",
        "completed": True,
        "correct": False,  # 写作练习没有明确的正确/错误
        "attempts": 1,
        "time_spent": 0,  # 后续可添加时间统计
        "feedback": len(feedback),
        "score": total_score,
        "metadata": {
            "chart_type": req.chart_type,
            "topic": req.topic,
            "keywords": req.keywords,
            "sentence_count": len(sentences)
        }
    }
    learning_tracker.track_exercise(current_user["id"], exercise_data)
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user["id"], 
        "writing_task1_analysis",
        {"chart_type": req.chart_type, "topic": req.topic}
    )

    # 写作弱项自动沉淀到错题本，统一进入复习链路
    # 仅记录中高严重度反馈，避免噪声过多
    for item in feedback:
        if item.severity not in {"medium", "high"}:
            continue
        normalized_error_type = normalize_writing_feedback_error_type(item.category)
        save_mistake(
            str(uuid4()),
            str(current_user["id"]),
            {
                "module": "writing",
                "question_id": f"task1_{req.chart_type}_{int(time.time())}",
                "question_type": "writing_task1",
                "error_type": normalized_error_type,
                "content": item.message,
                "user_answer": "",
                "correct_answer": "",
                "explanation": item.suggestion,
                "difficulty": "intermediate",
                "tags": ["writing_task1", item.category, f"error_type:{normalized_error_type}", "taxonomy:v1"],
            },
        )

    # 分维度低分也做聚合沉淀
    dim_scores = {
        "structure": structure_score,
        "content": content_score,
        "vocabulary": vocabulary_score,
        "grammar": grammar_score,
    }
    for dim, score in dim_scores.items():
        if int(score) < 6:
            normalized_error_type = normalize_writing_dim_error_type(dim)
            save_mistake(
                str(uuid4()),
                str(current_user["id"]),
                {
                    "module": "writing",
                    "question_id": f"task1_dim_{dim}_{int(time.time())}",
                    "question_type": "writing_task1",
                    "error_type": normalized_error_type,
                    "content": f"Task 1 {dim} score below target.",
                    "user_answer": str(score),
                    "correct_answer": ">=6",
                    "explanation": f"Current {dim} score is {score}. Follow feedback suggestions for improvement.",
                    "difficulty": "intermediate",
                    "tags": ["writing_task1", f"low_{dim}", f"error_type:{normalized_error_type}", "taxonomy:v1"],
                },
            )

    return Task1Analysis(
        structure_score=structure_score,
        content_score=content_score,
        vocabulary_score=vocabulary_score,
        grammar_score=grammar_score,
        total_score=total_score,
        feedback=feedback,
        common_mistakes=common_mistakes,
        improvement_tips=improvement_tips
    )

@router.post("/task1/practice")
async def save_task1_practice(req: Task1WritingRequest, current_user: dict = Depends(get_current_user)):
    """保存Task 1 写作练习"""
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪练习保存
    exercise_data = {
        "exercise_id": f"writing_task1_save_{current_user['id']}_{int(time.time())}",
        "type": "writing_task1_save",
        "difficulty": "medium",
        "completed": True,
        "correct": False,
        "attempts": 1,
        "time_spent": 0,
        "feedback": 0,
        "score": 0,  # 保存时还没有评分
        "metadata": {
            "chart_type": req.chart_type,
            "topic": req.topic,
            "keywords": req.keywords,
            "text_length": len(req.text)
        }
    }
    learning_tracker.track_exercise(current_user["id"], exercise_data)
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user["id"], 
        "writing_task1_save",
        {"chart_type": req.chart_type, "topic": req.topic}
    )
    
    # 后续实现数据库存储
    return {
        "id": f"writing_task1_{current_user['id']}_{int(time.time())}",
        "message": "练习已保存",
        "data": {
            "task_id": f"writing_task1_{current_user['id']}_{int(time.time())}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        }
    }

@router.get("/task1/practices")
async def get_task1_practices(page: int = 1, limit: int = 10, current_user: dict = Depends(get_current_user)):
    """获取Task 1 写作练习历史"""
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user["id"], 
        "writing_task1_practices",
        {"page": page, "limit": limit}
    )
    
    # 后续实现数据库查询
    return {
        "page": page,
        "limit": limit,
        "total": 0,
        "practices": []
    }

@router.get("/task1/common-structures")
async def get_common_task1_structures(chart_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """获取Task 1 常用写作结构"""
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user["id"], 
        "writing_task1_structures",
        {"chart_type": chart_type}
    )
    
    filtered_structures = task1_structures
    if chart_type:
        # 后续根据图表类型过滤结构
        filtered_structures = task1_structures
    return {
        "structures": filtered_structures
    }

@router.get("/task1/common-vocabulary")
async def get_common_task1_vocabulary(category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """获取Task 1 常用词汇"""
    # 采集学习数据
    learning_tracker = get_learning_tracker()
    
    # 跟踪功能使用
    learning_tracker.track_feature_usage(
        current_user["id"], 
        "writing_task1_vocabulary",
        {"category": category}
    )
    
    filtered_vocab = task1_vocabulary
    if category and category in task1_vocabulary:
        filtered_vocab = {category: task1_vocabulary[category]}
    return {
        "vocabulary": filtered_vocab
    }


class PeerSubmissionCreateRequest(BaseModel):
    task_type: Literal["task1", "task2"] = "task1"
    topic: str
    content: str = Field(..., min_length=30)


class PeerSubmissionItem(BaseModel):
    id: str
    task_type: str
    topic: str
    content: str
    status: str
    review_count: int
    avg_overall_score: float
    created_at: int
    updated_at: int


class PeerSubmissionCreateResponse(BaseModel):
    submission_id: str
    status: str
    message: str


class PeerReviewClaimResponse(BaseModel):
    claimed: bool
    submission: Optional[PeerSubmissionItem] = None
    message: str = ""


class PeerReviewSubmitRequest(BaseModel):
    submission_id: str
    tr_score: float = Field(..., ge=0, le=9)
    cc_score: float = Field(..., ge=0, le=9)
    lr_score: float = Field(..., ge=0, le=9)
    gra_score: float = Field(..., ge=0, le=9)
    strengths: str = ""
    improvements: str = ""
    comment_text: str = ""


class PeerReviewItem(BaseModel):
    id: str
    submission_id: str
    reviewer_id: str
    reviewee_id: str
    tr_score: float
    cc_score: float
    lr_score: float
    gra_score: float
    overall_score: float
    strengths: str
    improvements: str
    comment_text: str
    quality_tier: str
    created_at: int
    task_type: Optional[str] = None
    topic: Optional[str] = None


class PeerReviewSubmitResponse(BaseModel):
    review_id: str
    submission_id: str
    overall_score: float
    quality_tier: str
    message: str


@router.post("/peer/submit", response_model=PeerSubmissionCreateResponse)
async def submit_peer_writing(req: PeerSubmissionCreateRequest, current_user: dict = Depends(get_current_user)):
    submission_id = str(uuid4())
    create_writing_submission(
        submission_id=submission_id,
        user_id=str(current_user["id"]),
        task_type=req.task_type,
        topic=req.topic,
        content=req.content,
    )
    return PeerSubmissionCreateResponse(
        submission_id=submission_id,
        status="open",
        message="已加入互评池，等待他人点评。",
    )


@router.get("/peer/submissions", response_model=List[PeerSubmissionItem])
async def get_my_peer_submissions(limit: int = 20, current_user: dict = Depends(get_current_user)):
    rows = list_user_writing_submissions(user_id=str(current_user["id"]), limit=limit)
    return [
        PeerSubmissionItem(
            id=str(x["id"]),
            task_type=str(x.get("task_type") or "task1"),
            topic=str(x.get("topic") or ""),
            content=str(x.get("content") or ""),
            status=str(x.get("status") or "open"),
            review_count=int(x.get("review_count") or 0),
            avg_overall_score=float(x.get("avg_overall_score") or 0.0),
            created_at=int(x.get("created_at") or 0),
            updated_at=int(x.get("updated_at") or 0),
        )
        for x in rows
    ]


@router.post("/peer/claim", response_model=PeerReviewClaimResponse)
async def claim_peer_submission(current_user: dict = Depends(get_current_user)):
    row = claim_writing_submission_for_review(reviewer_id=str(current_user["id"]))
    if not row:
        return PeerReviewClaimResponse(claimed=False, submission=None, message="当前没有可领取的互评作文。")
    item = PeerSubmissionItem(
        id=str(row["id"]),
        task_type=str(row.get("task_type") or "task1"),
        topic=str(row.get("topic") or ""),
        content=str(row.get("content") or ""),
        status=str(row.get("status") or "in_review"),
        review_count=int(row.get("review_count") or 0),
        avg_overall_score=float(row.get("avg_overall_score") or 0.0),
        created_at=int(row.get("created_at") or 0),
        updated_at=int(row.get("updated_at") or 0),
    )
    return PeerReviewClaimResponse(claimed=True, submission=item, message="已领取1篇互评任务。")


@router.post("/peer/review", response_model=PeerReviewSubmitResponse)
async def submit_peer_review(req: PeerReviewSubmitRequest, current_user: dict = Depends(get_current_user)):
    submission = get_writing_submission(req.submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    reviewee_id = str(submission.get("user_id") or "")
    reviewer_id = str(current_user["id"])
    if reviewee_id == reviewer_id:
        raise HTTPException(status_code=400, detail="Cannot review your own submission")

    overall_score = _calc_overall_band(req.tr_score, req.cc_score, req.lr_score, req.gra_score)
    quality_tier = _calc_review_quality_tier(req.comment_text, req.strengths, req.improvements)
    review_id = str(uuid4())
    try:
        create_writing_peer_review(
            review_id=review_id,
            submission_id=req.submission_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            tr_score=req.tr_score,
            cc_score=req.cc_score,
            lr_score=req.lr_score,
            gra_score=req.gra_score,
            overall_score=overall_score,
            strengths=req.strengths,
            improvements=req.improvements,
            comment_text=req.comment_text,
            quality_tier=quality_tier,
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=400, detail="You already reviewed this submission") from exc
        raise

    return PeerReviewSubmitResponse(
        review_id=review_id,
        submission_id=req.submission_id,
        overall_score=overall_score,
        quality_tier=quality_tier,
        message="互评提交成功。",
    )


@router.get("/peer/reviews/received", response_model=List[PeerReviewItem])
async def get_received_peer_reviews(submission_id: Optional[str] = None, limit: int = 30, current_user: dict = Depends(get_current_user)):
    if submission_id:
        submission = get_writing_submission(submission_id)
        if not submission or str(submission.get("user_id")) != str(current_user["id"]):
            raise HTTPException(status_code=404, detail="Submission not found")
        rows = list_reviews_for_submission(submission_id, limit=limit)
        return [
            PeerReviewItem(
                id=str(x["id"]),
                submission_id=str(x["submission_id"]),
                reviewer_id=str(x["reviewer_id"]),
                reviewee_id=str(x["reviewee_id"]),
                tr_score=float(x["tr_score"]),
                cc_score=float(x["cc_score"]),
                lr_score=float(x["lr_score"]),
                gra_score=float(x["gra_score"]),
                overall_score=float(x["overall_score"]),
                strengths=str(x.get("strengths") or ""),
                improvements=str(x.get("improvements") or ""),
                comment_text=str(x.get("comment_text") or ""),
                quality_tier=str(x.get("quality_tier") or "basic"),
                created_at=int(x.get("created_at") or 0),
            )
            for x in rows
        ]

    rows = list_received_writing_reviews(user_id=str(current_user["id"]), limit=limit)
    return [
        PeerReviewItem(
            id=str(x["id"]),
            submission_id=str(x["submission_id"]),
            reviewer_id=str(x["reviewer_id"]),
            reviewee_id=str(x["reviewee_id"]),
            tr_score=float(x["tr_score"]),
            cc_score=float(x["cc_score"]),
            lr_score=float(x["lr_score"]),
            gra_score=float(x["gra_score"]),
            overall_score=float(x["overall_score"]),
            strengths=str(x.get("strengths") or ""),
            improvements=str(x.get("improvements") or ""),
            comment_text=str(x.get("comment_text") or ""),
            quality_tier=str(x.get("quality_tier") or "basic"),
            created_at=int(x.get("created_at") or 0),
            task_type=str(x.get("task_type") or ""),
            topic=str(x.get("topic") or ""),
        )
        for x in rows
    ]

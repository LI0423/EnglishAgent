from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import re
import time
import hashlib
import os
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
    get_writing_peer_stats,
    list_writing_peer_leaderboard,
    create_gamification_event,
    get_user_entitlement_balance,
    consume_user_entitlement,
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


class Task2WritingRequest(BaseModel):
    """Task 2 写作请求模型"""
    text: str = Field(..., min_length=30, description="写作内容")
    topic: str = Field(..., description="写作题目")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    stance: Optional[str] = Field(None, description="立场（agree/disagree/balanced）")

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


class Task2BrainstormResponse(BaseModel):
    topic: str
    thesis_options: List[str]
    arguments_for: List[str]
    arguments_against: List[str]
    example_angles: List[str]
    paragraph_outline: List[str]
    conclusion_frame: str


class Task2BrainstormRequest(BaseModel):
    topic: str
    keywords: Optional[List[str]] = None
    stance: Optional[str] = None

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

task2_structures = [
    "开头段：改写题目 + 明确立场（thesis）",
    "主体段1：主论点 + 解释 + 具体例子",
    "主体段2：次论点/反驳段 + 解释 + 具体例子",
    "结尾段：重申立场 + 总结影响",
]


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


def _build_reviewer_alias(user_id: str) -> str:
    suffix = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()[:6].upper()
    return f"互评同学#{suffix}"


def _safe_range_score(value: float) -> float:
    return max(0.0, min(9.0, round(float(value), 1)))


def _ai_assist_for_peer_review(content: str, task_type: str = "task1") -> Dict[str, Any]:
    text = str(content or "").strip()
    words = re.findall(r"[A-Za-z]+", text)
    word_count = len(words)
    sentences = [x.strip() for x in re.split(r"[.!?]+", text) if x.strip()]
    paragraphs = [x.strip() for x in text.split("\n") if x.strip()]
    grammar_errors, grammar_score_base = check_basic_grammar(text)

    connectors = [
        "however", "therefore", "moreover", "in addition", "for example",
        "for instance", "while", "although", "because", "as a result",
    ]
    connector_hits = sum(1 for c in connectors if c in text.lower())
    unique_ratio = (len(set(w.lower() for w in words)) / word_count) if word_count > 0 else 0.0

    tr = 5.5
    cc = 5.5
    lr = 5.5
    gra = float(grammar_score_base)

    if task_type == "task1":
        if word_count >= 150:
            tr += 1.0
        if "overall" in text.lower():
            tr += 0.5
    else:
        if word_count >= 250:
            tr += 1.0
        if any(k in text.lower() for k in ["in conclusion", "to conclude", "in summary"]):
            tr += 0.5

    if len(paragraphs) >= 3:
        cc += 0.7
    if connector_hits >= 3:
        cc += 0.8
    elif connector_hits >= 1:
        cc += 0.4

    if unique_ratio >= 0.58:
        lr += 1.1
    elif unique_ratio >= 0.50:
        lr += 0.7
    elif unique_ratio >= 0.42:
        lr += 0.3

    if len(sentences) >= 6:
        gra += 0.3
    if len(grammar_errors) >= 4:
        gra -= 0.7
    elif len(grammar_errors) >= 2:
        gra -= 0.3

    tr = _safe_range_score(tr)
    cc = _safe_range_score(cc)
    lr = _safe_range_score(lr)
    gra = _safe_range_score(gra)
    overall = _calc_overall_band(tr, cc, lr, gra)

    strengths: list[str] = []
    improvements: list[str] = []

    if word_count >= (250 if task_type == "task2" else 150):
        strengths.append("篇幅达标，任务完成度基础较好。")
    if connector_hits >= 2:
        strengths.append("衔接词使用较自然，段落逻辑较连贯。")
    if unique_ratio >= 0.5:
        strengths.append("词汇有一定变化，重复率控制较好。")
    if gra >= 6.5:
        strengths.append("语法准确性较稳，明显错误较少。")

    if not strengths:
        strengths.append("整体有清晰表达，具备继续打磨的基础。")

    if task_type == "task1" and "overall" not in text.lower():
        improvements.append("建议补充明确的 Overall 句，总结核心趋势。")
    if len(paragraphs) < 3:
        improvements.append("建议至少分为3段，提升结构可读性。")
    if connector_hits < 2:
        improvements.append("增加连接词（however/therefore/in addition）强化逻辑衔接。")
    if unique_ratio < 0.45:
        improvements.append("提升词汇多样性，减少高频词重复。")
    if len(grammar_errors) >= 2:
        improvements.append("优先修正常见语法与拼写错误，提高 GRA 稳定性。")

    if not improvements:
        improvements.append("可在例证深度与句式多样性上继续拉开分差。")

    sample_comment = (
        f"这篇作文估计在 {overall:.1f} 分左右。"
        f"优势在于{strengths[0]}；"
        f"建议优先改进：{improvements[0]}"
    )

    return {
        "estimated_scores": {
            "tr_score": tr,
            "cc_score": cc,
            "lr_score": lr,
            "gra_score": gra,
            "overall_score": overall,
        },
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "sample_comment": sample_comment,
        "meta": {
            "word_count": word_count,
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "grammar_issue_count": len(grammar_errors),
        },
    }


def _guard_and_consume_writing_review_entitlement(
    user_id: str,
    request_id: str,
    *,
    endpoint: str = "task1_analyze",
    note: str = "写作Task1 AI批改扣减1次",
) -> None:
    strict = str(os.environ.get("PAYMENT_REQUIRE_WRITING_REVIEW", "0")).strip() in {"1", "true", "yes"}
    balance = get_user_entitlement_balance(str(user_id), "writing_ai_review")
    if balance is None:
        if strict:
            raise HTTPException(status_code=402, detail="写作AI批改权益不足，请先在支付中心购买次数包")
        return
    if int(balance) <= 0:
        raise HTTPException(status_code=402, detail="写作AI批改权益已用尽，请前往支付中心续费")
    ok = consume_user_entitlement(
        user_id=str(user_id),
        feature_code="writing_ai_review",
        amount=1,
        source_type="writing_analyze",
        source_id=str(request_id),
        note=note,
        metadata={"module": "writing", "endpoint": endpoint},
    )
    if not ok:
        raise HTTPException(status_code=402, detail="写作AI批改权益扣减失败，请稍后重试")

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
    _guard_and_consume_writing_review_entitlement(
        str(current_user["id"]),
        str(uuid4()),
        endpoint="task1_analyze",
        note="写作Task1 AI批改扣减1次",
    )

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


@router.post("/task2/analyze", response_model=Task1Analysis)
async def analyze_task2_writing(req: Task2WritingRequest, current_user: dict = Depends(get_current_user)):
    """分析Task 2写作内容（独立链路）"""
    if not req.text:
        raise HTTPException(status_code=400, detail="写作内容不能为空")

    _guard_and_consume_writing_review_entitlement(
        str(current_user["id"]),
        str(uuid4()),
        endpoint="task2_analyze",
        note="写作Task2 AI批改扣减1次",
    )

    text = str(req.text or "").strip()
    text_lower = text.lower()
    words = re.findall(r"[A-Za-z]+", text)
    word_count = len(words)
    paragraphs = [x.strip() for x in text.split("\n") if x.strip()]
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]

    grammar_errors, grammar_score = check_basic_grammar(text)

    thesis_markers = ["i agree", "i disagree", "i believe", "in my opinion", "this essay will"]
    logic_markers = ["firstly", "secondly", "however", "therefore", "moreover", "for example", "in conclusion"]
    evidence_markers = ["for example", "for instance", "data", "study", "research", "evidence"]
    counter_markers = ["although", "while", "opponents", "on the other hand", "admittedly"]

    has_thesis = any(k in text_lower for k in thesis_markers)
    logic_hits = sum(1 for k in logic_markers if k in text_lower)
    evidence_hits = sum(1 for k in evidence_markers if k in text_lower)
    counter_hits = sum(1 for k in counter_markers if k in text_lower)
    unique_ratio = (len(set(w.lower() for w in words)) / word_count) if word_count > 0 else 0.0

    structure_score = 5
    if has_thesis:
        structure_score += 2
    if len(paragraphs) >= 4:
        structure_score += 2
    if any("in conclusion" in s.lower() or "to conclude" in s.lower() for s in sentences):
        structure_score += 1
    structure_score = max(0, min(9, structure_score))

    content_score = 5
    if word_count >= 250:
        content_score += 1
    if evidence_hits >= 2:
        content_score += 2
    if counter_hits >= 1:
        content_score += 1
    if req.keywords:
        keyword_hits = sum(1 for k in req.keywords if str(k).lower() in text_lower)
        if keyword_hits >= max(1, len(req.keywords) // 2):
            content_score += 1
    content_score = max(0, min(9, content_score))

    vocabulary_score = 5
    if unique_ratio >= 0.58:
        vocabulary_score += 2
    elif unique_ratio >= 0.50:
        vocabulary_score += 1
    if any(x in text_lower for x in ["significant", "sustainable", "substantial", "consequence", "policy"]):
        vocabulary_score += 1
    if any(x in text_lower for x in ["beneficial", "detrimental", "feasible", "equitable"]):
        vocabulary_score += 1
    vocabulary_score = max(0, min(9, vocabulary_score))

    grammar_score = max(0, min(9, int(round(grammar_score))))
    if len(sentences) >= 8:
        grammar_score = min(9, grammar_score + 1)
    if len(grammar_errors) >= 5:
        grammar_score = max(0, grammar_score - 1)

    total_score = (structure_score + content_score + vocabulary_score + grammar_score) * 2

    feedback: List[Task1FeedbackItem] = []
    for error in grammar_errors:
        feedback.append(Task1FeedbackItem(**error))
    if not has_thesis:
        feedback.append(
            Task1FeedbackItem(
                category="structure",
                severity="high",
                message="立场表达不够明确",
                suggestion="在开头用一句 thesis 明确你的观点（同意/不同意/折中）。",
                position=0,
            )
        )
    if len(paragraphs) < 4:
        feedback.append(
            Task1FeedbackItem(
                category="structure",
                severity="medium",
                message="段落组织偏少",
                suggestion="建议使用四段式：引言、主体1、主体2、结论。",
                position=0,
            )
        )
    if evidence_hits < 2:
        feedback.append(
            Task1FeedbackItem(
                category="content",
                severity="medium",
                message="论据支撑偏弱",
                suggestion="每个主体段补充具体例子或数据支撑论点。",
                position=0,
            )
        )
    if logic_hits < 3:
        feedback.append(
            Task1FeedbackItem(
                category="content",
                severity="medium",
                message="逻辑衔接不足",
                suggestion="增加逻辑连接词（however/therefore/moreover）并明确因果关系。",
                position=0,
            )
        )

    common_mistakes: List[str] = []
    if not has_thesis:
        common_mistakes.append("thesis_missing")
    if evidence_hits < 2:
        common_mistakes.append("weak_supporting_examples")
    if len(paragraphs) < 4:
        common_mistakes.append("paragraph_structure_weak")
    if logic_hits < 3:
        common_mistakes.append("cohesion_markers_insufficient")
    if len(grammar_errors) >= 2:
        common_mistakes.append("grammar_surface_errors")

    improvement_tips = [
        "先写 thesis 再展开两个主体段，每段只讲一个核心论点。",
        "每个主体段使用“观点-解释-例子”三步结构。",
        "结尾段避免新观点，聚焦总结与立场重申。",
    ]

    learning_tracker = get_learning_tracker()
    exercise_data = {
        "exercise_id": f"writing_task2_{current_user['id']}_{int(time.time())}",
        "type": "writing_task2",
        "difficulty": "medium",
        "completed": True,
        "correct": False,
        "attempts": 1,
        "time_spent": 0,
        "feedback": len(feedback),
        "score": total_score,
        "metadata": {
            "topic": req.topic,
            "keyword_count": len(req.keywords or []),
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
        },
    }
    learning_tracker.track_exercise(current_user["id"], exercise_data)
    learning_tracker.track_feature_usage(
        current_user["id"],
        "writing_task2_analysis",
        {"topic": req.topic, "stance": req.stance or ""},
    )

    for item in feedback:
        if item.severity not in {"medium", "high"}:
            continue
        normalized_error_type = normalize_writing_feedback_error_type(item.category)
        save_mistake(
            str(uuid4()),
            str(current_user["id"]),
            {
                "module": "writing",
                "question_id": f"task2_{int(time.time())}",
                "question_type": "writing_task2",
                "error_type": normalized_error_type,
                "content": item.message,
                "user_answer": "",
                "correct_answer": "",
                "explanation": item.suggestion,
                "difficulty": "intermediate",
                "tags": ["writing_task2", item.category, f"error_type:{normalized_error_type}", "taxonomy:v1"],
            },
        )

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
                    "question_id": f"task2_dim_{dim}_{int(time.time())}",
                    "question_type": "writing_task2",
                    "error_type": normalized_error_type,
                    "content": f"Task 2 {dim} score below target.",
                    "user_answer": str(score),
                    "correct_answer": ">=6",
                    "explanation": f"Current {dim} score is {score}. Follow feedback suggestions for improvement.",
                    "difficulty": "intermediate",
                    "tags": ["writing_task2", f"low_{dim}", f"error_type:{normalized_error_type}", "taxonomy:v1"],
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
        improvement_tips=improvement_tips,
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


@router.post("/task2/practice")
async def save_task2_practice(req: Task2WritingRequest, current_user: dict = Depends(get_current_user)):
    """保存Task 2 写作练习"""
    learning_tracker = get_learning_tracker()
    exercise_data = {
        "exercise_id": f"writing_task2_save_{current_user['id']}_{int(time.time())}",
        "type": "writing_task2_save",
        "difficulty": "medium",
        "completed": True,
        "correct": False,
        "attempts": 1,
        "time_spent": 0,
        "feedback": 0,
        "score": 0,
        "metadata": {
            "topic": req.topic,
            "keywords": req.keywords,
            "text_length": len(req.text),
        },
    }
    learning_tracker.track_exercise(current_user["id"], exercise_data)
    learning_tracker.track_feature_usage(
        current_user["id"],
        "writing_task2_save",
        {"topic": req.topic},
    )
    return {
        "id": f"writing_task2_{current_user['id']}_{int(time.time())}",
        "message": "练习已保存",
        "data": {
            "task_id": f"writing_task2_{current_user['id']}_{int(time.time())}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        },
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


@router.get("/task2/common-structures")
async def get_common_task2_structures(current_user: dict = Depends(get_current_user)):
    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "writing_task2_structures",
        {},
    )
    return {"structures": task2_structures}


@router.post("/task2/brainstorm", response_model=Task2BrainstormResponse)
async def brainstorm_task2(req: Task2BrainstormRequest, current_user: dict = Depends(get_current_user)):
    topic = str(req.topic or "").strip() or "Task 2 Topic"
    keywords = [str(x).strip() for x in (req.keywords or []) if str(x).strip()]
    kw_text = ", ".join(keywords[:4]) if keywords else "cost, fairness, long-term impact"
    thesis_options = [
        f"I largely agree that {topic.lower()} should be prioritized because long-term social benefits outweigh short-term costs.",
        f"While {topic.lower()} has merits, a balanced approach is more practical for different stakeholder groups.",
        f"I disagree that {topic.lower()} is always effective; outcomes depend heavily on policy design and local context.",
    ]
    arguments_for = [
        "可提升长期社会收益与系统效率。",
        "能减少结构性不平等，扩大机会可及性。",
        "在政策连续性下，边际收益会逐步放大。",
    ]
    arguments_against = [
        "短期财政或执行成本较高。",
        "若缺乏配套制度，可能产生实施偏差。",
        "不同地区条件差异大，统一政策效果不稳。",
    ]
    example_angles = [
        f"公共政策案例：围绕 {kw_text} 展开对比。",
        "教育/就业场景中的群体差异案例。",
        "短期收益与长期影响冲突的反例。",
    ]
    paragraph_outline = [
        "引言：改写题目并给出明确立场。",
        "主体段1：主论点 + 原因解释 + 具体例子。",
        "主体段2：反方观点或限制条件 + 反驳/让步。",
        "结论：重申立场并给出可执行建议。",
    ]
    conclusion_frame = "In conclusion, although there are valid concerns, a carefully designed approach can maximize benefits while minimizing trade-offs."
    learning_tracker = get_learning_tracker()
    learning_tracker.track_feature_usage(
        current_user["id"],
        "writing_task2_brainstorm",
        {"topic": topic, "keyword_count": len(keywords)},
    )
    return Task2BrainstormResponse(
        topic=topic,
        thesis_options=thesis_options,
        arguments_for=arguments_for,
        arguments_against=arguments_against,
        example_angles=example_angles,
        paragraph_outline=paragraph_outline,
        conclusion_frame=conclusion_frame,
    )


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
    reviewer_alias: Optional[str] = None


class PeerReviewSubmitResponse(BaseModel):
    review_id: str
    submission_id: str
    overall_score: float
    quality_tier: str
    message: str


class PeerReviewAssistRequest(BaseModel):
    submission_id: Optional[str] = None
    task_type: Literal["task1", "task2"] = "task1"
    topic: str = ""
    content: str = ""


class PeerReviewAssistResponse(BaseModel):
    tr_score: float
    cc_score: float
    lr_score: float
    gra_score: float
    overall_score: float
    strengths: List[str]
    improvements: List[str]
    sample_comment: str
    quality_hint: str
    meta: Dict[str, Any]


class PeerStatsResponse(BaseModel):
    user_id: str
    total_submissions: int
    open_submissions: int
    in_review_submissions: int
    reviewed_submissions: int
    avg_received_score: float
    total_reviews_written: int
    avg_given_score: float
    quality_counts: Dict[str, int]
    total_points: int
    reviewer_level: str
    reviewer_badges: List[str]


class PeerLeaderboardItem(BaseModel):
    reviewer_id: str
    reviewer_alias: str
    total_reviews: int
    avg_given_score: float
    advanced_count: int
    standard_count: int
    basic_count: int
    total_points: int
    rank: int


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

    reward_points = 1 if quality_tier == "basic" else (3 if quality_tier == "standard" else 6)
    create_gamification_event(
        str(uuid4()),
        user_id=reviewer_id,
        source="writing_peer_review",
        source_id=review_id,
        points=reward_points,
        note=f"完成作文互评（{quality_tier}）",
        metadata={
            "submission_id": req.submission_id,
            "quality_tier": quality_tier,
            "overall_score": overall_score,
        },
    )

    return PeerReviewSubmitResponse(
        review_id=review_id,
        submission_id=req.submission_id,
        overall_score=overall_score,
        quality_tier=quality_tier,
        message="互评提交成功。",
    )


@router.post("/peer/review/assist", response_model=PeerReviewAssistResponse)
async def get_peer_review_ai_assist(req: PeerReviewAssistRequest, current_user: dict = Depends(get_current_user)):
    text = str(req.content or "").strip()
    task_type = req.task_type
    if req.submission_id:
        submission = get_writing_submission(req.submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        if str(submission.get("user_id")) == str(current_user["id"]):
            raise HTTPException(status_code=400, detail="Cannot assist your own submission review")
        text = str(submission.get("content") or "").strip()
        task_type = str(submission.get("task_type") or task_type)

    if len(text) < 30:
        raise HTTPException(status_code=400, detail="Content is too short for review assist")

    assist = _ai_assist_for_peer_review(text, task_type=task_type)
    est = assist["estimated_scores"]
    quality_hint = _calc_review_quality_tier(
        assist.get("sample_comment", ""),
        " ".join(assist.get("strengths") or []),
        " ".join(assist.get("improvements") or []),
    )
    return PeerReviewAssistResponse(
        tr_score=float(est["tr_score"]),
        cc_score=float(est["cc_score"]),
        lr_score=float(est["lr_score"]),
        gra_score=float(est["gra_score"]),
        overall_score=float(est["overall_score"]),
        strengths=[str(x) for x in (assist.get("strengths") or [])],
        improvements=[str(x) for x in (assist.get("improvements") or [])],
        sample_comment=str(assist.get("sample_comment") or ""),
        quality_hint=quality_hint,
        meta=dict(assist.get("meta") or {}),
    )


@router.get("/peer/stats", response_model=PeerStatsResponse)
async def get_peer_stats(current_user: dict = Depends(get_current_user)):
    stats = get_writing_peer_stats(user_id=str(current_user["id"]))
    points = int(stats.get("total_points") or 0)
    reviews = int(stats.get("total_reviews_written") or 0)

    if points >= 180:
        level = "review_master"
    elif points >= 90:
        level = "review_pro"
    elif points >= 30:
        level = "review_active"
    else:
        level = "review_newbie"

    badges: list[str] = []
    quality = stats.get("quality_counts") or {}
    if int(quality.get("advanced") or 0) >= 5:
        badges.append("高质量评语达人")
    if reviews >= 10:
        badges.append("互评活跃贡献者")
    if float(stats.get("avg_given_score") or 0.0) >= 7.0 and reviews >= 3:
        badges.append("稳定评分官")
    if not badges:
        badges.append("互评新星")

    return PeerStatsResponse(
        user_id=str(stats.get("user_id") or str(current_user["id"])),
        total_submissions=int(stats.get("total_submissions") or 0),
        open_submissions=int(stats.get("open_submissions") or 0),
        in_review_submissions=int(stats.get("in_review_submissions") or 0),
        reviewed_submissions=int(stats.get("reviewed_submissions") or 0),
        avg_received_score=float(stats.get("avg_received_score") or 0.0),
        total_reviews_written=int(stats.get("total_reviews_written") or 0),
        avg_given_score=float(stats.get("avg_given_score") or 0.0),
        quality_counts={
            "advanced": int((quality.get("advanced") or 0)),
            "standard": int((quality.get("standard") or 0)),
            "basic": int((quality.get("basic") or 0)),
        },
        total_points=points,
        reviewer_level=level,
        reviewer_badges=badges,
    )


@router.get("/peer/leaderboard", response_model=List[PeerLeaderboardItem])
async def get_peer_leaderboard(limit: int = 10, current_user: dict = Depends(get_current_user)):
    rows = list_writing_peer_leaderboard(limit=max(1, min(50, int(limit))))
    items: list[PeerLeaderboardItem] = []
    for idx, row in enumerate(rows):
        reviewer_id = str(row.get("reviewer_id") or "")
        items.append(
            PeerLeaderboardItem(
                reviewer_id=reviewer_id,
                reviewer_alias=_build_reviewer_alias(reviewer_id),
                total_reviews=int(row.get("total_reviews") or 0),
                avg_given_score=round(float(row.get("avg_given_score") or 0.0), 3),
                advanced_count=int(row.get("advanced_count") or 0),
                standard_count=int(row.get("standard_count") or 0),
                basic_count=int(row.get("basic_count") or 0),
                total_points=int(row.get("total_points") or 0),
                rank=idx + 1,
            )
        )
    return items


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
                reviewer_alias=_build_reviewer_alias(str(x.get("reviewer_id") or "")),
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
            reviewer_alias=_build_reviewer_alias(str(x.get("reviewer_id") or "")),
        )
        for x in rows
    ]

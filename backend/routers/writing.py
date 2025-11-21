from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import re
from ..deps import get_current_user

router = APIRouter()

class Task1Type(str):
    """Task 1 图表类型"""
    CHART = "chart"
    GRAPH = "graph"
    TABLE = "table"
    DIAGRAM = "diagram"

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
    # 后续实现数据库存储
    return {
        "id": 1,  # 模拟ID
        "message": "练习已保存",
        "data": {
            "task_id": 1,
            "created_at": "2025-01-12T10:30:00"
        }
    }

@router.get("/task1/practices")
async def get_task1_practices(page: int = 1, limit: int = 10, current_user: dict = Depends(get_current_user)):
    """获取Task 1 写作练习历史"""
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
    filtered_vocab = task1_vocabulary
    if category and category in task1_vocabulary:
        filtered_vocab = {category: task1_vocabulary[category]}
    return {
        "vocabulary": filtered_vocab
    }
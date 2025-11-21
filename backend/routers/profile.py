from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from ..db import get_scores, get_transcripts  # 引入数据库查询函数
from ..deps import get_current_user


router = APIRouter()


class WeaknessDetail(BaseModel):
    section: str  # 模块: L/R/W/S
    category: str  # 类别: fluency, vocabulary, grammar等
    item: str  # 具体薄弱点
    score: float  # 对应评分
    improvement_tip: str  # 提升建议

class DetailedWeakness(BaseModel):
    main_weaknesses: List[str]  # 主要薄弱环节
    detailed: List[WeaknessDetail]  # 详细薄弱点分析
    improvement_plan: List[str]  # 初步提升计划

class Profile(BaseModel):
    radar: dict  # 各项能力雷达图
    history: List[dict]  # 历史成绩记录
    weaknesses: DetailedWeakness  # 详细薄弱环节分析
    strengths: List[str]  # 优势领域


@router.get("/me", response_model=Profile)
async def me(current_user: dict = Depends(get_current_user)):
    """获取用户详细能力画像"""
    user_id = current_user.get("id") or 1  # 使用模拟数据
    
    # 从数据库获取用户成绩（这里使用模拟数据，后续替换为真实查询）
    # scores = get_scores(user_id, limit=20)
    # transcripts = get_transcripts(user_id, limit=10)
    
    # 模拟综合成绩数据
    radar_scores = {"L": 6.5, "R": 6.0, "W": 6.0, "S": 6.5}
    
    # 详细薄弱环节分析
    weaknesses = []
    detailed_weaknesses = []
    strengths = []
    
    # 评分标准与薄弱点映射
    criteria_mapping = {
        "S": {
            "FC": {"name": "Fluency & Coherence", "weak": ["hesitations", "disorganization", "lack of linking words"], "tip": "Practice speaking with a timer; use linking words like 'however', 'furthermore'"},
            "LR": {"name": "Lexical Resource", "weak": ["limited vocabulary", "inappropriate word choices"], "tip": "Learn topic-specific vocabulary; practice collocations"},
            "GR": {"name": "Grammar", "weak": ["tense errors", "subject-verb agreement"], "tip": "Review grammar rules; practice complex sentences"},
            "PR": {"name": "Pronunciation", "weak": ["mispronunciation", "intonation"], "tip": "Listen to native speakers; record and compare"}
        },
        "W": {
            "TR": {"name": "Task Response", "weak": ["insufficient data analysis", "off-topic"], "tip": "Focus on answering all parts of the task; include specific details"},
            "CC": {"name": "Coherence", "weak": ["poor organization", "lack of logical flow"], "tip": "Use paragraph structure; plan before writing"},
            "LR": {"name": "Vocabulary", "weak": ["simple words", "repetition"], "tip": "Expand your vocabulary with synonyms"},
            "GR": {"name": "Grammar", "weak": ["punctuation errors", "sentence fragments"], "tip": "Proofread carefully; use grammar checking tools"}
        },
        "R": {
            "TFNG": {"name": "True/False/Not Given", "weak": ["inferencing", "detail matching"], "tip": "Practice locating keywords; learn to distinguish fact from opinion"},
            "MC": {"name": "Multiple Choice", "weak": ["distractors", "main idea"], "tip": "Read questions first; eliminate wrong answers"},
            "MH": {"name": "Matching Headings", "weak": ["topic sentences", "skimming"], "tip": "Identify paragraph topics; practice skimming"}
        },
        "L": {
            "MC": {"name": "Multiple Choice", "weak": ["distractors", "note-taking"], "tip": "Practice note-taking skills; focus on key words"},
            "FC": {"name": "Form Completion", "weak": ["spelling", "number recognition"], "tip": "Practice spelling common words; listen carefully for numbers"},
            "MA": {"name": "Matching", "weak": ["speaker identification", "synonyms"], "tip": "Identify speaker voices; learn synonyms"}
        }
    }
    
    # 模拟详细薄弱点分析
    detailed_weaknesses = [
        WeaknessDetail(
            section="S",
            category="FC",
            item="lack of linking words",
            score=6.0,
            improvement_tip="Practice using linking words like 'however', 'furthermore' to connect ideas"
        ),
        WeaknessDetail(
            section="W",
            category="TR",
            item="insufficient data analysis",
            score=5.5,
            improvement_tip="Include specific data points and explanations in your response"
        ),
        WeaknessDetail(
            section="R",
            category="TFNG",
            item="inferencing",
            score=6.0,
            improvement_tip="Learn to identify implicit information in the text"
        )
    ]
    
    # 提取主要薄弱点
    main_weaknesses = list(set(dw.item for dw in detailed_weaknesses))
    
    # 识别优势领域
    for section, score in radar_scores.items():
        if score >= 7.0:
            strengths.append(f"{section} section: strong overall performance")
    
    # 生成提升计划
    improvement_plan = []
    for dw in detailed_weaknesses[:3]:  # 只取前3个重点
        improvement_plan.append(f"For {dw.section} {dw.category}, focus on: {dw.improvement_tip}")
    
    # 历史记录
    history = [{"date": "2025-11-01", "S": 6.0}, {"date": "2025-11-03", "S": 6.5}]
    
    return Profile(
        radar=radar_scores,
        history=history,
        weaknesses=DetailedWeakness(
            main_weaknesses=main_weaknesses,
            detailed=detailed_weaknesses,
            improvement_plan=improvement_plan
        ),
        strengths=strengths
    )



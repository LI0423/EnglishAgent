from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import uuid
from ..db import (
    create_diagnostic_session,
    complete_diagnostic_session,
    create_diagnostic_report,
    get_diagnostic_report
)
from ..deps import get_current_user


router = APIRouter()


class DiagnosticModule(BaseModel):
    name: str
    questions: int
    time_limit: int

class DiagnosticStart(BaseModel):
    modules: List[str]
    target_time: Optional[int] = None

class DiagnosticAnswer(BaseModel):
    question_id: str
    answer: Any
    time_taken: Optional[int] = None

class DiagnosticAnswers(BaseModel):
    answers: List[DiagnosticAnswer]

class ModuleScore(BaseModel):
    module: str
    score: float
    max_score: float

class Weakness(BaseModel):
    module: str
    skills: List[str]
    error_types: List[str]

class Recommendation(BaseModel):
    type: str
    content: str
    priority: int

class DiagnosticReport(BaseModel):
    overall_band: float
    module_scores: List[ModuleScore]
    weaknesses: List[Weakness]
    recommendations: List[Recommendation]

class DiagnosticSession(BaseModel):
    id: str
    user_id: str
    start_time: int
    modules: List[str]
    estimated_questions: int

class NextQuestion(BaseModel):
    question_id: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[str]] = None
    time_limit: Optional[int] = None

class AnswerResponse(BaseModel):
    next_question: Optional[NextQuestion] = None
    estimated_ability: Optional[float] = None


@router.post("/start", response_model=DiagnosticSession)
async def start_diagnostic(
    diagnostic_data: DiagnosticStart,
    current_user: dict = Depends(get_current_user)
):
    """开始诊断测试"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 生成会话ID
    session_id = str(uuid.uuid4())
    
    # 创建诊断会话
    create_diagnostic_session(session_id, user_id, diagnostic_data.modules)
    
    # 估算题目数量
    estimated_questions = 0
    for module in diagnostic_data.modules:
        if module == "listening":
            estimated_questions += 10
        elif module == "reading":
            estimated_questions += 10
        elif module == "writing":
            estimated_questions += 2
        elif module == "speaking":
            estimated_questions += 3
    
    return DiagnosticSession(
        id=session_id,
        user_id=user_id,
        start_time=int(time.time()),
        modules=diagnostic_data.modules,
        estimated_questions=estimated_questions
    )


@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    answer_data: DiagnosticAnswers,
    current_user: dict = Depends(get_current_user)
):
    """提交答案"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 这里应该实现自适应出题逻辑
    # 暂时返回空，后续实现
    return AnswerResponse(
        next_question=None,
        estimated_ability=5.0
    )


@router.get("/{session_id}/report", response_model=DiagnosticReport)
async def get_report(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取诊断报告"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 从数据库获取报告
    report = get_diagnostic_report(session_id)
    if report:
        # 解析报告数据
        module_scores = []
        if report.get('module_scores'):
            module_scores_data = report['module_scores']
            for item in module_scores_data:
                module_scores.append(ModuleScore(
                    module=item['module'],
                    score=item['score'],
                    max_score=item.get('max_score', 9.0)
                ))
        
        weaknesses = []
        if report.get('weaknesses'):
            weaknesses_data = report['weaknesses']
            for item in weaknesses_data:
                weaknesses.append(Weakness(
                    module=item['module'],
                    skills=item['skills'],
                    error_types=item['error_types']
                ))
        
        recommendations = []
        if report.get('recommendations'):
            recommendations_data = report['recommendations']
            for item in recommendations_data:
                recommendations.append(Recommendation(
                    type=item['type'],
                    content=item['content'],
                    priority=item.get('priority', 1)
                ))
        
        return DiagnosticReport(
            overall_band=report['overall_band'],
            module_scores=module_scores,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    else:
        # 如果没有报告，生成一个默认报告
        # 这里应该实现真实的报告生成逻辑
        return DiagnosticReport(
            overall_band=5.0,
            module_scores=[
                ModuleScore(module="listening", score=5.0, max_score=9.0),
                ModuleScore(module="reading", score=5.0, max_score=9.0),
                ModuleScore(module="writing", score=5.0, max_score=9.0),
                ModuleScore(module="speaking", score=5.0, max_score=9.0)
            ],
            weaknesses=[
                Weakness(
                    module="listening",
                    skills=["note-taking", "distractor identification"],
                    error_types=["missing key information", "incorrect predictions"]
                )
            ],
            recommendations=[
                Recommendation(
                    type="listening",
                    content="Practice note-taking skills with different accents",
                    priority=1
                )
            ]
        )


@router.post("/{session_id}/complete")
async def complete_diagnostic(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """完成诊断测试"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 完成诊断会话
    end_time = int(time.time())
    complete_diagnostic_session(
        session_id=session_id,
        end_time=end_time,
        total_questions=25,
        completed_questions=25,
        estimated_band=5.0
    )
    
    # 生成诊断报告
    report_id = str(uuid.uuid4())
    report_data = {
        "overall_band": 5.0,
        "module_scores": [
            {"module": "listening", "score": 5.0, "max_score": 9.0},
            {"module": "reading", "score": 5.0, "max_score": 9.0},
            {"module": "writing", "score": 5.0, "max_score": 9.0},
            {"module": "speaking", "score": 5.0, "max_score": 9.0}
        ],
        "weaknesses": [
            {
                "module": "listening",
                "skills": ["note-taking", "distractor identification"],
                "error_types": ["missing key information", "incorrect predictions"]
            }
        ],
        "recommendations": [
            {
                "type": "listening",
                "content": "Practice note-taking skills with different accents",
                "priority": 1
            }
        ]
    }
    create_diagnostic_report(report_id, session_id, report_data)
    
    return {
        "message": "Diagnostic completed successfully",
        "report_id": report_id,
        "estimated_band": 5.0
    }

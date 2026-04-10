from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import time
import uuid
from datetime import datetime, timedelta, time as dtime
from ..deps import get_current_user
from ..db import (
    create_learning_plan,
    get_learning_plan,
    list_user_plans,
    update_plan_status,
    update_learning_plan_settings,
    create_plan_calibration_log,
    create_daily_task,
    get_daily_task,
    get_daily_tasks_by_plan,
    get_daily_task_by_date,
    append_daily_task_items,
    update_task_completion,
    update_task_progress,
    get_plan_progress,
    get_plan_execution_health,
    get_mistake_module_comparison,
)


router = APIRouter()


def _model_dump(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


class Exercise(BaseModel):
    skill: str  # The skill being targeted (e.g., "speaking fluency", "writing coherence")
    description: str  # Detailed exercise description
    time_required: str  # Estimated time (e.g., "30 mins", "1 hour")
    materials: List[str] = []  # Any materials needed (e.g., "paper", "recording device")
    difficulty: str = "intermediate"  # Difficulty level

class DailyPlan(BaseModel):
    day: str  # Day identifier (e.g., "day1", "day2")
    focus_area: str  # The main focus area for the day
    exercises: List[Exercise]  # List of exercises for the day
    goals: List[str]  # What the user should achieve
    progress_tip: str  # Tip to track progress

class PlanResponse(BaseModel):
    plan: List[DailyPlan]  # List of daily plans instead of a dict
    summary: str  # Summary of the plan
    total_hours: str  # Total estimated hours for the plan

class PlanRequest(BaseModel):
    weaknesses: List[str] = []  # List of user's weaknesses
    target_score: float = 7.0  # User's target score
    daily_time_available: str = "1-2 hours"  # Daily time user can dedicate


class LearningPlanCreate(BaseModel):
    target_band: float
    daily_minutes: int
    focus_modules: List[str]
    duration_weeks: int = 7


class LearningPlan(BaseModel):
    id: str
    user_id: str
    target_band: float
    start_date: int
    end_date: int
    daily_minutes: int
    focus_modules: List[str]
    status: str
    created_at: int


class TaskItem(BaseModel):
    id: Optional[str] = None
    module: Optional[str] = ""
    title: str
    description: str = ""
    time_required: Optional[int] = None
    duration_minutes: Optional[int] = None
    completed: bool = False
    progress: int = 0
    time_spent: int = 0


class DailyTaskCreate(BaseModel):
    date: Union[int, str]
    tasks: List[TaskItem]


class DailyTask(BaseModel):
    id: str
    plan_id: str
    date: int
    tasks: List[TaskItem]
    completed: bool
    created_at: int
    updated_at: int


class TaskProgressUpdate(BaseModel):
    task_id: str
    completed: bool = False
    progress: int = 0
    time_spent: int = 0


class PlanProgress(BaseModel):
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    tasks: List[DailyTask]


class PlanCreateResponse(BaseModel):
    plan_id: str
    plan: LearningPlan
    message: str


class PlanStatusUpdate(BaseModel):
    status: str


class PlanSettingsUpdate(BaseModel):
    daily_minutes: Optional[int] = None
    focus_modules: Optional[List[str]] = None
    status: Optional[str] = None
    source: Optional[str] = "manual"
    note: Optional[str] = ""


class WeeklyTaskGenerateRequest(BaseModel):
    days: int = 7


class WeeklyTaskGenerateResponse(BaseModel):
    plan_id: str
    requested_days: int
    generated_days: int
    skipped_days: int
    generated_task_ids: List[str]
    message: str


class InterventionPreviewResponse(BaseModel):
    plan_id: str
    days: int
    remedial_days: int
    health_level: str
    task_completion_rate: float
    top_modules: List[str]
    suggestions: List[str]
    proposed_daily_minutes: int
    intervention_daily_tasks: List[Dict[str, Any]]


class InterventionApplyRequest(BaseModel):
    days: int = 14
    remedial_days: int = 3


class InterventionApplyResponse(BaseModel):
    plan_id: str
    days: int
    remedial_days: int
    intervention_batch_id: str
    created_days: int
    appended_days: int
    task_count_added: int
    message: str


def _parse_date_to_ts(raw_date: Union[int, str]) -> int:
    if isinstance(raw_date, int):
        return raw_date
    try:
        return int(datetime.strptime(raw_date, "%Y-%m-%d").timestamp())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD") from exc


def _normalize_task_item(task: TaskItem) -> Dict[str, Any]:
    task_id = task.id or str(uuid.uuid4())
    time_required = task.time_required if task.time_required is not None else (task.duration_minutes or 30)
    return {
        "id": task_id,
        "module": task.module or "",
        "title": task.title,
        "description": task.description or "",
        "time_required": time_required,
        "completed": task.completed,
        "progress": task.progress,
        "time_spent": task.time_spent,
    }


def _module_task_templates(module: str) -> List[Dict[str, str]]:
    mapping: Dict[str, List[Dict[str, str]]] = {
        "listening": [
            {"title": "听力精听复盘", "description": "完成 1 组精听并记录关键词抓取错误点。"},
            {"title": "听力题型强化", "description": "完成 10 题听力选择/填空专项训练。"},
        ],
        "reading": [
            {"title": "阅读定位训练", "description": "完成 1 篇阅读并标注定位线索句。"},
            {"title": "阅读错因复盘", "description": "针对错题做 TFNG/匹配题型复盘。"},
        ],
        "writing": [
            {"title": "写作结构演练", "description": "完成 1 篇写作提纲并检查段落逻辑。"},
            {"title": "写作表达升级", "description": "改写 8 句低分句型，提升语法与词汇。"},
        ],
        "speaking": [
            {"title": "口语录音打卡", "description": "完成 2 段口语录音并自评流利度与逻辑。"},
            {"title": "口语话题复述", "description": "围绕高频话题进行 10 分钟复述训练。"},
        ],
        "vocabulary": [
            {"title": "词汇新词学习", "description": "学习并造句 15 个高频学术词。"},
            {"title": "词汇复习回顾", "description": "完成到期词汇复习并标注遗忘词。"},
        ],
    }
    return mapping.get(module, [{"title": f"{module} 模块训练", "description": f"完成 {module} 模块专项练习并复盘。"}])


def _build_auto_tasks(focus_modules: List[str], daily_minutes: int, day_index: int) -> List[Dict[str, Any]]:
    modules = [str(m).strip().lower() for m in focus_modules if str(m).strip()]
    if not modules:
        modules = ["listening", "reading", "writing", "speaking"]

    minutes_per_module = max(10, int(daily_minutes / max(1, len(modules))))
    tasks: List[Dict[str, Any]] = []
    for idx, module in enumerate(modules):
        templates = _module_task_templates(module)
        picked = templates[day_index % len(templates)]
        tasks.append(
            {
                "id": str(uuid.uuid4()),
                "module": module,
                "title": picked["title"],
                "description": picked["description"],
                "time_required": minutes_per_module,
                "completed": False,
                "progress": 0,
                "time_spent": 0,
            }
        )
        if idx == 0:
            tasks.append(
                {
                    "id": str(uuid.uuid4()),
                    "module": module,
                    "title": "错题复盘",
                    "description": f"复盘 {module} 模块错题，优先处理今日到期项目。",
                    "time_required": max(10, int(minutes_per_module * 0.4)),
                    "completed": False,
                    "progress": 0,
                    "time_spent": 0,
                }
            )
    return tasks


def _build_intervention_plan(
    *,
    plan: Dict[str, Any],
    health: Dict[str, Any],
    module_rows: List[Dict[str, Any]],
    remedial_days: int,
) -> Dict[str, Any]:
    health_level = str(health.get("health_level") or "unknown")
    task_completion_rate = float(health.get("task_completion_rate") or 0.0)
    day_completion_rate = float(health.get("day_completion_rate") or 0.0)
    top_modules = [str(x.get("module") or "") for x in module_rows[:2] if str(x.get("module") or "").strip()]
    if not top_modules:
        top_modules = [str(x).strip().lower() for x in (plan.get("focus_modules") or []) if str(x).strip()][:2]
    if not top_modules:
        top_modules = ["listening", "reading"]

    suggestions: List[str] = []
    base_minutes = int(plan.get("daily_minutes") or 90)
    proposed_daily_minutes = base_minutes
    if health_level == "at_risk" or task_completion_rate < 50 or day_completion_rate < 40:
        proposed_daily_minutes = max(45, int(round(base_minutes * 0.85)))
        suggestions.append("近阶段执行负荷偏高，建议短期降负并聚焦高风险模块。")
    elif health_level == "watch":
        proposed_daily_minutes = max(60, int(round(base_minutes * 0.95)))
        suggestions.append("执行节奏略不稳定，建议减少分散任务，优先完成核心训练。")
    else:
        proposed_daily_minutes = min(180, int(round(base_minutes * 1.0)))
        suggestions.append("执行状态健康，建议通过短周期补救任务继续巩固薄弱点。")

    suggestions.append(f"未来 {remedial_days} 天优先处理模块：{', '.join(top_modules)}。")
    suggestions.append("每天先完成 1 个补救任务，再进行常规计划任务。")

    per_day_minutes = max(15, min(40, int(round(proposed_daily_minutes * 0.3))))
    intervention_daily_tasks: List[Dict[str, Any]] = []
    for day_index in range(remedial_days):
        module = top_modules[day_index % len(top_modules)]
        templates = _module_task_templates(module)
        picked = templates[day_index % len(templates)]
        intervention_daily_tasks.append(
            {
                "module": module,
                "title": f"干预 · {picked['title']}",
                "description": f"{picked['description']}（补救任务，优先完成）",
                "time_required": per_day_minutes,
                "completed": False,
                "progress": 0,
                "time_spent": 0,
            }
        )

    return {
        "health_level": health_level,
        "task_completion_rate": round(task_completion_rate, 2),
        "top_modules": top_modules,
        "suggestions": suggestions,
        "proposed_daily_minutes": proposed_daily_minutes,
        "intervention_daily_tasks": intervention_daily_tasks,
    }



# 薄弱环节到练习的映射
detailed_weakness_mapping = {
    "lack of linking words": {
        "speaking": [
            {"skill": "speaking fluency & coherence", "description": "Practice using linking words (however, furthermore, therefore) to connect 5 random ideas. Record yourself and review the flow.", "time_required": "30 mins", "materials": ["recording device"], "difficulty": "intermediate"},
            {"skill": "speaking fluency & coherence", "description": "Listen to a TED talk, identify linking words, and practice paraphrasing the talk using those words.", "time_required": "45 mins", "materials": ["internet access", "notebook"], "difficulty": "intermediate"}
        ],
        "writing": [
            {"skill": "writing coherence", "description": "Write a 150-word paragraph about your favorite hobby, using at least 5 linking words to connect ideas smoothly.", "time_required": "25 mins", "materials": ["notebook"], "difficulty": "intermediate"}
        ]
    },
    "insufficient data analysis": {
        "writing": [
            {"skill": "writing task response", "description": "Find a line graph about population growth and practice writing an overview that includes specific data points.", "time_required": "35 mins", "materials": ["practice graph"], "difficulty": "intermediate"},
            {"skill": "writing task response", "description": "Analyze a bar chart and write 3 sentences that compare different categories using data.", "time_required": "20 mins", "materials": ["practice chart"], "difficulty": "intermediate"}
        ]
    },
    "inferencing": {
        "reading": [
            {"skill": "reading true/false/not given", "description": "Practice 20 TFNG questions focusing on implicit information. Write down clues for each answer.", "time_required": "40 mins", "materials": ["past papers"], "difficulty": "advanced"}
        ],
        "listening": [
            {"skill": "listening multiple choice", "description": "Listen to a podcast segment and answer 10 inferential questions.", "time_required": "35 mins", "materials": ["podcast audio"], "difficulty": "advanced"}
        ]
    },
    "limited vocabulary": {
        "general": [
            {"skill": "vocabulary", "description": "Learn 20 topic-specific words (education/technology) with example sentences.", "time_required": "25 mins", "materials": ["vocab list"], "difficulty": "intermediate"}
        ]
    },
    "grammar errors": {
        "general": [
            {"skill": "grammar", "description": "Practice complex sentence structures (relative clauses, conditionals) with 15 exercises.", "time_required": "30 mins", "materials": ["grammar book"], "difficulty": "intermediate"}
        ]
    }
}

@router.post("/7d", response_model=PlanResponse)
async def plan_7d(req: PlanRequest, current_user: dict = Depends(get_current_user)):
    weaknesses = req.weaknesses
    target_score = req.target_score
    daily_time = req.daily_time_available
    plan = []
    
    # If no weaknesses provided, use default
    if not weaknesses:
        weaknesses = ["lack of linking words", "limited vocabulary", "grammar errors"]
    
    # Select unique exercises from mapping
    selected_exercises = []
    for weakness in weaknesses:
        if weakness in detailed_weakness_mapping:
            # Collect exercises from all sections for this weakness
            for section_exercises in detailed_weakness_mapping[weakness].values():
                selected_exercises.extend(section_exercises)
    
    # Fallback to default exercises if none found
    if not selected_exercises:
        selected_exercises = [
            {"skill": "speaking fluency", "description": "5-min monologue practice", "time_required": "30 mins", "materials": ["recording device"], "difficulty": "intermediate"},
            {"skill": "writing coherence", "description": "Paragraph writing with linking words", "time_required": "25 mins", "materials": ["notebook"], "difficulty": "intermediate"}
        ]
    
    # Generate 7-day plan
    for day in range(1, 8):
        daily_exercises = []
        daily_focus = ""
        daily_goals = []
        
        if day == 1:
            daily_focus = f"Foundation: {weaknesses[0]}"
            daily_exercises = selected_exercises[:2] if len(selected_exercises) >= 2 else selected_exercises
            daily_goals = [f"Understand the core issues with {weaknesses[0]}", "Master 2 key exercises"]
        elif day == 2:
            daily_focus = f"Foundation: {weaknesses[1]}"
            daily_exercises = selected_exercises[2:4] if len(selected_exercises) >= 4 else selected_exercises
            daily_goals = [f"Understand the core issues with {weaknesses[1]}", "Master 2 key exercises"]
        elif day == 3:
            daily_focus = "Integration: Combining Weaknesses"
            daily_exercises = selected_exercises[4:6] if len(selected_exercises) >= 6 else selected_exercises[:2]
            daily_goals = ["Practice using multiple skills together", "Build confidence in combined exercises"]
        elif day == 4:
            daily_focus = "Deep Dive: Specific Skills"
            daily_exercises = selected_exercises[:2]  # Repeat key exercises for reinforcement
            daily_goals = ["Reinforce learned skills", "Improve accuracy and speed"]
        elif day == 5:
            daily_focus = "Mock Practice: Controlled"
            daily_exercises = [
                {"skill": "mock practice", "description": "Complete a timed mock test focusing on your weaknesses", "time_required": "1 hour", "materials": ["past papers"], "difficulty": "advanced"}
            ]
            daily_goals = ["Simulate exam conditions", "Identify remaining gaps"]
        elif day == 6:
            daily_focus = "Review & Reinforcement"
            daily_exercises = [
                {"skill": "review", "description": "Review all notes and exercises from the week", "time_required": "45 mins", "materials": ["notebook"], "difficulty": "intermediate"},
                {"skill": "practice", "description": "Focus on your weakest area with 30 mins of targeted exercises", "time_required": "30 mins", "materials": ["practice materials"], "difficulty": "advanced"}
            ]
            daily_goals = ["Solidify learning", "Address remaining weaknesses"]
        elif day == 7:
            daily_focus = "Full Mock Test"
            daily_exercises = [
                {"skill": "full mock", "description": "Complete a full mock test under exam conditions", "time_required": "2 hours", "materials": ["past papers", "timer"], "difficulty": "advanced"},
                {"skill": "self-assessment", "description": "Grade your test and identify improvement areas", "time_required": "1 hour", "materials": ["answer key", "notebook"], "difficulty": "advanced"}
            ]
            daily_goals = ["Final simulation", "Evaluate progress", "Set next steps"]
        
        # Create DailyPlan object
        daily_plan = DailyPlan(
            day=f"day{day}",
            focus_area=daily_focus,
            exercises=[Exercise(**ex) for ex in daily_exercises],
            goals=daily_goals,
            progress_tip=f"Track time and accuracy for each exercise; focus on improvement from day{day-1 if day > 1 else 1}"
        )
        
        plan.append(daily_plan)
    
    # Calculate total hours
    total_hours = 0
    for daily_plan in plan:
        for ex in daily_plan.exercises:
            # Extract minutes from time_required string
            if "min" in ex.time_required:
                minutes = int(ex.time_required.split()[0])
                total_hours += minutes / 60
            elif "hour" in ex.time_required:
                hours = float(ex.time_required.split()[0])
                total_hours += hours
    
    total_hours_str = f"{round(total_hours, 1)} hours"
    
    summary = f"7-day personalized IELTS study plan focusing on {', '.join(weaknesses[:3])}" + (f" and {len(weaknesses) - 3} more" if len(weaknesses) > 3 else "") + f" with a target score of {target_score}."
    
    return PlanResponse(plan=plan, summary=summary, total_hours=total_hours_str)


@router.post("/create", response_model=PlanCreateResponse)
async def create_plan(
    plan_data: LearningPlanCreate,
    current_user: dict = Depends(get_current_user)
):
    """创建个性化学习计划"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 生成计划ID
    plan_id = str(uuid.uuid4())
    
    # 计算开始和结束日期
    start_date = int(time.time())
    end_date = start_date + (plan_data.duration_weeks * 7 * 24 * 3600)
    
    # 创建学习计划
    plan_info = {
        "target_band": plan_data.target_band,
        "start_date": start_date,
        "end_date": end_date,
        "daily_minutes": plan_data.daily_minutes,
        "focus_modules": plan_data.focus_modules,
        "status": "active"
    }
    
    create_learning_plan(plan_id, user_id, plan_info)
    
    # 获取创建的计划
    created_plan = get_learning_plan(plan_id)
    if not created_plan:
        raise HTTPException(status_code=500, detail="Failed to create plan")
    
    # 转换为响应格式
    learning_plan = LearningPlan(
        id=created_plan["id"],
        user_id=created_plan["user_id"],
        target_band=created_plan["target_band"],
        start_date=created_plan["start_date"],
        end_date=created_plan["end_date"],
        daily_minutes=created_plan["daily_minutes"],
        focus_modules=created_plan["focus_modules"],
        status=created_plan["status"],
        created_at=created_plan["created_at"]
    )
    
    return PlanCreateResponse(
        plan_id=plan_id,
        plan=learning_plan,
        message="Learning plan created successfully"
    )


@router.get("/{plan_id}", response_model=LearningPlan)
async def get_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取学习计划详情"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # 验证计划属于当前用户
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return LearningPlan(
        id=plan["id"],
        user_id=plan["user_id"],
        target_band=plan["target_band"],
        start_date=plan["start_date"],
        end_date=plan["end_date"],
        daily_minutes=plan["daily_minutes"],
        focus_modules=plan["focus_modules"],
        status=plan["status"],
        created_at=plan["created_at"]
    )


@router.get("/", response_model=List[LearningPlan])
async def get_user_plans(
    current_user: dict = Depends(get_current_user)
):
    """获取用户的学习计划列表"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    plans = list_user_plans(user_id)
    return [
        LearningPlan(
            id=plan["id"],
            user_id=plan["user_id"],
            target_band=plan["target_band"],
            start_date=plan["start_date"],
            end_date=plan["end_date"],
            daily_minutes=plan["daily_minutes"],
            focus_modules=plan["focus_modules"],
            status=plan["status"],
            created_at=plan["created_at"]
        )
        for plan in plans
    ]


@router.put("/{plan_id}/status")
async def update_status(
    plan_id: str,
    payload: PlanStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新学习计划状态"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证计划存在且属于当前用户
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_plan_status(plan_id, payload.status)
    return {"message": "Plan status updated successfully", "status": payload.status}


@router.put("/{plan_id}/settings", response_model=LearningPlan)
async def update_plan_settings(
    plan_id: str,
    payload: PlanSettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """更新学习计划配置（日分钟/模块/状态）"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    next_minutes = payload.daily_minutes
    if next_minutes is not None:
        next_minutes = max(30, min(240, int(next_minutes)))
    next_focus_modules = payload.focus_modules
    if next_focus_modules is not None:
        next_focus_modules = [str(x).strip().lower() for x in next_focus_modules if str(x).strip()]
    next_status = payload.status

    update_learning_plan_settings(
        plan_id,
        daily_minutes=next_minutes,
        focus_modules=next_focus_modules,
        status=next_status,
    )

    before_minutes = int(plan.get("daily_minutes") or 0)
    after_minutes = int(next_minutes if next_minutes is not None else before_minutes)
    before_modules = [str(x) for x in (plan.get("focus_modules") or [])]
    after_modules = [str(x) for x in (next_focus_modules if next_focus_modules is not None else before_modules)]
    changed = (before_minutes != after_minutes) or (before_modules != after_modules)
    if changed:
        create_plan_calibration_log(
            str(uuid.uuid4()),
            plan_id=str(plan_id),
            user_id=str(user_id),
            before_daily_minutes=before_minutes,
            after_daily_minutes=after_minutes,
            before_focus_modules=before_modules,
            after_focus_modules=after_modules,
            source=str(payload.source or "manual"),
            note=str(payload.note or ""),
        )

    updated = get_learning_plan(plan_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update plan")

    return LearningPlan(
        id=updated["id"],
        user_id=updated["user_id"],
        target_band=updated["target_band"],
        start_date=updated["start_date"],
        end_date=updated["end_date"],
        daily_minutes=updated["daily_minutes"],
        focus_modules=updated["focus_modules"],
        status=updated["status"],
        created_at=updated["created_at"],
    )


@router.post("/{plan_id}/tasks", response_model=DailyTask)
async def create_task(
    plan_id: str,
    task_data: DailyTaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """创建每日任务"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证计划存在且属于当前用户
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    target_date = _parse_date_to_ts(task_data.date)

    # 检查是否已存在该日期的任务
    existing_task = get_daily_task_by_date(plan_id, target_date)
    if existing_task:
        raise HTTPException(status_code=400, detail="Task for this date already exists")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 转换任务数据
    tasks = [_normalize_task_item(task) for task in task_data.tasks]
    
    create_daily_task(task_id, plan_id, target_date, tasks)
    
    # 获取创建的任务
    created_task = get_daily_task(task_id)
    if not created_task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    # 转换为响应格式
    daily_task = DailyTask(
        id=created_task["id"],
        plan_id=created_task["plan_id"],
        date=created_task["date"],
        tasks=[TaskItem(**task) for task in created_task["tasks"]],
        completed=bool(created_task["completed"]),
        created_at=created_task["created_at"],
        updated_at=created_task["updated_at"]
    )
    
    return daily_task


@router.get("/{plan_id}/tasks", response_model=List[DailyTask])
async def get_plan_tasks(
    plan_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取计划的所有每日任务"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证计划存在且属于当前用户
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tasks = get_daily_tasks_by_plan(plan_id)
    return [
        DailyTask(
            id=task["id"],
            plan_id=task["plan_id"],
            date=task["date"],
            tasks=[TaskItem(**t) for t in task["tasks"]],
            completed=bool(task["completed"]),
            created_at=task["created_at"],
            updated_at=task["updated_at"]
        )
        for task in tasks
    ]


@router.get("/{plan_id}/tasks/{date}", response_model=DailyTask)
async def get_task_by_date(
    plan_id: str,
    date: Union[int, str],
    current_user: dict = Depends(get_current_user)
):
    """获取指定日期的每日任务"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证计划存在且属于当前用户
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    target_date = _parse_date_to_ts(date)
    task = get_daily_task_by_date(plan_id, target_date)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return DailyTask(
        id=task["id"],
        plan_id=task["plan_id"],
        date=task["date"],
        tasks=[TaskItem(**t) for t in task["tasks"]],
        completed=bool(task["completed"]),
        created_at=task["created_at"],
        updated_at=task["updated_at"]
    )


@router.put("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    completed: bool,
    current_user: dict = Depends(get_current_user)
):
    """更新任务完成状态"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证任务存在且属于当前用户
    task = get_daily_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    plan = get_learning_plan(task["plan_id"])
    if not plan or plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_task_completion(task_id, completed)
    return {"message": "Task completion status updated successfully", "completed": completed}


@router.put("/tasks/{task_id}/progress")
async def update_progress(
    task_id: str,
    progress: TaskProgressUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新任务进度"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证任务存在且属于当前用户
    task = get_daily_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    plan = get_learning_plan(task["plan_id"])
    if not plan or plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_task_progress(task_id, _model_dump(progress))
    return {"message": "Task progress updated successfully"}


@router.get("/{plan_id}/progress", response_model=PlanProgress)
async def get_progress(
    plan_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取计划执行进度"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 验证计划存在且属于当前用户
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    progress = get_plan_progress(plan_id)
    
    # 转换任务格式
    daily_tasks = [
        DailyTask(
            id=task["id"],
            plan_id=task["plan_id"],
            date=task["date"],
            tasks=[TaskItem(**t) for t in task["tasks"]],
            completed=bool(task["completed"]),
            created_at=task["created_at"],
            updated_at=task["updated_at"]
        )
        for task in progress["tasks"]
    ]
    
    return PlanProgress(
        total_tasks=progress["total_tasks"],
        completed_tasks=progress["completed_tasks"],
        completion_rate=progress["completion_rate"],
        tasks=daily_tasks
    )


@router.post("/{plan_id}/tasks/generate-weekly", response_model=WeeklyTaskGenerateResponse)
async def generate_weekly_tasks(
    plan_id: str,
    payload: WeeklyTaskGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """按学习计划自动生成未来 N 天任务（同一天只生成一次）"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    days = max(1, min(28, int(payload.days or 7)))
    daily_minutes = max(30, int(plan.get("daily_minutes", 60) or 60))
    modules = plan.get("focus_modules") or []

    existing_tasks = get_daily_tasks_by_plan(plan_id)
    existing_day_keys = {int(int(item.get("date", 0)) // 86400) for item in existing_tasks}

    today = datetime.now().date()
    generated_ids: List[str] = []
    skipped = 0
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        day_start_ts = int(datetime.combine(current_day, dtime.min).timestamp())
        day_key = day_start_ts // 86400
        if day_key in existing_day_keys:
            skipped += 1
            continue

        task_id = str(uuid.uuid4())
        tasks = _build_auto_tasks(modules, daily_minutes, day_offset)
        create_daily_task(task_id, plan_id, day_start_ts, tasks)
        existing_day_keys.add(day_key)
        generated_ids.append(task_id)

    generated = len(generated_ids)
    return WeeklyTaskGenerateResponse(
        plan_id=plan_id,
        requested_days=days,
        generated_days=generated,
        skipped_days=skipped,
        generated_task_ids=generated_ids,
        message=f"已生成 {generated} 天任务，跳过 {skipped} 天（已有任务）。",
    )


@router.get("/{plan_id}/intervention/preview", response_model=InterventionPreviewResponse)
async def get_intervention_preview(
    plan_id: str,
    days: int = 14,
    remedial_days: int = 3,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if str(plan.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    safe_days = max(3, min(30, int(days or 14)))
    safe_remedial_days = max(1, min(7, int(remedial_days or 3)))
    health = get_plan_execution_health(plan_id, days=safe_days)
    module_rows = get_mistake_module_comparison(user_id=user_id, days=safe_days)
    suggestion = _build_intervention_plan(
        plan=plan,
        health=health,
        module_rows=module_rows,
        remedial_days=safe_remedial_days,
    )
    return InterventionPreviewResponse(
        plan_id=str(plan_id),
        days=safe_days,
        remedial_days=safe_remedial_days,
        health_level=str(suggestion["health_level"]),
        task_completion_rate=float(suggestion["task_completion_rate"]),
        top_modules=list(suggestion["top_modules"]),
        suggestions=list(suggestion["suggestions"]),
        proposed_daily_minutes=int(suggestion["proposed_daily_minutes"]),
        intervention_daily_tasks=list(suggestion["intervention_daily_tasks"]),
    )


@router.post("/{plan_id}/intervention/apply", response_model=InterventionApplyResponse)
async def apply_intervention_plan(
    plan_id: str,
    payload: InterventionApplyRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    plan = get_learning_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if str(plan.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    safe_days = max(3, min(30, int(payload.days or 14)))
    safe_remedial_days = max(1, min(7, int(payload.remedial_days or 3)))
    health = get_plan_execution_health(plan_id, days=safe_days)
    module_rows = get_mistake_module_comparison(user_id=user_id, days=safe_days)
    suggestion = _build_intervention_plan(
        plan=plan,
        health=health,
        module_rows=module_rows,
        remedial_days=safe_remedial_days,
    )
    items = suggestion["intervention_daily_tasks"]

    created_days = 0
    appended_days = 0
    task_count_added = 0
    intervention_batch_id = str(uuid.uuid4())
    intervention_created_at = int(time.time())
    today = datetime.now().date()
    for day_offset in range(safe_remedial_days):
        current_day = today + timedelta(days=day_offset)
        day_start_ts = int(datetime.combine(current_day, dtime.min).timestamp())
        base_item = items[day_offset % len(items)]
        intervention_task = {
            "id": str(uuid.uuid4()),
            "module": str(base_item.get("module") or ""),
            "kind": "intervention",
            "intervention_batch_id": intervention_batch_id,
            "intervention_created_at": intervention_created_at,
            "title": str(base_item.get("title") or "干预任务"),
            "description": str(base_item.get("description") or ""),
            "time_required": int(base_item.get("time_required") or 20),
            "completed": False,
            "progress": 0,
            "time_spent": 0,
        }
        existing = get_daily_task_by_date(plan_id, day_start_ts)
        if existing:
            append_daily_task_items(str(existing["id"]), [intervention_task])
            appended_days += 1
        else:
            create_daily_task(str(uuid.uuid4()), plan_id, day_start_ts, [intervention_task])
            created_days += 1
        task_count_added += 1

    return InterventionApplyResponse(
        plan_id=str(plan_id),
        days=safe_days,
        remedial_days=safe_remedial_days,
        intervention_batch_id=intervention_batch_id,
        created_days=created_days,
        appended_days=appended_days,
        task_count_added=task_count_added,
        message=f"已应用干预：新增/追加 {task_count_added} 个补救任务（新建天数 {created_days}，追加天数 {appended_days}）。",
    )

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from ..deps import get_current_user


router = APIRouter()


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



from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..db import get_user_profile, create_user_profile
from ..deps import get_current_user


router = APIRouter()


class UserProfileBase(BaseModel):
    target_band: Optional[float] = None
    current_band_overall: Optional[float] = None
    current_band_listening: Optional[float] = None
    current_band_reading: Optional[float] = None
    current_band_writing: Optional[float] = None
    current_band_speaking: Optional[float] = None
    skill_vocabulary: Optional[float] = None
    skill_grammar: Optional[float] = None
    skill_pronunciation: Optional[float] = None
    skill_fluency: Optional[float] = None
    skill_coherence: Optional[float] = None
    learning_total_hours: Optional[float] = None
    learning_sessions_count: Optional[int] = None
    learning_streak_days: Optional[int] = None
    learning_avg_daily_minutes: Optional[float] = None
    weaknesses: Optional[List[str]] = None
    strong_areas: Optional[List[str]] = None

class UserProfileCreate(UserProfileBase):
    pass

class UserProfile(UserProfileBase):
    user_id: str
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserProfile)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """获取用户详细能力画像"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    profile = get_user_profile(user_id)
    if not profile:
        # 如果没有用户画像，返回默认值
        return UserProfile(
            user_id=user_id,
            target_band=6.5,
            current_band_overall=5.0,
            current_band_listening=5.0,
            current_band_reading=5.0,
            current_band_writing=5.0,
            current_band_speaking=5.0,
            skill_vocabulary=5.0,
            skill_grammar=5.0,
            skill_pronunciation=5.0,
            skill_fluency=5.0,
            skill_coherence=5.0,
            learning_total_hours=0.0,
            learning_sessions_count=0,
            learning_streak_days=0,
            learning_avg_daily_minutes=0.0,
            weaknesses=[],
            strong_areas=[]
        )
    
    # 转换数据库格式到响应格式
    return UserProfile(
        user_id=profile['user_id'],
        target_band=profile['target_band'],
        current_band_overall=profile['current_band_overall'],
        current_band_listening=profile['current_band_listening'],
        current_band_reading=profile['current_band_reading'],
        current_band_writing=profile['current_band_writing'],
        current_band_speaking=profile['current_band_speaking'],
        skill_vocabulary=profile['skill_vocabulary'],
        skill_grammar=profile['skill_grammar'],
        skill_pronunciation=profile['skill_pronunciation'],
        skill_fluency=profile['skill_fluency'],
        skill_coherence=profile['skill_coherence'],
        learning_total_hours=profile['learning_total_hours'],
        learning_sessions_count=profile['learning_sessions_count'],
        learning_streak_days=profile['learning_streak_days'],
        learning_avg_daily_minutes=profile['learning_avg_daily_minutes'],
        weaknesses=profile['weaknesses'],
        strong_areas=profile['strong_areas'],
        created_at=profile['created_at'],
        updated_at=profile['updated_at']
    )


@router.put("/me", response_model=UserProfile)
async def update_my_profile(
    profile_data: UserProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """更新用户能力画像"""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    
    # 构建更新数据
    update_data = {
        "target_band": profile_data.target_band,
        "current_band_overall": profile_data.current_band_overall,
        "current_band_listening": profile_data.current_band_listening,
        "current_band_reading": profile_data.current_band_reading,
        "current_band_writing": profile_data.current_band_writing,
        "current_band_speaking": profile_data.current_band_speaking,
        "skill_vocabulary": profile_data.skill_vocabulary,
        "skill_grammar": profile_data.skill_grammar,
        "skill_pronunciation": profile_data.skill_pronunciation,
        "skill_fluency": profile_data.skill_fluency,
        "skill_coherence": profile_data.skill_coherence,
        "learning_total_hours": profile_data.learning_total_hours,
        "learning_sessions_count": profile_data.learning_sessions_count,
        "learning_streak_days": profile_data.learning_streak_days,
        "learning_avg_daily_minutes": profile_data.learning_avg_daily_minutes,
        "weaknesses": profile_data.weaknesses,
        "strong_areas": profile_data.strong_areas
    }
    
    # 过滤掉None值
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    # 如果没有提供任何数据，获取现有数据
    existing_profile = get_user_profile(user_id)
    if existing_profile:
        # 合并现有数据和更新数据
        for key, value in existing_profile.items():
            if key not in update_data and key not in ['user_id', 'created_at', 'updated_at']:
                update_data[key] = value
    
    # 创建或更新用户画像
    create_user_profile(user_id, update_data)
    
    # 返回更新后的画像
    updated_profile = get_user_profile(user_id)
    if not updated_profile:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    
    return UserProfile(
        user_id=updated_profile['user_id'],
        target_band=updated_profile['target_band'],
        current_band_overall=updated_profile['current_band_overall'],
        current_band_listening=updated_profile['current_band_listening'],
        current_band_reading=updated_profile['current_band_reading'],
        current_band_writing=updated_profile['current_band_writing'],
        current_band_speaking=updated_profile['current_band_speaking'],
        skill_vocabulary=updated_profile['skill_vocabulary'],
        skill_grammar=updated_profile['skill_grammar'],
        skill_pronunciation=updated_profile['skill_pronunciation'],
        skill_fluency=updated_profile['skill_fluency'],
        skill_coherence=updated_profile['skill_coherence'],
        learning_total_hours=updated_profile['learning_total_hours'],
        learning_sessions_count=updated_profile['learning_sessions_count'],
        learning_streak_days=updated_profile['learning_streak_days'],
        learning_avg_daily_minutes=updated_profile['learning_avg_daily_minutes'],
        weaknesses=updated_profile['weaknesses'],
        strong_areas=updated_profile['strong_areas'],
        created_at=updated_profile['created_at'],
        updated_at=updated_profile['updated_at']
    )




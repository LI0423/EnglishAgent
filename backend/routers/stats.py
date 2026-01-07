"""
用户统计路由
实现学习数据统计和分析功能
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from backend.deps import get_current_user
from backend.utils.tracking import get_learning_tracker
from backend.db import get_user_activities, get_user_events

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/overview")
async def get_stats_overview(
    time_range: Optional[int] = 86400,  # 默认24小时
    current_user = Depends(get_current_user)
):
    """获取用户学习统计概览
    
    Args:
        time_range: 时间范围（秒）
        current_user: 当前用户
        
    Returns:
        Dict: 学习统计概览数据
    """
    try:
        learning_tracker = get_learning_tracker()
        stats = learning_tracker.get_event_stats(current_user['id'], time_range)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")


@router.get("/activities")
async def get_user_activity_list(
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    current_user = Depends(get_current_user)
):
    """获取用户活动列表
    
    Args:
        limit: 限制数量
        offset: 偏移量
        current_user: 当前用户
        
    Returns:
        List[Dict]: 用户活动列表
    """
    try:
        activities = get_user_activities(current_user['id'], limit, offset)
        return {"activities": activities, "total": len(activities)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活动数据失败: {str(e)}")


@router.get("/events")
async def get_user_event_list(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    current_user = Depends(get_current_user)
):
    """获取用户事件列表
    
    Args:
        limit: 限制数量
        offset: 偏移量
        current_user: 当前用户
        
    Returns:
        List[Dict]: 用户事件列表
    """
    try:
        events = get_user_events(current_user['id'], limit, offset)
        return {"events": events, "total": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件数据失败: {str(e)}")


@router.get("/detailed")
async def get_detailed_stats(
    time_range: Optional[int] = 86400,  # 默认24小时
    current_user = Depends(get_current_user)
):
    """获取详细的学习统计数据
    
    Args:
        time_range: 时间范围（秒）
        current_user: 当前用户
        
    Returns:
        Dict: 详细统计数据
    """
    try:
        learning_tracker = get_learning_tracker()
        overview = learning_tracker.get_event_stats(current_user['id'], time_range)
        
        # 获取最近的活动和事件
        recent_activities = get_user_activities(current_user['id'], 10, 0)
        recent_events = get_user_events(current_user['id'], 20, 0)
        
        # 构建详细统计
        detailed_stats = {
            "overview": overview,
            "recent_activities": recent_activities,
            "recent_events": recent_events
        }
        
        return detailed_stats
    except Exception as e:
        print(f"获取详细统计数据失败: {str(e)}")
        # raise HTTPException(status_code=500, detail=f"获取详细统计数据失败: {str(e)}")

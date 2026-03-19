"""
智能提醒任务模块
实现基于用户学习习惯的智能提醒
"""
from ..tasks import celery_app
from ..db import get_last_reminder_time, get_recent_learning_sessions, get_reminder_preferences
from ..services.intelligent_reminder import get_intelligent_reminder_strategy
from ..services.reminder_service import get_reminder_service
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task
def generate_intelligent_reminders(user_id):
    """为用户生成智能提醒
    
    Args:
        user_id: 用户ID
    """
    logger.info(f"Generating intelligent reminders for user {user_id}...")
    
    try:
        # 获取智能提醒策略
        strategy = get_intelligent_reminder_strategy()
        
        # 获取用户提醒偏好
        preferences = get_reminder_preferences(user_id)
        if not preferences or not preferences['enabled']:
            logger.info(f"Reminders disabled for user {user_id}, skipping")
            return False
        
        learning_sessions = _get_user_learning_sessions(user_id)
        
        # 分析学习习惯
        habits = strategy.analyze_learning_habits(user_id, learning_sessions)
        
        # 生成提醒计划
        reminder_schedule = strategy.generate_reminder_schedule(user_id, habits, preferences)
        
        # 调度提醒
        scheduled_count = 0
        for reminder_data in reminder_schedule:
            try:
                from ..tasks.reminder_tasks import schedule_reminder
                schedule_reminder.delay(reminder_data)
                scheduled_count += 1
                logger.info(f"Scheduled intelligent reminder for user {user_id}")
            except Exception as e:
                logger.error(f"Error scheduling reminder: {e}")
        
        logger.info(f"Generated {scheduled_count} intelligent reminders for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating intelligent reminders for user {user_id}: {e}")
        return False


@celery_app.task
def analyze_user_habits(user_id):
    """分析用户学习习惯
    
    Args:
        user_id: 用户ID
    """
    logger.info(f"Analyzing learning habits for user {user_id}...")
    
    try:
        # 获取智能提醒策略
        strategy = get_intelligent_reminder_strategy()
        
        learning_sessions = _get_user_learning_sessions(user_id)
        
        # 分析学习习惯
        habits = strategy.analyze_learning_habits(user_id, learning_sessions)
        
        logger.info(f"Learning habits analysis completed for user {user_id}")
        return habits
        
    except Exception as e:
        logger.error(f"Error analyzing learning habits for user {user_id}: {e}")
        return {}


@celery_app.task
def send_personalized_reminder(user_id, context):
    """发送个性化提醒
    
    Args:
        user_id: 用户ID
        context: 上下文信息
    """
    logger.info(f"Sending personalized reminder to user {user_id}...")
    
    try:
        # 获取智能提醒策略
        strategy = get_intelligent_reminder_strategy()
        
        # 生成个性化提醒
        reminder = strategy.generate_personalized_reminder(user_id, context)
        
        # 发送提醒
        reminder_service = get_reminder_service()
        success = reminder_service.send_reminder(reminder)
        
        logger.info(f"Personalized reminder sent to user {user_id}: {success}")
        return success
        
    except Exception as e:
        logger.error(f"Error sending personalized reminder to user {user_id}: {e}")
        return False


@celery_app.task
def check_user_activity(user_id):
    """检查用户活动并发送提醒
    
    Args:
        user_id: 用户ID
    """
    logger.info(f"Checking activity for user {user_id}...")
    
    try:
        # 获取智能提醒策略
        strategy = get_intelligent_reminder_strategy()
        
        # 获取用户提醒偏好
        preferences = get_reminder_preferences(user_id)
        if not preferences or not preferences['enabled']:
            logger.info(f"Reminders disabled for user {user_id}, skipping")
            return False
        
        learning_sessions = _get_user_learning_sessions(user_id)
        
        # 分析学习习惯
        habits = strategy.analyze_learning_habits(user_id, learning_sessions)
        
        # 检查是否需要发送提醒
        last_reminder_time = get_last_reminder_time(user_id)
        if strategy.should_send_reminder(user_id, last_reminder_time, habits):
            # 发送提醒
            context = {
                'habits': habits,
                'preferences': preferences,
                'last_activity': time.time()
            }
            send_personalized_reminder.delay(user_id, context)
            logger.info(f"Sent activity reminder to user {user_id}")
        else:
            logger.info(f"No reminder needed for user {user_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking user activity for {user_id}: {e}")
        return False


def _get_user_learning_sessions(user_id):
    """
    从真实学习数据源读取最近会话（user_activities + learning_events）。
    """
    sessions = get_recent_learning_sessions(user_id, days=14, limit=200)
    if not sessions:
        logger.info(f"No recent sessions found for user {user_id}")
    return sessions

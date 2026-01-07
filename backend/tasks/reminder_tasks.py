from ..tasks import celery_app
from ..db import get_pending_reminders, update_reminder_status, get_reminder_preferences
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task
def check_pending_reminders():
    """检查待处理的提醒并发送"""
    logger.info("Checking pending reminders...")
    
    try:
        # 获取待处理的提醒
        pending_reminders = get_pending_reminders()
        logger.info(f"Found {len(pending_reminders)} pending reminders")
        
        for reminder in pending_reminders:
            # 检查用户提醒偏好
            preferences = get_reminder_preferences(reminder['user_id'])
            if preferences and not preferences['enabled']:
                logger.info(f"Reminders disabled for user {reminder['user_id']}, skipping")
                continue
            
            # 检查是否在安静时间
            if is_quiet_hour(preferences, time.localtime()):
                logger.info(f"Currently in quiet hours for user {reminder['user_id']}, skipping")
                continue
            
            # 发送提醒
            try:
                send_reminder.delay(reminder['id'])
                logger.info(f"Scheduled reminder {reminder['id']} for delivery")
            except Exception as e:
                logger.error(f"Error scheduling reminder {reminder['id']}: {e}")
                
    except Exception as e:
        logger.error(f"Error checking pending reminders: {e}")


@celery_app.task
def send_reminder(reminder_id):
    """发送提醒"""
    logger.info(f"Sending reminder {reminder_id}...")
    
    try:
        from ..db import get_reminder
        from ..services.reminder_service import get_reminder_service
        
        # 获取提醒信息
        reminder = get_reminder(reminder_id)
        if not reminder:
            logger.error(f"Reminder {reminder_id} not found")
            return False
        
        # 获取提醒服务
        reminder_service = get_reminder_service()
        
        # 发送提醒
        success = reminder_service.send_reminder(reminder)
        
        # 更新提醒状态
        if success:
            update_reminder_status(reminder_id, 'sent', int(time.time()))
            logger.info(f"Reminder {reminder_id} sent successfully")
        else:
            update_reminder_status(reminder_id, 'failed')
            logger.error(f"Failed to send reminder {reminder_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id}: {e}")
        # 更新提醒状态为失败
        update_reminder_status(reminder_id, 'failed')
        return False


@celery_app.task
def schedule_reminder(reminder_data):
    """调度提醒"""
    logger.info(f"Scheduling reminder for {reminder_data.get('scheduled_at')}")
    
    try:
        from ..db import create_reminder
        import uuid
        
        # 生成提醒ID
        reminder_id = str(uuid.uuid4())
        user_id = reminder_data['user_id']
        
        # 创建提醒
        create_reminder(reminder_id, user_id, reminder_data)
        logger.info(f"Reminder scheduled with ID: {reminder_id}")
        
        return reminder_id
        
    except Exception as e:
        logger.error(f"Error scheduling reminder: {e}")
        raise


def is_quiet_hour(preferences, current_time):
    """检查是否在安静时间"""
    if not preferences or not preferences.get('quiet_hours'):
        return False
    
    quiet_hours = preferences['quiet_hours']
    start_time = quiet_hours.get('start', '')
    end_time = quiet_hours.get('end', '')
    
    if not start_time or not end_time:
        return False
    
    # 解析安静时间
    try:
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        
        current_hour = current_time.tm_hour
        current_minute = current_time.tm_min
        
        # 计算总分钟数
        current_total = current_hour * 60 + current_minute
        start_total = start_hour * 60 + start_minute
        end_total = end_hour * 60 + end_minute
        
        # 检查是否在安静时间范围内
        if start_total <= end_total:
            return start_total <= current_total <= end_total
        else:
            # 跨天的情况
            return current_total >= start_total or current_total <= end_total
            
    except ValueError:
        logger.error("Invalid quiet hours format")
        return False


@celery_app.task
def send_daily_reminder(user_id, message):
    """发送每日提醒"""
    logger.info(f"Sending daily reminder to user {user_id}: {message}")
    
    try:
        # 这里实现每日提醒的发送逻辑
        time.sleep(0.5)  # 模拟发送延迟
        
        logger.info(f"Daily reminder sent to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending daily reminder to user {user_id}: {e}")
        return False

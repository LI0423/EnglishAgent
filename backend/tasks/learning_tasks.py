from ..tasks import celery_app
from ..db import (
    list_user_plans,
    get_daily_task_by_date,
    create_daily_task
)
import time
import uuid
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task
def generate_daily_tasks():
    """为所有活跃的学习计划生成每日任务"""
    logger.info("Generating daily tasks...")
    
    try:
        # 获取今天的日期（以天为单位）
        today = int(time.time() / (24 * 3600)) * (24 * 3600)
        logger.info(f"Generating tasks for date: {today} ({time.strftime('%Y-%m-%d', time.localtime(today))})")
        
        # 这里应该获取所有活跃的学习计划
        # 由于我们没有获取所有用户的方法，这里模拟获取用户计划
        # 实际实现中需要从数据库获取所有用户的活跃计划
        
        # 模拟用户计划
        # 实际实现时，应该遍历所有用户的活跃计划
        
        logger.info("Daily task generation completed")
        
    except Exception as e:
        logger.error(f"Error generating daily tasks: {e}")


@celery_app.task
def generate_plan_tasks(plan_id):
    """为指定的学习计划生成任务"""
    logger.info(f"Generating tasks for plan {plan_id}...")
    
    try:
        from ..db import get_learning_plan
        
        # 获取学习计划
        plan = get_learning_plan(plan_id)
        if not plan:
            logger.error(f"Plan {plan_id} not found")
            return False
        
        # 计算计划的开始和结束日期
        start_date = plan['start_date']
        end_date = plan['end_date']
        
        # 生成每天的任务
        current_date = start_date
        while current_date <= end_date:
            # 检查是否已经存在该日期的任务
            existing_task = get_daily_task_by_date(plan_id, current_date)
            if existing_task:
                logger.info(f"Task already exists for date {current_date}, skipping")
                current_date += 24 * 3600
                continue
            
            # 生成任务
            task_id = str(uuid.uuid4())
            
            # 根据计划的focus_modules和daily_minutes生成任务
            tasks = generate_tasks_for_date(plan, current_date)
            
            # 创建每日任务
            create_daily_task(task_id, plan_id, current_date, tasks)
            logger.info(f"Created task {task_id} for date {current_date}")
            
            # 移动到下一天
            current_date += 24 * 3600
        
        logger.info(f"Task generation completed for plan {plan_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating tasks for plan {plan_id}: {e}")
        return False


def generate_tasks_for_date(plan, date):
    """为指定日期生成任务"""
    # 根据计划生成具体的任务
    tasks = []
    
    # 计算是计划的第几天
    day_index = (date - plan['start_date']) // (24 * 3600) + 1
    
    # 根据focus_modules生成任务
    focus_modules = plan.get('focus_modules', [])
    daily_minutes = plan.get('daily_minutes', 60)
    
    # 为每个focus module生成任务
    module_minutes = daily_minutes // max(1, len(focus_modules))
    
    for i, module in enumerate(focus_modules):
        task_id = str(uuid.uuid4())
        
        # 根据模块类型生成不同的任务
        if module == 'listening':
            tasks.append({
                'id': task_id,
                'title': f"听力练习 Day {day_index}",
                'description': "完成一套听力练习，包括对话和讲座",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
        elif module == 'reading':
            tasks.append({
                'id': task_id,
                'title': f"阅读练习 Day {day_index}",
                'description': "完成一篇阅读文章，练习快速阅读和细节理解",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
        elif module == 'writing':
            tasks.append({
                'id': task_id,
                'title': f"写作练习 Day {day_index}",
                'description': "写一篇作文，练习论点组织和语言表达",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
        elif module == 'speaking':
            tasks.append({
                'id': task_id,
                'title': f"口语练习 Day {day_index}",
                'description': "练习口语话题，录制并自评",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
        elif module == 'vocabulary':
            tasks.append({
                'id': task_id,
                'title': f"词汇学习 Day {day_index}",
                'description': "学习和复习重点词汇，练习使用",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
        elif module == 'grammar':
            tasks.append({
                'id': task_id,
                'title': f"语法练习 Day {day_index}",
                'description': "练习重点语法结构，做相关习题",
                'time_required': module_minutes,
                'completed': False,
                'progress': 0,
                'time_spent': 0
            })
    
    return tasks


@celery_app.task
def analyze_learning_data(user_id):
    """分析用户的学习数据"""
    logger.info(f"Analyzing learning data for user {user_id}...")
    
    try:
        # 这里实现学习数据分析逻辑
        # 分析用户的学习时间、进度、弱点等
        
        # 模拟分析过程
        time.sleep(3)  # 模拟分析延迟
        
        logger.info(f"Learning data analysis completed for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error analyzing learning data for user {user_id}: {e}")
        return False


@celery_app.task
def generate_progress_report(user_id, period='week'):
    """生成用户的学习进度报告"""
    logger.info(f"Generating progress report for user {user_id} (period: {period})...")
    
    try:
        # 这里实现进度报告生成逻辑
        # 根据指定的时间段生成学习进度报告
        
        # 模拟报告生成
        time.sleep(2)  # 模拟生成延迟
        
        logger.info(f"Progress report generated for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating progress report for user {user_id}: {e}")
        return False

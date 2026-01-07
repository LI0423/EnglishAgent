from celery import Celery
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 创建Celery应用
celery_app = Celery(
    'english_agent_tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['backend.tasks.reminder_tasks', 'backend.tasks.learning_tasks', 'backend.tasks.intelligent_reminder_tasks']
)

# 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    beat_schedule={
        'check-pending-reminders': {
            'task': 'backend.tasks.reminder_tasks.check_pending_reminders',
            'schedule': 60.0,  # 每分钟检查一次
        },
        'generate-daily-tasks': {
            'task': 'backend.tasks.learning_tasks.generate_daily_tasks',
            'schedule': 3600.0,  # 每小时检查一次
        },
    },
)

if __name__ == '__main__':
    celery_app.start()

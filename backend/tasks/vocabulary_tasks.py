from ..tasks import celery_app
from ..utils.tracking import learning_tracker
import logging
import random
import sqlite3
from datetime import datetime, time as dt_time
import yagmail
import os
from utils.milvus_client import MilvusDBClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 词汇数据库路径
VOCABULARY_DB_PATH = "ielts_vocabulary.db"


def get_random_vocabulary(limit=100):
    """从雅思核心词汇中随机获取指定数量的单词"""
    # 初始化Milvus客户端
    milvus_client = MilvusDBClient()

    filter_condition = f''
    results = milvus_client.query(
        filter=filter_condition,
        output_fields=["word", "content", "part_of_speech"],
        limit=limit,
    )

    if not results:
        logger.warning("No vocabulary found in database")
        return []

    # 随机选择指定数量的词汇
    selected_vocabulary = random.sample(results, min(limit, len(results)))
    logger.info(f"Selected {len(selected_vocabulary)} vocabulary items")

    # 处理选中的词汇
    vocabulary_list = []
    for vocab in selected_vocabulary:
        try:
            word_info = {
                'word': vocab.get('word', ''),
                'definition': vocab.get('content', ''),
                'examples': [],  # Milvus数据库中可能没有存储例句
                'pronunciation': '',  # Milvus数据库中可能没有存储发音
                'part_of_speech': vocab.get('part_of_speech', '')
            }
            vocabulary_list.append(word_info)
        except Exception as e:
            logger.error(f"Error processing vocabulary: {e}")
            continue
    
    return vocabulary_list


def send_email(to_email, subject, content):
    """发送邮件"""

    # 从环境变量读取SMTP配置
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.qq.com')  # 例如：smtp.qq.com、smtp.163.com
    SMTP_USER = os.getenv('SMTP_USER', '')  # 你的邮箱账号
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')  # 你的邮箱密码或授权码
    
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP configuration missing. Please set SMTP_USER and SMTP_PASSWORD environment variables.")
        return False
    
    try:
        # 初始化yagmail
        yag = yagmail.SMTP(user=SMTP_USER, password=SMTP_PASSWORD, host=SMTP_SERVER)
        
        # 发送邮件（支持HTML）
        yag.send(
            to=to_email,
            subject=subject,
            contents=content  # yagmail会自动识别HTML
        )
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


def format_vocabulary_email(vocabulary_list):
    """格式化词汇邮件内容"""
    subject = "每日雅思核心词汇 - " + datetime.now().strftime("%Y-%m-%d")
    
    content = f"<h2>每日雅思核心词汇 ({len(vocabulary_list)}个单词)</h2>\n"
    content += "<p>以下是今天为您精选的雅思核心词汇，建议每天花时间复习巩固：</p>\n"
    content += "<ul>\n"
    
    for i, vocab in enumerate(vocabulary_list, 1):
        word = vocab.get('word', '').capitalize()
        definition = vocab.get('definition', 'N/A')
        examples = vocab.get('examples', [])
        pronunciation = vocab.get('pronunciation', 'N/A')
        part_of_speech = vocab.get('part_of_speech', 'N/A')
        
        content += f"<li>\n"
        content += f"<strong>{i}. {word}</strong> ({part_of_speech})\n"
        if pronunciation:
            content += f"<br>发音: {pronunciation}\n"
        content += f"<br>释义: {definition}\n"
        if examples:
            content += "<br>例句: " + "<br>".join([f"- {example}" for example in examples[:2]]) + "\n"
        content += "</li>\n"
    
    content += "</ul>\n"
    content += "<p>祝您学习愉快！</p>"
    
    return subject, content


@celery_app.task
def send_daily_vocabulary_email():
    """发送每日词汇邮件"""
    logger.info("Starting daily vocabulary email task...")
    
    try:
        # 获取所有用户
        conn = sqlite3.connect("ielts_agent.db")
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT id, email FROM users WHERE email IS NOT NULL AND email != ''")
        users = cur.fetchall()
        conn.close()
        
        if not users:
            logger.info("No users with email found")
            return
        
        # 获取随机词汇
        vocabulary_list = get_random_vocabulary(100)
        
        if not vocabulary_list:
            logger.warning("No vocabulary available to send")
            return
        
        # 格式化邮件内容
        subject, html_content = format_vocabulary_email(vocabulary_list)
        
        # 发送邮件给每个用户
        for user in users:
            user_id = user['id']
            email = user['email']
            
            try:
                success = send_email(email, subject, html_content)
                if success:
                    logger.info(f"Vocabulary email sent to user {user_id} at {email}")
                    # 跟踪事件
                    learning_tracker.track_event(
                        user_id=user_id,
                        event_type="feature_used",
                        properties={
                            "feature_name": "每日词汇邮件",
                            "word_count": len(vocabulary_list),
                            "email": email
                        }
                    )
                else:
                    logger.error(f"Failed to send vocabulary email to user {user_id} at {email}")
            except Exception as e:
                logger.error(f"Error sending email to user {user_id}: {e}")
        
    except Exception as e:
        logger.error(f"Error in daily vocabulary email task: {e}")


@celery_app.task
def check_and_send_vocabulary_email():
    """检查时间并发送词汇邮件"""
    # 获取当前时间
    now = datetime.now()
    current_time = now.time()
    
    # 检查是否是晚上9点
    target_time = dt_time(21, 0, 0)
    
    # 允许1分钟的误差
    if target_time <= current_time <= dt_time(21, 1, 0):
        logger.info("It's 9 PM, sending vocabulary emails...")
        send_daily_vocabulary_email.delay()
    else:
        logger.info(f"Current time is {current_time}, not 9 PM, skipping")

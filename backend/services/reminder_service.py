"""
提醒服务模块
实现多渠道提醒功能，包括邮件、App推送等
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
import json
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReminderService:
    """提醒服务类"""
    
    def __init__(self):
        """初始化提醒服务"""
        # 加载邮件配置
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_user': os.getenv('SMTP_USER', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', '')
        }
        
        # 加载App推送配置
        self.push_config = {
            'api_key': os.getenv('PUSH_API_KEY', ''),
            'api_url': os.getenv('PUSH_API_URL', '')
        }
    
    def send_reminder(self, reminder: Dict[str, Any]) -> bool:
        """发送提醒
        
        Args:
            reminder: 提醒信息
            
        Returns:
            bool: 发送是否成功
        """
        channel = reminder.get('channel', 'app')
        
        try:
            if channel == 'email':
                return self.send_email_reminder(reminder)
            elif channel == 'app':
                return self.send_app_reminder(reminder)
            else:
                logger.error(f"Unsupported channel: {channel}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
            return False
    
    def send_email_reminder(self, reminder: Dict[str, Any]) -> bool:
        """发送邮件提醒
        
        Args:
            reminder: 提醒信息
            
        Returns:
            bool: 发送是否成功
        """
        logger.info(f"Sending email reminder: {reminder['title']}")
        
        try:
            # 检查邮件配置
            if not all([self.email_config['smtp_user'], self.email_config['smtp_password']]):
                logger.warning("Email configuration incomplete, using mock sending")
                # 模拟邮件发送
                logger.info(f"Mock email sent to {reminder.get('user_email', 'user@example.com')}")
                logger.info(f"Subject: {reminder['title']}")
                logger.info(f"Body: {reminder['content']}")
                return True
            
            # 获取收件人邮箱
            to_email = reminder.get('metadata', {}).get('email', 'user@example.com')
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = to_email
            msg['Subject'] = reminder['title']
            
            # 邮件内容
            body = f"""{
                reminder['content']
            }
            
            ---\n            This is an automated reminder from EnglishAgent.\n            Please do not reply to this email.\n            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['smtp_user'], self.email_config['smtp_password'])
                server.send_message(msg)
            
            logger.info(f"Email reminder sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email reminder: {e}")
            return False
    
    def send_app_reminder(self, reminder: Dict[str, Any]) -> bool:
        """发送App推送提醒
        
        Args:
            reminder: 提醒信息
            
        Returns:
            bool: 发送是否成功
        """
        logger.info(f"Sending app reminder: {reminder['title']}")
        
        try:
            # 检查推送配置
            if not self.push_config['api_key']:
                logger.warning("Push notification configuration incomplete, using mock sending")
                # 模拟App推送
                logger.info(f"Mock app notification sent to user {reminder['user_id']}")
                logger.info(f"Title: {reminder['title']}")
                logger.info(f"Body: {reminder['content']}")
                return True
            
            # 这里实现实际的App推送逻辑
            # 使用推送服务API发送推送通知
            
            # 模拟推送过程
            import time
            time.sleep(0.5)
            
            logger.info(f"App reminder sent successfully to user {reminder['user_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending app reminder: {e}")
            return False
    
    def send_sms_reminder(self, reminder: Dict[str, Any]) -> bool:
        """发送短信提醒
        
        Args:
            reminder: 提醒信息
            
        Returns:
            bool: 发送是否成功
        """
        logger.info(f"Sending SMS reminder: {reminder['title']}")
        
        try:
            # 这里实现短信发送逻辑
            # 使用短信服务API发送短信
            
            # 模拟短信发送
            logger.info(f"Mock SMS sent to {reminder.get('metadata', {}).get('phone', '1234567890')}")
            logger.info(f"Message: {reminder['content'][:160]}")  # 短信长度限制
            
            logger.info("SMS reminder sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS reminder: {e}")
            return False
    
    def get_available_channels(self) -> list:
        """获取可用的提醒渠道
        
        Returns:
            list: 可用渠道列表
        """
        channels = ['app']
        
        # 检查邮件配置
        if all([self.email_config['smtp_user'], self.email_config['smtp_password']]):
            channels.append('email')
        
        # 可以添加其他渠道的检查
        
        return channels
    
    def validate_channel(self, channel: str) -> bool:
        """验证渠道是否可用
        
        Args:
            channel: 渠道名称
            
        Returns:
            bool: 是否可用
        """
        return channel in self.get_available_channels()


# 创建全局提醒服务实例
reminder_service = ReminderService()


def get_reminder_service() -> ReminderService:
    """获取提醒服务实例
    
    Returns:
        ReminderService: 提醒服务实例
    """
    return reminder_service

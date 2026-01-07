"""
学习数据采集模块
实现学习行为埋点和数据采集功能
"""
import time
import logging
import json
from typing import Dict, Any, Optional
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LearningTracker:
    """学习数据采集器"""
    
    def __init__(self):
        """初始化学习数据采集器"""
        # 事件类型定义
        self.event_types = {
            'study_session_started': '学习会话开始',
            'study_session_completed': '学习会话完成',
            'exercise_started': '练习开始',
            'exercise_completed': '练习完成',
            'mistake_made': '出错',
            'vocabulary_learned': '学习词汇',
            'diagnostic_taken': '诊断测试',
            'plan_created': '创建学习计划',
            'plan_updated': '更新学习计划',
            'plan_completed': '完成学习计划',
            'reminder_sent': '发送提醒',
            'reminder_clicked': '点击提醒',
            'feedback_provided': '提供反馈',
            'feature_used': '使用功能'
        }
    
    def track_event(self, user_id: str, event_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪学习事件
        
        Args:
            user_id: 用户ID
            event_type: 事件类型
            properties: 事件属性
            
        Returns:
            Dict: 事件数据
        """
        if event_type not in self.event_types:
            logger.warning(f"Unknown event type: {event_type}")
        
        # 构建事件数据
        event = {
            'event_id': str(uuid.uuid4()),
            'user_id': user_id,
            'event_type': event_type,
            'event_name': self.event_types.get(event_type, event_type),
            'properties': properties,
            'timestamp': int(time.time()),
            'created_at': int(time.time())
        }
        
        logger.info(f"Tracking event: {event_type} for user {user_id}")
        
        # 这里可以添加数据存储逻辑
        # 例如写入数据库、消息队列等
        
        # 模拟数据存储
        self._store_event(event)
        
        return event
    
    def track_study_session(self, user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪学习会话
        
        Args:
            user_id: 用户ID
            session_data: 会话数据
            
        Returns:
            Dict: 会话事件数据
        """
        properties = {
            'session_id': session_data.get('session_id', str(uuid.uuid4())),
            'module': session_data.get('module', 'general'),
            'duration': session_data.get('duration', 0),
            'completed': session_data.get('completed', False),
            'score': session_data.get('score', 0),
            'activities': session_data.get('activities', []),
            'metadata': session_data.get('metadata', {})
        }
        
        return self.track_event(user_id, 'study_session_completed', properties)
    
    def track_exercise(self, user_id: str, exercise_data: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪练习
        
        Args:
            user_id: 用户ID
            exercise_data: 练习数据
            
        Returns:
            Dict: 练习事件数据
        """
        properties = {
            'exercise_id': exercise_data.get('exercise_id', str(uuid.uuid4())),
            'type': exercise_data.get('type', 'general'),
            'difficulty': exercise_data.get('difficulty', 'medium'),
            'completed': exercise_data.get('completed', False),
            'correct': exercise_data.get('correct', False),
            'attempts': exercise_data.get('attempts', 1),
            'time_spent': exercise_data.get('time_spent', 0),
            'feedback': exercise_data.get('feedback', ''),
            'metadata': exercise_data.get('metadata', {})
        }
        
        event_type = 'exercise_completed' if exercise_data.get('completed', False) else 'exercise_started'
        return self.track_event(user_id, event_type, properties)
    
    def track_mistake(self, user_id: str, mistake_data: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪错误
        
        Args:
            user_id: 用户ID
            mistake_data: 错误数据
            
        Returns:
            Dict: 错误事件数据
        """
        properties = {
            'mistake_id': mistake_data.get('mistake_id', str(uuid.uuid4())),
            'module': mistake_data.get('module', 'general'),
            'type': mistake_data.get('type', 'general'),
            'content': mistake_data.get('content', ''),
            'user_answer': mistake_data.get('user_answer', ''),
            'correct_answer': mistake_data.get('correct_answer', ''),
            'difficulty': mistake_data.get('difficulty', 'medium'),
            'tags': mistake_data.get('tags', []),
            'metadata': mistake_data.get('metadata', {})
        }
        
        return self.track_event(user_id, 'mistake_made', properties)
    
    def track_vocabulary(self, user_id: str, vocab_data: Dict[str, Any]) -> Dict[str, Any]:
        """跟踪词汇学习
        
        Args:
            user_id: 用户ID
            vocab_data: 词汇数据
            
        Returns:
            Dict: 词汇学习事件数据
        """
        properties = {
            'word': vocab_data.get('word', ''),
            'definition': vocab_data.get('definition', ''),
            'difficulty': vocab_data.get('difficulty', 'medium'),
            'mastery_level': vocab_data.get('mastery_level', 0),
            'source': vocab_data.get('source', 'general'),
            'metadata': vocab_data.get('metadata', {})
        }
        
        return self.track_event(user_id, 'vocabulary_learned', properties)
    
    def track_feature_usage(self, user_id: str, feature_name: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """跟踪功能使用
        
        Args:
            user_id: 用户ID
            feature_name: 功能名称
            metadata: 元数据
            
        Returns:
            Dict: 功能使用事件数据
        """
        properties = {
            'feature_name': feature_name,
            'metadata': metadata or {}
        }
        
        return self.track_event(user_id, 'feature_used', properties)
    
    def _store_event(self, event: Dict[str, Any]):
        """存储事件数据
        
        Args:
            event: 事件数据
        """
        # 导入数据库模块
        from backend.db import save_learning_event
        
        try:
            # 存储到数据库
            save_learning_event(
                event_id=event['event_id'],
                user_id=event['user_id'],
                event_data=event
            )
            logger.info(f"Event stored successfully: {event['event_type']} with ID: {event['event_id']}")
        except Exception as e:
            logger.error(f"Error storing event: {str(e)}")
            # 可以添加错误处理逻辑，例如重试机制或写入本地文件
    
    def get_event_stats(self, user_id: str, time_range: int = 86400) -> Dict[str, Any]:
        """获取用户事件统计
        
        Args:
            user_id: 用户ID
            time_range: 时间范围（秒）
            
        Returns:
            Dict: 事件统计数据
        """
        # 导入数据库模块
        from backend.db import get_event_stats as get_db_event_stats
        from backend.db import get_activity_stats
        
        try:
            # 从数据库获取事件统计
            event_stats = get_db_event_stats(user_id, time_range)
            activity_stats = get_activity_stats(user_id, time_range)
            
            # 构建完整的统计数据
            stats = {
                'total_events': event_stats['total_events'],
                'event_counts': event_stats['event_counts'],
                'active_days': event_stats['active_days'],
                'total_study_time': activity_stats['total_duration'],
                'average_session_duration': activity_stats['average_duration'],
                'total_activities': activity_stats['total_activities'],
                'average_score': activity_stats['average_score'],
                'time_range': time_range
            }
            
            return stats
        except Exception as e:
            logger.error(f"Error getting event stats: {str(e)}")
            # 返回默认值
            return {
                'total_events': 0,
                'event_counts': {},
                'active_days': 0,
                'total_study_time': 0,
                'average_session_duration': 0,
                'total_activities': 0,
                'average_score': 0.0,
                'time_range': time_range
            }


# 创建全局学习追踪器实例
learning_tracker = LearningTracker()


def get_learning_tracker() -> LearningTracker:
    """获取学习追踪器实例
    
    Returns:
        LearningTracker: 学习追踪器实例
    """
    return learning_tracker

"""
智能提醒策略模块
实现基于用户学习习惯的智能提醒算法
"""
import time
import logging
import statistics
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligentReminderStrategy:
    """智能提醒策略类"""
    
    def __init__(self):
        """初始化智能提醒策略"""
        # 学习习惯分析参数
        self.min_session_count = 3  # 最小学习会话数
        self.time_window_days = 14  # 时间窗口（天）
        
        # 提醒策略参数
        self.default_reminder_hour = 9  # 默认提醒时间（小时）
        self.reminder_frequency = 1  # 默认每天提醒次数
        self.max_reminders_per_day = 3  # 每天最大提醒次数
    
    def analyze_learning_habits(self, user_id: str, learning_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析用户的学习习惯
        
        Args:
            user_id: 用户ID
            learning_sessions: 学习会话列表
            
        Returns:
            Dict: 学习习惯分析结果
        """
        logger.info(f"Analyzing learning habits for user {user_id}...")
        
        if not learning_sessions or len(learning_sessions) < self.min_session_count:
            logger.info(f"Insufficient learning sessions for user {user_id}, using default habits")
            return self._get_default_habits()
        
        # 过滤最近的学习会话
        cutoff_time = time.time() - (self.time_window_days * 24 * 3600)
        recent_sessions = [s for s in learning_sessions if s.get('created_at', 0) >= cutoff_time]
        
        if not recent_sessions:
            logger.info(f"No recent learning sessions for user {user_id}, using default habits")
            return self._get_default_habits()
        
        # 分析学习时间模式
        study_hours = []
        study_durations = []
        study_days = set()
        
        for session in recent_sessions:
            session_time = session.get('created_at', 0)
            if session_time:
                session_dt = datetime.fromtimestamp(session_time)
                study_hours.append(session_dt.hour)
                study_days.add(session_dt.date())
                
                # 计算学习时长
                duration = session.get('duration', 0)
                if duration:
                    study_durations.append(duration)
        
        # 计算统计数据
        analysis = {
            'preferred_hours': self._get_preferred_hours(study_hours),
            'average_session_duration': statistics.mean(study_durations) if study_durations else 30,
            'study_frequency': len(study_days) / self.time_window_days,
            'total_sessions': len(recent_sessions),
            'habits_established': len(study_days) >= 5,  # 至少5天有学习记录
            'last_study_time': max(s.get('created_at', 0) for s in recent_sessions)
        }
        
        logger.info(f"Learning habits analysis completed for user {user_id}: {analysis}")
        return analysis
    
    def generate_reminder_schedule(self, user_id: str, habits: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成提醒计划
        
        Args:
            user_id: 用户ID
            habits: 学习习惯分析结果
            preferences: 用户提醒偏好
            
        Returns:
            List: 提醒计划列表
        """
        logger.info(f"Generating reminder schedule for user {user_id}...")
        
        reminders = []
        today = datetime.now().date()
        
        # 确定提醒时间
        reminder_times = self._calculate_reminder_times(habits, preferences)
        
        # 生成今天的提醒
        for reminder_time in reminder_times:
            scheduled_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=reminder_time)
            scheduled_timestamp = int(scheduled_time.timestamp())
            
            # 确保提醒时间在未来
            if scheduled_timestamp > time.time():
                reminder = {
                    'user_id': user_id,
                    'type': 'study_reminder',
                    'title': self._generate_reminder_title(habits),
                    'content': self._generate_reminder_content(habits),
                    'scheduled_at': scheduled_timestamp,
                    'channel': preferences.get('channels', ['app'])[0],
                    'metadata': {
                        'habits': habits,
                        'preferences': preferences
                    }
                }
                reminders.append(reminder)
        
        logger.info(f"Generated {len(reminders)} reminders for user {user_id}")
        return reminders
    
    def _calculate_reminder_times(self, habits: Dict[str, Any], preferences: Dict[str, Any]) -> List[float]:
        """计算最佳提醒时间
        
        Args:
            habits: 学习习惯分析结果
            preferences: 用户提醒偏好
            
        Returns:
            List: 提醒时间列表（小时）
        """
        # 使用用户偏好的时间
        if preferences.get('preferred_times'):
            preferred_times = []
            for time_str in preferences['preferred_times']:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    preferred_times.append(hour + minute/60)
                except ValueError:
                    logger.warning(f"Invalid time format: {time_str}")
            if preferred_times:
                return preferred_times[:self.max_reminders_per_day]
        
        # 使用学习习惯分析结果
        preferred_hours = habits.get('preferred_hours', [self.default_reminder_hour])
        
        # 计算提醒时间
        reminder_times = []
        for hour in preferred_hours[:self.max_reminders_per_day]:
            # 检查是否在安静时间
            if not self._is_quiet_hour(hour, preferences.get('quiet_hours')):
                reminder_times.append(hour)
        
        # 如果没有合适的时间，使用默认时间
        if not reminder_times:
            reminder_times = [self.default_reminder_hour]
        
        return reminder_times
    
    def _generate_reminder_title(self, habits: Dict[str, Any]) -> str:
        """生成提醒标题
        
        Args:
            habits: 学习习惯分析结果
            
        Returns:
            str: 提醒标题
        """
        if habits.get('habits_established'):
            return "📚 该学习了！坚持你的学习习惯"
        else:
            return "🌟 开始学习之旅，建立良好习惯"
    
    def _generate_reminder_content(self, habits: Dict[str, Any]) -> str:
        """生成提醒内容
        
        Args:
            habits: 学习习惯分析结果
            
        Returns:
            str: 提醒内容
        """
        avg_duration = habits.get('average_session_duration', 30)
        study_frequency = habits.get('study_frequency', 0.5)
        
        if study_frequency >= 0.7:  # 每周学习5天以上
            content = f"""你已经养成了良好的学习习惯！

建议今天学习 {int(avg_duration)} 分钟，保持你的学习节奏。

坚持就是胜利，加油！"""
        elif study_frequency >= 0.3:  # 每周学习2-4天
            content = f"""你的学习习惯正在形成中！

建议今天学习 {int(avg_duration)} 分钟，继续保持。

 consistency is key to success!"""
        else:  # 每周学习少于2天
            content = f"""开始你的学习之旅吧！

建议今天学习 {int(avg_duration)} 分钟，培养良好的学习习惯。

Small steps lead to big achievements!"""
        
        return content
    
    def _get_preferred_hours(self, study_hours: List[int]) -> List[float]:
        """获取用户偏好的学习时间
        
        Args:
            study_hours: 学习时间列表（小时）
            
        Returns:
            List: 偏好学习时间列表
        """
        if not study_hours:
            return [self.default_reminder_hour]
        
        # 统计每个小时的学习次数
        hour_counts = {}
        for hour in study_hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        # 按学习次数排序
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 返回前3个最常用的学习时间
        preferred_hours = [hour for hour, _ in sorted_hours[:3]]
        
        # 如果不足3个，添加默认时间
        while len(preferred_hours) < 3:
            default_hour = self.default_reminder_hour + len(preferred_hours)
            if default_hour not in preferred_hours and default_hour < 24:
                preferred_hours.append(default_hour)
            else:
                break
        
        return preferred_hours
    
    def _is_quiet_hour(self, hour: float, quiet_hours: Optional[Dict[str, str]]) -> bool:
        """检查是否在安静时间
        
        Args:
            hour: 小时
            quiet_hours: 安静时间设置
            
        Returns:
            bool: 是否在安静时间
        """
        if not quiet_hours:
            return False
        
        try:
            start_time = quiet_hours.get('start', '22:00')
            end_time = quiet_hours.get('end', '08:00')
            
            start_hour, start_minute = map(int, start_time.split(':'))
            end_hour, end_minute = map(int, end_time.split(':'))
            
            start_total = start_hour + start_minute/60
            end_total = end_hour + end_minute/60
            
            # 检查是否在安静时间范围内
            if start_total <= end_total:
                return start_total <= hour <= end_total
            else:
                # 跨天的情况
                return hour >= start_total or hour <= end_total
                
        except ValueError:
            logger.warning(f"Invalid quiet hours format: {quiet_hours}")
            return False
    
    def _get_default_habits(self) -> Dict[str, Any]:
        """获取默认学习习惯
        
        Returns:
            Dict: 默认学习习惯
        """
        return {
            'preferred_hours': [self.default_reminder_hour],
            'average_session_duration': 30,
            'study_frequency': 0.5,
            'total_sessions': 0,
            'habits_established': False,
            'last_study_time': time.time() - 24 * 3600  # 假设昨天学习过
        }
    
    def should_send_reminder(self, user_id: str, last_reminder_time: Optional[int], habits: Dict[str, Any]) -> bool:
        """判断是否应该发送提醒
        
        Args:
            user_id: 用户ID
            last_reminder_time: 上次提醒时间
            habits: 学习习惯分析结果
            
        Returns:
            bool: 是否应该发送提醒
        """
        # 检查上次提醒时间
        if last_reminder_time:
            time_since_last = time.time() - last_reminder_time
            # 至少1小时后再发送提醒
            if time_since_last < 3600:
                return False
        
        # 检查学习频率
        study_frequency = habits.get('study_frequency', 0.5)
        if study_frequency >= 0.7:
            # 高频学习者，减少提醒
            return True
        elif study_frequency >= 0.3:
            # 中频学习者，正常提醒
            return True
        else:
            # 低频学习者，增加提醒
            return True
    
    def generate_personalized_reminder(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成个性化提醒
        
        Args:
            user_id: 用户ID
            context: 上下文信息
            
        Returns:
            Dict: 个性化提醒
        """
        habits = context.get('habits', self._get_default_habits())
        preferences = context.get('preferences', {})
        
        # 生成提醒内容
        reminder = {
            'user_id': user_id,
            'type': 'personalized_reminder',
            'title': self._generate_reminder_title(habits),
            'content': self._generate_reminder_content(habits),
            'scheduled_at': int(time.time() + 3600),  # 1小时后提醒
            'channel': preferences.get('channels', ['app'])[0],
            'metadata': {
                'context': context,
                'habits': habits
            }
        }
        
        return reminder


# 创建全局智能提醒策略实例
intelligent_reminder_strategy = IntelligentReminderStrategy()


def get_intelligent_reminder_strategy() -> IntelligentReminderStrategy:
    """获取智能提醒策略实例
    
    Returns:
        IntelligentReminderStrategy: 智能提醒策略实例
    """
    return intelligent_reminder_strategy

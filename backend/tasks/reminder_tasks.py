from ..tasks import celery_app
from ..db import (
    count_recent_user_reminders,
    get_pending_reminders,
    get_reminder_preferences,
    mark_reminder_retry,
    reschedule_reminder,
    update_reminder_metadata,
    update_reminder_status,
)
from datetime import datetime, timedelta
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 5 * 60
MAX_REMINDERS_PER_WINDOW = 2
REMINDER_WINDOW_SECONDS = 3 * 3600
PREFERRED_TIME_TOLERANCE_MINUTES = 90


@celery_app.task
def check_pending_reminders():
    """检查待处理的提醒并发送"""
    logger.info("Checking pending reminders...")
    
    try:
        # 获取待处理的提醒
        pending_reminders = get_pending_reminders()
        logger.info(f"Found {len(pending_reminders)} pending reminders")

        now = int(time.time())
        by_user = {}
        for reminder in pending_reminders:
            user_id = str(reminder.get("user_id") or "")
            by_user.setdefault(user_id, []).append(reminder)

        for user_id, reminders in by_user.items():
            preferences = get_reminder_preferences(user_id)
            if preferences and not preferences['enabled']:
                logger.info(f"Reminders disabled for user {user_id}, skipping")
                continue

            max_per_window = _strategy_int(preferences, "max_reminders_per_window", MAX_REMINDERS_PER_WINDOW, 1, 10)
            window_seconds = _strategy_int(preferences, "frequency_window_hours", int(REMINDER_WINDOW_SECONDS / 3600), 1, 24) * 3600
            preferred_tolerance_minutes = _strategy_int(
                preferences,
                "preferred_tolerance_minutes",
                PREFERRED_TIME_TOLERANCE_MINUTES,
                15,
                360,
            )
            merge_similar_enabled = _strategy_bool(preferences, "merge_similar_enabled", True)
            high_priority_bypass_cap = _strategy_bool(preferences, "high_priority_bypass_cap", True)

            merged_reminders = _merge_user_reminders(reminders) if merge_similar_enabled else reminders
            sent_recent = count_recent_user_reminders(
                user_id,
                since_ts=now - window_seconds,
                statuses=["sent"],
            )
            non_urgent_budget = max(0, max_per_window - int(sent_recent or 0))
            current_local = time.localtime(now)

            for reminder in sorted(
                merged_reminders,
                key=lambda x: (-_priority_rank(x), int(x.get("scheduled_at") or 0)),
            ):
                rid = str(reminder.get("id") or "")
                if not rid:
                    continue
                priority = _priority_rank(reminder)

                # 安静时段：重排到安静时段结束后
                if is_quiet_hour(preferences, current_local):
                    next_time = _next_quiet_end_ts(preferences, now)
                    reschedule_reminder(rid, next_time, reason="quiet_hours")
                    logger.info(f"Reminder {rid} deferred due to quiet hours, next={next_time}")
                    continue

                # 偏好时段：非高优先级在偏好窗口外时重排
                if priority < 3 and not _in_preferred_window(preferences, current_local, preferred_tolerance_minutes):
                    next_time = _next_preferred_ts(preferences, now)
                    reschedule_reminder(rid, next_time, reason="preferred_time")
                    logger.info(f"Reminder {rid} deferred to preferred time, next={next_time}")
                    continue

                # 频控：非高优先级超预算后延迟
                if ((priority < 3) or (not high_priority_bypass_cap)) and non_urgent_budget <= 0:
                    next_time = now + window_seconds // 2
                    reschedule_reminder(rid, next_time, reason="frequency_cap")
                    logger.info(f"Reminder {rid} deferred by frequency cap, next={next_time}")
                    continue

                try:
                    send_reminder.delay(rid)
                    if (priority < 3) or (not high_priority_bypass_cap):
                        non_urgent_budget -= 1
                    logger.info(f"Scheduled reminder {rid} for delivery")
                except Exception as e:
                    logger.error(f"Error scheduling reminder {rid}: {e}")
                
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
            metadata = dict(reminder.get("metadata") or {})
            metadata["delivered_at"] = int(time.time())
            metadata["last_error"] = ""
            update_reminder_metadata(reminder_id, metadata)
            update_reminder_status(reminder_id, 'sent', int(time.time()))
            logger.info(f"Reminder {reminder_id} sent successfully")
        else:
            retry_state = mark_reminder_retry(
                reminder_id,
                "delivery_failed",
                max_retries=MAX_RETRY_COUNT,
                retry_delay_seconds=RETRY_DELAY_SECONDS,
            )
            logger.error(f"Failed to send reminder {reminder_id}, state={retry_state}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id}: {e}")
        mark_reminder_retry(
            reminder_id,
            str(e),
            max_retries=MAX_RETRY_COUNT,
            retry_delay_seconds=RETRY_DELAY_SECONDS,
        )
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


def _priority_rank(reminder):
    metadata = dict(reminder.get("metadata") or {})
    raw = str(metadata.get("priority", "medium")).strip().lower()
    if raw == "high":
        return 3
    if raw == "low":
        return 1
    return 2


def _preferred_minutes(preferences):
    if not preferences:
        return []
    minutes = []
    for t in list(preferences.get("preferred_times") or [])[:6]:
        try:
            h_str, m_str = str(t).split(":")
            h = max(0, min(23, int(h_str)))
            m = max(0, min(59, int(m_str)))
            minutes.append(h * 60 + m)
        except Exception:
            continue
    return sorted(set(minutes))


def _strategy_config(preferences):
    if not preferences:
        return {}
    return dict(preferences.get("strategy_config") or {})


def _strategy_int(preferences, key, default, low, high):
    cfg = _strategy_config(preferences)
    try:
        value = int(cfg.get(key, default))
    except Exception:
        value = int(default)
    return max(int(low), min(int(high), int(value)))


def _strategy_bool(preferences, key, default):
    cfg = _strategy_config(preferences)
    if key not in cfg:
        return bool(default)
    raw = cfg.get(key)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _in_preferred_window(preferences, current_time, tolerance_minutes=PREFERRED_TIME_TOLERANCE_MINUTES):
    preferred = _preferred_minutes(preferences)
    if not preferred:
        return True
    current_minutes = int(current_time.tm_hour) * 60 + int(current_time.tm_min)
    for target in preferred:
        diff = abs(current_minutes - target)
        circular_diff = min(diff, 1440 - diff)
        if circular_diff <= int(tolerance_minutes):
            return True
    return False


def _next_preferred_ts(preferences, now_ts):
    preferred = _preferred_minutes(preferences)
    if not preferred:
        return int(now_ts) + 5 * 60

    now_dt = datetime.fromtimestamp(int(now_ts))
    candidates = []
    for minute in preferred:
        hour = minute // 60
        mins = minute % 60
        target = datetime.combine(now_dt.date(), datetime.min.time()).replace(hour=hour, minute=mins)
        if int(target.timestamp()) <= int(now_ts):
            target = target + timedelta(days=1)
        candidates.append(int(target.timestamp()))
    return min(candidates) if candidates else int(now_ts) + 5 * 60


def _next_quiet_end_ts(preferences, now_ts):
    if not preferences or not preferences.get("quiet_hours"):
        return int(now_ts) + 30 * 60
    quiet = preferences.get("quiet_hours") or {}
    try:
        s_h, s_m = [int(x) for x in str(quiet.get("start", "23:00")).split(":")]
        e_h, e_m = [int(x) for x in str(quiet.get("end", "07:00")).split(":")]
    except Exception:
        return int(now_ts) + 30 * 60

    current = time.localtime(int(now_ts))
    current_total = int(current.tm_hour) * 60 + int(current.tm_min)
    start_total = max(0, min(23, s_h)) * 60 + max(0, min(59, s_m))
    end_total = max(0, min(23, e_h)) * 60 + max(0, min(59, e_m))
    # +1 分钟保证已脱离安静窗口
    if start_total <= end_total:
        offset = (end_total - current_total + 1) if current_total <= end_total else (1440 - current_total + end_total + 1)
    else:
        if current_total >= start_total:
            offset = 1440 - current_total + end_total + 1
        elif current_total <= end_total:
            offset = end_total - current_total + 1
        else:
            offset = 1
    return int(now_ts) + max(1, int(offset)) * 60


def _merge_user_reminders(reminders):
    if len(reminders) <= 1:
        return reminders

    grouped = {}
    passthrough = []
    for item in reminders:
        if _priority_rank(item) >= 3:
            passthrough.append(item)
            continue
        key = (str(item.get("type") or "task"), str(item.get("channel") or "app"))
        grouped.setdefault(key, []).append(item)

    merged_dispatch = list(passthrough)
    now = int(time.time())
    for _, rows in grouped.items():
        if len(rows) <= 1:
            merged_dispatch.extend(rows)
            continue

        sorted_rows = sorted(
            rows,
            key=lambda x: (-_priority_rank(x), int(x.get("scheduled_at") or 0), str(x.get("id") or "")),
        )
        primary = sorted_rows[0]
        rest = sorted_rows[1:]
        primary_meta = dict(primary.get("metadata") or {})
        merged_ids = [str(x.get("id") or "") for x in rest if str(x.get("id") or "")]
        merged_contents = [str(primary.get("content") or "").strip()] + [str(x.get("content") or "").strip() for x in rest]
        merged_contents = [x for x in merged_contents if x]

        if merged_ids:
            primary_title = str(primary.get("title") or "学习提醒")
            primary["title"] = f"{primary_title}（合并{len(merged_ids)}条）"
            primary["content"] = "；".join(merged_contents[:4])
            primary_meta["merged_count"] = len(merged_ids)
            primary_meta["merged_ids"] = merged_ids
            primary_meta["merged_at"] = now
            update_reminder_metadata(str(primary.get("id")), primary_meta)
            primary["metadata"] = primary_meta

            for secondary in rest:
                sid = str(secondary.get("id") or "")
                if not sid:
                    continue
                s_meta = dict(secondary.get("metadata") or {})
                s_meta["merged_into"] = str(primary.get("id") or "")
                s_meta["merged_at"] = now
                update_reminder_metadata(sid, s_meta)
                update_reminder_status(sid, "merged", None)

        merged_dispatch.append(primary)

    return merged_dispatch


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

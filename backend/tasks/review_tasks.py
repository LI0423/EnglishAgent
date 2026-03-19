import time
import uuid
import logging

from ..tasks import celery_app
from ..db import (
    create_reminder,
    get_due_mistake_user_counts,
    get_due_vocabulary_user_counts,
    has_recent_reminder,
)

logger = logging.getLogger(__name__)


def _build_channel() -> str:
    return "app"


@celery_app.task
def schedule_due_review_reminders():
    """按到期复习数据生成站内提醒，避免重复推送。"""
    now = int(time.time())
    created = 0
    skipped = 0

    # 错题复习提醒
    for row in get_due_mistake_user_counts(now_ts=now):
        user_id = str(row.get("user_id") or "")
        if not user_id:
            continue
        source = "mistake_due_daily"
        if has_recent_reminder(user_id, "review", source, lookback_seconds=18 * 3600):
            skipped += 1
            continue
        due_count = int(row.get("due_count") or 0)
        create_reminder(
            str(uuid.uuid4()),
            user_id,
            {
                "type": "review",
                "title": "错题复习提醒",
                "content": f"你有 {due_count} 道错题已到复习时间，建议现在完成一轮复盘。",
                "scheduled_at": now,
                "status": "pending",
                "channel": _build_channel(),
                "metadata": {
                    "source": source,
                    "due_count": due_count,
                },
            },
        )
        created += 1

    # 词汇复习提醒
    for row in get_due_vocabulary_user_counts(now_ts=now):
        user_id = str(row.get("user_id") or "")
        if not user_id:
            continue
        source = "vocabulary_due_daily"
        if has_recent_reminder(user_id, "review", source, lookback_seconds=18 * 3600):
            skipped += 1
            continue
        due_count = int(row.get("due_count") or 0)
        create_reminder(
            str(uuid.uuid4()),
            user_id,
            {
                "type": "review",
                "title": "词汇复习提醒",
                "content": f"你有 {due_count} 个词汇已到复习时间，建议完成一次间隔复习。",
                "scheduled_at": now,
                "status": "pending",
                "channel": _build_channel(),
                "metadata": {
                    "source": source,
                    "due_count": due_count,
                },
            },
        )
        created += 1

    logger.info("schedule_due_review_reminders done: created=%s skipped=%s", created, skipped)
    return {"created": created, "skipped": skipped}

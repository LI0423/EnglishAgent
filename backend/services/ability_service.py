from __future__ import annotations

import time
from statistics import mean
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.db import (
    get_daily_task_by_date,
    get_latest_user_plan,
    get_user_events,
    get_user_profile,
    save_learning_event,
    update_task_progress,
)


DIFFICULTY_LABELS = {
    "easy": "基础",
    "medium": "进阶",
    "hard": "高阶",
}

DIFFICULTY_RANK = {
    "easy": 1,
    "basic": 1,
    "medium": 2,
    "intermediate": 2,
    "hard": 3,
    "advanced": 3,
}


def normalize_difficulty(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"easy", "basic"}:
        return "easy"
    if raw in {"hard", "advanced"}:
        return "hard"
    return "medium"


def difficulty_label(value: Any) -> str:
    return DIFFICULTY_LABELS.get(normalize_difficulty(value), "进阶")


def record_practice_result(
    user_id: str,
    module: str,
    result: Dict[str, Any],
    *,
    difficulty: str = "medium",
    topic: str = "general",
    direction: str = "",
    practice_mode: str = "",
    used_hint: bool = False,
    source: str = "",
) -> None:
    now = int(time.time())
    score = _to_float(result.get("overall"))
    properties = {
        "module": module,
        "difficulty": normalize_difficulty(difficulty),
        "difficulty_label": difficulty_label(difficulty),
        "topic": topic,
        "direction": direction,
        "practice_mode": practice_mode,
        "used_hint": bool(used_hint),
        "source": source,
        "score": score,
        "accuracy": _to_float(result.get("accuracy")),
        "fluency": _to_float(result.get("fluency")),
        "grammar": _to_float(result.get("grammar")),
        "vocabulary": _to_float(result.get("vocabulary")),
    }
    save_learning_event(
        str(uuid4()),
        user_id,
        {
            "event_type": "practice_result",
            "event_name": f"{module}_practice_checked",
            "properties": properties,
            "timestamp": now,
        },
    )
    _mark_daily_plan_task(user_id, module, now)


def _mark_daily_plan_task(user_id: str, module: str, now: int) -> None:
    plan = get_latest_user_plan(user_id)
    if not plan or str(plan.get("status") or "").lower() != "active":
        return
    today_task = get_daily_task_by_date(str(plan["id"]), _day_start(now))
    if not today_task:
        return

    module_key = str(module or "").strip().lower()
    for item in today_task.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        if bool(item.get("completed")):
            continue
        item_module = str(item.get("module") or "").strip().lower()
        if item_module != module_key:
            continue
        update_task_progress(
            str(today_task["id"]),
            {
                "task_id": item.get("id"),
                "completed": True,
                "progress": 100,
                "time_spent": int(item.get("time_spent") or item.get("duration_minutes") or 10),
            },
        )
        return


def _day_start(ts: int) -> int:
    local = time.localtime(ts)
    return int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, local.tm_wday, local.tm_yday, local.tm_isdst)))


def get_difficulty_recommendation(user_id: str, module: str = "translation") -> Dict[str, Any]:
    module_key = str(module or "translation").strip().lower()
    events = _recent_module_practice_events(user_id, module_key, limit=20)
    scored_events = [event for event in events if event.get("score") is not None]
    recent = scored_events[:5]

    if len(recent) >= 3:
        avg_score = round(mean(_to_float(event.get("score")) for event in recent), 2)
        recommended = _difficulty_from_score(avg_score)
        trend = _score_trend(scored_events[:10])
        reason = _score_reason(avg_score, trend, len(recent))
        return {
            "module": module_key,
            "recommended_difficulty": recommended,
            "label": DIFFICULTY_LABELS[recommended],
            "reason": reason,
            "confidence": min(0.95, round(0.5 + len(recent) * 0.08, 2)),
            "sample_count": len(scored_events),
            "average_score": avg_score,
            "trend": trend,
            "source": "recent_practice",
        }

    profile = get_user_profile(user_id)
    profile_band = _to_float((profile or {}).get("current_band_overall"))
    if profile_band > 0:
        recommended = _difficulty_from_band(profile_band)
        return {
            "module": module_key,
            "recommended_difficulty": recommended,
            "label": DIFFICULTY_LABELS[recommended],
            "reason": f"当前翻译练习样本不足，暂按能力档案 {profile_band:.1f} 分推荐{DIFFICULTY_LABELS[recommended]}。",
            "confidence": 0.45,
            "sample_count": len(scored_events),
            "average_score": None,
            "trend": "insufficient_data",
            "source": "profile",
        }

    return {
        "module": module_key,
        "recommended_difficulty": "easy",
        "label": "基础",
        "reason": "暂无足够练习数据，先从基础难度开始，完成几次批改后会自动调整。",
        "confidence": 0.25,
        "sample_count": len(scored_events),
        "average_score": None,
        "trend": "insufficient_data",
        "source": "default",
    }


def _recent_module_practice_events(user_id: str, module: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = get_user_events(user_id, limit=max(limit * 3, 60), offset=0)
    matched: List[Dict[str, Any]] = []
    for row in rows:
        props = row.get("properties") or {}
        row_module = str(props.get("module") or "").strip().lower()
        if row.get("event_type") != "practice_result" or row_module != module:
            continue
        matched.append({
            "score": props.get("score"),
            "difficulty": normalize_difficulty(props.get("difficulty")),
            "timestamp": row.get("timestamp"),
        })
        if len(matched) >= limit:
            break
    return matched


def _difficulty_from_score(score: float) -> str:
    if score >= 8.0:
        return "hard"
    if score >= 6.0:
        return "medium"
    return "easy"


def _difficulty_from_band(band: float) -> str:
    if band >= 7.0:
        return "hard"
    if band >= 5.5:
        return "medium"
    return "easy"


def _score_trend(events: List[Dict[str, Any]]) -> str:
    if len(events) < 6:
        return "stable"
    recent = mean(_to_float(event.get("score")) for event in events[:3])
    previous = mean(_to_float(event.get("score")) for event in events[3:6])
    if recent - previous >= 0.5:
        return "up"
    if previous - recent >= 0.5:
        return "down"
    return "stable"


def _score_reason(avg_score: float, trend: str, count: int) -> str:
    if avg_score >= 8.0:
        base = f"最近 {count} 次翻译练习平均 {avg_score:.1f} 分，可以挑战高阶难度。"
    elif avg_score >= 6.0:
        base = f"最近 {count} 次翻译练习平均 {avg_score:.1f} 分，建议保持进阶难度巩固。"
    else:
        base = f"最近 {count} 次翻译练习平均 {avg_score:.1f} 分，建议回到基础难度打稳准确性。"
    if trend == "up":
        return f"{base} 最近表现有上升趋势。"
    if trend == "down":
        return f"{base} 最近表现略有回落，先稳住正确率。"
    return base


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

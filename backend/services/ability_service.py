from __future__ import annotations

import logging
import time
from statistics import mean
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.db import (
    begin_immediate,
    ensure_skill_tag,
    get_conn,
    get_daily_task_by_date,
    get_latest_user_plan,
    get_user_events,
    get_user_profile,
    link_learning_event_skill,
    save_learning_event,
    update_user_skill_state,
    update_task_progress,
)


logger = logging.getLogger(__name__)


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
    # 本函数只负责「埋点 / 成长引擎」写入，调用方的主业务结果此时通常已落库。
    # 因此这里的任何异常都不得向上抛，否则会把已成功的练习变成 500，并诱发用户重复提交。
    try:
        now = int(time.time())
        score = _to_float(result.get("overall"))
        outcome = _score_to_outcome(score)
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
        skill_tags = _derive_skill_tags(module, properties, result)
        properties["skill_tags"] = [item["skill_key"] for item in skill_tags]
        event_id = str(uuid4())
        save_learning_event(
            event_id,
            user_id,
            {
                "event_type": "practice_result",
                "event_name": f"{module}_practice_checked",
                "properties": properties,
                "timestamp": now,
            },
        )
        _update_skill_states(user_id, event_id, skill_tags, outcome, now)
        _record_hidden_growth_sample(user_id, module, result, properties, outcome)
        _mark_daily_plan_task(user_id, module, now)
    except Exception:
        logger.exception("record_practice_result failed: user=%s module=%s", user_id, module)


def _record_hidden_growth_sample(
    user_id: str,
    module: str,
    result: Dict[str, Any],
    properties: Dict[str, Any],
    outcome: float,
) -> None:
    try:
        from backend.services.learning_event_service import (
            ability_keys_for_practice_result,
            record_hidden_learning_event,
        )

        module_key = str(module or "general").strip().lower() or "general"
        quality = max(0, min(5, int(round(float(outcome or 0.0) * 5))))
        topic = _normalize_key(properties.get("topic") or "general") or "general"
        mode = _normalize_key(properties.get("practice_mode") or "general") or "general"
        difficulty = normalize_difficulty(properties.get("difficulty"))
        unit_key = f"{module_key}:{topic}:{mode}:{difficulty}"
        title = f"{_module_label(module_key)}-{properties.get('practice_mode') or '练习'}"
        record_hidden_learning_event(
            user_id=str(user_id),
            module=module_key,
            event_type="practice_growth_sample",
            unit_type="practice",
            unit_key=unit_key,
            title=title,
            quality=quality,
            score=float(outcome or 0.0),
            ability_keys=ability_keys_for_practice_result(module_key, result, properties),
            tags=list(properties.get("skill_tags") or []),
            metadata={
                "source": properties.get("source", ""),
                "difficulty": difficulty,
                "topic": properties.get("topic", "general"),
                "practice_mode": properties.get("practice_mode", ""),
                "score": properties.get("score"),
            },
        )
    except Exception:
        return


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
        reason = _score_reason(avg_score, trend, len(recent), module_key)
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
            "reason": f"当前{_module_label(module_key)}练习样本不足，暂按能力档案 {profile_band:.1f} 分推荐{DIFFICULTY_LABELS[recommended]}。",
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
    # 成长引擎会写第二条事件（practice_growth_sample），窗口需放大才能凑够真实练习样本
    rows = get_user_events(user_id, limit=max(limit * 6, 120), offset=0)
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


def _score_to_outcome(score: float) -> float:
    if score <= 0:
        return 0.0
    if score <= 1:
        return max(0.0, min(1.0, score))
    return max(0.0, min(1.0, score / 10.0))


def _derive_skill_tags(module: str, properties: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, str]]:
    module_key = str(module or "general").strip().lower() or "general"
    topic = _normalize_key(properties.get("topic") or "general")
    difficulty = normalize_difficulty(properties.get("difficulty"))
    tags: List[Dict[str, str]] = [
        {"skill_key": f"module:{module_key}", "name": _module_label(module_key), "category": "module"},
        {"skill_key": f"{module_key}:difficulty:{difficulty}", "name": f"{_module_label(module_key)}-{difficulty_label(difficulty)}", "category": "difficulty"},
    ]
    if topic and topic != "general":
        tags.append({"skill_key": f"topic:{topic}", "name": f"话题-{topic}", "category": "topic"})

    practice_mode = _normalize_key(properties.get("practice_mode") or "")
    if practice_mode:
        tags.append({"skill_key": f"{module_key}:mode:{practice_mode}", "name": f"{_module_label(module_key)}模式-{practice_mode}", "category": "mode"})

    for sub_skill in ("accuracy", "fluency", "grammar", "vocabulary"):
        if _to_float(result.get(sub_skill)) > 0:
            tags.append({
                "skill_key": f"{module_key}:{sub_skill}",
                "name": f"{_module_label(module_key)}-{sub_skill}",
                "category": "skill",
            })
    word = _normalize_key(result.get("word") or "")
    if module_key == "vocabulary" and word:
        tags.append({"skill_key": f"word:{word}", "name": f"词汇-{word}", "category": "word"})
    return _dedupe_skill_tags(tags)


def _update_skill_states(
    user_id: str,
    event_id: str,
    skill_tags: List[Dict[str, str]],
    outcome: float,
    practiced_at: int,
) -> None:
    """批量写入技能状态：单连接单事务，避免每个 tag 开 3 个连接。"""
    conn = get_conn()
    try:
        begin_immediate(conn)
        for item in skill_tags:
            skill_key = item.get("skill_key", "")
            if not skill_key:
                continue
            ensure_skill_tag(
                skill_key,
                item.get("name") or skill_key,
                item.get("category") or "general",
                conn=conn,
            )
            link_learning_event_skill(event_id, skill_key, weight=1.0, outcome=outcome, conn=conn)
            update_user_skill_state(
                user_id,
                skill_key,
                item.get("category") or "general",
                outcome,
                practiced_at,
                conn=conn,
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _normalize_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    normalized = []
    for ch in raw:
        if ch.isalnum():
            normalized.append(ch)
        elif ch in {"-", "_"}:
            normalized.append("_")
    return "".join(normalized).strip("_")


def _dedupe_skill_tags(tags: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    rows: List[Dict[str, str]] = []
    for item in tags:
        key = str(item.get("skill_key") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({**item, "skill_key": key})
    return rows


def _module_label(module: str) -> str:
    return {
        "translation": "翻译",
        "vocabulary": "词汇",
        "reading": "阅读",
        "listening": "听力",
        "writing": "写作",
        "speaking": "口语",
    }.get(module, module)


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


def _score_reason(avg_score: float, trend: str, count: int, module: str = "translation") -> str:
    label = _module_label(module)
    if avg_score >= 8.0:
        base = f"最近 {count} 次{label}练习平均 {avg_score:.1f} 分，可以挑战高阶难度。"
    elif avg_score >= 6.0:
        base = f"最近 {count} 次{label}练习平均 {avg_score:.1f} 分，建议保持进阶难度巩固。"
    else:
        base = f"最近 {count} 次{label}练习平均 {avg_score:.1f} 分，建议回到基础难度打稳准确性。"
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

from __future__ import annotations

import json
import time
from typing import Any, Dict, List
from uuid import uuid4

from backend.db import (
    create_daily_task,
    create_learning_plan,
    get_conn,
    get_daily_task_by_date,
    get_latest_user_plan,
    get_plan_execution_health,
    get_user_profile,
    get_vocabulary_stats,
    list_user_diagnostic_reports,
    update_plan_status,
)


MODULE_META = {
    "listening": {"label": "听力练习", "target": 3},
    "reading": {"label": "阅读练习", "target": 3},
    "writing": {"label": "写作练习", "target": 2},
    "speaking": {"label": "口语练习", "target": 2},
}


def get_dashboard_overview(user_id: str, username: str = "") -> Dict[str, Any]:
    now = int(time.time())
    today_start = _day_start(now)
    week_start = today_start - 6 * 86400

    profile = get_user_profile(user_id) or {}
    latest_plan = ensure_default_learning_plan(user_id, profile=profile, now_ts=now)
    plan_health = get_plan_execution_health(str(latest_plan["id"]), days=14, now_ts=now) if latest_plan else None
    checkin_calendar = get_checkin_calendar(user_id, now_ts=now, ensure_plan=False)
    events = _get_learning_events(user_id, week_start, now)
    activities = _get_user_activities(user_id, week_start, now)
    vocabulary = _build_vocabulary_summary(user_id, week_start)
    latest_report = _latest_diagnostic_report(user_id)

    modules = _build_module_cards(events, activities, today_start)
    trend = _build_trend(user_id, events, activities, week_start)
    total_completion = _total_completion(plan_health, events, activities)
    current_band = _current_band(profile, latest_report)
    target_band = _to_float(profile.get("target_band")) or 6.5

    return {
        "summary": {
            "username": username,
            "learning_days": _learning_days(user_id),
            "streak_days": int(checkin_calendar.get("streak_days") or 0),
            "total_completion": total_completion,
            "current_band": current_band,
            "target_band": target_band,
            "has_plan": bool(latest_plan),
        },
        "vocabulary": vocabulary,
        "modules": modules,
        "trend": trend,
        "checkin_calendar": checkin_calendar,
        "recommendations": _build_recommendations(user_id, modules, vocabulary, latest_report),
        "today_tasks": _build_today_tasks(latest_plan, today_start) if latest_plan else _fallback_today_tasks(modules, vocabulary),
        "data_sources": {
            "profile": bool(profile),
            "plan": bool(latest_plan),
            "events": len(events),
            "activities": len(activities),
            "diagnostic_report": bool(latest_report),
        },
    }


def get_checkin_calendar(
    user_id: str,
    month: str | None = None,
    now_ts: int | None = None,
    ensure_plan: bool = True,
) -> Dict[str, Any]:
    now = int(now_ts or time.time())
    if ensure_plan:
        ensure_default_learning_plan(user_id, now_ts=now)
    month_start = _month_start(month, now)
    next_month = _add_month(month_start)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    rows = _get_plan_day_rows(user_id, month_start, next_month)
    row_by_date: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        date_text = time.strftime("%Y-%m-%d", time.localtime(int(row.get("date") or 0)))
        merged = row_by_date.setdefault(date_text, {"date": int(row.get("date") or 0), "tasks": []})
        merged["tasks"].extend(_loads(row.get("tasks"), []))

    days: List[Dict[str, Any]] = []
    cursor = month_start
    while cursor < next_month:
        date_text = time.strftime("%Y-%m-%d", time.localtime(cursor))
        row = row_by_date.get(date_text)
        done, total, tasks = _daily_task_counts(row)
        days.append(
            {
                "date": date_text,
                "day": int(time.strftime("%d", time.localtime(cursor))),
                "status": _day_status(done, total, date_text, today),
                "done": done,
                "total": total,
                "is_today": date_text == today,
                "tasks": tasks,
            }
        )
        cursor += 86400

    planned_days = sum(1 for day in days if int(day["total"]) > 0)
    completed_days = sum(1 for day in days if day["status"] == "completed")
    return {
        "month": time.strftime("%Y-%m", time.localtime(month_start)),
        "streak_days": _plan_streak_days(user_id, now),
        "completed_days": completed_days,
        "planned_days": planned_days,
        "today_status": next((day["status"] for day in days if day["is_today"]), "empty"),
        "days": days,
    }


def ensure_default_learning_plan(user_id: str, profile: Dict[str, Any] | None = None, now_ts: int | None = None) -> Dict[str, Any]:
    now = int(now_ts or time.time())
    today_start = _day_start(now)
    profile = profile or get_user_profile(user_id) or {}
    plan = get_latest_user_plan(user_id)
    if plan and str(plan.get("status") or "").lower() == "active" and int(plan.get("end_date") or 0) >= today_start:
        _ensure_plan_tasks(str(plan["id"]), today_start, profile)
        refreshed = get_latest_user_plan(user_id)
        return refreshed or plan

    if plan and str(plan.get("status") or "").lower() == "active":
        update_plan_status(str(plan["id"]), "completed")

    plan_id = f"default_7d_{uuid4().hex}"
    target_band = _to_float(profile.get("target_band")) or 6.5
    focus_modules = _default_focus_modules(profile)
    create_learning_plan(
        plan_id,
        user_id,
        {
            "target_band": target_band,
            "start_date": today_start,
            "end_date": today_start + 7 * 86400 - 1,
            "daily_minutes": 30,
            "focus_modules": focus_modules,
            "status": "active",
        },
    )
    _ensure_plan_tasks(plan_id, today_start, profile)
    return get_latest_user_plan(user_id) or {
        "id": plan_id,
        "user_id": user_id,
        "target_band": target_band,
        "start_date": today_start,
        "end_date": today_start + 7 * 86400 - 1,
        "daily_minutes": 30,
        "focus_modules": focus_modules,
        "status": "active",
        "created_at": now,
    }


def _ensure_plan_tasks(plan_id: str, today_start: int, profile: Dict[str, Any]) -> None:
    for idx in range(7):
        date_ts = today_start + idx * 86400
        if get_daily_task_by_date(plan_id, date_ts):
            continue
        create_daily_task(
            str(uuid4()),
            plan_id,
            date_ts,
            _default_tasks_for_day(idx, profile),
        )


def _default_focus_modules(profile: Dict[str, Any]) -> List[str]:
    bands = {
        "listening": _to_float(profile.get("current_band_listening")),
        "reading": _to_float(profile.get("current_band_reading")),
        "writing": _to_float(profile.get("current_band_writing")),
        "speaking": _to_float(profile.get("current_band_speaking")),
    }
    known = {k: v for k, v in bands.items() if v > 0}
    if known:
        return [k for k, _ in sorted(known.items(), key=lambda item: item[1])[:2]]
    return ["vocabulary", "translation", "reading"]


def _default_tasks_for_day(day_index: int, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    level = _level_from_profile(profile)
    weekly = [
        [
            ("translation", "完成一次翻译练习", "用智能推荐难度完成 1 道翻译题，提交批改。"),
            ("vocabulary", "学习 10 个新词汇", "优先选择教育/科技等雅思高频主题词。"),
            ("reading", "完成一次阅读短练习", "训练定位关键词和句子主干理解。"),
        ],
        [
            ("listening", "完成一组听力练习", "完成 1 组听力题并记录错因。"),
            ("vocabulary", "复习到期词汇", "完成今日到期词汇复习。"),
            ("translation", "完成一次盲译练习", "先独立翻译，再查看提示或批改。"),
        ],
        [
            ("reading", "完成一组阅读练习", "重点训练判断题或匹配题。"),
            ("writing", "完成一次短写作", "写一段 120-150 词短文或 Task 1 片段。"),
            ("mistakes", "复盘一个错题类型", "从错题本挑选一个高频错因复盘。"),
        ],
        [
            ("speaking", "完成一次口语练习", "完成 1 个 Part 1/2 口语回答。"),
            ("translation", "完成词汇句型造句", "围绕目标词汇和句型完成造句。"),
            ("vocabulary", "复习本周新增词汇", "回看本周新增词并补充例句。"),
        ],
        [
            ("listening", "听力短练 1 组", "完成一组听力素材。"),
            ("reading", "阅读短练 1 组", "完成一组阅读题。"),
            ("translation", "翻译练习 1 题", "完成并提交批改。"),
        ],
        [
            ("writing", "完成一次写作练习", "完成 Task 1/Task 2 片段并保存。"),
            ("speaking", "完成一次口语练习", "录音或输入回答并查看反馈。"),
            ("mistakes", "批改结果复盘", "回看最近一次批改建议，整理 2 条改进点。"),
        ],
        [
            ("mistakes", "复习本周错题", "处理本周新增错题或高优先级错题。"),
            ("vocabulary", "复习到期词汇", "完成到期词汇复习。"),
            ("report", "查看学习报告", "查看本周数据并确认下周重点。"),
        ],
    ]
    return [
        {
            "id": f"day{day_index + 1}_{idx}_{module}",
            "module": module,
            "title": title,
            "description": f"{desc} 当前建议难度：{level}。",
            "duration_minutes": 10,
            "time_required": 10,
            "completed": False,
            "progress": 0,
            "time_spent": 0,
        }
        for idx, (module, title, desc) in enumerate(weekly[day_index % 7], start=1)
    ]


def _level_from_profile(profile: Dict[str, Any]) -> str:
    band = _to_float(profile.get("current_band_overall"))
    if band >= 6.5:
        return "高阶"
    if band >= 5.5:
        return "进阶"
    return "基础"


def _get_learning_events(user_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT event_id, event_type, event_name, properties, timestamp
            FROM learning_events
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (user_id, start_ts, end_ts),
        ).fetchall()
        events: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["properties"] = _loads(item.get("properties"), {})
            events.append(item)
        return events
    finally:
        conn.close()


def _get_user_activities(user_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, activity_type, module, duration, score, metadata, created_at
            FROM user_activities
            WHERE user_id = ? AND created_at >= ? AND created_at <= ?
            ORDER BY created_at ASC
            """,
            (user_id, start_ts, end_ts),
        ).fetchall()
        activities: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = _loads(item.get("metadata"), {})
            activities.append(item)
        return activities
    finally:
        conn.close()


def _build_vocabulary_summary(user_id: str, week_start: int) -> Dict[str, Any]:
    stats = get_vocabulary_stats(user_id)
    conn = get_conn()
    try:
        weekly_new = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vocabulary WHERE user_id = ? AND created_at >= ?",
            (user_id, week_start),
        ).fetchone()
        return {
            "total": int(stats.get("total") or 0),
            "weekly_new": int(weekly_new["cnt"] if weekly_new else 0),
            "due_review": int(stats.get("due_count") or 0),
            "avg_mastery": float(stats.get("avg_mastery") or 0.0),
        }
    finally:
        conn.close()


def _build_module_cards(events: List[Dict[str, Any]], activities: List[Dict[str, Any]], today_start: int) -> List[Dict[str, Any]]:
    counts = {key: 0 for key in MODULE_META}
    for event in events:
        if int(event.get("timestamp") or 0) < today_start:
            continue
        module = _normalize_module((event.get("properties") or {}).get("module") or event.get("event_name"))
        if module in counts:
            counts[module] += 1
    for activity in activities:
        if int(activity.get("created_at") or 0) < today_start:
            continue
        module = _normalize_module(activity.get("module") or activity.get("activity_type"))
        if module in counts:
            counts[module] += 1
    return [
        {
            "module": key,
            "name": meta["label"],
            "todayCount": int(counts.get(key) or 0),
            "targetCount": int(meta["target"]),
        }
        for key, meta in MODULE_META.items()
    ]


def _build_trend(user_id: str, events: List[Dict[str, Any]], activities: List[Dict[str, Any]], week_start: int) -> List[Dict[str, Any]]:
    by_day: Dict[str, Dict[str, Any]] = {}
    today_text = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    for idx in range(7):
        ts = week_start + idx * 86400
        day_key = time.strftime("%Y-%m-%d", time.localtime(ts))
        by_day[day_key] = {
            "date": day_key,
            "day": time.strftime("%a", time.localtime(ts)),
            "minutes": 0,
            "sessions": 0,
            "done": 0,
            "total": 0,
            "completion_rate": 0,
            "status": "empty",
        }
    plan_rows = _get_plan_day_rows(user_id, week_start, week_start + 7 * 86400)
    for row in plan_rows:
        day_key = time.strftime("%Y-%m-%d", time.localtime(int(row.get("date") or 0)))
        if day_key not in by_day:
            continue
        done, total, _ = _daily_task_counts(row)
        by_day[day_key]["done"] += done
        by_day[day_key]["total"] += total
    for event in events:
        ts = int(event.get("timestamp") or 0)
        day_key = time.strftime("%Y-%m-%d", time.localtime(ts))
        if day_key in by_day:
            props = event.get("properties") or {}
            by_day[day_key]["minutes"] += max(1, int(props.get("duration", 0) or 0) // 60) if props.get("duration") else 0
            by_day[day_key]["sessions"] += 1
    for activity in activities:
        ts = int(activity.get("created_at") or 0)
        day_key = time.strftime("%Y-%m-%d", time.localtime(ts))
        if day_key in by_day:
            by_day[day_key]["minutes"] += max(1, int(activity.get("duration") or 0) // 60) if activity.get("duration") else 0
            by_day[day_key]["sessions"] += 1
    for item in by_day.values():
        if item["minutes"] == 0 and item["sessions"] > 0:
            item["minutes"] = item["sessions"] * 10
        if int(item["total"] or 0) > 0:
            item["completion_rate"] = int(round((int(item["done"] or 0) / int(item["total"] or 1)) * 100))
            item["status"] = _day_status(int(item["done"] or 0), int(item["total"] or 0), str(item["date"]), today_text)
    return list(by_day.values())


def _total_completion(plan_health: Dict[str, Any] | None, events: List[Dict[str, Any]], activities: List[Dict[str, Any]]) -> int:
    if plan_health:
        return int(round(float(plan_health.get("task_completion_rate") or 0.0)))
    weekly_sessions = len(events) + len(activities)
    return max(0, min(100, int(round((weekly_sessions / 14) * 100))))


def _build_today_tasks(plan: Dict[str, Any] | None, today_start: int) -> List[Dict[str, Any]]:
    if not plan:
        return []
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT tasks
            FROM daily_tasks
            WHERE plan_id = ? AND date >= ? AND date < ?
            ORDER BY date ASC
            LIMIT 1
            """,
            (str(plan["id"]), today_start, today_start + 86400),
        ).fetchone()
        tasks = _loads(row["tasks"], []) if row else []
        return [
            {
                "id": str(item.get("id") or idx),
                "title": str(item.get("title") or item.get("skill") or item.get("description") or "学习任务"),
                "completed": bool(item.get("completed")),
                "progress": int(item.get("progress") or (100 if item.get("completed") else 0)),
            }
            for idx, item in enumerate(tasks[:5], start=1)
        ]
    finally:
        conn.close()


def _fallback_today_tasks(modules: List[Dict[str, Any]], vocabulary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    weakest = sorted(modules, key=lambda x: int(x.get("todayCount") or 0))[:2]
    for idx, module in enumerate(weakest, start=1):
        rows.append({
            "id": f"module-{module['module']}",
            "title": f"完成一次{module['name']}",
            "completed": int(module.get("todayCount") or 0) > 0,
            "progress": 100 if int(module.get("todayCount") or 0) > 0 else 0,
        })
    if int(vocabulary.get("due_review") or 0) > 0:
        rows.append({
            "id": "vocab-review",
            "title": f"复习 {int(vocabulary['due_review'])} 个到期词汇",
            "completed": False,
            "progress": 0,
        })
    return rows[:4]


def _build_recommendations(
    user_id: str,
    modules: List[Dict[str, Any]],
    vocabulary: Dict[str, Any],
    latest_report: Dict[str, Any] | None,
) -> List[Dict[str, str]]:
    recs: List[Dict[str, str]] = []
    low_modules = [m for m in modules if int(m.get("todayCount") or 0) < int(m.get("targetCount") or 0)]
    if low_modules:
        m = low_modules[0]
        recs.append({
            "title": f"补齐今日{m['name']}",
            "description": f"今日已完成 {m['todayCount']}/{m['targetCount']}，建议先完成一组短练习。",
        })
    if int(vocabulary.get("due_review") or 0) > 0:
        recs.append({
            "title": "优先复习到期词汇",
            "description": f"当前有 {int(vocabulary['due_review'])} 个词汇到期，适合先做间隔复习。",
        })
    weaknesses = (latest_report or {}).get("weaknesses") or []
    if weaknesses:
        recs.append({
            "title": "根据诊断报告补强薄弱项",
            "description": str(weaknesses[0])[:80],
        })
    if not recs:
        recs.append({
            "title": "完成一次翻译或阅读练习",
            "description": "系统会根据新的练习结果更新能力画像和推荐难度。",
        })
    return [{"id": str(idx), **item} for idx, item in enumerate(recs[:3], start=1)]


def _latest_diagnostic_report(user_id: str) -> Dict[str, Any] | None:
    rows = list_user_diagnostic_reports(user_id, limit=1)
    return rows[0] if rows else None


def _current_band(profile: Dict[str, Any], latest_report: Dict[str, Any] | None) -> float | None:
    if latest_report and _to_float(latest_report.get("overall_band")) > 0:
        return _to_float(latest_report.get("overall_band"))
    band = _to_float(profile.get("current_band_overall"))
    return band if band > 0 else None


def _learning_days(user_id: str) -> int:
    conn = get_conn()
    try:
        values: List[int] = []
        row = conn.execute("SELECT created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if row and int(row["created_at"] or 0) > 0:
            values.append(int(row["created_at"]))
        first_event = conn.execute("SELECT MIN(timestamp) AS ts FROM learning_events WHERE user_id = ?", (user_id,)).fetchone()
        if first_event and int(first_event["ts"] or 0) > 0:
            values.append(int(first_event["ts"]))
        first_activity = conn.execute("SELECT MIN(created_at) AS ts FROM user_activities WHERE user_id = ?", (user_id,)).fetchone()
        if first_activity and int(first_activity["ts"] or 0) > 0:
            values.append(int(first_activity["ts"]))
        if not values:
            return 0
        return max(1, int((time.time() - min(values)) // 86400) + 1)
    finally:
        conn.close()


def _active_day_set(events: List[Dict[str, Any]], activities: List[Dict[str, Any]]) -> set[str]:
    days = {time.strftime("%Y-%m-%d", time.localtime(int(e.get("timestamp") or 0))) for e in events}
    days.update(time.strftime("%Y-%m-%d", time.localtime(int(a.get("created_at") or 0))) for a in activities)
    return {d for d in days if d and d != "1970-01-01"}


def _streak_days(active_days: set[str], now: int) -> int:
    streak = 0
    for idx in range(30):
        day = time.strftime("%Y-%m-%d", time.localtime(now - idx * 86400))
        if day not in active_days:
            break
        streak += 1
    return streak


def _month_start(month: str | None, now: int) -> int:
    if month:
        parts = str(month).strip().split("-")
        if len(parts) == 2:
            try:
                year = int(parts[0])
                month_num = int(parts[1])
                if 1 <= month_num <= 12:
                    return int(time.mktime((year, month_num, 1, 0, 0, 0, 0, 0, -1)))
            except (TypeError, ValueError):
                pass
    local = time.localtime(now)
    return int(time.mktime((local.tm_year, local.tm_mon, 1, 0, 0, 0, 0, 0, local.tm_isdst)))


def _add_month(month_start: int) -> int:
    local = time.localtime(month_start)
    year = local.tm_year
    month_num = local.tm_mon + 1
    if month_num > 12:
        year += 1
        month_num = 1
    return int(time.mktime((year, month_num, 1, 0, 0, 0, 0, 0, local.tm_isdst)))


def _get_plan_day_rows(user_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT dt.date, dt.tasks
            FROM daily_tasks dt
            JOIN learning_plans lp ON lp.id = dt.plan_id
            WHERE lp.user_id = ? AND dt.date >= ? AND dt.date < ?
            ORDER BY dt.date ASC, dt.created_at ASC
            """,
            (user_id, start_ts, end_ts),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _daily_task_counts(row: Dict[str, Any] | None) -> tuple[int, int, List[Dict[str, Any]]]:
    if not row:
        return 0, 0, []
    raw_tasks = row.get("tasks")
    tasks = raw_tasks if isinstance(raw_tasks, list) else _loads(raw_tasks, [])
    visible_tasks: List[Dict[str, Any]] = []
    done = 0
    for idx, item in enumerate(tasks, start=1):
        if not isinstance(item, dict):
            continue
        progress = _to_int(item.get("progress"), 100 if item.get("completed") else 0)
        completed = bool(item.get("completed")) or progress >= 100
        if completed:
            done += 1
        visible_tasks.append(
            {
                "id": str(item.get("id") or idx),
                "module": str(item.get("module") or ""),
                "title": str(item.get("title") or item.get("description") or "学习任务"),
                "completed": completed,
                "progress": max(0, min(100, progress)),
            }
        )
    return done, len(visible_tasks), visible_tasks


def _day_status(done: int, total: int, date_text: str | None = None, today_text: str | None = None) -> str:
    if total <= 0:
        return "empty"
    if done >= total:
        return "completed"
    if done > 0:
        return "partial"
    if date_text and today_text and date_text >= today_text:
        return "planned"
    return "missed"


def _plan_streak_days(user_id: str, now: int) -> int:
    today_start = _day_start(now)
    start_ts = today_start - 90 * 86400
    rows = _get_plan_day_rows(user_id, start_ts, today_start + 86400)
    row_by_date: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        date_text = time.strftime("%Y-%m-%d", time.localtime(int(row.get("date") or 0)))
        merged = row_by_date.setdefault(date_text, {"date": int(row.get("date") or 0), "tasks": []})
        merged["tasks"].extend(_loads(row.get("tasks"), []))

    today_text = time.strftime("%Y-%m-%d", time.localtime(today_start))
    today_done, today_total, _ = _daily_task_counts(row_by_date.get(today_text))
    cursor = today_start if _day_status(today_done, today_total, today_text, today_text) == "completed" else today_start - 86400

    streak = 0
    while cursor >= start_ts:
        day_text = time.strftime("%Y-%m-%d", time.localtime(cursor))
        done, total, _ = _daily_task_counts(row_by_date.get(day_text))
        if _day_status(done, total, day_text, today_text) != "completed":
            break
        streak += 1
        cursor -= 86400
    return streak


def _day_start(ts: int) -> int:
    local = time.localtime(ts)
    return int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, local.tm_wday, local.tm_yday, local.tm_isdst)))


def _normalize_module(value: Any) -> str:
    text = str(value or "").lower()
    for key in MODULE_META:
        if key in text:
            return key
    if "听力" in text:
        return "listening"
    if "阅读" in text:
        return "reading"
    if "写作" in text:
        return "writing"
    if "口语" in text:
        return "speaking"
    return "unknown"


def _loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

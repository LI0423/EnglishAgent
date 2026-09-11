from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from backend import db
from backend.redis_client import get_timed_state
from backend.services.spaced_repetition import calculate_sm2_review, outcome_from_quality
from backend.utils.time_utils import day_start_ts


ABILITY_LABELS = {
    "vocabulary": "词汇积累",
    "mistake_review": "错题复盘",
    "listening_detail": "听力细节",
    "reading_accuracy": "阅读准确性",
    "writing_coherence": "写作连贯",
    "speaking_coherence": "口语连贯",
    "speaking_fluency": "口语流利度",
    "speaking_grammar": "口语语法",
    "speaking_vocabulary": "口语词汇",
    "writing_task_response": "写作任务回应",
    "writing_grammar": "写作语法",
    "writing_lexical_resource": "写作词汇",
    "translation_accuracy": "翻译准确性",
    "grammar": "语法能力",
    "pronunciation": "发音能力",
    "fluency": "流利度",
    "coherence": "连贯性",
    "lexical": "词汇丰富度",
}


def ability_keys_for_unit(module: str, unit_type: str, tags: Optional[Iterable[Any]] = None) -> List[str]:
    module_key = str(module or "").strip().lower()
    unit = str(unit_type or "").strip().lower()
    raw_tags = {str(x or "").strip().lower() for x in (tags or []) if str(x or "").strip()}
    keys: list[str] = []
    if unit == "vocabulary" or module_key == "vocabulary":
        keys.append("vocabulary")
    if unit == "mistake":
        keys.append("mistake_review")
    if module_key == "listening":
        keys.append("listening_detail")
    if module_key == "reading":
        keys.append("reading_accuracy")
    if module_key == "writing":
        keys.append("writing_coherence")
    if module_key == "speaking":
        keys.append("speaking_coherence")
    if module_key == "translation":
        keys.append("translation_accuracy")
    for tag in raw_tags:
        if tag in {"grammar", "pronunciation", "fluency", "coherence", "lexical"}:
            keys.append(tag)
    return list(dict.fromkeys(keys or [module_key or "general"]))


def ability_keys_for_practice_result(
    module: str,
    result: Dict[str, Any],
    properties: Optional[Dict[str, Any]] = None,
) -> List[str]:
    module_key = str(module or "general").strip().lower() or "general"
    props = properties or {}
    keys = ability_keys_for_unit(module_key, "practice", [])

    if module_key == "writing":
        if _has_score(result, "accuracy"):
            keys.append("writing_task_response")
        if _has_score(result, "fluency"):
            keys.append("writing_coherence")
        if _has_score(result, "grammar"):
            keys.append("writing_grammar")
        if _has_score(result, "vocabulary"):
            keys.append("writing_lexical_resource")
    elif module_key == "speaking":
        if _has_score(result, "fluency"):
            keys.append("speaking_fluency")
        if _has_score(result, "grammar"):
            keys.append("speaking_grammar")
        if _has_score(result, "vocabulary"):
            keys.append("speaking_vocabulary")
    elif module_key == "translation":
        keys.append("translation_accuracy")
        if _has_score(result, "grammar"):
            keys.append("grammar")
        if _has_score(result, "vocabulary"):
            keys.append("lexical")
    elif module_key == "listening":
        keys.append("listening_detail")
    elif module_key == "reading":
        keys.append("reading_accuracy")

    mode = str(props.get("practice_mode") or "").lower()
    if "dictation" in mode or "keyword" in mode:
        keys.append("listening_detail")
    if "inference" in mode:
        keys.append(f"{module_key}_inference")
    return list(dict.fromkeys(keys))


def record_hidden_learning_event(
    *,
    user_id: str,
    module: str,
    event_type: str,
    unit_type: str,
    unit_key: str,
    title: str,
    quality: int,
    score: Optional[float] = None,
    ability_keys: Optional[List[str]] = None,
    tags: Optional[List[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    sm2_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = int(time.time())
    safe_module = str(module or "general").strip().lower() or "general"
    safe_unit_type = str(unit_type or "general").strip().lower() or "general"
    safe_unit_key = str(unit_key or "").strip().lower()
    if not user_id or not safe_unit_key:
        return {}

    abilities = ability_keys or ability_keys_for_unit(safe_module, safe_unit_type, tags)

    # 整个埋点在「单连接 + 单事务」内完成：既避免半写，也把一次埋点从 ~9 个连接降为 1 个。
    conn = db.get_conn()
    try:
        db.begin_immediate(conn)
        if sm2_result is None:
            sm2_result = _calculate_unit_sm2(
                user_id=str(user_id),
                unit_type=safe_unit_type,
                unit_key=safe_unit_key,
                quality=int(quality),
                reviewed_at=now,
                conn=conn,
            )
        unit_id = _upsert_learning_unit(
            unit_type=safe_unit_type,
            unit_key=safe_unit_key,
            title=title,
            source_modules=[safe_module],
            ability_keys=abilities,
            tags=tags or [],
            now=now,
            conn=conn,
        )
        event_id = str(uuid4())
        properties = {
            "module": safe_module,
            "unit_type": safe_unit_type,
            "unit_key": safe_unit_key,
            "unit_id": unit_id,
            "title": title,
            "quality": int(quality),
            "score": score,
            "ability_keys": abilities,
            "tags": tags or [],
            "metadata": metadata or {},
            "sm2": sm2_result or {},
        }
        db.save_learning_event(
            event_id,
            str(user_id),
            {
                "event_type": event_type,
                "event_name": f"{safe_module}_{safe_unit_type}_reviewed",
                "properties": properties,
                "timestamp": now,
            },
            conn=conn,
        )
        outcome = outcome_from_quality(int(quality))
        for ability in abilities:
            _record_ability_sample(str(user_id), ability, outcome, now, conn=conn)
            db.ensure_skill_tag(
                f"ability:{ability}",
                ABILITY_LABELS.get(ability, ability),
                "ability",
                metadata={"hidden_growth_engine": True},
                conn=conn,
            )
            db.link_learning_event_skill(event_id, f"ability:{ability}", weight=1.0, outcome=outcome, conn=conn)
            db.update_user_skill_state(
                str(user_id), f"ability:{ability}", "ability", outcome, practiced_at=now, conn=conn
            )
        _upsert_user_unit_memory(
            user_id=str(user_id),
            unit_id=unit_id,
            quality=int(quality),
            sm2_result=sm2_result or {},
            now=now,
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
    return {
        "event_id": event_id,
        "unit_id": unit_id,
        "ability_keys": abilities,
    }


def get_today_learning_plan(user_id: str, limit: int = 6) -> Dict[str, Any]:
    now = int(time.time())
    completed_ids = _completed_today_task_ids(str(user_id), now)
    tasks: List[Dict[str, Any]] = []
    for item in _due_memory_items(user_id, now, limit=limit):
        task_id = f"smart-review-{item.get('unit_id')}"
        tasks.append(
            {
                "id": task_id,
                "type": "review",
                "module": _primary_source(item),
                "title": f"复习 {item.get('title')}",
                "reason": _memory_reason(item, now),
                "priority": 95 - int(float(item.get("memory_strength") or 0.0) * 20),
                "route": _route_for_module(_primary_source(item)),
                "unit_type": item.get("unit_type"),
                "unit_key": item.get("unit_key"),
                "completed": task_id in completed_ids,
            }
        )
    for item in _risky_abilities(user_id, limit=limit):
        task_id = f"smart-growth-{item.get('ability_key')}"
        tasks.append(
            {
                "id": task_id,
                "type": "growth",
                "module": module_for_ability(str(item.get("ability_key") or "")),
                "title": f"补强 {ABILITY_LABELS.get(str(item.get('ability_key') or ''), item.get('ability_key'))}",
                "reason": _ability_reason(item),
                "priority": 82 - int(float(item.get("current_score") or 0.0) * 20),
                "route": _route_for_module(module_for_ability(str(item.get("ability_key") or ""))),
                "ability_key": item.get("ability_key"),
                "completed": task_id in completed_ids,
            }
        )
    if not tasks:
        tasks = [
            {
                "id": "smart-starter-vocabulary",
                "type": "starter",
                "module": "vocabulary",
                "title": "完成一组核心词主动回忆",
                "reason": "先建立今日学习样本，系统会据此调整后续安排。",
                "priority": 60,
                "route": "/vocabulary",
                "completed": "smart-starter-vocabulary" in completed_ids,
            },
            {
                "id": "smart-starter-translation",
                "type": "starter",
                "module": "translation",
                "title": "完成一次短句翻译练习",
                "reason": "用短练习补充能力画像。",
                "priority": 55,
                "route": "/translation-search",
                "completed": "smart-starter-translation" in completed_ids,
            },
        ]
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(tasks, key=lambda x: int(x.get("priority") or 0), reverse=True):
        key = (str(item.get("type") or ""), str(item.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max(1, min(int(limit or 6), 10)):
            break
    return {
        "user_id": str(user_id),
        "generated_at": now,
        "title": "今日智能学习安排",
        "summary": _plan_summary(deduped),
        "tasks": deduped,
    }


def get_growth_insights(user_id: str, limit: int = 8) -> Dict[str, Any]:
    return {
        "user_id": str(user_id),
        "abilities": _risky_abilities(user_id, limit=limit, include_normal=True),
        "due_memory_count": _count_due_memory_items(user_id, int(time.time())),
    }


def _count_due_memory_items(user_id: str, now: int) -> int:
    """到期记忆数量用 COUNT(*) 统计，避免为了计数把最多 200 行读进内存。"""
    conn = db.get_conn()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM user_unit_memory
            WHERE user_id = ? AND next_review_at > 0 AND next_review_at <= ?
            """,
            (str(user_id), int(now)),
        ).fetchone()
        return int(row["c"] or 0)
    finally:
        conn.close()


def _calculate_unit_sm2(
    user_id: str,
    unit_type: str,
    unit_key: str,
    quality: int,
    reviewed_at: int,
    conn: Any = None,
) -> Dict[str, Any]:
    own = conn is None
    conn = db.get_conn() if own else conn
    try:
        row = conn.execute(
            """
            SELECT m.sm2_repetitions, m.sm2_interval_days, m.sm2_ease_factor, m.sm2_lapses
            FROM user_unit_memory m
            JOIN learning_units u ON u.id = m.unit_id
            WHERE m.user_id = ? AND u.unit_type = ? AND u.unit_key = ?
            LIMIT 1
            """,
            (user_id, unit_type, unit_key),
        ).fetchone()
        return calculate_sm2_review(
            quality=quality,
            repetitions=(row["sm2_repetitions"] if row else 0),
            interval_days=(row["sm2_interval_days"] if row else 0.0),
            ease_factor=(row["sm2_ease_factor"] if row else 2.5),
            lapses=(row["sm2_lapses"] if row else 0),
            reviewed_at=reviewed_at,
        )
    finally:
        if own:
            conn.close()


def _merge_json_list(raw: Any, new_items: List[Any]) -> List[Any]:
    try:
        existing = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        existing = []
    if not isinstance(existing, list):
        existing = []
    merged: List[Any] = []
    seen: set[str] = set()
    for item in list(existing) + list(new_items or []):
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _upsert_learning_unit(
    *,
    unit_type: str,
    unit_key: str,
    title: str,
    source_modules: List[str],
    ability_keys: List[str],
    tags: List[Any],
    now: int,
    conn: Any = None,
) -> str:
    own = conn is None
    conn = db.get_conn() if own else conn
    try:
        db.begin_immediate(conn)
        unit_id = str(uuid4())
        existing = conn.execute(
            "SELECT source_modules, ability_keys, tags FROM learning_units WHERE unit_type = ? AND unit_key = ?",
            (unit_type, unit_key),
        ).fetchone()
        if existing:
            # 冲突时按并集合并，避免后写入的单一来源/标签覆盖历史信息。
            source_modules = _merge_json_list(existing["source_modules"], source_modules)
            ability_keys = _merge_json_list(existing["ability_keys"], ability_keys)
            tags = _merge_json_list(existing["tags"], tags)
        conn.execute(
            """
            INSERT INTO learning_units (
              id, unit_type, unit_key, title, description,
              source_modules, ability_keys, tags, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?)
            ON CONFLICT(unit_type, unit_key) DO UPDATE SET
              title = excluded.title,
              source_modules = excluded.source_modules,
              ability_keys = excluded.ability_keys,
              tags = excluded.tags,
              updated_at = excluded.updated_at
            """,
            (
                unit_id,
                unit_type,
                unit_key,
                title or unit_key,
                json.dumps(source_modules, ensure_ascii=False),
                json.dumps(ability_keys, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                now,
                now,
            ),
        )
        if own:
            conn.commit()
        row = conn.execute(
            "SELECT id FROM learning_units WHERE unit_type = ? AND unit_key = ?",
            (unit_type, unit_key),
        ).fetchone()
        return str(row["id"] if row else unit_id)
    finally:
        if own:
            conn.close()


def _upsert_user_unit_memory(
    user_id: str,
    unit_id: str,
    quality: int,
    sm2_result: Dict[str, Any],
    now: int,
    conn: Any = None,
) -> None:
    own = conn is None
    conn = db.get_conn() if own else conn
    try:
        mastery = max(0.0, min(1.0, outcome_from_quality(quality) * 0.75 + float(sm2_result.get("memory_strength") or 0.0) * 0.25))
        conn.execute(
            """
            INSERT INTO user_unit_memory (
              id, user_id, unit_id, mastery_level, memory_strength,
              sm2_repetitions, sm2_interval_days, sm2_ease_factor,
              sm2_lapses, sm2_last_quality, next_review_at, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, unit_id) DO UPDATE SET
              mastery_level = excluded.mastery_level,
              memory_strength = excluded.memory_strength,
              sm2_repetitions = excluded.sm2_repetitions,
              sm2_interval_days = excluded.sm2_interval_days,
              sm2_ease_factor = excluded.sm2_ease_factor,
              sm2_lapses = excluded.sm2_lapses,
              sm2_last_quality = excluded.sm2_last_quality,
              next_review_at = excluded.next_review_at,
              last_seen_at = excluded.last_seen_at,
              updated_at = excluded.updated_at
            """,
            (
                str(uuid4()),
                user_id,
                unit_id,
                round(mastery, 4),
                float(sm2_result.get("memory_strength") or 0.0),
                int(sm2_result.get("repetitions") or 0),
                float(sm2_result.get("interval_days") or 0.0),
                float(sm2_result.get("ease_factor") or 2.5),
                int(sm2_result.get("lapses") or 0),
                int(quality),
                int(sm2_result.get("next_review_at") or now),
                now,
                now,
            ),
        )
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def _record_ability_sample(user_id: str, ability_key: str, outcome: float, now: int, conn: Any = None) -> None:
    own = conn is None
    conn = db.get_conn() if own else conn
    try:
        db.begin_immediate(conn)
        row = conn.execute(
            "SELECT * FROM user_ability_growth WHERE user_id = ? AND ability_key = ?",
            (user_id, ability_key),
        ).fetchone()
        if row:
            current = dict(row)
            old_score = float(current.get("current_score") or 0.0)
            current_score = round(old_score * 0.82 + outcome * 0.18, 4)
            velocity = round(current_score - old_score, 4)
            sample_count = int(current.get("sample_count") or 0) + 1
            stability = round(max(0.0, min(1.0, float(current.get("stability") or 0.0) * 0.85 + (1.0 - abs(velocity)) * 0.15)), 4)
        else:
            current_score = round(outcome, 4)
            velocity = 0.0
            sample_count = 1
            stability = 0.35 if outcome >= 0.6 else 0.15
        confidence = round(min(0.95, 0.18 + sample_count * 0.08), 4)
        risk = _risk_level(current_score, velocity, stability, confidence, sample_count)
        conn.execute(
            """
            INSERT INTO user_ability_growth (
              id, user_id, ability_key, current_score, velocity, stability,
              confidence, risk_level, sample_count, last_active_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ability_key) DO UPDATE SET
              current_score = excluded.current_score,
              velocity = excluded.velocity,
              stability = excluded.stability,
              confidence = excluded.confidence,
              risk_level = excluded.risk_level,
              sample_count = excluded.sample_count,
              last_active_at = excluded.last_active_at,
              updated_at = excluded.updated_at
            """,
            (str(uuid4()), user_id, ability_key, current_score, velocity, stability, confidence, risk, sample_count, now, now),
        )
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def _has_score(result: Dict[str, Any], key: str) -> bool:
    try:
        return float(result.get(key) or 0) > 0
    except (TypeError, ValueError):
        return False


def _due_memory_items(user_id: str, now: int, limit: int = 20) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT m.*, u.unit_type, u.unit_key, u.title, u.source_modules, u.ability_keys
            FROM user_unit_memory m
            JOIN learning_units u ON u.id = m.unit_id
            WHERE m.user_id = ? AND m.next_review_at > 0 AND m.next_review_at <= ?
            ORDER BY m.next_review_at ASC, m.memory_strength ASC
            LIMIT ?
            """,
            (user_id, now, max(1, min(int(limit or 20), 200))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _completed_today_task_ids(user_id: str, now: int) -> set[str]:
    day_start = day_start_ts(now)
    today_key = time.strftime("%Y-%m-%d", time.localtime(now))
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT dt.tasks
            FROM daily_tasks dt
            JOIN learning_plans lp ON lp.id = dt.plan_id
            WHERE lp.user_id = ? AND lp.status = 'active' AND dt.date = ?
            """,
            (user_id, day_start),
        ).fetchall()
        completed: set[str] = set()
        for row in rows:
            try:
                items = json.loads(row["tasks"] or "[]")
            except (TypeError, ValueError):
                items = []
            for item in items:
                if isinstance(item, dict) and bool(item.get("completed")):
                    completed.add(str(item.get("id") or ""))
        if get_timed_state(f"vocabulary:today_learning:completed:{user_id}:{today_key}") == "completed":
            completed.add("smart-starter-vocabulary")
        return completed
    finally:
        conn.close()


def _risky_abilities(user_id: str, limit: int = 8, include_normal: bool = False) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        where = "" if include_normal else "AND risk_level != 'normal'"
        rows = conn.execute(
            f"""
            SELECT *
            FROM user_ability_growth
            WHERE user_id = ? {where}
            ORDER BY
              CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
              current_score ASC,
              updated_at DESC
            LIMIT ?
            """,
            (user_id, max(1, min(int(limit or 8), 100))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _risk_level(
    current_score: float,
    velocity: float,
    stability: float,
    confidence: float,
    sample_count: int = 0,
) -> str:
    # 单样本不足以判定风险（否则一次好/坏练习就会把能力标成 high/medium）
    if sample_count < 2:
        return "normal"
    if confidence >= 0.25 and (current_score < 0.45 or velocity < -0.08):
        return "high"
    if confidence >= 0.25 and (current_score < 0.62 or stability < 0.35 or velocity < -0.03):
        return "medium"
    return "normal"


def _primary_source(item: Dict[str, Any]) -> str:
    try:
        sources = json.loads(item.get("source_modules") or "[]")
    except (TypeError, ValueError):
        sources = []
    return str((sources or ["vocabulary"])[0] or "vocabulary")


def _route_for_module(module: str) -> str:
    return {
        "vocabulary": "/vocabulary",
        "listening": "/listening",
        "reading": "/reading",
        "writing": "/writing",
        "speaking": "/speaking",
        "translation": "/translation-search",
        "mistakes": "/mistakes",
    }.get(str(module or ""), "/")


def module_for_ability(ability_key: str) -> str:
    key = str(ability_key or "").strip().lower()
    if key == "vocabulary":
        return "vocabulary"
    if key == "mistake_review":
        return "mistakes"
    if "_" in key:
        first = key.split("_", 1)[0]
        if first in {"listening", "reading", "writing", "speaking", "translation"}:
            return first
    # 不携带模块前缀的通用能力（grammar/pronunciation/fluency/coherence/lexical）
    # 旧实现一律兜底成 translation，会把发音/流利度任务错误导到翻译页。
    return {
        "pronunciation": "speaking",
        "fluency": "speaking",
        "coherence": "writing",
        "grammar": "translation",
        "lexical": "translation",
    }.get(key, "translation")


def _memory_reason(item: Dict[str, Any], now: int) -> str:
    due = int(item.get("next_review_at") or now)
    overdue_hours = max(0, int((now - due) / 3600))
    if overdue_hours >= 24:
        return f"已经过期约 {round(overdue_hours / 24)} 天，优先恢复记忆稳定度。"
    if float(item.get("memory_strength") or 0.0) < 0.45:
        return "记忆强度偏低，适合现在做一次主动回忆。"
    return "到了系统安排的复习窗口。"


def _ability_reason(item: Dict[str, Any]) -> str:
    score = int(round(float(item.get("current_score") or 0.0) * 100))
    risk = str(item.get("risk_level") or "normal")
    if risk == "high":
        return f"近期稳定度偏低，当前估计约 {score}%。"
    if risk == "medium":
        return f"处在巩固窗口，当前估计约 {score}%。"
    return f"保持当前成长节奏，当前估计约 {score}%。"


def _plan_summary(tasks: List[Dict[str, Any]]) -> str:
    review_count = sum(1 for item in tasks if item.get("type") == "review")
    growth_count = sum(1 for item in tasks if item.get("type") == "growth")
    if review_count and growth_count:
        return f"今天优先处理 {review_count} 个记忆风险点，再补强 {growth_count} 个能力点。"
    if review_count:
        return f"今天优先处理 {review_count} 个到期复习项。"
    if growth_count:
        return f"今天优先补强 {growth_count} 个成长曲线偏弱的能力点。"
    return "先完成一组短练习，系统会据此生成更个性化的安排。"

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import db as db_module
from backend.services.learning_event_service import get_growth_insights, get_today_learning_plan
from backend.services.spaced_repetition import calculate_sm2_review
from backend.services.ability_service import record_practice_result
from backend.services.dashboard_service import complete_smart_learning_task, get_checkin_calendar
from backend.redis_client import set_timed_state


def _init_tmp_db(tmp_path):
    db_module.DB_PATH = str(tmp_path / "growth_engine.db")
    db_module.init_db()
    db_module.init_db()
    conn = db_module.get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("u1", "u1", "hash", 0),
        )
        conn.commit()
    finally:
        conn.close()


def test_sm2_success_extends_interval():
    first = calculate_sm2_review(quality=5)
    second = calculate_sm2_review(
        quality=4,
        repetitions=first["repetitions"],
        interval_days=first["interval_days"],
        ease_factor=first["ease_factor"],
        lapses=first["lapses"],
    )
    assert first["interval_days"] == 1.0
    assert second["interval_days"] == 6.0
    assert second["ease_factor"] >= 2.5


def test_vocabulary_review_records_hidden_growth_state(tmp_path):
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {
            "word": "coherent",
            "definition": "logical and consistent",
            "examples": [],
            "tags": ["writing"],
            "source_module": "manual",
            "mastery_level": 0.2,
        },
    )

    reviewed = db_module.review_vocabulary("v1", mastery_delta=0.2, quality=5)
    assert reviewed is not None
    assert reviewed["sm2"]["repetitions"] == 1
    assert reviewed["next_review_date"] > reviewed["last_reviewed_at"]

    plan = get_today_learning_plan("u1")
    insights = get_growth_insights("u1")
    assert plan["tasks"]
    assert any(item["ability_key"] == "vocabulary" for item in insights["abilities"])


def test_mistake_review_records_hidden_growth_state(tmp_path):
    _init_tmp_db(tmp_path)
    db_module.save_mistake(
        "m1",
        "u1",
        {
            "module": "listening",
            "question_id": "q1",
            "question_type": "date",
            "error_type": "detail_miss",
            "content": "What date is the meeting?",
            "user_answer": "Monday",
            "correct_answer": "Tuesday",
            "tags": ["detail"],
            "mastery_level": 0.1,
        },
    )

    reviewed = db_module.review_mistake("m1", mastery_delta=-0.1)
    assert reviewed is not None
    assert reviewed["sm2"]["lapses"] == 1

    insights = get_growth_insights("u1", limit=10)
    ability_keys = {item["ability_key"] for item in insights["abilities"]}
    assert "mistake_review" in ability_keys
    assert "listening_detail" in ability_keys


def test_review_quality_overrides_delta_mapping(tmp_path):
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v_quality",
        "u1",
        {
            "word": "nuance",
            "definition": "a subtle difference",
            "examples": [],
            "tags": ["writing"],
            "mastery_level": 0.3,
        },
    )
    db_module.save_mistake(
        "m_quality",
        "u1",
        {
            "module": "reading",
            "question_id": "q-quality",
            "question_type": "inference",
            "error_type": "logic",
            "content": "Inference question",
            "tags": ["inference"],
            "mastery_level": 0.3,
        },
    )

    vocab_reviewed = db_module.review_vocabulary("v_quality", mastery_delta=0.01, quality=5)
    mistake_reviewed = db_module.review_mistake("m_quality", mastery_delta=0.2, quality=1)

    assert vocab_reviewed is not None
    assert vocab_reviewed["sm2"]["quality"] == 5
    assert vocab_reviewed["sm2"]["repetitions"] == 1
    assert vocab_reviewed["mastery_level"] > 0.4
    assert mistake_reviewed is not None
    assert mistake_reviewed["sm2"]["quality"] == 1
    assert mistake_reviewed["sm2"]["lapses"] == 1
    assert mistake_reviewed["mastery_level"] < 0.2


def test_practice_result_feeds_cross_module_growth_engine(tmp_path):
    _init_tmp_db(tmp_path)

    record_practice_result(
        "u1",
        "writing",
        {
            "overall": 5.4,
            "accuracy": 5.0,
            "fluency": 5.5,
            "grammar": 4.5,
            "vocabulary": 5.0,
        },
        difficulty="medium",
        topic="education",
        practice_mode="task2_review",
        source="unit_test",
    )
    record_practice_result(
        "u1",
        "speaking",
        {
            "overall": 7.2,
            "fluency": 7.0,
            "grammar": 6.8,
            "vocabulary": 7.2,
        },
        difficulty="medium",
        topic="work",
        practice_mode="part2_turn",
        source="unit_test",
    )

    insights = get_growth_insights("u1", limit=20)
    ability_keys = {item["ability_key"] for item in insights["abilities"]}
    assert "writing_coherence" in ability_keys
    assert "writing_grammar" in ability_keys
    assert "speaking_fluency" in ability_keys

    plan = get_today_learning_plan("u1", limit=5)
    assert any(task["type"] in {"review", "growth"} for task in plan["tasks"])


def test_complete_smart_task_updates_today_checkin(tmp_path):
    _init_tmp_db(tmp_path)
    plan = get_today_learning_plan("u1", limit=2)
    task_id = plan["tasks"][0]["id"]

    completed = complete_smart_learning_task("u1", task_id)
    assert completed["ok"] is True
    assert completed["completed"] is True
    assert completed["today_tasks_completed"] >= 1

    refreshed = get_today_learning_plan("u1", limit=2)
    matching = [item for item in refreshed["tasks"] if item["id"] == task_id]
    assert matching and matching[0]["completed"] is True

    calendar = get_checkin_calendar("u1")
    assert calendar["today_status"] in {"partial", "completed"}


def test_redis_vocabulary_today_status_updates_home_calendar_partially(tmp_path):
    _init_tmp_db(tmp_path)
    today_key = time.strftime("%Y-%m-%d", time.localtime())
    set_timed_state(f"vocabulary:today_learning:completed:u1:{today_key}", "completed", 3600)

    calendar = get_checkin_calendar("u1")
    assert calendar["today_status"] == "partial"
    today = next(day for day in calendar["days"] if day["is_today"])
    assert today["status"] == "partial"
    assert today["done"] == 1
    assert today["total"] >= 2

    plan = get_today_learning_plan("u1", limit=5)
    vocab_task = next(task for task in plan["tasks"] if task["id"] == "smart-starter-vocabulary")
    translation_task = next(task for task in plan["tasks"] if task["id"] == "smart-starter-translation")
    assert vocab_task["completed"] is True
    assert translation_task["completed"] is False

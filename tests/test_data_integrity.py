"""数据完整性不变量回归测试。

覆盖审查中发现并修复的几类问题：
- 并发读-改-写丢更新（BEGIN IMMEDIATE）
- save_vocabulary 并发写入触发唯一索引冲突
- 重新收藏时从成长引擎回填 SM-2 状态
- 「已掌握」阈值使用 OR（兼容 mastery 高但 interval=0 的历史数据）
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import db as db_module
from backend.services.learning_event_service import _record_ability_sample


def _init_tmp_db(tmp_path):
    db_module.DB_PATH = str(tmp_path / "data_integrity.db")
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


def test_save_vocabulary_is_concurrency_safe(tmp_path):
    """并发收藏同一个词不应抛 IntegrityError，也不应产生重复行。"""
    _init_tmp_db(tmp_path)
    errors = []

    def worker(index):
        try:
            db_module.save_vocabulary(
                f"c{index}",
                "u1",
                {
                    "word": "concurrent",
                    "definition": "并发",
                    "examples": [],
                    "tags": [],
                    "source_module": "manual",
                },
            )
        except Exception as exc:  # noqa: BLE001 - 测试需要捕获任何异常
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    rows = [w for w in db_module.get_user_vocabulary("u1", 100) if w["word"] == "concurrent"]
    assert len(rows) == 1


def test_recollect_restores_sm2_state(tmp_path):
    """硬删除后重新收藏，应把成长引擎里积累的 SM-2 状态回填回来。"""
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {"word": "restore", "definition": "恢复", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.0},
    )
    for _ in range(3):
        db_module.review_vocabulary("v1", quality=5)
    before = db_module.get_vocabulary_by_id("v1")

    db_module.delete_vocabulary("v1", "u1")
    db_module.save_vocabulary(
        "v2",
        "u1",
        {"word": "restore", "definition": "恢复", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.0},
    )
    after = db_module.get_user_vocabulary_by_word("u1", "restore")

    assert after is not None
    assert int(after["sm2_repetitions"]) == int(before["sm2_repetitions"])
    assert float(after["sm2_interval_days"]) == float(before["sm2_interval_days"])
    # mastery 按迭代次数重建，应与删除前一致（而不是把成长引擎口径的高值搬过来）
    assert float(after["mastery_level"]) == float(before["mastery_level"])
    assert float(after["mastery_level"]) < db_module.VOCABULARY_MASTERED_MASTERY


def test_read_modify_write_survives_concurrency(tmp_path):
    """12 个线程并发累加同一条能力记录，sample_count 必须等于 12（不丢更新）。"""
    _init_tmp_db(tmp_path)
    now = int(time.time())

    def bump():
        _record_ability_sample("u1", "grammar", 0.8, now)

    threads = [threading.Thread(target=bump) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    conn = db_module.get_conn()
    try:
        row = conn.execute(
            "SELECT sample_count FROM user_ability_growth WHERE user_id = 'u1' AND ability_key = 'grammar'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert int(row["sample_count"]) == 12


def test_user_skill_state_survives_concurrency(tmp_path):
    """user_skill_state 同样是读-改-写，并发累加不应丢更新。"""
    _init_tmp_db(tmp_path)
    now = int(time.time())

    def bump():
        db_module.update_user_skill_state("u1", "module:writing", "module", 0.8, practiced_at=now)

    threads = [threading.Thread(target=bump) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    conn = db_module.get_conn()
    try:
        row = conn.execute(
            "SELECT exposure_count FROM user_skill_state WHERE user_id = 'u1' AND skill_key = 'module:writing'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert int(row["exposure_count"]) == 12


def test_mastered_threshold_accepts_high_mastery_without_interval(tmp_path):
    """历史数据迁移后 sm2_interval_days=0，但 mastery 已很高的词仍应算「已掌握」。"""
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "m1",
        "u1",
        {"word": "hist", "definition": "历史", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.95},
    )

    counts = db_module.get_vocabulary_mastery_counts("u1")
    assert counts["mastered"] == 1
    assert counts["active"] == 0

    page = db_module.get_vocabulary_page("u1", status="mastered")
    assert [item["word"] for item in page["items"]] == ["hist"]


def test_hidden_learning_event_write_is_atomic(tmp_path, monkeypatch):
    """埋点中途失败必须整体回滚，不能留下部分状态（半写）。"""
    _init_tmp_db(tmp_path)
    from backend.services import learning_event_service as les

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(les.db, "link_learning_event_skill", boom)

    with pytest.raises(RuntimeError):
        les.record_hidden_learning_event(
            user_id="u1",
            module="writing",
            event_type="practice_growth_sample",
            unit_type="practice",
            unit_key="writing:work:task2:medium",
            title="写作练习",
            quality=4,
        )

    conn = les.db.get_conn()
    try:
        events = conn.execute("SELECT COUNT(*) AS c FROM learning_events").fetchone()["c"]
        units = conn.execute("SELECT COUNT(*) AS c FROM learning_units").fetchone()["c"]
        abilities = conn.execute("SELECT COUNT(*) AS c FROM user_ability_growth").fetchone()["c"]
    finally:
        conn.close()

    assert events == 0, "失败后不应留下 learning_events"
    assert units == 0, "失败后不应留下 learning_units"
    assert abilities == 0, "失败后不应留下 user_ability_growth"

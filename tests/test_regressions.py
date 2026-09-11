"""针对审查中发现问题的回归测试（补测批次）。

覆盖此前没有测试的盲区：
- 个人词库的 examples 是字符串列表，不能被当成 bank 的 {english, chinese} 字典
- 埋点失败不得影响主流程（fail-open）
- SM-2 的边界（quality 归一化、q<3 间隔、E-Factor 下限）
- review_interval_seconds 覆盖时 SM-2 口径一致
- 词汇本分页过滤与批量删除
- 旧库缺 sm2_* 列时 init_db 能补齐
- Redis 不可用时降级到进程内存储
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import db as db_module
from backend.services.spaced_repetition import calculate_sm2_review, normalize_quality


def _init_tmp_db(tmp_path):
    db_module.DB_PATH = str(tmp_path / "regressions.db")
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


# ── #35 个人词库进 prompt ────────────────────────────────────────────────


def test_format_core_words_accepts_string_examples():
    """个人词库 examples 是 List[str]，bank 是 List[dict]，两种都要能格式化。"""
    from backend.services.ielts_vocabulary_bank_service import format_core_words_for_prompt

    personal = [
        {
            "head_word": "coherent",
            "part_of_speech": "adj",
            "definition_cn": "连贯的",
            "examples": ["This essay is coherent.", {"english": "A coherent plan.", "chinese": "连贯的计划"}],
            "phrases": ["coherent with / 与…一致", {"phrase": "coherent whole", "chinese": "统一整体"}],
        }
    ]
    text = format_core_words_for_prompt(personal)
    assert "coherent" in text
    assert "This essay is coherent." in text
    assert "coherent with" in text


def test_select_translation_core_words_personal_path_is_usable(tmp_path):
    """个人词被选中后，整条 prompt 组装链路不应抛异常。"""
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {
            "word": "coherent",
            "definition": "连贯的",
            "examples": ["This essay is coherent."],
            "tags": ["topic:writing"],
            "source_module": "manual",
            "mastery_level": 0.2,
        },
    )
    from backend.services.ielts_vocabulary_bank_service import (
        format_core_words_for_prompt,
        select_translation_core_words,
    )

    words = select_translation_core_words(difficulty="medium", topic="general", limit=3, user_id="u1")
    assert words, "个人词库应能产出候选词"
    # 不应抛 AttributeError
    text = format_core_words_for_prompt(words)
    assert "coherent" in text


# ── #36 埋点失败不影响主流程 ─────────────────────────────────────────────


def test_review_survives_hidden_engine_failure(tmp_path, monkeypatch):
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {"word": "resilient", "definition": "有韧性的", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.3},
    )

    # review_vocabulary 内部是局部导入，因此要 patch learning_event_service 上的同名符号
    from backend.services import learning_event_service

    def boom(*args, **kwargs):
        raise RuntimeError("hidden engine down")

    monkeypatch.setattr(learning_event_service, "record_hidden_learning_event", boom)

    reviewed = db_module.review_vocabulary("v1", quality=5, user_id="u1")
    assert reviewed is not None
    assert reviewed["mastery_level"] > 0.3
    # 主写已提交
    row = db_module.get_vocabulary_by_id("v1")
    assert float(row["mastery_level"]) == float(reviewed["mastery_level"])


# ── #39 SM-2 边界 ────────────────────────────────────────────────────────


def test_normalize_quality_clamps_and_handles_bad_input():
    assert normalize_quality(0) == 0
    assert normalize_quality(5) == 5
    assert normalize_quality(9) == 5
    assert normalize_quality(-3) == 0
    assert normalize_quality("abc", default=3) == 3
    assert normalize_quality(None, default=4) == 4
    assert normalize_quality(3.4) == 3


def test_sm2_failure_branches_and_ease_floor():
    # q<=1 → 0.25 天；q==2 → 1 天；且失败不惩罚 E-Factor
    q1 = calculate_sm2_review(quality=1, repetitions=4, interval_days=30.0, ease_factor=2.5)
    assert q1["interval_days"] == 0.25
    assert q1["repetitions"] == 0
    assert q1["ease_factor"] == 2.5
    assert q1["lapses"] == 1

    q2 = calculate_sm2_review(quality=2, repetitions=4, interval_days=30.0, ease_factor=2.5)
    assert q2["interval_days"] == 1.0
    assert q2["repetitions"] == 0

    # E-Factor 有 1.3 下限
    low = calculate_sm2_review(quality=3, repetitions=1, interval_days=1.0, ease_factor=1.3)
    assert low["ease_factor"] >= 1.3


def test_sm2_third_review_multiplies_by_ease():
    first = calculate_sm2_review(quality=5)
    second = calculate_sm2_review(
        quality=5,
        repetitions=first["repetitions"],
        interval_days=first["interval_days"],
        ease_factor=first["ease_factor"],
        lapses=first["lapses"],
    )
    third = calculate_sm2_review(
        quality=5,
        repetitions=second["repetitions"],
        interval_days=second["interval_days"],
        ease_factor=second["ease_factor"],
        lapses=second["lapses"],
    )
    assert second["interval_days"] == 6.0
    assert third["interval_days"] == pytest.approx(round(6.0 * second["ease_factor"], 2))


# ── #42 契约分支 ─────────────────────────────────────────────────────────


def test_review_interval_override_keeps_sm2_consistent(tmp_path):
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {"word": "override", "definition": "覆盖", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.2},
    )
    reviewed = db_module.review_vocabulary("v1", quality=5, review_interval_seconds=15 * 60, user_id="u1")
    assert reviewed is not None
    row = db_module.get_vocabulary_by_id("v1")
    # sm2_interval_days 必须与 next_review_date 口径一致（15 分钟 ≈ 0.0104 天）
    assert float(row["sm2_interval_days"]) == pytest.approx(15 / (24 * 60), abs=1e-4)
    assert reviewed["sm2"]["interval_days"] == pytest.approx(15 / (24 * 60), abs=1e-4)


def test_vocabulary_page_filters_and_bulk_delete(tmp_path):
    _init_tmp_db(tmp_path)
    for word, source in [("a", "manual"), ("b", "manual"), ("c", "reading"), ("d", "listening")]:
        db_module.save_vocabulary(
            f"v_{word}",
            "u1",
            {"word": word, "definition": word, "examples": [], "tags": [], "source_module": source, "mastery_level": 0.1},
        )

    assert db_module.get_vocabulary_page("u1", status="all")["total"] == 4
    assert db_module.get_vocabulary_page("u1", source_module="manual")["total"] == 2
    assert db_module.get_vocabulary_page("u1", status="active")["total"] == 4
    assert db_module.get_vocabulary_page("u1", status="mastered")["total"] == 0

    ids = [item["id"] for item in db_module.get_vocabulary_page("u1", source_module="manual")["items"]]
    assert db_module.delete_vocabulary_bulk(ids, "u1") == 2
    assert db_module.get_vocabulary_page("u1", status="all")["total"] == 2
    # 他人的 id 不应被删除
    assert db_module.delete_vocabulary_bulk(ids, "someone_else") == 0


def test_review_requires_owner_when_user_id_given(tmp_path):
    _init_tmp_db(tmp_path)
    db_module.save_vocabulary(
        "v1",
        "u1",
        {"word": "owned", "definition": "归属", "examples": [], "tags": [], "source_module": "manual", "mastery_level": 0.2},
    )
    # 传别人的 user_id → 查不到，返回 None（不会被越权更新）
    assert db_module.review_vocabulary("v1", quality=5, user_id="u2") is None
    row = db_module.get_vocabulary_by_id("v1")
    assert float(row["mastery_level"]) == 0.2


# ── #41 旧库补列 ─────────────────────────────────────────────────────────


def test_init_db_adds_sm2_columns_to_legacy_db(tmp_path):
    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.execute(
        """
        CREATE TABLE vocabulary (
          id TEXT PRIMARY KEY, user_id TEXT, word TEXT, definition TEXT,
          examples TEXT, pronunciation TEXT, part_of_speech TEXT, tags TEXT,
          source_module TEXT, mastery_level REAL, last_reviewed_at INTEGER,
          next_review_date INTEGER, created_at INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

    db_module.DB_PATH = str(legacy)
    db_module.init_db()  # 应通过 _add_column_if_missing 补齐 sm2_* 列

    conn = db_module.get_conn()
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(vocabulary)").fetchall()}
    finally:
        conn.close()
    for column in (
        "sm2_repetitions",
        "sm2_interval_days",
        "sm2_ease_factor",
        "sm2_lapses",
        "sm2_last_quality",
    ):
        assert column in columns, f"缺少列 {column}"

    # 再跑一次不应报错（幂等）
    db_module.init_db()


# ── #42 Redis 降级 ───────────────────────────────────────────────────────


def test_redis_falls_back_and_resets_broken_client(monkeypatch):
    import backend.redis_client as redis_client

    class Broken:
        def setex(self, *args, **kwargs):
            raise RuntimeError("connection lost")

        def get(self, *args, **kwargs):
            raise RuntimeError("connection lost")

        def delete(self, *args, **kwargs):
            raise RuntimeError("connection lost")

    monkeypatch.setattr(redis_client, "REDIS_URL", None)  # 不尝试连接真实 Redis，保持用例确定性
    monkeypatch.setattr(redis_client, "_redis", Broken())
    redis_client._timed_memory_store.clear()
    redis_client.set_timed_state("k", "v", 60)
    # 失效客户端应被置空以触发下次重连
    assert redis_client._redis is None
    assert redis_client.get_timed_state("k") == "v"


# ── #40 风险分级边界 ─────────────────────────────────────────────────────


def test_risk_level_requires_two_samples():
    from backend.services.learning_event_service import _risk_level

    # 单样本不判风险（旧实现 confidence=0.26 就会判 high）
    assert _risk_level(0.1, -0.5, 0.0, 0.9, sample_count=1) == "normal"
    assert _risk_level(0.1, -0.5, 0.0, 0.9, sample_count=2) == "high"
    assert _risk_level(0.5, -0.05, 0.5, 0.5, sample_count=3) == "medium"
    assert _risk_level(0.9, 0.0, 0.9, 0.9, sample_count=5) == "normal"

"""测试全局配置。

多个测试文件会把 `backend.db.DB_PATH` 指向自己的临时库，但不会还原，
导致同一次 pytest 会话里后续文件可能读到上一个测试的库（顺序耦合）。
这里用 autouse fixture 在每个测试结束后还原。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _restore_db_path():
    from backend import db

    original = db.DB_PATH
    yield
    db.DB_PATH = original

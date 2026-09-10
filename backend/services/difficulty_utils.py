from __future__ import annotations

from typing import List


_DIFFICULTY_RANK = {
    "easy": 1,
    "basic": 1,
    "medium": 2,
    "intermediate": 2,
    "hard": 3,
    "advanced": 3,
}


def dominant_difficulty(values: List[str]) -> str:
    """取一组难度的中位难度（偶数个元素取上中位）；空集合返回 medium。

    listening / reading 两个题库共用同一套难度词表与归一化口径。
    """
    normalized: List[str] = []
    for value in values:
        raw = str(value or "").strip().lower()
        if raw in {"easy", "basic"}:
            normalized.append("easy")
        elif raw in {"hard", "advanced"}:
            normalized.append("hard")
        else:
            normalized.append("medium")
    if not normalized:
        return "medium"
    return sorted(normalized, key=lambda item: _DIFFICULTY_RANK[item])[len(normalized) // 2]

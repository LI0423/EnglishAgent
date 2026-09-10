from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5


@dataclass(frozen=True)
class SM2State:
    repetitions: int = 0
    interval_days: float = 0.0
    ease_factor: float = DEFAULT_EASE_FACTOR
    lapses: int = 0


def normalize_quality(value: Any, default: int = 3) -> int:
    try:
        quality = int(round(float(value)))
    except (TypeError, ValueError):
        quality = int(default)
    return max(0, min(5, quality))


def quality_from_mastery_delta(delta: Any) -> int:
    try:
        value = float(delta)
    except (TypeError, ValueError):
        value = 0.0
    if value <= -0.12:
        return 1
    if value < 0.0:
        return 2
    if value < 0.08:
        return 3
    if value < 0.18:
        return 4
    return 5


def mastery_delta_from_quality(quality: int) -> float:
    q = normalize_quality(quality)
    return {
        0: -0.24,
        1: -0.18,
        2: -0.08,
        3: 0.05,
        4: 0.12,
        5: 0.18,
    }[q]


def calculate_sm2_review(
    *,
    quality: Any,
    repetitions: Any = 0,
    interval_days: Any = 0.0,
    ease_factor: Any = DEFAULT_EASE_FACTOR,
    lapses: Any = 0,
    reviewed_at: Optional[int] = None,
) -> Dict[str, Any]:
    q = normalize_quality(quality)
    reps = max(0, int(repetitions or 0))
    lapses_count = max(0, int(lapses or 0))
    try:
        previous_interval = max(0.0, float(interval_days or 0.0))
    except (TypeError, ValueError):
        previous_interval = 0.0
    try:
        ease = max(MIN_EASE_FACTOR, float(ease_factor or DEFAULT_EASE_FACTOR))
    except (TypeError, ValueError):
        ease = DEFAULT_EASE_FACTOR

    now = int(reviewed_at or time.time())
    if q < 3:
        new_reps = 0
        new_interval = 0.25 if q <= 1 else 1.0
        new_lapses = lapses_count + 1
    else:
        new_reps = reps + 1
        new_lapses = lapses_count
        if new_reps == 1:
            new_interval = 1.0
        elif new_reps == 2:
            new_interval = 6.0
        else:
            base_interval = max(1.0, previous_interval)
            new_interval = round(base_interval * ease, 2)

    if q < 3:
        # 标准 SM-2：回忆失败时不调整 E-Factor，避免连续失败把 ease 直接压到下限。
        new_ease = ease
    else:
        ease_delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        new_ease = round(max(MIN_EASE_FACTOR, ease + ease_delta), 4)
    next_review_at = now + int(new_interval * 24 * 3600)
    memory_strength = _memory_strength(q, new_reps, new_interval, new_ease, new_lapses)

    return {
        "quality": q,
        "repetitions": new_reps,
        "interval_days": new_interval,
        "ease_factor": new_ease,
        "lapses": new_lapses,
        "next_review_at": next_review_at,
        "memory_strength": memory_strength,
        "mastery_delta": mastery_delta_from_quality(q),
        "state": _state_from_review(q, new_reps, new_lapses),
        "next_review_label": label_for_interval_days(new_interval),
    }


def label_for_interval_days(interval_days: float) -> str:
    if interval_days < 1:
        hours = max(1, round(interval_days * 24))
        return f"约{hours}小时后复习"
    if interval_days < 2:
        return "明天复习"
    days = int(round(interval_days))
    return f"约{days}天后复习"


def outcome_from_quality(quality: int) -> float:
    return round(normalize_quality(quality) / 5.0, 4)


def _memory_strength(quality: int, repetitions: int, interval_days: float, ease_factor: float, lapses: int) -> float:
    q_factor = normalize_quality(quality) / 5.0
    interval_factor = min(1.0, max(0.0, interval_days / 30.0))
    ease_factor_norm = min(1.0, max(0.0, (ease_factor - MIN_EASE_FACTOR) / 2.2))
    repetition_factor = min(1.0, repetitions / 6.0)
    lapse_penalty = min(0.35, lapses * 0.06)
    strength = q_factor * 0.45 + interval_factor * 0.2 + ease_factor_norm * 0.2 + repetition_factor * 0.15
    return round(max(0.0, min(1.0, strength - lapse_penalty)), 4)


def _state_from_review(quality: int, repetitions: int, lapses: int) -> str:
    if quality < 3:
        return "relearning"
    if repetitions >= 5 and lapses == 0:
        return "mastered"
    if repetitions >= 2:
        return "reviewing"
    return "learning"

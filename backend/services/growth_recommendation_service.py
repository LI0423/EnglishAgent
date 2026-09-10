from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

from backend.db import get_user_skill_states, get_vocabulary_stats
from backend.services.ability_service import get_difficulty_recommendation
from backend.services.learning_event_service import module_for_ability


MODULE_LABELS = {
    "vocabulary": "词汇学习",
    "translation": "翻译练习",
    "reading": "阅读练习",
    "listening": "听力练习",
    "writing": "写作练习",
    "speaking": "口语练习",
    "mistakes": "错题复盘",
}

MODULE_ROUTES = {
    "vocabulary": "/vocabulary",
    "translation": "/translation-search",
    "reading": "/reading",
    "listening": "/listening",
    "writing": "/writing",
    "speaking": "/speaking",
    "mistakes": "/mistakes",
}

MODULE_PRACTICE_MODE = {
    "vocabulary": "复习巩固",
    "translation": "盲译练习",
    "reading": "策略训练",
    "listening": "精听训练",
    "writing": "片段批改",
    "speaking": "口语回答",
    "mistakes": "错题重练",
}


def get_growth_recommendations(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    states = get_user_skill_states(user_id, limit=300)
    vocabulary = get_vocabulary_stats(user_id)
    recommendations: List[Dict[str, Any]] = []

    if int(vocabulary.get("due_count") or 0) > 0:
        recommendations.append(
            _build_recommendation(
                user_id,
                module="vocabulary",
                title="先复习到期词汇",
                description=f"有 {int(vocabulary['due_count'])} 个词需要回看，适合先用短时间恢复记忆稳定度。",
                reason="到期复习优先",
                priority=100,
                practice_mode="间隔复习",
            )
        )

    now = int(time.time())
    due_states = [
        item for item in states
        if int(item.get("next_review_at") or 0) > 0 and int(item.get("next_review_at") or 0) <= now
    ]
    for item in sorted(due_states, key=lambda x: float(x.get("mastery") or 0.0))[:3]:
        module = _module_from_skill(item)
        recommendations.append(
            _build_recommendation(
                user_id,
                module=module,
                title=f"回看{_display_skill(item)}",
                description="这个能力点到了适合复习的时间，先做一组短练习能减少遗忘。",
                reason="能力点到期复习",
                priority=90 - int(float(item.get("mastery") or 0.0) * 20),
                practice_mode=MODULE_PRACTICE_MODE.get(module, "短练习"),
            )
        )

    weak_states = [
        item for item in states
        if int(item.get("exposure_count") or 0) > 0
        and float(item.get("mastery") or 0.0) < 0.58
        and str(item.get("category") or "") in {"module", "skill", "topic", "mode", "word"}
    ]
    for item in sorted(weak_states, key=lambda x: (float(x.get("mastery") or 0.0), -int(x.get("error_count") or 0)))[:5]:
        module = _module_from_skill(item)
        recommendations.append(
            _build_recommendation(
                user_id,
                module=module,
                title=f"补强{_display_skill(item)}",
                description=_weak_description(item, module),
                reason="近期掌握度偏低",
                priority=75 - int(float(item.get("mastery") or 0.0) * 30),
                practice_mode=MODULE_PRACTICE_MODE.get(module, "针对训练"),
            )
        )

    if not recommendations:
        recommendations.extend(_fallback_recommendations(user_id))

    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(recommendations, key=lambda x: int(x.get("priority") or 0), reverse=True):
        key = (str(item.get("module") or ""), str(item.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max(1, min(int(limit or 5), 10)):
            break
    return deduped


def _build_recommendation(
    user_id: str,
    *,
    module: str,
    title: str,
    description: str,
    reason: str,
    priority: int,
    practice_mode: str,
) -> Dict[str, Any]:
    module_key = module if module in MODULE_LABELS else "translation"
    difficulty = get_difficulty_recommendation(user_id, module=module_key)
    # 用稳定摘要作为 id，避免内置 hash() 受 PYTHONHASHSEED 影响导致跨进程不稳定。
    stable_digest = hashlib.sha1(f"{title}|{reason}".encode("utf-8")).hexdigest()[:12]
    return {
        "id": f"{module_key}-{stable_digest}",
        "module": module_key,
        "module_label": MODULE_LABELS.get(module_key, module_key),
        "title": title,
        "description": description,
        "reason": reason,
        "priority": int(priority),
        "route": MODULE_ROUTES.get(module_key, "/"),
        "practice_mode": practice_mode,
        "recommended_difficulty": difficulty.get("recommended_difficulty", "easy"),
        "difficulty_label": difficulty.get("label", "基础"),
        "confidence": difficulty.get("confidence", 0.25),
    }


def _fallback_recommendations(user_id: str) -> List[Dict[str, Any]]:
    return [
        _build_recommendation(
            user_id,
            module="translation",
            title="完成一次翻译练习",
            description="先用一题建立今日表现样本，系统会据此调整后续难度。",
            reason="暂无足够近期数据",
            priority=60,
            practice_mode="盲译练习",
        ),
        _build_recommendation(
            user_id,
            module="vocabulary",
            title="学习一组核心词汇",
            description="先积累表达素材，后续翻译和写作会优先调用这些词。",
            reason="建立词汇基础",
            priority=55,
            practice_mode="主动回忆",
        ),
        _build_recommendation(
            user_id,
            module="reading",
            title="完成一组阅读短练",
            description="用短题型补充阅读表现样本，帮助系统识别定位和理解能力。",
            reason="补充能力样本",
            priority=50,
            practice_mode="策略训练",
        ),
    ]


def _module_from_skill(item: Dict[str, Any]) -> str:
    category = str(item.get("category") or "")
    skill_key = str(item.get("skill_key") or "")
    if category == "word" or skill_key.startswith("word:"):
        return "vocabulary"
    if skill_key.startswith("ability:"):
        return module_for_ability(skill_key.split(":", 1)[1])
    if skill_key.startswith("module:"):
        module = skill_key.split(":", 1)[1]
        return module if module in MODULE_LABELS else "translation"
    first = skill_key.split(":", 1)[0]
    return first if first in MODULE_LABELS else "translation"


def _display_skill(item: Dict[str, Any]) -> str:
    skill_key = str(item.get("skill_key") or "")
    category = str(item.get("category") or "")
    if skill_key.startswith("module:"):
        return MODULE_LABELS.get(skill_key.split(":", 1)[1], "当前模块")
    if skill_key.startswith("word:"):
        return f"词汇 {skill_key.split(':', 1)[1]}"
    if skill_key.startswith("topic:"):
        return f"{skill_key.split(':', 1)[1]} 话题"
    parts = skill_key.split(":")
    if len(parts) >= 2:
        module = MODULE_LABELS.get(parts[0], parts[0])
        return f"{module} {parts[-1]}"
    return category or "薄弱点"


def _weak_description(item: Dict[str, Any], module: str) -> str:
    mastery = int(round(float(item.get("mastery") or 0.0) * 100))
    exposure = int(item.get("exposure_count") or 0)
    base = f"当前掌握度约 {mastery}%，已练 {exposure} 次。"
    if module == "vocabulary":
        return f"{base} 建议先做主动回忆或语境复现。"
    if module == "translation":
        return f"{base} 建议做一题低提示盲译，再查看批改。"
    if module == "reading":
        return f"{base} 建议优先做定位或主旨策略训练。"
    if module == "listening":
        return f"{base} 建议做一组精听，先慢速再恢复正常速度。"
    if module == "writing":
        return f"{base} 建议写一个短段落并立即批改。"
    if module == "speaking":
        return f"{base} 建议完成一轮口语回答，重点控制展开和节奏。"
    return f"{base} 建议完成一组针对性短练习。"

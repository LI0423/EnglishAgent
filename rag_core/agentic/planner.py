from typing import Any, Dict


class Planner:
    """根据问题和意图做一层轻量规划。"""

    def plan(self, question: str, intent: Dict[str, Any], module: str = "general") -> Dict[str, Any]:
        intent_type = intent.get("type", "general")
        target_word = intent.get("target_word", "")

        strategy = "balanced"
        if intent_type in {"synonym", "definition", "example"}:
            strategy = "intent_focused"
        elif module == "deep_search":
            strategy = "coverage_focused"

        return {
            "intent_type": intent_type,
            "target_word": target_word,
            "strategy": strategy,
            "goal": "answer_question_with_grounded_evidence",
            "module": module,
            "question": question,
        }

    def decompose(
        self,
        question: str,
        intent: Dict[str, Any],
        module: str = "general",
        max_sub_queries: int = 2,
    ) -> list[str]:
        target_word = (intent.get("target_word") or "").strip()
        base = question.strip()
        if not base:
            return []

        if module == "deep_search":
            candidates = [
                f"{base} 请先给出核心定义与边界。",
                f"{base} 请补充关键对比、场景和结论。",
            ]
        elif target_word:
            candidates = [
                f"{base}（聚焦：{target_word} 的定义与关键点）",
                f"{base}（聚焦：{target_word} 的用法、例子和常见误区）",
            ]
        else:
            candidates = [
                base,
                f"{base} 请补充可验证证据与要点对比。",
            ]

        # 去重并裁剪
        deduped = []
        seen = set()
        for item in candidates:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped[:max_sub_queries]

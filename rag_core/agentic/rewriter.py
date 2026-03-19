from typing import Dict


class QueryRewriter:
    """按计划重写查询，便于二次检索。"""

    def rewrite(self, question: str, plan: Dict, previous_feedback: str = "") -> str:
        target_word = plan.get("target_word") or ""
        strategy = plan.get("strategy", "balanced")

        suffix = ""
        if strategy == "intent_focused":
            suffix = " 请优先返回定义、同义词、例句等直接证据。"
        elif strategy == "coverage_focused":
            suffix = " 请覆盖背景、关键点、对比和结论。"

        if previous_feedback:
            suffix += f" 纠偏要求：{previous_feedback}"

        if target_word and target_word not in question:
            return f"{question}（核心词：{target_word}）{suffix}".strip()
        return f"{question}{suffix}".strip()

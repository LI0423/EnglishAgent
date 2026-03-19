from typing import Any, Dict, List


class RetrievalStrategyScheduler:
    """根据模块、意图和上一轮反馈动态调度检索策略。"""

    def __init__(self):
        self._module_defaults = {
            "vocabulary": ["intention_aware", "semantic", "keyword_bm25"],
            "deep_search": ["keyword_bm25", "semantic", "intention_aware"],
            "reading": ["semantic", "keyword_bm25", "intention_aware"],
            "writing": ["semantic", "keyword_bm25", "intention_aware"],
            "speaking": ["intention_aware", "semantic", "keyword_bm25"],
            "general": ["semantic", "keyword_bm25", "intention_aware"],
        }

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        out = []
        seen = set()
        for it in items:
            if it not in seen:
                out.append(it)
                seen.add(it)
        return out

    def schedule(
        self,
        *,
        module: str,
        intent: Dict[str, Any],
        base_top_k: int,
        iteration: int,
        previous_feedback: str = "",
        previous_citation_coverage: float = 0.0,
        has_memory_context: bool = False,
    ) -> Dict[str, Any]:
        strategies = list(self._module_defaults.get(module, self._module_defaults["general"]))
        top_k = max(1, int(base_top_k))
        reason = ["module_default"]

        intent_type = str(intent.get("type", "general"))
        if intent_type in {"synonym", "definition", "example", "usage_guidance", "word_family"}:
            strategies = ["intention_aware", "keyword_bm25", "semantic"] + strategies
            reason.append("intent_focus")

        if has_memory_context:
            strategies = ["semantic"] + strategies
            reason.append("memory_boost")

        feedback = previous_feedback or ""
        if "召回数量不足" in feedback:
            top_k += 2
            strategies = ["keyword_bm25", "semantic", "intention_aware"] + strategies
            reason.append("expand_recall")
        elif "高置信证据不足" in feedback:
            top_k += 1
            strategies = ["keyword_bm25", "intention_aware", "semantic"] + strategies
            reason.append("raise_precision")
        elif "证据覆盖不足" in feedback or previous_citation_coverage < 0.2:
            top_k += 1
            strategies = ["semantic", "keyword_bm25", "intention_aware"] + strategies
            reason.append("coverage_repair")

        if iteration > 1:
            top_k += 1
            reason.append("iterative_expansion")

        strategies = self._dedupe_keep_order(strategies)
        top_k = min(top_k, 12)
        return {
            "strategies": strategies,
            "top_k": top_k,
            "reason": ",".join(reason),
        }

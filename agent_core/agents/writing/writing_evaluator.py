from typing import Any, Dict

from utils.llm_utils import extract_json
from .text_features import extract_features


class WritingEvaluator:
    """
    纯评分引擎：无 session / 无 history
    """

    WEIGHTS = {
        "academic_task1": {"TR": 0.35, "CC": 0.30, "LR": 0.20, "GRA": 0.15},
        "general_task1": {"TR": 0.40, "CC": 0.25, "LR": 0.20, "GRA": 0.15},
        "task2": {"TR": 0.30, "CC": 0.25, "LR": 0.25, "GRA": 0.20},
    }

    def __init__(self, llm):
        self.llm = llm

    def build_prompt(self, essay: str, task_type: str) -> str:
        return (
            "你是雅思写作考官，请严格按照官方 Band Descriptor 评分。\n"
            "仅返回 JSON，不要解释。\n\n"
            "{\n"
            '  "scores": {"TR": float, "CC": float, "LR": float, "GRA": float},\n'
            '  "rationales": {"TR": str, "CC": str, "LR": str, "GRA": str},\n'
            '  "actionItems": [{"type": str, "before": str, "after": str, "examples": [str]}]\n'
            "}\n\n"
            f"Task 类型：{task_type}\n"
            f"作文：\n{essay}"
        )

    def evaluate(self, essay: str, task_type: str) -> Dict[str, Any]:
        # 使用RAG系统获取相关的写作评估标准和建议
        from rag_core.rag_system import RAGSystem
        rag_system = RAGSystem()
        rag_result = rag_system.query(essay, top_k=5, module="writing")
        
        prompt = self.build_prompt(essay, task_type)
        # 添加RAG系统获取的评估资料
        enhanced_prompt = prompt + f"\n\n相关写作评估资料：\n{rag_result}"
        
        _, raw = self.llm.communicate(enhanced_prompt)

        parsed = extract_json(raw)
        if not parsed:
            raise ValueError("LLM JSON parse failed")

        scores = parsed["scores"]
        features = extract_features(essay)

        self.apply_rules(scores, features, task_type)

        overall = self.compute_overall(scores, task_type)

        return {
            "task_type": task_type,
            "scores": scores,
            "overall": overall,
            "features": features,
            "rationales": parsed.get("rationales", {}),
            "actionItems": parsed.get("actionItems", []),
        }

    def apply_rules(self, scores: Dict[str, float], features: Dict[str, float], task_type: str):
        min_words = 250 if task_type == "task2" else 150
        if features["word_count"] < min_words:
            scores["TR"] = min(scores["TR"], 5.0)

        if features["ttr"] < 0.35:
            scores["LR"] -= 0.5

        for k in scores:
            scores[k] = min(9.0, max(1.0, round(scores[k] * 2) / 2))

    def compute_overall(self, scores: Dict[str, float], task_type: str) -> float:
        w = self.WEIGHTS[task_type]
        return round(sum(scores[k] * w[k] for k in w), 2)

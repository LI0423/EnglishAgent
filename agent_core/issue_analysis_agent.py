from typing import Dict, Any, Optional
from rag_core.intent_recognizer import IntentRecognizer
from rag_core.rag_system import RAGSystem
"""
延迟导入 agent 实例，避免在缺少第三方依赖（如 langchain_core）时包导入失败。
实际使用时 handler 内部会再导入对应的 agent 实例。
"""


class IssueAnalysisAgent:
    """分析用户问题并路由到合适的智能体（Orchestrator）"""

    def __init__(self, confidence_threshold: float = 0.4):
        self._intent = IntentRecognizer()
        # 延迟初始化 RAG，避免在导入模块时加载大型模型
        self._rag = None
        self.confidence_threshold = confidence_threshold
        self._mapping = {
            # 词汇/知识类走检索式RAG
            "synonym": self._handle_rag,
            "definition": self._handle_rag,
            "example": self._handle_rag,
            "pronunciation": self._handle_rag,
            "usage_guidance": self._handle_rag,
            "etymology": self._handle_rag,
            "word_family": self._handle_rag,
            "general": self._handle_rag,
            # 专门的能力
            "speaking": self._handle_speaking,
            "writing": self._handle_writing,
            "reading": self._handle_reading,
            "listening": self._handle_listening,
            "planning": self._handle_planning,
            "translation": self._handle_translation,
        }

    def analyze_and_route(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """主入口：识别意图并路由。返回统一结构。"""
        user_context = user_context or {}
        intent = self._intent.recognize_intent(query, top_k=3)

        # 如果意图置信度较低，先建议澄清
        if float(intent.get("confidence", 0.0)) < self.confidence_threshold:
            return {
                "query": query,
                "intent": intent,
                "handler": None,
                "clarify": True,
                "message": "意图不明确，请提供更多信息或选择下面的候选意图。",
                "candidates": intent.get("candidates", []),
            }

        itype = intent.get("type", "general")
        handler = self._mapping.get(itype, self._handle_rag)

        result: Dict[str, Any] = {"query": query, "intent": intent, "handler": handler.__name__}
        try:
            payload = handler(query, intent, user_context)
            result["result"] = payload
        except Exception as e:
            result["error"] = str(e)
        return result

    # handlers
    def _handle_rag(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        # 延迟创建 RAGSystem 实例并执行检索式回答（减少导入时副作用）
        if self._rag is None:
            try:
                self._rag = RAGSystem()
            except Exception as e:
                return {"error": f"RAGSystem unavailable: {e}"}
        return self._rag.query(query, top_k=5)

    def _handle_speaking(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        transcript = ctx.get("transcript")
        try:
            from .agent import speaking_agent
        except Exception as e:
            return {"error": "speaking_agent not available: %s" % e}

        if transcript:
            return speaking_agent.evaluate_speaking(transcript)
        return {"message": "请上传口语录音或提供口语文本(transcript)以进行评估。"}

    def _handle_writing(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        essay = ctx.get("essay")
        if essay:
            try:
                from .agent import writing_agent
            except Exception as e:
                return {"error": "writing_agent not available: %s" % e}
            return writing_agent.evaluate_writing(essay, task_type=ctx.get("task_type", "task2"))
        return {"message": "请提供写作文本(essay)以便评估。"}

    def _handle_reading(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        passage = ctx.get("passage")
        if passage:
            try:
                from .agent import reading_agent
            except Exception as e:
                return {"error": "reading_agent not available: %s" % e}
            return reading_agent.analyze_passage(passage)
        return {"message": "请提供文章内容(passage)以便分析。"}

    def _handle_listening(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        transcript = ctx.get("transcript", "")
        answers = ctx.get("answers", [])
        correct = ctx.get("correct_answers", [])
        try:
            from .agent import listening_agent
        except Exception as e:
            return {"error": "listening_agent not available: %s" % e}
        return listening_agent.evaluate_listening(transcript, answers, correct)

    def _handle_planning(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        profile = ctx.get("user_profile", {})
        assessment = ctx.get("assessment_results")
        try:
            from .agent import planning_agent
        except Exception as e:
            return {"error": "planning_agent not available: %s" % e}
        return planning_agent.generate_personalized_plan(profile, assessment)

    def _handle_translation(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        try:
            from .agent import translation_agent
        except Exception as e:
            return {"error": "translation_agent not available: %s" % e}

        if ctx.get("user_translation") and ctx.get("chinese_sentence"):
            return translation_agent.check_translation(ctx["chinese_sentence"], ctx["user_translation"])
        return translation_agent.generate_translation_question(difficulty=ctx.get("difficulty", "medium"))


# 实例
issue_analysis_agent = IssueAnalysisAgent()

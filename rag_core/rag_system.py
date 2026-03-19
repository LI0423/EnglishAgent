from typing import Any, Dict

from rag_core.agentic import AgenticRAGConfig, AgenticRAGOrchestrator
from rag_core.generator import Generator
from rag_core.intent_recognizer import IntentRecognizer
from rag_core.reranker import Reranker
from rag_core.retriever import Retriever


class RAGSystem:
    def __init__(self):
        self.metrics = {}
        self._intent_recognizer = IntentRecognizer()
        self._retriever = Retriever()
        self._reranker = Reranker()
        self._generator = Generator()
        self._agentic_orchestrator = AgenticRAGOrchestrator(
            self._intent_recognizer,
            self._retriever,
            self._reranker,
            self._generator,
        )

    def query(self, question: str, top_k: int = 5, module: str = "general"):
        """完整的RAG查询流程"""
        # 0. 意图识别
        intent = self._intent_recognizer.recognize_intent(question, top_k)
        # 1. 检索
        retrieved_docs = self._retriever.multi_way_retrieve(question, intent, top_k, module=module)
        # 2. 重排序
        reranked_docs = self._reranker.rerank(question, retrieved_docs, module)
        # 3. 生成
        result = self._generator.generate(question, reranked_docs, module)
        return result

    def query_agentic(
        self,
        question: str,
        module: str = "general",
        config: AgenticRAGConfig = None,
        session_id: str = "default",
        user_id: str = "default",
        return_legacy_payload: bool = True,
    ) -> Dict[str, Any]:
        """
        Agentic RAG 流程。
        return_legacy_payload=True 时返回 dict，方便上层直接消费；
        否则返回 AgenticRAGResult 对象。
        """
        result = self._agentic_orchestrator.run(
            question=question,
            module=module,
            config=config,
            session_id=session_id,
            user_id=user_id,
        )
        if return_legacy_payload:
            return {
                "answer": result.answer,
                "accepted": result.accepted,
                "iterations": result.iterations,
                "trace_id": result.trace_id,
                "final_query": result.final_query,
                "citations": result.citations,
                "memory_context": result.memory_context,
                "fallback_action": result.fallback_action,
                "needs_clarification": result.needs_clarification,
                "traces": [
                    {
                        "iteration": t.iteration,
                        "plan": t.plan,
                        "sub_queries": t.sub_queries,
                        "rewritten_query": t.rewritten_query,
                        "retrieved_count": t.retrieved_count,
                        "top_score": t.top_score,
                        "citation_coverage": t.citation_coverage,
                        "critic_passed": t.critic_passed,
                        "critic_score": t.critic_score,
                        "critic_feedback": t.critic_feedback,
                    }
                    for t in result.traces
                ],
            }
        return result

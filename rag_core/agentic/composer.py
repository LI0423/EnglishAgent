from typing import Any, Dict, List

from rag_core.agentic.schemas import AgenticRAGResult, IterationTrace


class Composer:
    def compose(
        self,
        answer: str,
        final_query: str,
        iterations: int,
        accepted: bool,
        trace_id: str,
        citations: List[Dict[str, Any]],
        memory_context: List[str],
        fallback_action: str,
        needs_clarification: bool,
        traces: List[IterationTrace],
    ) -> AgenticRAGResult:
        return AgenticRAGResult(
            answer=answer,
            final_query=final_query,
            iterations=iterations,
            accepted=accepted,
            trace_id=trace_id,
            citations=citations,
            memory_context=memory_context,
            fallback_action=fallback_action,
            needs_clarification=needs_clarification,
            traces=traces,
        )

    def to_legacy_payload(self, result: AgenticRAGResult) -> Dict[str, Any]:
        return {
            "answer": result.answer,
            "accepted": result.accepted,
            "iterations": result.iterations,
            "trace_id": result.trace_id,
            "final_query": result.final_query,
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
            "citations": result.citations,
            "memory_context": result.memory_context,
            "fallback_action": result.fallback_action,
            "needs_clarification": result.needs_clarification,
        }

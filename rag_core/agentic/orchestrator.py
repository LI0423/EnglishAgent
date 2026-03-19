from typing import List

from rag_core.agentic.citation_checker import CitationChecker
from rag_core.agentic.composer import Composer
from rag_core.agentic.critic import Critic
from rag_core.agentic.memory import HybridMemory
from rag_core.agentic.planner import Planner
from rag_core.agentic.reasoner import Reasoner
from rag_core.agentic.retrieval_executor import RetrievalExecutor
from rag_core.agentic.rewriter import QueryRewriter
from rag_core.agentic.schemas import AgenticRAGConfig, AgenticRAGResult, IterationTrace
from rag_core.agentic.strategy_scheduler import RetrievalStrategyScheduler
from rag_core.agentic.trace_logger import TraceLogger


class AgenticRAGOrchestrator:
    def __init__(self, intent_recognizer, retriever, reranker, generator):
        self._intent_recognizer = intent_recognizer
        self._planner = Planner()
        self._rewriter = QueryRewriter()
        self._retrieval_executor = RetrievalExecutor(retriever, reranker)
        self._reasoner = Reasoner(generator)
        self._critic = Critic()
        self._citation_checker = CitationChecker()
        self._memory = HybridMemory()
        self._strategy_scheduler = RetrievalStrategyScheduler()
        self._composer = Composer()

    @staticmethod
    def _merge_docs(doc_groups: List[List[dict]]) -> List[dict]:
        merged = {}
        for docs in doc_groups:
            for d in docs:
                key = d.get("content") or str(d.get("corpus_id"))
                if key not in merged:
                    merged[key] = d
                    continue
                if float(d.get("score", 0.0)) > float(merged[key].get("score", 0.0)):
                    merged[key] = d
        result = list(merged.values())
        result.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return result

    @staticmethod
    def _build_fallback_answer(question: str, docs: List[dict], feedback: str) -> tuple[str, str, bool]:
        if not docs:
            clarifying = (
                f"当前问题“{question}”的可用证据不足，我先不做武断结论。\n"
                "请补充：1) 你关注的具体词/句；2) 场景（阅读/写作/口语）；3) 你已有答案或样例。"
            )
            return clarifying, "clarify", True

        snippets = []
        for doc in docs[:3]:
            content = (doc.get("content") or "").strip().replace("\n", " ")
            if len(content) > 120:
                content = content[:120] + "..."
            snippets.append(f"- {content}")

        conservative = (
            "当前答案置信不足，先给出保守结论（仅基于已有证据）：\n"
            + "\n".join(snippets)
            + f"\n\n待补强点：{feedback}"
        )
        return conservative, "conservative", False

    def run(
        self,
        question: str,
        module: str = "general",
        config: AgenticRAGConfig = None,
        session_id: str = "default",
        user_id: str = "default",
    ) -> AgenticRAGResult:
        if config is None:
            config = AgenticRAGConfig()
        trace_logger = TraceLogger(config.trace_log_file)
        trace_id = trace_logger.new_trace_id()

        intent = self._intent_recognizer.recognize_intent(question, top_k=1)
        traces: List[IterationTrace] = []

        accepted = False
        answer = ""
        last_query = question
        feedback = ""
        final_citations = []
        memory_context: List[str] = []
        fallback_action = ""
        needs_clarification = False
        docs: List[dict] = []
        previous_citation_coverage = 0.0

        short_items = []
        long_items = []
        if config.enable_short_memory:
            short_items = self._memory.get_short_memory(session_id=session_id, window=config.short_memory_window)
        if config.enable_long_memory:
            long_items = self._memory.retrieve_long_memory(
                user_id=user_id,
                query=question,
                top_k=config.long_memory_top_k,
                module=module,
                backend=config.long_memory_backend,
                ttl_seconds=config.long_memory_ttl_seconds,
                db_path=config.long_memory_db_path,
                memory_file=config.long_memory_file,
            )
        memory_context = self._memory.build_memory_hints(short_items, long_items)
        memory_hint_text = " ".join(memory_context).strip()
        working_question = question if not memory_hint_text else f"{question}\n记忆线索: {memory_hint_text}"

        for idx in range(1, config.max_iterations + 1):
            plan = self._planner.plan(working_question, intent, module)
            retrieval_schedule = self._strategy_scheduler.schedule(
                module=module,
                intent=intent,
                base_top_k=config.top_k,
                iteration=idx,
                previous_feedback=feedback,
                previous_citation_coverage=previous_citation_coverage,
                has_memory_context=bool(memory_context),
            )
            plan["retrieval_schedule"] = retrieval_schedule
            sub_queries = [question]
            if config.enable_two_hop:
                sub_queries = self._planner.decompose(
                    question=working_question,
                    intent=intent,
                    module=module,
                    max_sub_queries=config.max_sub_queries,
                )
            rewritten_query = self._rewriter.rewrite(working_question, plan, feedback)
            retrieval_inputs = []
            if rewritten_query:
                retrieval_inputs.append(rewritten_query)
            retrieval_inputs.extend([q for q in sub_queries if q and q != rewritten_query])
            doc_groups = []
            for q in retrieval_inputs:
                doc_groups.append(
                    self._retrieval_executor.execute(
                        q,
                        intent,
                        top_k=int(retrieval_schedule.get("top_k", config.top_k)),
                        strategies=retrieval_schedule.get("strategies"),
                        module=module,
                    )
                )
            docs = self._merge_docs(doc_groups)
            answer = self._reasoner.reason(question, docs, module)
            citations, citation_coverage = self._citation_checker.evaluate(
                answer=answer,
                docs=docs,
                overlap_threshold=config.citation_overlap_threshold,
            )
            passed, score, feedback = self._critic.evaluate(
                answer=answer,
                docs=docs,
                min_doc_count=config.min_doc_count,
                min_doc_score=config.min_doc_score,
                citation_coverage=citation_coverage,
                min_citation_coverage=config.min_citation_coverage,
            )
            accepted = passed and score >= config.critic_accept_threshold
            top_score = float(docs[0].get("score", 0.0)) if docs else 0.0
            previous_citation_coverage = citation_coverage

            iteration_trace = IterationTrace(
                iteration=idx,
                plan=plan,
                sub_queries=sub_queries,
                rewritten_query=rewritten_query,
                retrieved_count=len(docs),
                top_score=top_score,
                citation_coverage=citation_coverage,
                critic_passed=accepted,
                critic_score=score,
                critic_feedback=feedback,
            )
            traces.append(iteration_trace)
            final_citations = citations
            if config.enable_trace:
                trace_logger.log_iteration(trace_id, iteration_trace)

            last_query = rewritten_query
            if accepted:
                break

        if not accepted and config.enable_fallback:
            answer, fallback_action, needs_clarification = self._build_fallback_answer(
                question=question,
                docs=docs,
                feedback=feedback,
            )

        # 回写记忆
        self._memory.add_short_memory(
            session_id=session_id,
            item={
                "question": question,
                "answer": answer,
                "accepted": accepted,
                "module": module,
            },
            maxlen=max(2, config.short_memory_window),
        )
        if config.enable_long_memory:
            self._memory.append_long_memory(
                user_id=user_id,
                session_id=session_id,
                module=module,
                question=question,
                answer=answer,
                backend=config.long_memory_backend,
                db_path=config.long_memory_db_path,
                ttl_seconds=config.long_memory_ttl_seconds,
                dedup_window_seconds=config.long_memory_dedup_window_seconds,
                memory_file=config.long_memory_file,
                extra={
                    "accepted": accepted,
                    "module": module,
                    "trace_id": trace_id,
                },
            )

        return self._composer.compose(
            answer=answer,
            final_query=last_query,
            iterations=len(traces),
            accepted=accepted,
            trace_id=trace_id,
            citations=final_citations,
            memory_context=memory_context,
            fallback_action=fallback_action,
            needs_clarification=needs_clarification,
            traces=traces,
        )

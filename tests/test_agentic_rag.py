import os
import sqlite3
import tempfile

from rag_core.agentic.orchestrator import AgenticRAGOrchestrator
from rag_core.agentic.schemas import AgenticRAGConfig


class _FakeIntentRecognizer:
    def recognize_intent(self, question: str, top_k: int = 1):
        return {
            "type": "definition",
            "target_word": "abandon",
            "confidence": 0.95,
        }


class _FakeRetriever:
    def __init__(self, docs):
        self._docs = docs
        self.queries = []
        self.calls = []

    def multi_way_retrieve(self, query, intent, top_k=10, strategies=None, module="general"):
        self.queries.append(query)
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "strategies": list(strategies or []),
                "module": module,
            }
        )
        return self._docs[:top_k]


class _FakeReranker:
    def rerank(self, query, res_list, module="general"):
        out = []
        for idx, item in enumerate(res_list):
            out.append(
                {
                    "corpus_id": idx,
                    "score": float(item.get("score", 0.0)),
                    "content": item.get("content", ""),
                }
            )
        out.sort(key=lambda x: x["score"], reverse=True)
        return out


class _FakeGenerator:
    def __init__(self, answer: str):
        self._answer = answer

    def generate(self, query, res, module="general"):
        return self._answer


def test_agentic_two_hop_and_accept():
    docs = [
        {"content": "abandon means to leave something behind.", "score": 0.92},
        {"content": "example: he abandoned the plan due to risk.", "score": 0.83},
        {"content": "synonym: desert, quit, forsake.", "score": 0.77},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator(
            "abandon 的核心含义是放弃或离开。常见用法是 abandon + noun，例如 abandon the plan。"
        ),
    )
    config = AgenticRAGConfig(
        max_iterations=1,
        top_k=3,
        enable_two_hop=True,
        max_sub_queries=2,
        min_doc_count=2,
        min_doc_score=0.5,
        min_citation_coverage=0.3,
        critic_accept_threshold=0.7,
    )

    result = orchestrator.run("abandon 是什么意思？", module="vocabulary", config=config)

    assert result.iterations == 1
    assert result.accepted is True
    assert len(result.traces) == 1
    assert len(result.traces[0].sub_queries) == 2
    assert len(retriever.queries) >= 2
    assert result.fallback_action == ""
    assert result.needs_clarification is False
    assert result.citations


def test_agentic_fallback_to_clarify_when_no_docs():
    retriever = _FakeRetriever([])
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("这里给一个没有证据支撑的回答。"),
    )
    config = AgenticRAGConfig(
        max_iterations=1,
        top_k=3,
        enable_two_hop=True,
        max_sub_queries=2,
        min_doc_count=2,
        min_doc_score=0.6,
        min_citation_coverage=0.6,
        critic_accept_threshold=0.8,
        enable_fallback=True,
    )

    result = orchestrator.run("解释这个概念", module="general", config=config)

    assert result.accepted is False
    assert result.fallback_action == "clarify"
    assert result.needs_clarification is True
    assert "请补充" in result.answer


def test_agentic_citation_gate_triggers_conservative_fallback():
    docs = [
        {"content": "this passage is about climate policy only.", "score": 0.91},
        {"content": "it does not mention requested term.", "score": 0.85},
        {"content": "another unrelated context text.", "score": 0.8},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("abandon means to leave and example is abandon the plan immediately."),
    )
    config = AgenticRAGConfig(
        max_iterations=1,
        top_k=3,
        enable_two_hop=False,
        min_doc_count=2,
        min_doc_score=0.5,
        min_citation_coverage=0.8,
        citation_overlap_threshold=0.4,
        critic_accept_threshold=0.8,
        enable_fallback=True,
    )

    result = orchestrator.run("abandon 的意思是什么？", module="vocabulary", config=config)

    assert result.accepted is False
    assert result.fallback_action == "conservative"
    assert result.needs_clarification is False
    assert "保守结论" in result.answer


def test_agentic_short_memory_is_used_in_next_turn():
    docs = [
        {"content": "abandon means to leave something behind.", "score": 0.92},
        {"content": "example: he abandoned the plan due to risk.", "score": 0.83},
        {"content": "synonym: desert, quit, forsake.", "score": 0.77},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("abandon means to leave and stop supporting a plan."),
    )
    config = AgenticRAGConfig(
        max_iterations=1,
        top_k=3,
        enable_two_hop=False,
        enable_long_memory=False,
        enable_short_memory=True,
        short_memory_window=6,
        min_doc_count=2,
        min_doc_score=0.5,
        min_citation_coverage=0.1,
        critic_accept_threshold=0.5,
    )

    orchestrator.run("abandon 是什么意思？", config=config, session_id="s1", user_id="u1")
    result2 = orchestrator.run("这个词常见搭配有哪些？", config=config, session_id="s1", user_id="u1")

    assert result2.memory_context
    assert any("短期记忆" in x for x in result2.memory_context)


def test_agentic_long_memory_retrieval_cross_session():
    docs = [
        {"content": "abandon means to leave something behind.", "score": 0.92},
        {"content": "example: he abandoned the plan due to risk.", "score": 0.83},
        {"content": "synonym: desert, quit, forsake.", "score": 0.77},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("abandon means to leave and stop supporting a plan."),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_db = os.path.join(tmpdir, "agentic_memory.db")
        config = AgenticRAGConfig(
            max_iterations=1,
            top_k=3,
            enable_two_hop=False,
            enable_long_memory=True,
            enable_short_memory=False,
            long_memory_backend="sqlite",
            long_memory_db_path=memory_db,
            long_memory_top_k=2,
            min_doc_count=2,
            min_doc_score=0.5,
            min_citation_coverage=0.1,
            critic_accept_threshold=0.5,
        )
        orchestrator.run("abandon 是什么意思？", config=config, session_id="s1", user_id="u42")
        result2 = orchestrator.run("abandon 的例句有哪些？", config=config, session_id="s2", user_id="u42")

    assert result2.memory_context
    assert any("长期记忆" in x for x in result2.memory_context)


def test_agentic_long_memory_ttl_and_dedup():
    docs = [
        {"content": "abandon means to leave something behind.", "score": 0.92},
        {"content": "example: he abandoned the plan due to risk.", "score": 0.83},
        {"content": "synonym: desert, quit, forsake.", "score": 0.77},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("abandon means to leave and stop supporting a plan."),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_db = os.path.join(tmpdir, "agentic_memory.db")

        config_dedup = AgenticRAGConfig(
            max_iterations=1,
            top_k=3,
            enable_two_hop=False,
            enable_long_memory=True,
            enable_short_memory=False,
            long_memory_backend="sqlite",
            long_memory_db_path=memory_db,
            long_memory_dedup_window_seconds=3600,
            long_memory_ttl_seconds=3600,
            min_doc_count=2,
            min_doc_score=0.5,
            min_citation_coverage=0.1,
            critic_accept_threshold=0.5,
        )
        orchestrator.run("abandon 是什么意思？", config=config_dedup, session_id="s1", user_id="u77")
        orchestrator.run("abandon 是什么意思？", config=config_dedup, session_id="s1", user_id="u77")

        conn = sqlite3.connect(memory_db)
        try:
            row = conn.execute(
                "SELECT COUNT(*), MAX(hit_count) FROM agentic_long_memory WHERE user_id = ?",
                ("u77",),
            ).fetchone()
            assert row[0] == 1
            assert row[1] >= 2
        finally:
            conn.close()

        config_ttl_expired = AgenticRAGConfig(
            max_iterations=1,
            top_k=3,
            enable_two_hop=False,
            enable_long_memory=True,
            enable_short_memory=False,
            long_memory_backend="sqlite",
            long_memory_db_path=memory_db,
            long_memory_ttl_seconds=-1,
            long_memory_top_k=3,
            min_doc_count=2,
            min_doc_score=0.5,
            min_citation_coverage=0.1,
            critic_accept_threshold=0.5,
        )
        result = orchestrator.run("abandon 的例句有哪些？", config=config_ttl_expired, session_id="s2", user_id="u77")
        assert not any("长期记忆" in x for x in result.memory_context)


def test_dynamic_retrieval_strategy_scheduler_escalates_on_feedback():
    docs = [
        {"content": "weak evidence 1", "score": 0.12},
        {"content": "weak evidence 2", "score": 0.1},
        {"content": "weak evidence 3", "score": 0.08},
    ]
    retriever = _FakeRetriever(docs)
    orchestrator = AgenticRAGOrchestrator(
        _FakeIntentRecognizer(),
        retriever,
        _FakeReranker(),
        _FakeGenerator("这是一段很短但证据不足的回答。"),
    )
    config = AgenticRAGConfig(
        max_iterations=2,
        top_k=3,
        enable_two_hop=False,
        enable_short_memory=False,
        enable_long_memory=False,
        min_doc_count=2,
        min_doc_score=0.9,
        min_citation_coverage=0.9,
        critic_accept_threshold=0.95,
        enable_fallback=True,
    )

    result = orchestrator.run("abandon 是什么意思？", module="vocabulary", config=config)

    assert result.iterations == 2
    # 每轮可能有多个检索输入（rewrite + sub query），取每轮第一条进行比较
    assert len(retriever.calls) >= 3
    first_iter_call = retriever.calls[0]
    second_iter_call = retriever.calls[2]
    assert second_iter_call["top_k"] > first_iter_call["top_k"]
    assert "keyword_bm25" in second_iter_call["strategies"]
    assert result.traces[1].plan.get("retrieval_schedule", {}).get("reason")

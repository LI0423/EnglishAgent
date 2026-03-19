import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _default_long_memory_db_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.environ.get("IELTS_AGENT_DB", os.path.join(root, "ielts_agent.db"))


@dataclass
class AgenticRAGConfig:
    max_iterations: int = 2
    min_doc_count: int = 3
    min_doc_score: float = 0.3
    min_citation_coverage: float = 0.4
    critic_accept_threshold: float = 0.7
    top_k: int = 5
    enable_two_hop: bool = True
    max_sub_queries: int = 2
    citation_overlap_threshold: float = 0.12
    enable_fallback: bool = True
    enable_short_memory: bool = True
    enable_long_memory: bool = True
    short_memory_window: int = 6
    long_memory_top_k: int = 3
    long_memory_backend: str = "sqlite"
    long_memory_db_path: Optional[str] = field(default_factory=_default_long_memory_db_path)
    long_memory_file: Optional[str] = "rag_core/agentic/memory_store.jsonl"
    long_memory_ttl_seconds: int = 30 * 24 * 3600
    long_memory_dedup_window_seconds: int = 3600
    enable_trace: bool = True
    trace_log_file: Optional[str] = None


@dataclass
class IterationTrace:
    iteration: int
    plan: Dict[str, Any]
    sub_queries: List[str]
    rewritten_query: str
    retrieved_count: int
    top_score: float
    citation_coverage: float
    critic_passed: bool
    critic_score: float
    critic_feedback: str


@dataclass
class AgenticRAGResult:
    answer: str
    final_query: str
    iterations: int
    accepted: bool
    trace_id: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    memory_context: List[str] = field(default_factory=list)
    fallback_action: str = ""
    needs_clarification: bool = False
    traces: List[IterationTrace] = field(default_factory=list)

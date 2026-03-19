from typing import Any, Dict, List


class RetrievalExecutor:
    def __init__(self, retriever, reranker):
        self._retriever = retriever
        self._reranker = reranker

    def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        top_k: int,
        strategies: List[str] = None,
        module: str = "general",
    ) -> List[Dict[str, Any]]:
        retrieved_docs = self._retriever.multi_way_retrieve(
            query,
            intent,
            top_k,
            strategies=strategies,
            module=module,
        )
        return self._reranker.rerank(query, retrieved_docs, module)

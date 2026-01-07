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

    def query(self, question: str, top_k: int = 5, module: str = "general"):
        """完整的RAG查询流程"""
        # 0. 意图识别
        intent = self._intent_recognizer.recognize_intent(question, top_k)
        # 1. 检索
        retrieved_docs = self._retriever.multi_way_retrieve(question, intent, top_k, module)
        # 2. 重排序
        reranked_docs = self._reranker.rerank(question, retrieved_docs, module)
        # 3. 生成
        result = self._generator.generate(question, reranked_docs, module)
        return result

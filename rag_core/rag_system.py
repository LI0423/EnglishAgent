import time
from typing import Dict, Any

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

    def query(self, question: str, top_k: int = 5):
        """完整的RAG查询流程"""
        # 0. 意图识别
        intent = self._intent_recognizer.recognize_intent(question)
        print(intent)
        # 1. 检索
        retrieved_docs = self._retriever.multi_way_retrieve(question, intent)
        print(retrieved_docs)

        # 2. 重排序
        # reranked_docs = self._reranker.rerank(question, retrieved_docs)
        #
        # # 3. 生成
        # generation_start = time.time()
        # result = self.generator.generate(question, reranked_docs)

        # # 记录指标
        # self.metrics['retrieval_times'].append(retrieval_time)
        # self.metrics['generation_times'].append(generation_time)
        # self.metrics['total_times'].append(total_time)
        #
        # # 添加元数据
        # result.update({
        #     'retrieval_metrics': {
        #         'retrieval_time': retrieval_time,
        #         'documents_retrieved': len(retrieved_docs),
        #         'top_similarities': [doc.get('similarity', 0) for doc in reranked_docs[:3]]
        #     },
        #     'generation_metrics': {
        #         'generation_time': generation_time
        #     },
        #     'total_time': total_time
        # })

        # return result

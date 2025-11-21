import time
from typing import Dict, Any

from rag_core.generator import Generator
from rag_core.reranker import Reranker
from rag_core.retriever import Retriever



class RAGSystem:
    def __init__(self):
        self.metrics = {}
        self.retriever = Retriever()
        self.reranker = Reranker()
        self.generator = Generator()

    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """完整的RAG查询流程"""
        start_time = time.time()

        # 1. 检索
        retrieval_start = time.time()
        retrieved_docs = self.retriever.retrieve(question, top_k=top_k)
        retrieval_time = time.time() - retrieval_start

        # 2. 重排序
        reranked_docs = self.reranker.rerank(question, retrieved_docs)

        # 3. 生成
        generation_start = time.time()
        result = self.generator.generate(question, reranked_docs)
        generation_time = time.time() - generation_start

        total_time = time.time() - start_time

        # 记录指标
        self.metrics['retrieval_times'].append(retrieval_time)
        self.metrics['generation_times'].append(generation_time)
        self.metrics['total_times'].append(total_time)

        # 添加元数据
        result.update({
            'retrieval_metrics': {
                'retrieval_time': retrieval_time,
                'documents_retrieved': len(retrieved_docs),
                'top_similarities': [doc.get('similarity', 0) for doc in reranked_docs[:3]]
            },
            'generation_metrics': {
                'generation_time': generation_time
            },
            'total_time': total_time
        })

        return result


if __name__ == '__main__':
    rag = RAGSystem()
    query = "sensible的近义词有哪些"
    res = rag.retrieve(query)
    print(res)
    rerank_results = rag.rerank(query, res)
    print(rerank_results)
    generate_result = rag.generate(query, rerank_results)
    print(generate_result)

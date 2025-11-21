from typing import List, Dict, Any

from rag_core.prompt import RERANK_PROMPT
from models.reranker_model import RerankerModel


def parse_search_results(search_results):
    """解析搜索结果"""
    if not search_results or len(search_results[0]) == 0:
        return []

    parsed = []
    for result in search_results[0]:
        parsed.append({
            'id': result['id'],
            'distance': result['distance'],
            'content': result['entity']['content'],
            'word': result['entity']['word'],
            'chunk_type': result['entity']['chunk_type']
        })
    return parsed


def format_instruction(instruction, query):
    output = "<Instruct>: {instruction}\n<Query>: {query}".format(instruction=instruction, query=query)
    return output


def map_rerank_to_retrieval(retrieval_chunks: List[str], rerank_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将 reranker 的 corpus_id (index) 映射回 retrieval 列表中的 chunk，并返回排序后的 chunks。
    假设传给 reranker 的 documents 顺序就是 retrieval_chunks 按顺序取出的 content。
    """
    mapped = []
    for r in rerank_results:
        idx = int(r['corpus_id'])
        if 0 <= idx < len(retrieval_chunks):
            chunk = retrieval_chunks[idx]
            mapped.append({
                "corpus_id": idx,
                "score": float(r['score']),
                "content": chunk
            })
        else:
            mapped.append(
                {"corpus_id": idx, "score": float(r['score']), "content": None})
    return mapped


class Reranker:
    def __init__(self):
        self.rerank_model = RerankerModel()

    def rerank(self, query: str, res_list: List[List[dict]]) -> List[Dict[str, Any]]:
        parsed_results = parse_search_results(res_list)
        documents = [result['content'] for result in parsed_results]
        rerank_prompt = RERANK_PROMPT
        rerank_prompt += f"用户问题: {query}\n请判断该候选文本是否能直接回答问题（Relevant/NotRelevant 或 0-1 分数）。"
        format_output = format_instruction(instruction=rerank_prompt, query=query)
        rerank_results = self.rerank_model.rerank(format_output, documents)
        return map_rerank_to_retrieval(documents, rerank_results)

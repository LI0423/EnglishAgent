from typing import List, Dict, Any

from rag_core.prompt import RERANK_PROMPT
from models.reranker_model import RerankerModel


def parse_search_results(search_results):
    """解析搜索结果"""
    if not search_results or len(search_results) == 0:
        return []

    parsed = []
    for result in search_results:
        parsed.append({
            'id': result['id'],
            'score': result['score'],
            'content': result['content'],
            'word': result['word'],
            'chunk_type': result['chunk_type']
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

    def rerank(self, query: str, res_list: List[Dict[str, Any]], module: str = "general") -> List[Dict[str, Any]]:
        parsed_results = parse_search_results(res_list)
        documents = [result['content'] for result in parsed_results]
        
        # 为不同模块定制重排序提示词
        module_prompts = {
            "vocabulary": "请判断该候选文本是否包含词汇的详细释义、例句、词根词缀分析或同义词信息，与用户问题的相关性如何。",
            "reading": "请判断该候选文本是否包含阅读文章的分析、结构解析、阅读技巧或长难句分析，与用户问题的相关性如何。",
            "writing": "请判断该候选文本是否包含写作指导、写作技巧、常见错误分析或写作模板，与用户问题的相关性如何。",
            "speaking": "请判断该候选文本是否包含口语练习建议、口语技巧、常见错误分析或口语范例，与用户问题的相关性如何。",
            "deep_search": "请判断该候选文本是否包含与用户问题相关的全面、准确的信息，与用户问题的相关性如何。"
        }
        
        rerank_prompt = RERANK_PROMPT
        module_prompt = module_prompts.get(module, "请判断该候选文本是否能直接回答问题，与用户问题的相关性如何。")
        rerank_prompt += f"用户问题: {query}\n{module_prompt}"
        
        format_output = format_instruction(instruction=rerank_prompt, query=query)
        rerank_results = self.rerank_model.rerank(format_output, documents)
        return map_rerank_to_retrieval(documents, rerank_results)

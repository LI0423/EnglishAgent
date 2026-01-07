from langchain.tools import tool
from rag_core.rag_system import RAGSystem
from agent_core.search import tavily_search as online_search

rag = RAGSystem()


@tool
def retrieve(query: str):
    """检索相关文档

    Args:
        query: 检索查询

    Returns:
        检索到的相关文档
    """
    return rag.query(query, top_k=5)

@tool
def tavily_search(query: str, max_results: int = 5):
    """
    在线网络检索
    
    Args:
        query: 问题
        max_result: 最大答案条数
    Returns:
        问题检索结果
    """
    return online_search(query, max_results)

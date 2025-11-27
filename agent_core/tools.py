from langchain.tools import tool

from rag_core.rag_system import RAGSystem
from utils import MilvusDBClient

milvus_client = MilvusDBClient()
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

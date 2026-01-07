from typing import Any, List, Dict
from agent_core.agents.base_agent import BaseAgent
from rag_core.rag_system import RAGSystem

class VocabularyAgent(BaseAgent):
    """词汇智能体
    
    用于处理词汇相关的查询，集成RAG系统获取词汇信息
    """
    
    agent_key = "vocabulary"
    
    def __init__(self, temperature: float = 0.7, enable_thinking: bool = True, use_streamer: bool = True):
        super().__init__(temperature, enable_thinking, use_streamer)
        self.rag_system = RAGSystem()
    
    def can_handle(self, query: str) -> bool:
        """判断是否能处理该查询
        
        Args:
            query: 用户查询
            
        Returns:
            bool: 是否能处理
        """
        keywords = ["单词", "词汇", "意思", "定义", "释义", "例句", "用法", "同义词", "反义词", "词根", "词缀", "拼写", "发音", "词性", "vocabulary", "word", "meaning", "definition", "example", "usage", "synonym", "antonym", "root", "affix", "spelling", "pronunciation", "part of speech"]
        return any(keyword in query.lower() for keyword in keywords)
    
    def analyze_vocabulary(self, word: str) -> Dict[str, Any]:
        """分析词汇信息
        
        Args:
            word: 单词
            
        Returns:
            Dict[str, Any]: 词汇分析结果
        """
        # 使用RAG系统获取词汇信息
        result = self.rag_system.query(word, top_k=5, module="vocabulary")
        return self._parse_vocabulary_analysis(result)
    
    def _parse_vocabulary_analysis(self, result: str) -> Dict[str, Any]:
        """解析词汇分析结果
        
        Args:
            result: RAG系统返回的结果
            
        Returns:
            Dict[str, Any]: 解析后的词汇分析结果
        """
        # 简单解析，实际应用中可能需要更复杂的解析逻辑
        return {
            "word": "",
            "definition": "",
            "examples": [],
            "synonyms": [],
            "antonyms": [],
            "root_affix": "",
            "pronunciation": "",
            "part_of_speech": "",
            "raw": result
        }
    
    def generate_response(self, query: str, history: List[Any]) -> str:
        """生成响应
        
        Args:
            query: 用户查询
            history: 历史对话
            
        Returns:
            str: 响应内容
        """
        if not self.can_handle(query):
            return self.fallback()
        
        self.before_run(query, history)
        
        # 使用RAG系统处理词汇查询
        result = self.rag_system.query(query, top_k=5, module="vocabulary")
        
        return self.after_run(result)

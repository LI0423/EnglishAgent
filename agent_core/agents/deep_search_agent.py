from typing import Optional, Dict, List, Any
from agent_core.tools import retrieve, tavily_search
from .base_agent import BaseAgent


class DeepSearchAgent(BaseAgent):
    """深度搜索智能体
    
    用于执行深度搜索任务，通过多次迭代搜索和结果整合，获取更全面、准确的信息
    """
    
    agent_key = "deep_search"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.max_iterations = self.config.get("max_iterations", 3)
        self.max_results = self.config.get("max_results", 5)
    
    def can_handle(self, query: str) -> bool:
        """判断是否能处理该查询
        
        Args:
            query: 用户查询
            
        Returns:
            bool: 是否能处理
        """
        keywords = ["深度搜索", "详细信息", "全面了解", "深入分析", "deep search", "detailed information"]
        return any(keyword in query.lower() for keyword in keywords)
    
    def deep_search(self, query: str) -> Dict[str, Any]:
        """执行深度搜索
        
        Args:
            query: 用户查询
            
        Returns:
            Dict[str, Any]: 搜索结果
        """
        results = {
            "original_query": query,
            "iterations": [],
            "final_summary": "",
            "sources": []
        }
        
        current_query = query
        
        for i in range(self.max_iterations):
            iteration_result = self._perform_iteration(current_query, i+1)
            results["iterations"].append(iteration_result)
            
            # 整合来源
            if "sources" in iteration_result:
                results["sources"].extend(iteration_result["sources"])
            
            # 生成下一轮查询
            if i < self.max_iterations - 1:
                current_query = self._generate_next_query(query, iteration_result)
        
        # 生成最终摘要
        results["final_summary"] = self._generate_final_summary(results)
        
        return results
    
    def _perform_iteration(self, query: str, iteration: int) -> Dict[str, Any]:
        """执行单次搜索迭代
        
        Args:
            query: 当前查询
            iteration: 迭代次数
            
        Returns:
            Dict[str, Any]: 迭代结果
        """
        # 1. 使用RAG系统检索相关文档
        from rag_core.rag_system import RAGSystem
        rag_system = RAGSystem()
        rag_results = rag_system.query(query, top_k=5, module="deep_search")
        
        # 2. 使用在线搜索获取最新信息
        online_results = tavily_search(query, max_results=self.max_results)
        
        # 3. 整合结果
        sources = []
        if rag_results:
            sources.append({"type": "rag", "results": rag_results})
        if online_results:
            sources.append({"type": "online", "results": online_results})
        
        return {
            "iteration": iteration,
            "query": query,
            "sources": sources
        }
    
    def _generate_next_query(self, original_query: str, iteration_result: Dict[str, Any]) -> str:
        """生成下一轮查询
        
        Args:
            original_query: 原始查询
            iteration_result: 当前迭代结果
            
        Returns:
            str: 下一轮查询
        """
        # 这里可以使用LLM生成更具体的查询
        # 为了简单起见，我们使用基于关键词的方法
        
        # 提取当前结果中的关键词
        keywords = self._extract_keywords(iteration_result)
        
        # 生成更具体的查询
        if keywords:
            return f"{original_query} 关于 {' '.join(keywords[:3])} 的详细信息"
        else:
            return original_query
    
    def _extract_keywords(self, iteration_result: Dict[str, Any]) -> List[str]:
        """从迭代结果中提取关键词
        
        Args:
            iteration_result: 迭代结果
            
        Returns:
            List[str]: 关键词列表
        """
        # 简单实现：从查询中提取关键词
        query = iteration_result.get("query", "")
        # 这里可以使用更复杂的NLP技术提取关键词
        return query.split()[:5]  # 简单起见，返回前5个词
    
    def _generate_final_summary(self, results: Dict[str, Any]) -> str:
        """生成最终摘要
        
        Args:
            results: 所有搜索结果
            
        Returns:
            str: 最终摘要
        """
        # 使用LLM生成摘要
        prompt = f"请根据以下搜索结果，为用户提供一个全面、准确的摘要：\n\n"
        
        for i, iteration in enumerate(results["iterations"]):
            prompt += f"迭代 {iteration['iteration']} 查询: {iteration['query']}\n"
            for source in iteration.get("sources", []):
                prompt += f"来源类型: {source['type']}\n"
                if "results" in source:
                    prompt += f"结果: {str(source['results'])[:200]}...\n"
            prompt += "\n"
        
        prompt += f"原始查询: {results['original_query']}\n"
        prompt += "请提供一个详细的摘要，涵盖所有重要信息。"
        
        try:
            _, summary = self.qwen_llm.communicate(prompt)
            return summary
        except Exception:
            return "无法生成摘要，请稍后重试"
    
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
        
        # 执行深度搜索
        results = self.deep_search(query)
        
        # 格式化响应
        response = self._format_response(results)
        
        return self.after_run(response)
    
    def _format_response(self, results: Dict[str, Any]) -> str:
        """格式化响应
        
        Args:
            results: 搜索结果
            
        Returns:
            str: 格式化的响应
        """
        lines = [
            "【深度搜索结果】",
            f"原始查询: {results['original_query']}",
            f"搜索迭代次数: {len(results['iterations'])}",
            "",
            "【最终摘要】",
            results['final_summary'],
            "",
            "【搜索过程】"
        ]
        
        for iteration in results['iterations']:
            lines.append(f"迭代 {iteration['iteration']}: {iteration['query']}")
            for source in iteration.get("sources", []):
                lines.append(f"  来源: {source['type']}")
        
        return "\n".join(lines)
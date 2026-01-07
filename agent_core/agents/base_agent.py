from typing import Any, List, Optional
from agent_core.tools import retrieve, tavily_search
from models.pipeline_wrapper import QwenPipelineWrapper
from langchain_core.messages import BaseMessage

class BaseAgent:
    """智能体基类"""

    agent_key: str = "base"
    
    def __init__(self, temperature: float=0.7, enable_thinking: bool=True, use_streamer: bool=True):
        model_wrapper = QwenPipelineWrapper(
            device="mps",  # 自动选择设备
            max_new_tokens=2048,
            temperature=temperature,
            enable_thinking=enable_thinking,
            use_streamer=use_streamer
        )
        self.qwen_llm = model_wrapper.get_langchain_llm()
        self.tools = [retrieve, tavily_search]

        self.session_id: Optional[str] = None
        self.summary_store = None
        self.history_store = None
        
    def should_update_summary(self) -> bool:
        return False
    
    def summary_prompt(self, old_summary: str, new_dialogue: str) -> str:
        raise NotImplementedError
    
    def get_summary(self) -> str:
        if not self.summary_store or not self.session_id:
            return ""
        return self.summary_store.get(self.session_id, scope=self.agent_key)
    
    def before_run(self, query: str, history: List[BaseMessage]) -> None:
        return None
    
    def after_run(self, response: str) -> str:
        return response
    
    def allow_tools(self) -> bool:
        return True
    
    def get_tools(self) -> List[Any]:
        return self.tools if self.allow_tools() else []
    
    def can_handle(self, query: str) -> bool:
        return True
    
    def fallback(self) -> str:
        return "该问题超出当前智能体的处理能力"
    
    def build_prompt(self, query: str, history: List[BaseMessage]) -> str:
        summary = self.get_summary()
        return f"""
        你是一个专业的 {self.agent_key} 智能体。
        【长期记忆】
        {summary or "（无）"}
        【最近对话】
        {history}
        用户问题：
        {query}
        """
    
    def generate_response(self, query: str, history: List[BaseMessage]) -> str:
        if not self.can_handle(query):
            return self.fallback()
        
        self.before_run(query, history)
        prompt = self.build_prompt(query, history)
        try:
            _, response = self.qwen_llm.invoke(prompt)
        except Exception:
            return self.fallback()
        
        return self.after_run(response)
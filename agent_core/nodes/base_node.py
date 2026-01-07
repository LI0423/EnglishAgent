import logging
from abc import ABC, abstractmethod
from typing import Any

from agent_core.llms.base_llm import BaseLLM
from agent_core.state.state import State


class BaseNode(ABC):
    """节点基类"""
    def __init__(self, llm_client: BaseLLM, node_name: str=""):
        self.llm_client = llm_client
        self.node_name = node_name or self.__class__.__name__
        
    @abstractmethod
    def run(self, input_data: Any, **kwargs) -> str:
        """节点运行方法"""
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """输入数据验证方法"""
        return True
    
    def process_output(self, output: Any) -> Any:
        """处理输出数据"""
        return output
    
    def log_info(self, message: str):
        """日志记录方法"""
        logging.info(f"{self.node_name}: {message}")
        
    def log_error(self, message: str):
        """错误日志记录方法"""
        logging.error(f"{self.node_name}: {message}")
        
class StateMutationNode(BaseNode):
    """状态变更节点基类"""
    @abstractmethod
    def mutate_state(self, input_data: Any, state: State, **kwargs) -> State:
        """状态变更方法"""
        pass
        
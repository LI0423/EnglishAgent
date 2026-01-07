from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM基础抽象类"""

    def __init__(self, api_key, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用LLM生成回复
        :param system_prompt:
        :param user_prompt:
        :param kwargs:
        :return:
        """
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """
        获取默认模型名称
        :return:
        """
        pass

    def validate_response(self, response: str) -> str:
        """
        验证和清理相应内容
        :param response:
        :return:
        """
        if response is None:
            return ""
        return response.strip()

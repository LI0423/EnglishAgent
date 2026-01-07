import os
from dotenv import load_dotenv
import logging

from langchain_community.llms.openai import OpenAI
from langchain_community.chat_models import ChatTongyi

from agent_core.llms.base_llm import BaseLLM
from models.generator_model import GeneratorModel

load_dotenv()

class QWenLLM(BaseLLM):
    def __init__(self, api_key: str = os.getenv("QWEN_KEY"), api_url: str = os.getenv("QWEN_URL")):
        super().__init__(api_key, api_url)
        if api_key and api_url:
            self.chat_client = ChatTongyi(api_key=api_key,
                                          model=os.getenv("TONGYI_MODEL"),
                                          base_url=api_url)
        else:
            self.client = GeneratorModel()

    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用LLM生成回复
        :param system_prompt:
        :param user_prompt:
        :param kwargs:
        :return:
        """
        try:
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            # 设置默认参数
            params = {
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_token": kwargs.get("max_token", 4000),
                "stream": False
            }
            # 调用LLM
            response = self.client.communicate(**params)
            # 提取回复内容
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                return self.validate_response(content)
        except Exception as e:
            logging.error(f"调用LLM生成回复失败: {e}")
            return ""

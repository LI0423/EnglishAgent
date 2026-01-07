import json
from json import JSONDecodeError
from typing import Any, Dict

from agent_core.nodes.base_node import BaseNode
from agent_core.prompts import SYSTEM_PROMPT_FIRST_SEARCH
from agent_core.text_processing import remove_reasoning_from_output, clean_json_tags, extract_clean_response


class FirstSearchNode(BaseNode):
    """为段落生成首次搜索查询的节点"""

    def __init__(self, llm_client):
        super().__init__(llm_client)

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                return "title" in data and "content" in data
            except JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            return "title" in input_data and "content" in input_data
        else:
            return False

    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("Invalid input data")

            # 准备输入数据
            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)

            self.log_info("正在生成首次搜索查询")
            response = self.llm_client.invoke(SYSTEM_PROMPT_FIRST_SEARCH, message)
            processed_response = self.process_output(response)
            self.log_info(f"首次搜索查询生成完毕：{processed_response.get('search_query', 'N/A')}")
            return processed_response
        except Exception as e:
            self.log_error(f"生成首次搜索查询失败：{e}")
            raise e

    def process_output(self, output: str) -> Dict[str, str]:
        try:
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)

            # 解析JSON
            try:
                result = json.loads(cleaned_output)
            except JSONDecodeError:
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    raise ValueError(result["error"])
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")

            if not search_query:
                raise ValueError("未找到搜索查询")
            return {
                "search_query": search_query,
                "reasoning": reasoning
            }
        except Exception as e:
            self.log_error(f"处理输出失败：{e}")
            raise e

class ReflectionNode(BaseNode):
    """段落反思节点"""

    def __init__(self, llm_client):
        super().__init__(llm_client, "ReflectionNode")

    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("输入数据格式错误，需要包含title、content和paragraph_latest_state字段")

            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)
            self.log_info("正在生成段落反思并生成新搜索查询")

            response = self.llm_client.invoke(SYSTEM_PROMPT_FIRST_SEARCH, message)
            processed_response = self.process_output(response)
            self.log_info(f"段落反思生成完毕：{processed_response.get('search_query', 'N/A')}")
            return processed_response
        except Exception as e:
            self.log_error(f"生成段落反思失败：{e}")
            raise e

    def process_output(self, output: str) -> Dict[str, str]:
        """
        处理LLM输出，提取搜索查询和推理

        Args:
            output: LLM原始输出

        Returns:
            包含search_query和reasoning的字典
        """
        try:
            # 清理响应文本
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)

            # 解析JSON
            try:
                result = json.loads(cleaned_output)
            except JSONDecodeError:
                # 使用更强大的提取方法
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    raise ValueError("JSON解析失败")

            # 验证和清理结果
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")

            if not search_query:
                raise ValueError("未找到搜索查询")

            return {
                "search_query": search_query,
                "reasoning": reasoning
            }

        except Exception as e:
            self.log_error(f"处理输出失败: {str(e)}")
            # 返回默认查询
            return {
                "search_query": "深度研究补充信息",
                "reasoning": "由于解析失败，使用默认反思搜索查询"
            }
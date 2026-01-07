import json
from json import JSONDecodeError
from typing import Any

from agent_core.nodes.base_node import StateMutationNode
from agent_core.prompts import SYSTEM_PROMPT_FIRST_SUMMARY, SYSTEM_PROMPT_REFLECTION_SUMMARY
from agent_core.state.state import State
from agent_core.text_processing import remove_reasoning_from_output, clean_json_tags


class FirstSummaryNode(StateMutationNode):
    def __init__(self, llm_client):
        super().__init__(llm_client, "FirstSummaryNode")

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                required_fields = ["title", "content", "search_query", "search_results"]
                return all(field in data for field in required_fields)
            except json.JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            required_fields = ["title", "content", "search_query", "search_results"]
            return all(field in input_data for field in required_fields)
        return False

    def run(self, input_data: Any, **kwargs) -> str:
        try:
            if not self.validate_input(input_data):
                raise ValueError("Invalid input data")

            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)

            self.log_info("正在生成首次段落总结")
            response = self.llm_client.invoke(SYSTEM_PROMPT_FIRST_SUMMARY, message)

            processed_response = self.process_output(response)
            self.log_info(f"首次段落总结生成完毕")
            return processed_response
        except Exception as e:
            self.log_error(f"Error in FirstSummaryNode: {str(e)}")
            raise

    def process_output(self, output: str) -> str:
        try:
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            try:
                result = json.loads(cleaned_output)
            except JSONDecodeError:
                return cleaned_output

            if isinstance(result, dict):
                paragraph_content = result.get("paragraph_latest_state", "")
                if paragraph_content:
                    return paragraph_content

            return cleaned_output
        except Exception as e:
            self.log_error(f"Error in process_output: {str(e)}")
            raise

    def mutate_state(self, input_data: Any, state: State, **kwargs) -> State:
        try:
            paragraph_index = kwargs["paragraph_index"]
            summary = self.run(input_data, **kwargs)
            if 0 <= paragraph_index < len(state.paragraphs):
                state.paragraphs[paragraph_index].research.latest_summary = summary
                self.log_info(f"段落 {paragraph_index} 的最新总结已更新")
            else:
                raise ValueError(f"段落索引 {paragraph_index} 超出范围")
            state.update_timestamp()
            return state
        except Exception as e:
            self.log_error(f"Error in mutate_state: {str(e)}")
            raise

class ReflectionSummaryNode(StateMutationNode):
    def __init__(self, llm_client):
        super().__init__(llm_client, "ReflectionSummaryNode")

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                required_fields = ["title", "content", "search_results", "paragraph_latest_state"]
                return all(field in data for field in required_fields)
            except JSONDecodeError:
                return False

        elif isinstance(input_data, dict):
            required_fields = ["title", "content", "search_results", "paragraph_latest_state"]
            return all(field in input_data for field in required_fields)
        return False

    def run(self, input_data: Any, **kwargs) -> str:
        try:
            if not self.validate_input(input_data):
                raise ValueError("Invalid input data")

            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)

            self.log_info("正在生成段落反思总结")
            response = self.llm_client.invoke(SYSTEM_PROMPT_REFLECTION_SUMMARY, message)
            processed_response = self.process_output(response)
            self.log_info(f"段落反思总结生成完毕")
            return processed_response
        except Exception as e:
            self.log_error(f"Error in ReflectionSummaryNode: {str(e)}")
            raise e

    def process_output(self, output: Any) -> str:
        try:
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)

            try:
                result = json.loads(cleaned_output)
            except JSONDecodeError:
                return cleaned_output

            if isinstance(result, dict):
                updated_content = result.get("updated_paragraph_latest_state", "")
                if updated_content:
                    return updated_content
            return cleaned_output
        except Exception as e:
            self.log_error(f"Error in process_output: {str(e)}")
            raise e

    def mutate_state(self, input_data: Any, state: State, **kwargs) -> State:
        try:
            paragraph_index = kwargs["paragraph_index"]
            updated_summary = self.run(input_data, **kwargs)
            if 0 <= paragraph_index < len(state.paragraphs):
                state.paragraphs[paragraph_index].research.latest_summary = updated_summary
                state.paragraphs[paragraph_index].research.increment_reflection()
                self.log_info(f"段落 {paragraph_index} 的最新总结已更新")
            else:
                raise ValueError(f"段落索引 {paragraph_index} 超出范围")
            state.update_timestamp()
            return state
        except Exception as e:
            self.log_error(f"Error in mutate_state: {str(e)}")
            raise e
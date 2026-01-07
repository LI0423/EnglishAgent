import json
from typing import Any

from agent_core.llms.base_llm import BaseLLM
from agent_core.nodes.base_node import BaseNode
from agent_core.prompts import SYSTEM_PROMPT_REPORT_FORMATTING
from agent_core.text_processing import remove_reasoning_from_output, clean_markdown_tags


class ReportFormattingNode(BaseNode):
    """格式化最终报告节点"""

    def __init__(self, llm_client: BaseLLM):
        super().__init__(llm_client, "ReportFormattingNode")

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                return isinstance(data, list) and all(
                    isinstance(item, dict) and "title" in item and "paragraph_latest_state" in item
                    for item in data
                )
            except json.JSONDecodeError:
                return False

        elif isinstance(input_data, list):
            return all(
                isinstance(item, dict) and "title" in item and "paragraph_latest_state" in item
                for item in input_data
            )
        else:
            return False

    def run(self, input_data: Any, **kwargs) -> str:
        try:
            if not self.validate_input(input_data):
                raise ValueError("输入数据格式错误，需要包含title和paragraph_latest_state的列表")

            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)

            response = self.llm_client.invoke(SYSTEM_PROMPT_REPORT_FORMATTING, message)
            processed_response = self.process_output(response)
            return processed_response
        except Exception as e:
            self.log_error(f"格式化报告时发生错误: {str(e)}")
            return "格式化报告时发生错误"

    def process_output(self, output: str):
        try:
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_markdown_tags(cleaned_output)

            if not cleaned_output.strip():
                return "# 报告生成失败\n\n无法生成有效的报告内容。"

            if not cleaned_output.strip().startswith('#'):
                cleaned_output = "# 深度研究报告\n\n" + cleaned_output

            return cleaned_output.strip()

        except Exception as e:
            self.log_error(f"处理输出时发生错误: {str(e)}")
            return "处理输出时发生错误"

    def format_report_manually(self, paragraphs: list[dict[str, str]], report_title: str = "深度研究报告") -> str:
        try:
            report_lines = [
                f"# {report_title}",
                "",
                "---",
                ""
            ]
            for i, paragraph in enumerate(paragraphs, 1):
                title = paragraph.get("title", f"段落 {i}")
                content = paragraph.get("paragraph_latest_state", "")

                if content:
                    report_lines.extend([
                        f"## {title}",
                        "",
                        content,
                        "",
                        "---",
                        ""
                    ])
            if len(paragraphs) > 1:
                report_lines.extend([
                    "## 结论",
                    "",
                    "本报告通过深度搜索和研究，对相关主题进行了全面分析。",
                    "以上各个方面的内容为理解该主题提供了重要参考",
                    ""
                ])

            return "\n".join(report_lines)

        except Exception as e:
            self.log_error(f"手动格式化报告时发生错误: {str(e)}")
            return "# 报告生成失败\n\n无法完成报告格式化。"

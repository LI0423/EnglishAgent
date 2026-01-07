from typing import Any, Dict

from agent_core.agents.base_agent import BaseAgent

class ReadingAgent(BaseAgent):
    """阅读智能体"""
    
    agent_key = "reading"
    def __init__(self, temperature: float = 0.7, enable_thinking: bool = True, use_streamer: bool = True):
        super().__init__(temperature, enable_thinking, use_streamer)

    def can_handle(self, query: str) -> bool:
        return any(k in query for k in ("阅读", "文章", "passage", "雅思阅读"))

    def analyze_passage(self, passage: str) -> Dict[str, Any]:
        """分析阅读文章"""
        prompt = f"""请作为专业的雅思阅读教练，分析以下文章：

        {passage}

        请提供：
        1. 文章的主题和结构
        2. 关键的同义替换
        3. 长难句分析
        4. 阅读技巧建议

        请使用JSON格式输出，包含以下字段：
        主题: str
        结构: str
        synonymReplacements: [{"original": str, "replacement": str, "sentence": str}]
        complexSentences: [{"sentence": str, "analysis": str}]
        tips: [str]
        """
        
        try:
            _, response = self.qwen_llm.invoke(prompt)
        except Exception:
            return {"error": "阅读分析失败，请稍后重试"}
        return self._parse_reading_analysis(response)
    
    def _parse_reading_analysis(self, response: str) -> Dict[str, Any]:
        """解析JSON格式的阅读分析响应"""
        import json
        import re

        # 去除可能的代码块或多余文本
        text = re.sub(r"```.*?```", "", response, flags=re.DOTALL).strip()
        try:
            return json.loads(text)
        except Exception:
            # 返回部分结构，保证不会报错
            return {
                "主题": "",
                "结构": "",
                "synonymReplacements": [],
                "complexSentences": [],
                "tips": [],
                "raw": response  # 方便调试
            }
        
    def generate_response(self, query, history):
        if not self.can_handle(query):
            return self.fallback()
        
        self.before_run(query, history)
        analysis = self.analyze_passage(query)
        return self.after_run(self.format_analysis(analysis))
    
    def format_analysis(self, analysis: Dict[str, Any]) -> str:
        """格式化阅读分析结果为可读文本"""
        lines = [
            f"主题: {analysis.get('主题', '')}",
            f"结构: {analysis.get('结构', '')}",
            "\n同义替换:",
        ]
        for item in analysis.get("synonymReplacements", []):
            lines.append(f"- {item['original']} → {item['replacement']} （句子：{item['sentence']}）")

        lines.append("\n长难句分析:")
        for item in analysis.get("complexSentences", []):
            lines.append(f"- 句子: {item['sentence']}")
            lines.append(f"  分析: {item['analysis']}")

        lines.append("\n阅读技巧建议:")
        for tip in analysis.get("tips", []):
            lines.append(f"- {tip}")

        return "\n".join(lines)

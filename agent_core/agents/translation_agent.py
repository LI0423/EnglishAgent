import json
import re
from typing import Any, Dict, List
from langchain_core.messages import BaseMessage
from agent_core.agents.base_agent import BaseAgent

class TranslationAgent(BaseAgent):
    """翻译练习智能体"""
    agent_key = "translation"
    
    def __init__(self, temperature: float = 0.7, enable_thinking: bool = True, use_streamer: bool = True):
        super().__init__(temperature, enable_thinking, use_streamer)

    def can_handle(self, query):
        return any(k in query for k in ("翻译", "translation", "句子", "练习"))
    
    def generate_translation_question(self, difficulty: str = "medium") -> Dict[str, Any]:
        """生成翻译练习题"""
        prompt = f"""请作为专业的英语翻译教练，生成一个中文句子作为翻译练习题目。

        难度级别：{difficulty}（easy/medium/hard）

        请生成一个符合以下要求的中文句子：
        1. 符合指定难度级别
        2. 适合英语学习者练习翻译
        3. 包含常见的语法结构和词汇
        4. 句子长度适中

        请使用JSON格式输出，包含以下字段：
        - chinese_sentence: str
        - difficulty: str
        - topic: str
        """
        
        _, response = self.qwen_llm.invoke(prompt)
        return self._parse_translation_question(response, default={
            "chinese_sentence": "",
            "difficulty": difficulty,
            "topic": ""
        })
    
    def check_translation(self, chinese_sentence: str, user_translation: str) -> Dict[str, Any]:
        """检查翻译并给出评价"""
        prompt = f"""请作为专业的英语翻译教练，检查用户的翻译并给出详细评价。

        中文原句：{chinese_sentence}
        用户翻译：{user_translation}

        请从以下几个方面进行评价：
        1. 准确性（Accuracy）：翻译是否准确传达了原句的意思
        2. 流畅度（Fluency）：翻译是否自然流畅
        3. 语法（Grammar）：是否存在语法错误
        4. 词汇（Vocabulary）：词汇使用是否恰当
        5. 改进建议（Suggestions）：具体的改进建议

        请使用JSON格式输出，包含以下字段：
        - accuracy: float（0-10分）
        - fluency: float（0-10分）
        - grammar: float（0-10分）
        - vocabulary: float（0-10分）
        - overall: float（0-10分）
        - evaluation: str
        - suggestions: [str]
        - correct_translation: str
        """
        
        try:
            _, response = self.qwen_llm.invoke(prompt)
        except Exception:
            return {"error": "翻译检查失败，请稍后重试"}

        return self._parse_json_response(response, default={
            "accuracy": 0.0,
            "fluency": 0.0,
            "grammar": 0.0,
            "vocabulary": 0.0,
            "overall": 0.0,
            "evaluation": "",
            "suggestions": [],
            "correct_translation": ""
        })    
    
    def _parse_json_response(self, response: str, default: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 LLM 响应中的 JSON，兼容 LLM 输出可能带文本或代码块
        """
        try:
            # 去除代码块
            clean_text = re.sub(r"```.*?```", "", response, flags=re.DOTALL).strip()
            # 尝试提取 JSON
            json_text = clean_text[clean_text.find("{"): clean_text.rfind("}")+1]
            return json.loads(json_text)
        except Exception:
            return default
    
    def generate_response(self, query: str, history: List[BaseMessage]) -> str:
        if not self.can_handle(query):
            return self.fallback()

        self.before_run(query, history)

        # 判断用户意图：生成题目还是检查翻译
        if "生成" in query or "题目" in query:
            result = self.generate_translation_question(difficulty="medium")
        elif "检查" in query or "翻译" in query:
            # 假设 query 格式："检查 翻译：中文句子 || 用户翻译"
            try:
                parts = query.split("||")
                chinese_sentence = parts[0].replace("检查翻译：", "").strip()
                user_translation = parts[1].strip()
            except Exception:
                return "请按格式提供中文句子和用户翻译，中间用 '||' 分隔"
            result = self.check_translation(chinese_sentence, user_translation)
        else:
            return self.fallback()

        # 返回可读文本
        return self.after_run(self.format_translation_result(result))

    # ---------------- 格式化输出 ----------------
    def format_translation_result(self, result: Dict[str, Any]) -> str:
        if "error" in result:
            return result["error"]

        if "chinese_sentence" in result:
            # 翻译题目
            lines = [
                f"【翻译练习题】",
                f"难度: {result.get('difficulty', '')}",
                f"主题: {result.get('topic', '')}",
                f"中文句子: {result.get('chinese_sentence', '')}"
            ]
        else:
            # 翻译检查
            lines = [
                f"【翻译检查结果】",
                f"准确性: {result.get('accuracy', 0)}",
                f"流畅度: {result.get('fluency', 0)}",
                f"语法: {result.get('grammar', 0)}",
                f"词汇: {result.get('vocabulary', 0)}",
                f"综合评分: {result.get('overall', 0)}",
                f"评价: {result.get('evaluation', '')}",
                f"正确翻译示例: {result.get('correct_translation', '')}",
                "\n改进建议:"
            ]
            for s in result.get("suggestions", []):
                lines.append(f"- {s}")

        return "\n".join(lines)

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
    
    def generate_translation_question(
        self,
        difficulty: str = "medium",
        direction: str = "zh_to_en",
        topic: str = "general",
    ) -> Dict[str, Any]:
        """生成翻译练习题"""
        safe_direction = direction if direction in {"zh_to_en", "en_to_zh"} else "zh_to_en"
        safe_topic = (topic or "general").strip() or "general"
        source_language = "中文" if safe_direction == "zh_to_en" else "英文"
        target_language = "英文" if safe_direction == "zh_to_en" else "中文"
        prompt = f"""请作为专业的英语翻译教练，生成一个{source_language}句子作为{source_language}译{target_language}练习题目。

        难度级别：{difficulty}（easy/medium/hard）
        主题：{safe_topic}
        翻译方向：{safe_direction}

        请生成一个符合以下要求的{source_language}句子：
        1. 符合指定难度级别
        2. 适合英语学习者练习翻译
        3. 贴合指定主题
        4. 句子长度适中

        请使用JSON格式输出，包含以下字段：
        - source_sentence: str
        - chinese_sentence: str（若源语言不是中文，也给出中文释义）
        - direction: str
        - difficulty: str
        - topic: str
        - focus_points: [str]（本题重点）
        """
        
        try:
            _, response = self.qwen_llm.communicate(prompt)
        except Exception:
            return self._fallback_question(difficulty, safe_direction, safe_topic)
        return self._parse_translation_question(response, default={
            "source_sentence": "",
            "chinese_sentence": "",
            "direction": safe_direction,
            "difficulty": difficulty,
            "topic": safe_topic,
            "focus_points": [],
        })
    
    def check_translation(
        self,
        source_sentence: str = "",
        user_translation: str = "",
        direction: str = "zh_to_en",
        topic: str = "general",
        chinese_sentence: str = "",
    ) -> Dict[str, Any]:
        """检查翻译并给出评价"""
        safe_direction = direction if direction in {"zh_to_en", "en_to_zh"} else "zh_to_en"
        safe_topic = (topic or "general").strip() or "general"
        source = source_sentence or chinese_sentence
        source_language = "中文" if safe_direction == "zh_to_en" else "英文"
        target_language = "英文" if safe_direction == "zh_to_en" else "中文"
        prompt = f"""请作为专业的英语翻译教练，检查用户的翻译并给出详细评价。

        翻译方向：{source_language}译{target_language}
        主题：{safe_topic}
        原句：{source}
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
        - difficulty_analysis: {{
            long_sentence: [str],
            idioms_or_collocations: [str],
            grammar_points: [str],
            cultural_notes: [str],
            technique_tips: [str]
          }}
        - reusable_expressions: [str]
        """
        
        try:
            _, response = self.qwen_llm.communicate(prompt)
        except Exception:
            return self._fallback_evaluation(source, user_translation, safe_direction, safe_topic)

        default = {
            "accuracy": 0.0,
            "fluency": 0.0,
            "grammar": 0.0,
            "vocabulary": 0.0,
            "overall": 0.0,
            "evaluation": "",
            "suggestions": [],
            "correct_translation": "",
            "difficulty_analysis": {
                "long_sentence": [],
                "idioms_or_collocations": [],
                "grammar_points": [],
                "cultural_notes": [],
                "technique_tips": [],
            },
            "reusable_expressions": [],
            "source_sentence": source,
            "direction": safe_direction,
            "topic": safe_topic,
        }
        parsed = self._parse_json_response(response, default=default)
        if self._is_empty_evaluation(parsed):
            return self._fallback_evaluation(source, user_translation, safe_direction, safe_topic)
        return parsed

    def _parse_translation_question(self, response: str, default: Dict[str, Any]) -> Dict[str, Any]:
        parsed = self._parse_json_response(response, default=default)
        if not parsed.get("source_sentence") and parsed.get("chinese_sentence"):
            parsed["source_sentence"] = parsed.get("chinese_sentence")
        if not parsed.get("source_sentence"):
            return default
        if not parsed.get("chinese_sentence") and parsed.get("direction") == "zh_to_en":
            parsed["chinese_sentence"] = parsed.get("source_sentence")
        parsed["direction"] = parsed.get("direction") or default.get("direction", "zh_to_en")
        parsed["difficulty"] = parsed.get("difficulty") or default.get("difficulty", "medium")
        parsed["topic"] = parsed.get("topic") or "General"
        parsed["focus_points"] = parsed.get("focus_points") or []
        return parsed

    @staticmethod
    def _fallback_question(difficulty: str, direction: str = "zh_to_en", topic: str = "general") -> Dict[str, Any]:
        if direction == "en_to_zh":
            source = {
                "easy": "Many students use online courses to improve their English.",
                "hard": "Critical thinking enables learners to evaluate information rather than simply memorize it.",
            }.get(difficulty, "Technology has significantly changed the way people communicate and learn.")
            return {
                "source_sentence": source,
                "chinese_sentence": "用于英译中练习的英文句子。",
                "direction": direction,
                "difficulty": difficulty,
                "topic": topic or "education",
                "focus_points": ["准确传达逻辑关系", "自然中文表达"],
            }
        source = {
            "easy": "我每天早上都会读一篇英语短文。",
            "hard": "在数字化时代，批判性思维比单纯记忆知识更能决定一个人的长期竞争力。",
        }.get(difficulty, "随着科技的发展，人们的生活方式发生了显著变化。")
        return {
            "source_sentence": source,
            "chinese_sentence": source,
            "direction": direction,
            "difficulty": difficulty,
            "topic": topic or "technology",
            "focus_points": ["句子主干", "关键词准确性"],
        }

    @staticmethod
    def _fallback_evaluation(
        source_sentence: str,
        user_translation: str,
        direction: str = "zh_to_en",
        topic: str = "general",
    ) -> Dict[str, Any]:
        has_content = bool((user_translation or "").strip())
        score = 6.0 if has_content else 0.0
        return {
            "accuracy": score,
            "fluency": score,
            "grammar": score,
            "vocabulary": score,
            "overall": score,
            "evaluation": "当前为离线评估结果，建议联网后获取更准确反馈。",
            "suggestions": [
                "先确保句子主干完整，再优化从句与修饰成分。",
                "对照原句检查时态、一致性和关键词是否遗漏。",
            ],
            "correct_translation": (
                "With the development of technology, people's lifestyles have changed significantly."
                if direction == "zh_to_en"
                else "随着科技的发展，人们的生活方式发生了显著变化。"
            ),
            "source_sentence": source_sentence,
            "direction": direction,
            "topic": topic,
            "difficulty_analysis": {
                "long_sentence": ["先拆主干，再处理状语和从句。"],
                "idioms_or_collocations": ["注意固定搭配和自然表达。"],
                "grammar_points": ["检查时态、单复数和连接词。"],
                "cultural_notes": ["避免逐词直译，优先保证目标语言自然。"],
                "technique_tips": ["先直译保意思，再二次润色表达。"],
            },
            "reusable_expressions": ["with the development of", "play a crucial role in"],
        }
    
    def _parse_json_response(self, response: str, default: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 LLM 响应中的 JSON，兼容 LLM 输出可能带文本或代码块
        """
        try:
            clean_text = (response or "").strip()
            fenced = re.search(r"```(?:json)?\s*(.*?)```", clean_text, flags=re.DOTALL | re.IGNORECASE)
            if fenced:
                clean_text = fenced.group(1).strip()
            # 尝试提取 JSON
            json_text = clean_text[clean_text.find("{"): clean_text.rfind("}")+1]
            parsed = json.loads(json_text)
            if not isinstance(parsed, dict):
                return default
            return {**default, **parsed}
        except Exception:
            return default

    @staticmethod
    def _is_empty_evaluation(result: Dict[str, Any]) -> bool:
        """
        判断批改结果是否只是解析失败后的空默认值。
        避免前端收到 200 响应后展示 0 分、空反馈、空参考译文。
        """
        text_fields = [
            result.get("evaluation"),
            result.get("correct_translation"),
            *(result.get("suggestions") or []),
            *(result.get("reusable_expressions") or []),
        ]
        has_text = any(str(item or "").strip() for item in text_fields)
        score_keys = ("accuracy", "fluency", "grammar", "vocabulary", "overall")
        has_score = any(TranslationAgent._to_float(result.get(key)) > 0 for key in score_keys)
        return not has_text and not has_score

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
    
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

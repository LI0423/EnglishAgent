import json
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage
from agent_core.agents.base_agent import BaseAgent

class SpeakingAgent(BaseAgent):
    """口语智能体"""
    agent_key = "speaking"
    
    def __init__(self, temperature: float = 0.7, enable_thinking: bool = True, use_streamer: bool = True):
        super().__init__(temperature, enable_thinking, use_streamer)
        
    def can_handle(self, query):
        return any(k in query for k in ("口语", "speaking", "回答", "回答评估"))
    
    def evaluate_speaking(self, transcript: str, audio_url: Optional[str] = None) -> Dict[str, Any]:
        """评估口语表现"""
        # 使用RAG系统获取相关的口语评估标准和建议
        from rag_core.rag_system import RAGSystem
        rag_system = RAGSystem()
        rag_result = rag_system.query(transcript, top_k=5, module="speaking")
        
        prompt = f"""请作为专业的雅思口语考官，从以下四个维度评估学生的口语表现：
        1. 流利度与连贯性(Fluency & Coherence, FC)
        2. 词汇资源(Lexical Resource, LR)
        3. 语法范围与准确性(Grammatical Range & Accuracy, GR)
        4. 发音(Pronunciation, PR)

        学生的回答：{transcript}

        相关口语评估资料：
        {rag_result}

        请提供：
        - 每个维度的分数(1-9分)
        - 总体分数(1-9分)
        - 每个维度的详细评价
        - 具体的改进建议

        请使用JSON格式输出，包含以下字段：
        scores: {{"FC": float, "LR": float, "GR": float, "PR": float}}
        overall: float
        rationales: [str]
        actionItems: [{{"type": str, "before": str, "after": str, "examples": [str]}}]
        highlights: [{{"start": float, "end": float, "note": str}}]
        """
        
        try:
            _, response = self.qwen_llm.communicate(prompt)
        except Exception:
            return {"error": "口语评估失败，请稍后重试"}

        return self._parse_json_response(response, default={
            "scores": {"FC": 0.0, "LR": 0.0, "GR": 0.0, "PR": 0.0},
            "overall": 0.0,
            "rationales": [],
            "actionItems": [],
            "highlights": []
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
        """统一接口：评估口语回答"""
        if not self.can_handle(query):
            return self.fallback()

        self.before_run(query, history)

        # 假设 query 格式："口语评估：学生回答文本"
        transcript = query.replace("口语评估：", "").strip()
        result = self.evaluate_speaking(transcript)

        return self.after_run(self.format_evaluation_result(result))

    # ---------------- 格式化输出 ----------------
    def format_evaluation_result(self, result: Dict[str, Any]) -> str:
        if "error" in result:
            return result["error"]

        lines = [
            f"【口语评估结果】",
            f"流利度与连贯性(FC): {result['scores'].get('FC', 0)}",
            f"词汇资源(LR): {result['scores'].get('LR', 0)}",
            f"语法范围与准确性(GR): {result['scores'].get('GR', 0)}",
            f"发音(PR): {result['scores'].get('PR', 0)}",
            f"总体分数: {result.get('overall', 0)}",
            "\n详细评价:"
        ]
        for r in result.get("rationales", []):
            lines.append(f"- {r}")

        lines.append("\n改进建议:")
        for item in result.get("actionItems", []):
            lines.append(f"- {item['type']}: {item['before']} → {item['after']}")
            for ex in item.get("examples", []):
                lines.append(f"  示例: {ex}")

        lines.append("\n亮点/highlights:")
        for h in result.get("highlights", []):
            lines.append(f"- 时间 {h['start']}s ~ {h['end']}s: {h['note']}")

        return "\n".join(lines)
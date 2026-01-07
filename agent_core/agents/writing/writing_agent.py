from typing import List
from langchain_core.messages import BaseMessage
from agent_core.agents.base_agent import BaseAgent
from agent_core.agents.writing.writing_annotator import WritingAnnotator
from agent_core.agents.writing.writing_evaluator import WritingEvaluator
from agent_core.agents.writing.writing_generator import WritingGenerator

class WritingAgent(BaseAgent):
    """写作智能体"""

    agent_key: str = "writing"
    
    def __init__(self, temperature: float = 0.7, enable_thinking: bool = True, use_streamer: bool = True):
        super().__init__(temperature, enable_thinking, use_streamer)
        self.evaluator = WritingEvaluator(self.qwen_llm)
        self.generator = WritingGenerator(self.qwen_llm)
        self.annotator = WritingAnnotator(self.qwen_llm)

    def can_handle(self, query: str) -> bool:
        return any(k in query for k in ("写作", "作文", "雅思"))

    
    def generate_response(self, query: str, history: List[BaseMessage]) -> str:
        if "范文" in query or "例文" in query:
            return self.handle_generation_with_annotation(query)

        return self.handle_evaluation(query)
    
    def handle_generation_with_annotation(self, query: str) -> str:
        topic = self.extract_topic(query)

        essay = self.generator.generate(
            topic=topic,
            task_type="task2",
            target_band=7.0,
        )

        annotation = self.annotator.annotate(
            essay=essay,
            target_band=7.0,
        )

        return self.format_annotated_essay(essay, annotation)
    
    def handle_evaluation(self, essay: str) -> str:
        result = self.evaluator.evaluate(essay, "task2")
        return self.format_feedback(result)

    def extract_topic(self, query: str) -> str:
        return (
            query.replace("写一篇", "")
            .replace("范文", "")
            .replace("例文", "")
            .strip()
        )
    
    def format_feedback(self, result: dict) -> str:
        lines = [
            f"Overall Band: {result['overall']}",
            "",
            "评分明细：",
        ]
        for k, v in result["scores"].items():
            lines.append(f"- {k}: {v}")

        lines.append("\n改进建议：")
        for item in result["actionItems"][:3]:
            lines.append(f"- {item['type']}: {item['after']}")

        return "\n".join(lines)

    def format_annotated_essay(self, essay: str, annotation: dict) -> str:
        lines = [
            f"【Band {annotation['band']} 范文】",
            "",
            essay,
            "",
            "【Examiner 评分依据解析】",
        ]

        for crit, items in annotation["criteria"].items():
            lines.append(f"\n{crit}：")
            for item in items:
                lines.append(f"- 标准：{item['descriptor']}")
                lines.append(f"  例句：{item['quote']}")
                lines.append(f"  说明：{item['reason']}")

        return "\n".join(lines)

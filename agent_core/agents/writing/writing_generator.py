from typing import Optional


class WritingGenerator:
    """雅思范文生成器"""

    def __init__(self, llm):
        self.llm = llm

    def build_prompt(
        self,
        topic: str,
        task_type: str,
        target_band: float,
        word_limit: Optional[int],
    ) -> str:
        band_desc = {
            6.0: "论点清楚但展开有限，存在明显语言错误",
            6.5: "论点清楚，有一定展开，偶有不自然表达",
            7.0: "论证充分，衔接自然，词汇和语法控制良好",
            8.0: "论证成熟，语言自然准确，几乎无错误",
        }[target_band]

        structure = (
            "四段式：引言 + 两个主体段 + 结论"
            if task_type == "task2"
            else "概述段 + 特征段"
        )

        return (
            "你正在参加 IELTS Writing 考试。\n"
            f"写作任务类型：{task_type}\n"
            f"目标分数：Band {target_band}\n"
            f"评分标准特征：{band_desc}\n"
            f"文章结构要求：{structure}\n"
            f"字数要求：{word_limit}\n\n"
            "【重要】\n"
            "1. 不解释写作思路\n"
            "2. 不使用模板化表达\n"
            "3. 语言自然，符合该 Band 的真实考生水平\n"
            "4. 只输出完整作文正文\n\n"
            f"写作题目：\n{topic}\n"
        )

    def generate(
        self,
        topic: str,
        task_type: str = "task2",
        target_band: float = 7.0,
    ) -> str:
        prompt = self.build_prompt(
            topic,
            task_type,
            target_band,
            250 if task_type == "task2" else 150,
        )
        _, essay = self.llm.invoke(prompt)
        return essay.strip()

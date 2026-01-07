import json
from pathlib import Path
from typing import Dict, Any
from utils.llm_utils import extract_json


class WritingAnnotator:
    """反向 Examiner：解释范文为什么能达到该 Band"""

    def __init__(self, llm, task_type: str = "task2"):
        self.llm = llm
        self.task_type = task_type
        self.descriptors = self._load_descriptors()

    def _load_descriptors(self) -> Dict[str, Any]:
        path = Path(__file__).parent / "band_descriptors" / f"{self.task_type}.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_prompt(
        self,
        essay: str,
        target_band: float,
    ) -> str:
        descriptor_block = self.descriptors[str(target_band)]

        return (
            "你是一名 IELTS Writing Examiner。\n"
            "下面是官方 Band Descriptor（已固定，不可修改）。\n"
            "你的任务不是解释标准，而是：\n"
            "【从文章中找出证据，证明它满足这些标准】。\n\n"
            "Band Descriptor：\n"
            f"{json.dumps(descriptor_block, ensure_ascii=False, indent=2)}\n\n"
            "【任务要求】\n"
            "1. 对 TR / CC / LR / GRA 四项分别处理\n"
            "2. 对每一条 descriptor：\n"
            "   - 从文章中找 1 个具体句子作为 evidence\n"
            "   - 解释该句如何满足该 descriptor\n"
            "3. 如果某条 descriptor 没有明确证据，也必须说明原因\n"
            "4. 严格返回 JSON，不要任何额外文本\n\n"
            "输出格式：\n"
            "{\n"
            '  "band": float,\n'
            '  "criteria": {\n'
            '    "TR": [{"descriptor": str, "quote": str, "reason": str}],\n'
            '    "CC": [{"descriptor": str, "quote": str, "reason": str}],\n'
            '    "LR": [{"descriptor": str, "quote": str, "reason": str}],\n'
            '    "GRA": [{"descriptor": str, "quote": str, "reason": str}]\n'
            "  }\n"
            "}\n\n"
            "作文如下：\n"
            f"{essay}\n"
        )


    def annotate(
        self,
        essay: str,
        target_band: float,
    ) -> Dict[str, Any]:
        prompt = self.build_prompt(essay, target_band)
        _, raw = self.llm.invoke(prompt)

        parsed = extract_json(raw)
        if not parsed:
            raise ValueError("Descriptor-aligned annotation failed")

        return parsed


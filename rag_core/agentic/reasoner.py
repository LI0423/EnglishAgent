from typing import Any, Dict, List


class Reasoner:
    def __init__(self, generator):
        self._generator = generator

    def reason(self, question: str, docs: List[Dict[str, Any]], module: str = "general") -> str:
        return self._generator.generate(question, docs, module)

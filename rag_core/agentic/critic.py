from typing import Any, Dict, List, Tuple


class Critic:
    """基于检索质量做轻量打分，决定是否继续迭代。"""

    def evaluate(
        self,
        answer: str,
        docs: List[Dict[str, Any]],
        min_doc_count: int,
        min_doc_score: float,
        citation_coverage: float,
        min_citation_coverage: float,
    ) -> Tuple[bool, float, str]:
        if not docs:
            return False, 0.0, "没有检索到可用文档，请扩展查询范围。"

        top_score = float(docs[0].get("score", 0.0))
        enough_docs = len(docs) >= min_doc_count
        quality_ok = top_score >= min_doc_score
        answer_ok = bool(answer and answer.strip())
        citation_ok = citation_coverage >= min_citation_coverage

        score = 0.0
        if enough_docs:
            score += 0.3
        if quality_ok:
            score += 0.3
        if answer_ok:
            score += 0.1
        if citation_ok:
            score += 0.3

        if not enough_docs:
            return False, score, "召回数量不足，请扩展关键词或放宽匹配。"
        if not quality_ok:
            return False, score, "高置信证据不足，请强调核心概念并重检索。"
        if not answer_ok:
            return False, score, "生成结果为空，请重试推理。"
        if not citation_ok:
            return False, score, "答案证据覆盖不足，请补充可引用支撑。"
        return True, score, "通过。"

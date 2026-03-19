import re
from typing import Any, Dict, List, Tuple


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{1,}|[A-Za-z]{2,}", (text or "").lower())
    return {t for t in tokens if t.strip()}


def _extract_claims(answer: str) -> List[str]:
    if not answer:
        return []
    segments = re.split(r"[。！？!?;\n]+", answer)
    claims = [s.strip() for s in segments if len(s.strip()) >= 8]
    return claims[:8]


class CitationChecker:
    """对答案 claim 做证据覆盖检查，输出可引用文档位置信息。"""

    def evaluate(
        self,
        answer: str,
        docs: List[Dict[str, Any]],
        overlap_threshold: float = 0.12,
    ) -> Tuple[List[Dict[str, Any]], float]:
        claims = _extract_claims(answer)
        if not claims or not docs:
            return [], 0.0

        citations: List[Dict[str, Any]] = []
        supported = 0
        doc_tokens = [_tokenize(d.get("content", "")) for d in docs]

        for claim in claims:
            claim_tokens = _tokenize(claim)
            if not claim_tokens:
                citations.append(
                    {"claim": claim, "doc_index": -1, "overlap": 0.0, "supported": False}
                )
                continue

            best_idx = -1
            best_overlap = 0.0
            for idx, dt in enumerate(doc_tokens):
                if not dt:
                    continue
                overlap = len(claim_tokens & dt) / max(1, len(claim_tokens))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_idx = idx

            is_supported = best_overlap >= overlap_threshold
            if is_supported:
                supported += 1
            citations.append(
                {
                    "claim": claim,
                    "doc_index": best_idx,
                    "overlap": round(best_overlap, 4),
                    "supported": is_supported,
                }
            )

        coverage = supported / len(claims) if claims else 0.0
        return citations, round(coverage, 4)

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from agent_core.search import tavily_search
from rag_core.rag_system import RAGSystem

from .base_agent import BaseAgent


class DeepSearchAgent(BaseAgent):
    """深度搜索智能体：多源检索 + 迭代优化 + 证据可追溯总结。"""

    agent_key = "deep_search"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.max_iterations = int(self.config.get("max_iterations", 3))
        self.max_results = int(self.config.get("max_results", 5))
        self.max_citations = int(self.config.get("max_citations", 8))

    def can_handle(self, query: str) -> bool:
        keywords = ["深度搜索", "详细信息", "全面了解", "深入分析", "deep search", "detailed information"]
        q = (query or "").lower()
        return any(keyword in q for keyword in keywords)

    def deep_search(self, query: str) -> Dict[str, Any]:
        results = {
            "original_query": query,
            "iterations": [],
            "final_summary": "",
            "sources": [],
            "citations": [],
        }

        current_query = query
        for i in range(self.max_iterations):
            iteration_result = self._perform_iteration(current_query, i + 1)
            results["iterations"].append(iteration_result)
            if "sources" in iteration_result:
                results["sources"].extend(iteration_result["sources"])
            if i < self.max_iterations - 1:
                current_query = self._generate_next_query(query, iteration_result)

        results["final_summary"] = self._generate_final_summary(results)
        return results

    def _perform_iteration(self, query: str, iteration: int) -> Dict[str, Any]:
        rag_results: List[Dict[str, Any]] = []
        online_results: List[Dict[str, Any]] = []

        try:
            rag_raw = RAGSystem().query(query, top_k=5, module="deep_search")
            rag_results = self._normalize_rag_results(rag_raw)
        except Exception:
            rag_results = []

        try:
            online_raw = tavily_search(query, max_results=self.max_results)
            online_results = self._normalize_online_results(online_raw)
        except Exception:
            online_results = []

        sources = []
        if rag_results:
            sources.append({"type": "rag", "results": rag_results})
        if online_results:
            sources.append({"type": "online", "results": online_results})

        merged_docs = self._merge_sources(rag_results, online_results)
        return {
            "iteration": iteration,
            "query": query,
            "sources": sources,
            "docs": merged_docs,
        }

    def _generate_next_query(self, original_query: str, iteration_result: Dict[str, Any]) -> str:
        keywords = self._extract_keywords(iteration_result)
        if not keywords:
            return original_query

        if hasattr(self, "qwen_llm") and self.qwen_llm is not None:
            prompt = (
                "你是研究助理。请基于原始问题与已发现线索，给出一个更具体的下一轮检索查询。\n"
                "要求：\n"
                "1) 只输出1条检索语句\n"
                "2) 20字以内，中文\n"
                "3) 聚焦尚未明确的关键信息\n\n"
                f"原始问题：{original_query}\n"
                f"已发现关键词：{', '.join(keywords[:6])}\n"
            )
            try:
                _, next_query = self.qwen_llm.communicate(prompt, temperature=0.2, max_tokens=80)
                cleaned = (next_query or "").strip().splitlines()[0].strip()
                if cleaned:
                    return cleaned
            except Exception:
                pass

        return f"{original_query} {' '.join(keywords[:3])} 证据"

    def _extract_keywords(self, iteration_result: Dict[str, Any]) -> List[str]:
        text_parts: List[str] = [str(iteration_result.get("query", ""))]
        for doc in iteration_result.get("docs", [])[:8]:
            text_parts.append(str(doc.get("title", "")))
            text_parts.append(str(doc.get("snippet", "")))
        corpus = " ".join(text_parts).lower()
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z\-]{2,}", corpus)
        stop = {"信息", "问题", "详细", "分析", "about", "with", "that", "this"}
        dedup: List[str] = []
        for t in tokens:
            if t in stop:
                continue
            if t not in dedup:
                dedup.append(t)
            if len(dedup) >= 8:
                break
        return dedup

    def _generate_final_summary(self, results: Dict[str, Any]) -> str:
        citations, evidence_text = self._build_citations(results)
        results["citations"] = citations
        prompt = (
            "你是深度研究助手。请基于证据生成结构化结论。\n"
            "输出要求：\n"
            "1) 结构：结论、关键要点、不确定项、下一步建议\n"
            "2) 每条关键要点后标注证据编号，如 [1][3]\n"
            "3) 不要编造未在证据中出现的信息\n\n"
            f"原始问题：{results['original_query']}\n\n"
            f"证据清单：\n{evidence_text}\n"
        )
        try:
            _, summary = self.qwen_llm.communicate(prompt, temperature=0.2, max_tokens=900)
            if summary and summary.strip():
                return summary.strip()
        except Exception:
            pass

        fallback_lines = ["结论：基于当前检索，已汇总主要信息。", "关键要点："]
        for c in citations[:4]:
            fallback_lines.append(f"- {c['title']} [{c['id']}]")
        fallback_lines.append("不确定项：部分结论仍需更多权威来源交叉验证。")
        fallback_lines.append("下一步建议：补充最新年份报告与官方统计。")
        return "\n".join(fallback_lines)

    def generate_response(self, query: str, history: List[Any]) -> str:
        if not self.can_handle(query):
            return self.fallback()
        self.before_run(query, history)
        results = self.deep_search(query)
        response = self._format_response(results)
        return self.after_run(response)

    def _format_response(self, results: Dict[str, Any]) -> str:
        lines = [
            "【深度搜索结果】",
            f"原始查询: {results['original_query']}",
            f"搜索迭代次数: {len(results['iterations'])}",
            "",
            "【最终摘要】",
            results["final_summary"],
            "",
            "【参考来源】",
        ]

        for c in results.get("citations", [])[: self.max_citations]:
            lines.append(f"[{c['id']}] {c['title']} - {c['url']}")

        lines.append("")
        lines.append("【搜索过程】")
        for iteration in results["iterations"]:
            lines.append(f"迭代 {iteration['iteration']}: {iteration['query']}")
            for source in iteration.get("sources", []):
                lines.append(f"  来源: {source['type']}")
        return "\n".join(lines)

    @staticmethod
    def _is_academic_url(url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        academic_signals = [
            ".edu",
            ".ac.",
            ".gov",
            "scholar.google",
            "arxiv.org",
            "nature.com",
            "science.org",
            "ieee.org",
            "springer.com",
            "sciencedirect.com",
            "pubmed",
            "who.int",
            "oecd.org",
            "un.org",
        ]
        return any(x in host for x in academic_signals)

    def _normalize_online_results(self, rows: Any) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        if not isinstance(rows, list):
            return docs
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip() or "在线来源"
            url = str(item.get("url", "")).strip()
            snippet = str(item.get("content", "")).strip()
            score = float(item.get("score") or 0.0)
            is_academic = self._is_academic_url(url)
            trust_bonus = 0.15 if is_academic else 0.0
            docs.append(
                {
                    "source": "online",
                    "title": title,
                    "url": url,
                    "snippet": snippet[:500],
                    "score": score + trust_bonus,
                    "is_academic": is_academic,
                }
            )
        return docs

    def _normalize_rag_results(self, rag_result: Any) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        if isinstance(rag_result, dict):
            answer = str(rag_result.get("answer", "")).strip()
            citations = rag_result.get("citations") or []
            traces = rag_result.get("traces") or []
            if answer:
                docs.append(
                    {
                        "source": "rag",
                        "title": "RAG综合回答",
                        "url": "local://rag_answer",
                        "snippet": answer[:500],
                        "score": 0.8,
                        "is_academic": False,
                    }
                )
            if isinstance(citations, list):
                for c in citations:
                    if not isinstance(c, dict):
                        continue
                    url = str(c.get("url", "")).strip() or "local://rag_citation"
                    docs.append(
                        {
                            "source": "rag",
                            "title": str(c.get("title", "")).strip() or "RAG引用",
                            "url": url,
                            "snippet": str(c.get("snippet", "")).strip()[:500],
                            "score": float(c.get("score") or 0.7),
                            "is_academic": self._is_academic_url(url),
                        }
                    )
            if isinstance(traces, list):
                for t in traces[:3]:
                    if not isinstance(t, dict):
                        continue
                    fb = str(t.get("critic_feedback", "")).strip()
                    if fb:
                        docs.append(
                            {
                                "source": "rag",
                                "title": "RAG评审反馈",
                                "url": "local://rag_trace",
                                "snippet": fb[:500],
                                "score": float(t.get("critic_score") or 0.6),
                                "is_academic": False,
                            }
                        )
        elif isinstance(rag_result, str) and rag_result.strip():
            docs.append(
                {
                    "source": "rag",
                    "title": "RAG文本结果",
                    "url": "local://rag_text",
                    "snippet": rag_result.strip()[:500],
                    "score": 0.7,
                    "is_academic": False,
                }
            )
        return docs

    def _merge_sources(
        self,
        rag_docs: List[Dict[str, Any]],
        online_docs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged = list(rag_docs) + list(online_docs)
        dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for d in merged:
            key = (str(d.get("title", "")).strip(), str(d.get("url", "")).strip())
            if key not in dedup:
                dedup[key] = d
            else:
                if float(d.get("score", 0.0)) > float(dedup[key].get("score", 0.0)):
                    dedup[key] = d
        items = list(dedup.values())
        items.sort(
            key=lambda x: (
                1 if x.get("is_academic") else 0,
                float(x.get("score", 0.0)),
            ),
            reverse=True,
        )
        return items[: max(self.max_results * 2, 10)]

    def _build_citations(self, results: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        docs: List[Dict[str, Any]] = []
        for it in results.get("iterations", []):
            docs.extend(it.get("docs", []))

        seen = set()
        citations: List[Dict[str, Any]] = []
        for d in docs:
            key = (str(d.get("title", "")).strip(), str(d.get("url", "")).strip())
            if key in seen:
                continue
            seen.add(key)
            citations.append(d)
            if len(citations) >= self.max_citations:
                break

        for idx, c in enumerate(citations, start=1):
            c["id"] = idx

        lines: List[str] = []
        for c in citations:
            lines.append(
                f"[{c['id']}] 标题: {c.get('title', '')}\n"
                f"URL: {c.get('url', '')}\n"
                f"摘要: {c.get('snippet', '')}\n"
            )
        return citations, "\n".join(lines)

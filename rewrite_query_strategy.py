"""
Enhanced RewriteQueryStrategy

This module implements an enhanced query rewrite strategy suitable for both Chinese and English.
Features:
- Language-aware tokenization (uses jieba for Chinese and nltk where available, falls back to regex)
- Configurable stop-words and strategy parameters
- Better key-term extraction and normalization (simple lemmatization if nltk available)
- Strategy selection with more heuristics
- Returns enriched rewrites: each rewrite includes a score and short note
- Deduplication and limit on returned rewrites
- Optional synonym expansion using WordNet (if available)

Usage: see class docstring and `if __name__ == '__main__'` example at the bottom.
"""

from __future__ import annotations
import re
import logging
from typing import List, Dict, Optional, Any, Tuple

# Optional imports (soft)
try:
    import jieba
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False

try:
    import nltk
    from nltk.corpus import wordnet
    from nltk.stem import WordNetLemmatizer
    _HAS_NLTK = True
except Exception:
    _HAS_NLTK = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EnhancedRewriteQueryStrategy:
    """Enhanced query rewrite strategy class.

    Parameters
    ----------
    language: str
        "zh" for Chinese, "en" for English, or "auto" to detect from content
    use_jieba: bool
        Whether to use jieba for Chinese tokenization if available
    custom_stopwords: Optional[set]
        Additional stopwords to ignore when extracting key terms
    max_rewrites: int
        Maximum number of rewritten queries to return per strategy
    """

    def __init__(
        self,
        language: str = "auto",
        use_jieba: bool = True,
        custom_stopwords: Optional[set] = None,
        max_rewrites: int = 10,
        prefer_short: bool = False,
    ) -> None:
        self.language = language
        self.use_jieba = use_jieba and _HAS_JIEBA
        self.max_rewrites = max_rewrites
        self.prefer_short = prefer_short

        # Basic stop words for Chinese and English
        self.default_stopwords_zh = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
            "什么", "哪些", "怎么", "如何", "为什么", "吗", "呢", "吧", "啊",
        }
        self.default_stopwords_en = {
            "the", "is", "are", "a", "an", "in", "on", "of", "for", "to", "how",
            "what", "which", "why", "do", "does", "did",
        }

        self.custom_stopwords = custom_stopwords or set()

        if _HAS_NLTK:
            try:
                # ensure required corpora are present in user environment
                nltk.data.find('tokenizers/punkt')
            except Exception:
                # caller environment may need to download; we won't attempt to auto-download here
                logger.debug("nltk punkt tokenizer not found")

            self._lemmatizer = WordNetLemmatizer()
        else:
            self._lemmatizer = None

    # -------------------- Public API --------------------
    def requery(self, original_query: str, retrieval_context: Optional[Dict[str, Any]] = None, rewrite_strategy: str = "auto") -> Dict[str, Any]:
        """Main entry point: analyze and produce rewrites.

        Returns a dict with fields:
          - original_query
          - analysis
          - strategy_used
          - rewrites: a list of dicts {query, strategy, score, note}
          - model_prompts: dict containing prompts ready to send to a model
        """
        original_query = (original_query or "").strip()
        if not original_query:
            return {
                "original_query": original_query,
                "analysis": {},
                "strategy_used": None,
                "rewrites": [],
                "model_prompts": {"individual": [], "merged": ""}
            }

        analysis = self._analyze_query(original_query, retrieval_context)

        if rewrite_strategy == "auto":
            rewrite_strategy = self._select_rewrite_strategy(analysis)

        candidates = self._rewrite_query(original_query, analysis, rewrite_strategy)

        # Score and deduplicate
        scored = self._score_and_dedup(candidates, analysis)

        # trim
        scored = scored[: self.max_rewrites]

        # generate model-ready prompts (both individual and merged)
        model_prompts = self._generate_model_prompts(original_query, analysis, scored)

        return {
            "original_query": original_query,
            "analysis": analysis,
            "strategy_used": rewrite_strategy,
            "rewrites": scored,
            "model_prompts": model_prompts,
        }

        analysis = self._analyze_query(original_query, retrieval_context)

        if rewrite_strategy == "auto":
            rewrite_strategy = self._select_rewrite_strategy(analysis)

        candidates = self._rewrite_query(original_query, analysis, rewrite_strategy)

        # Score and deduplicate
        scored = self._score_and_dedup(candidates, analysis)

        # trim
        scored = scored[: self.max_rewrites]

        return {
            "original_query": original_query,
            "analysis": analysis,
            "strategy_used": rewrite_strategy,
            "rewrites": scored,
        }

    # -------------------- Analysis Helpers --------------------
    def _analyze_query(self, query: str, retrieval_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a structured analysis of the query."""
        lang = self._detect_language(query) if self.language == "auto" else self.language
        tokens = self._tokenize(query, lang)
        key_terms = self._extract_key_terms_from_tokens(tokens, lang)
        issues = self._identify_potential_issues(query, tokens)
        qtype = self._classify_query_type(query, lang)
        complexity = self._assess_query_complexity(query)

        return {
            "language": lang,
            "length": len(query),
            "word_count": len(tokens),
            "tokens": tokens,
            "key_terms": key_terms,
            "query_type": qtype,
            "complexity": complexity,
            "potential_issues": issues,
            "retrieval_context": retrieval_context,
        }

    def _detect_language(self, query: str) -> str:
        # naive: presence of CJK characters => zh
        if re.search(r"[\u4e00-\u9fff]", query):
            return "zh"
        return "en"

    def _tokenize(self, query: str, lang: str) -> List[str]:
        if lang == "zh" and self.use_jieba:
            try:
                return [t for t in jieba.lcut(query) if t.strip()]
            except Exception:
                pass

        if lang == "en" and _HAS_NLTK:
            try:
                return nltk.word_tokenize(query)
            except Exception:
                pass

        # fallback simple tokenization
        return re.findall(r"[\w']+", query)

    def _extract_key_terms_from_tokens(self, tokens: List[str], lang: str) -> List[str]:
        stopwords = (self.default_stopwords_zh if lang == "zh" else self.default_stopwords_en) | self.custom_stopwords
        terms = [t for t in tokens if t.lower() not in stopwords and len(t) > 1]

        # simple normalization for english
        if lang == "en" and _HAS_NLTK and self._lemmatizer:
            normalized = []
            for t in terms:
                try:
                    nt = self._lemmatizer.lemmatize(t.lower())
                    normalized.append(nt)
                except Exception:
                    normalized.append(t.lower())
            terms = normalized

        # keep order but unique
        seen = set()
        ordered = []
        for t in terms:
            if t not in seen:
                ordered.append(t)
                seen.add(t)
        return ordered

    def _assess_query_complexity(self, query: str) -> str:
        word_count = len(query.split())
        if word_count <= 4:
            return "low"
        elif word_count <= 8:
            return "medium"
        else:
            return "high"

    def _identify_potential_issues(self, query: str, tokens: List[str]) -> List[str]:
        issues = []
        # vague: short and contains interrogatives
        vague_terms = {"怎么样", "如何", "什么", "哪些", "how", "what", "which", "why"}
        if any(t.lower() in vague_terms for t in tokens) and len(tokens) <= 4:
            issues.append("vague")

        # ambiguous: many '的' or repeated conjunctions in chinese
        if query.count("的") > 2 or query.count("and") > 2 or query.count("和") > 1:
            issues.append("ambiguous")

        if len(tokens) > 12:
            issues.append("complex")

        professional_terms = {"语法", "时态", "句型", "词性", "syntax", "tense"}
        if any(t in professional_terms for t in tokens):
            issues.append("professional")

        return issues

    # -------------------- Strategy Selection --------------------
    def _select_rewrite_strategy(self, analysis: Dict[str, Any]) -> str:
        issues = analysis.get("potential_issues", [])
        qtype = analysis.get("query_type")
        complexity = analysis.get("complexity")

        if "ambiguous" in issues:
            return "clarify"
        if "vague" in issues:
            return "multi_perspective"
        if complexity == "high" and qtype in {"comparison", "explanation", "general"}:
            return "simplify"
        if complexity == "low" and qtype in {"definition", "fact"}:
            return "expand"
        return "paraphrase"

    # -------------------- Rewrite Implementations --------------------
    def _rewrite_query(self, original_query: str, analysis: Dict[str, Any], strategy: str) -> List[Dict[str, Any]]:
        method = getattr(self, f"_{strategy}_query", None)
        if not method:
            method = self._paraphrase_query
        return method(original_query, analysis)

    def _expand_query(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        key_terms = analysis.get("key_terms", [])
        qtype = analysis.get("query_type")
        expansions = []

        base = key_terms[0] if key_terms else query
        expansions.append({"query": f"{base} 的定义和详细解释", "note": "add definition and context", "strategy": "expand"})
        expansions.append({"query": f"{base} 的应用场景和示例", "note": "show usage examples", "strategy": "expand"})

        # English-friendly
        if analysis.get("language") == "en":
            expansions.append({"query": f"Definition and detailed explanation of {base}", "note": "english expansion", "strategy": "expand"})
            expansions.append({"query": f"Practical examples and use-cases for {base}", "note": "english examples", "strategy": "expand"})

        # synonym expansion via wordnet
        if analysis.get("language") == "en" and _HAS_NLTK:
            syns = self._get_synonyms_wordnet(base)
            if syns:
                expansions.append({"query": f"{base} and related terms: {', '.join(syns[:5])}", "note": "synonym expansion", "strategy": "expand"})

        return expansions

    def _simplify_query(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        key_terms = analysis.get("key_terms", [])
        simplifications = []

        if len(key_terms) >= 2:
            core = f"{key_terms[0]} 和 {key_terms[1]} 的区别"
            simplifications.append({"query": core, "note": "extract comparison core", "strategy": "simplify"})

        if "是什么" in query or "什么是" in query or analysis.get("language") == "en" and "what" in query.lower():
            base = key_terms[0] if key_terms else query
            simplifications.append({"query": f"{base} 的定义", "note": "definition simplification", "strategy": "simplify"})

        simplifications.append({"query": self._create_simple_version(query, key_terms, analysis.get("language")), "note": "general simplification", "strategy": "simplify"})

        return simplifications

    def _paraphrase_query(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        key_terms = analysis.get("key_terms", [])
        main = key_terms[0] if key_terms else query
        patterns = [
            "请解释{}",
            "什么是{}",
            "能不能介绍一下{}",
            "{}是什么意思",
            "如何理解{}",
            "请说明{}",
            "{}的定义是什么",
        ]
        paraphrases = []
        for p in patterns:
            text = p.format(main)
            paraphrases.append({"query": text, "note": "pattern paraphrase", "strategy": "paraphrase"})

        # english forms
        if analysis.get("language") == "en":
            en_patterns = [
                f"Explain {main}",
                f"What is {main}?",
                f"How to understand {main}?",
                f"Definition of {main}",
            ]
            for t in en_patterns:
                paraphrases.append({"query": t, "note": "en paraphrase", "strategy": "paraphrase"})

        # add usage paraphrases
        if any(w in query for w in ["用法", "怎么用", "how to", "use"]):
            paraphrases.append({"query": f"{main} 的使用方法和注意事项", "note": "usage paraphrase", "strategy": "paraphrase"})

        return paraphrases

    def _clarify_query(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        key_terms = analysis.get("key_terms", [])
        clarifications = []

        if len(key_terms) >= 2:
            clarifications.append({"query": f"{query} — 请具体说明您是关心{key_terms[0]}还是{key_terms[1]}?", "note": "ask which term", "strategy": "clarify"})
            clarifications.append({"query": f"关于{key_terms[0]}和{key_terms[1]}的关系，您想要比较还是了解各自定义?", "note": "clarify intent", "strategy": "clarify"})

        clarifications.append({"query": f"{query} 的具体含义和应用是什么?", "note": "generic clarification", "strategy": "clarify"})

        return clarifications

    def _multi_perspective_query(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        key_terms = analysis.get("key_terms", [])
        main = key_terms[0] if key_terms else "相关内容"
        perspectives = [
            {"query": f"{main} 的基本定义和概念", "note": "definition", "strategy": "multi_perspective"},
            {"query": f"{main} 的主要特点和特征", "note": "features", "strategy": "multi_perspective"},
            {"query": f"{main} 的常见用法和例子", "note": "usage_examples", "strategy": "multi_perspective"},
            {"query": f"{main} 的相关术语和概念", "note": "related_terms", "strategy": "multi_perspective"},
            {"query": f"{main} 的学习要点和注意事项", "note": "learning_tips", "strategy": "multi_perspective"},
        ]
        return perspectives

    # -------------------- Utilities --------------------
    def _create_simple_version(self, query: str, key_terms: List[str], lang: str) -> str:
        primary = key_terms[0] if key_terms else query
        qtype = self._classify_query_type(query, lang)
        if qtype == "definition":
            return f"{primary} 定义"
        if qtype == "synonym":
            return f"{primary} 近义词"
        if qtype == "example":
            return f"{primary} 例子"
        if qtype == "usage":
            return f"{primary} 用法"
        if qtype == "comparison" and len(key_terms) > 1:
            return f"{key_terms[0]} 对比 {key_terms[1]}"
        return primary

    def _score_and_dedup(self, candidates: List[Dict[str, Any]], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        seen = set()
        scored = []
        for c in candidates:
            q = c.get("query", "").strip()
            norm = re.sub(r"\s+", " ", q)
            if norm in seen:
                continue
            seen.add(norm)
            score = self._simple_score(q, analysis)
            entry = {**c, "score": score}
            scored.append(entry)

        # sort by score desc, then prefer shorter if configured
        scored.sort(key=lambda x: (-x["score"], len(x["query"]) if self.prefer_short else 0))
        return scored

    def _simple_score(self, q: str, analysis: Dict[str, Any]) -> float:
        # heuristic scoring: include key terms, length, and strategy
        key_terms = analysis.get("key_terms", [])
        score = 0.0
        lower = q.lower()
        for kt in key_terms:
            if kt.lower() in lower:
                score += 1.0
        # penalize overly long
        if len(q.split()) > 20:
            score -= 0.5
        # small boost for clarification candidates
        if analysis.get("query_type") == "comparison" and "区别" in q:
            score += 0.2
        return round(score, 3)

    def _get_synonyms_wordnet(self, term: str) -> List[str]:
        if not _HAS_NLTK:
            return []
        syns = set()
        try:
            for syn in wordnet.synsets(term):
                for lemma in syn.lemmas():
                    syns.add(lemma.name().replace('_', ' '))
        except Exception:
            return []
        return list(syns)

    # -------------------- Classification (multilingual) --------------------
    def _classify_query_type(self, query: str, lang: str) -> str:
        q = query.lower()
        if lang == "zh":
            if any(word in q for word in ["是什么", "定义", "意思", "含义"]):
                return "definition"
            if any(word in q for word in ["近义词", "同义词", "相似词"]):
                return "synonym"
            if any(word in q for word in ["例子", "示例", "举例"]):
                return "example"
            if any(word in q for word in ["区别", "不同", "差异", "对比"]):
                return "comparison"
            if any(word in q for word in ["用法", "如何使用", "怎么用"]):
                return "usage"
            if any(word in q for word in ["解释", "说明", "讲解"]):
                return "explanation"
            return "general"
        else:
            if any(w in q for w in ["what is", "definition of", "meaning of"]):
                return "definition"
            if any(w in q for w in ["synonym", "similar to", "similar words"]):
                return "synonym"
            if any(w in q for w in ["example", "examples", "use case"]):
                return "example"
            if any(w in q for w in ["difference", "vs", "vs."]):
                return "comparison"
            if any(w in q for w in ["how to use", "usage", "use case"]):
                return "usage"
            if any(w in q for w in ["explain", "explain why", "explain how"]):
                return "explanation"
            return "general"


    def _generate_model_prompts(self, original_query: str, analysis: Dict[str, Any], rewrites: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create model-ready prompts from rewrites.

        Returns a dict with:
          - individual: list of {id, prompt, strategy, score}
          - merged: a single comprehensive prompt that covers common information needs
          - structured: list of minimal prompt dicts suitable for batch calls
        """
        lang = analysis.get("language", "en")
        individual = []
        for idx, r in enumerate(rewrites, start=1):
            qtext = r.get("query", "").strip()
            # if rewrite text looks like a fragment, try to make it a full question
            if lang == "zh":
                if qtext and not qtext.endswith("？") and not qtext.endswith("?"):
                    full = qtext
                    # attempt to detect if it already contains a question word
                    if not any(w in qtext for w in ["什么", "如何", "为什么", "怎么", "是否", "怎样"]):
                        full = qtext + "？"
                else:
                    full = qtext
                prompt = (
                    f"原始问题：\"{original_query}\"\n请根据下列改写问题回答：\n{full}\n要求：回答要清晰、结构化；若为比较类问题，请列出逐项比较要点并给出结论。"
                )
            else:
                if qtext and not qtext.endswith("?"):
                    full = qtext + "?"
                else:
                    full = qtext
                prompt = (
                    f"Original query: \"{original_query}\"\nPlease answer the rewritten question below:\n{full}\nRequirements: Be concise and structured; for comparisons, present bullet points or a table and a short conclusion."
                )

            individual.append({"id": idx, "prompt": prompt, "strategy": r.get("strategy"), "score": r.get("score")})

        # merged comprehensive prompt
        if lang == "zh":
            merged = (
                f"原始问题：\"{original_query}\"\n请综合回答以下要点：\n"
                "1) 用 1-2 句给出该术语的简明定义。\n"
                "2) 说明关键组件与工作原理（对每个关键概念用一句话解释，例如自注意力、多头注意力、前馈层、位置编码）。\n"
                "3) 与 RNN（如 LSTM/GRU）在以下方面逐项比较：架构差异、并行化能力、长程依赖处理、训练效率和稳定性、适用场景。可使用 Markdown 表格或要点形式。\n"
                "4) 列出各自主要优缺点与典型应用场景。\n"
                "5) 给出一个简短示例（如机器翻译的高层流程或伪代码）以说明实际差异。\n"
                "请以【定义/关键点/比较表/结论】四段格式回答，并在比较处使用表格或清晰的逐项对比。"
            )
        else:
            merged = (
                f"Original query: \"{original_query}\"\nPlease provide a comprehensive, structured answer covering:\n"
                "1) A 1-2 sentence concise definition.\n"
                "2) Key components and how they work (one sentence per concept: self-attention, multi-head attention, feed-forward, positional encoding).\n"
                "3) A point-by-point comparison with RNNs (e.g., LSTM/GRU) across architecture, parallelizability, long-range dependency handling, training efficiency and stability, and typical use cases. Use a markdown table or bullet points.\n"
                "4) Main pros and cons and typical application scenarios.\n"
                "5) A brief example (high-level workflow or pseudocode) illustrating the differences (e.g., machine translation).\n"
                "Return in sections: [Definition] / [Key Points] / [Comparison Table] / [Conclusions]."
            )

        structured = [{"id": item["id"], "prompt": item["prompt"]} for item in individual]

        return {"individual": individual, "merged": merged, "structured": structured, "usage_note": "Use 'merged' when you want one comprehensive model call; use 'individual' to parallelize or A/B prompts."}


if __name__ == "__main__":

    s = EnhancedRewriteQueryStrategy(language="auto", use_jieba=True, max_rewrites=8)
    q = "什么是 Transformer 模型, 它和 RNN 有什么区别?"
    result = s.requery(q)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))

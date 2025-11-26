# intent_recognizer.py
import re
from typing import List, Dict, Any, Iterable, Tuple
from enum import Enum

from rag_core.prompt import INTENT_EXAMPLES, INTENT_KEYWORDS


# -------------------------
# 简单的 IntentType 枚举（用于 pattern 映射）
# -------------------------
class IntentType(Enum):
    SYNONYM = "synonym"
    DEFINITION = "definition"
    EXAMPLE = "example"
    PRONUNCIATION = "pronunciation"
    USAGE_GUIDANCE = "usage_guidance"
    ETYMOLOGY = "etymology"
    WORD_FAMILY = "word_family"
    GENERAL = "general"

# -------------------------
# 基础相似度（简化 Jaccard）
# -------------------------
def _calculate_text_similarity(text1: str, text2: str) -> float:
    words1 = set(re.findall(r'\b\w+\b', (text1 or "").lower()))
    words2 = set(re.findall(r'\b\w+\b', (text2 or "").lower()))

    if not words1 or not words2:
        return 0.0

    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


# -------------------------
# 辅助：统一 candidate 类型处理
# -------------------------
def _ensure_str_candidates(candidate) -> List[str]:
    """确保 candidate 最终为字符串列表（从 str 或 List[str] 统一转换）"""
    if not candidate:
        return []
    if isinstance(candidate, str):
        c = candidate.strip()
        return [c] if c else []
    if isinstance(candidate, Iterable):
        res = []
        for c in candidate:
            if isinstance(c, str):
                s = c.strip()
                if s:
                    res.append(s)
        return res
    return []


# -------------------------
# 目标校验（更严格）
# -------------------------
def _is_valid_target(candidate: str, query: str) -> bool:
    """判断候选词是否是有效的目标词（candidate 必须为 str）"""
    if not candidate or not isinstance(candidate, str):
        return False

    candidate = candidate.strip()
    if len(candidate) == 0:
        return False

    # 过短或单字符非缩写视为无效
    if len(candidate) == 1 and not candidate.isupper():
        return False

    # 常见疑问词/功能词（作为整体或子串出现则认为不是目标）
    stop_words = {
        '什么', '哪些', '怎么', '如何', '为什么', '为何', '哪个', '哪', '什么是',
        'what', 'which', 'how', 'why', 'when', 'where', 'who',
        '有没有', '有什么', '是否', '可以', '能否'
    }
    low = candidate.lower()
    for sw in stop_words:
        if sw in low:
            return False

    # 如果候选词里包含空格且看起来像完整句子，认为不是实体
    if len(candidate.split()) > 3:
        return False

    # 如果候选在查询中出现且不是疑问结构，优先认为是有效
    if query and candidate in query and not any(sw in candidate for sw in ('什么', '有什么', '有没有', '?', '？')):
        return True

    # 中文或英文长度判定
    if re.search(r'[\u4e00-\u9fff]', candidate):
        return len(candidate) >= 2
    if re.search(r'[A-Za-z]', candidate):
        return len(re.sub(r'[^A-Za-z]', '', candidate)) >= 2

    return False


def filter_valid_target(words: List[str], query: str):
    return [w for w in words if _is_valid_target(w, query)]


# -------------------------
# 中文候选清洗
# -------------------------
def _clean_chinese_candidate(word: str) -> List[str]:
    """清洗中文候选，剥离常见疑问前缀，返回 list 以便统一处理"""
    if not word or not isinstance(word, str):
        return []
    w = word.strip()
    w = re.sub(r'^(?:有|有没有|什么|哪些|哪个|哪|是否|能否|可以|有什么|是什么|什么是)[，,。；;：:\s]*', '', w)
    w = re.sub(r'[？?。.！!，,；;\s]+$', '', w)
    w = w.strip()
    return [w] if w else []


# -------------------------
# 选择最佳中文目标（评分）
# -------------------------
def _select_best_chinese_target(chinese_words: List[str], query: str) -> List[str]:
    if not chinese_words:
        return []

    chinese_stop_words = {
        '什么', '哪些', '怎么', '如何', '为什么', '为何', '哪个', '哪', '什么是',
        '这个', '那个', '这些', '那些', '有没有', '是否', '可以', '能够', '有', '是什么'
    }

    # 清洗并过滤
    cleaned = []
    for word in chinese_words:
        cand_list = _clean_chinese_candidate(word)
        for w in cand_list:
            if not w:
                continue
            if any(sw == w for sw in chinese_stop_words):
                continue
            if re.search(r'^(?:什么|有没有|有什么|是否|能否|可以)', w):
                continue
            cleaned.append(w)

    if not cleaned:
        # 退化回原始（清洗后有效的）
        words = []
        for w in chinese_words:
            w2 = _clean_chinese_candidate(w)
            for s in w2:
                if s and s not in chinese_stop_words:
                    words.append(s)
        return words or chinese_words

    scored_words = []
    qlen = len(query) if query else 1
    for word in cleaned:
        score = 0.0
        word_length = len(word)
        if 2 <= word_length <= 4:
            score += 2
        elif word_length == 1:
            score -= 1

        word_position = query.find(word) if query else -1
        if word_position >= 0:
            position_score = max(0.0, 1 - word_position / max(1, qlen))
            score += position_score * 3

        context_patterns = [
            re.escape(word) + r'的同义词',
            re.escape(word) + r'的定义',
            r'查询' + re.escape(word),
            r'搜索' + re.escape(word)
        ]
        for pattern in context_patterns:
            if re.search(pattern, query or '', re.IGNORECASE):
                score += 3
                break

        common_words = {'意思', '解释', '查询', '搜索', '查找', '帮助'}
        if word in common_words:
            score -= 2

        scored_words.append((word, score))

    if scored_words:
        best_words = sorted(scored_words, key=lambda x: x[1], reverse=True)
        return [word for word, _ in best_words]

    return cleaned


# -------------------------
# 选择最佳英文目标（评分）
# -------------------------
def _select_best_english_target(words: List[str], query: str) -> List[str]:
    if not words:
        return []

    scored_words = []
    for word in words:
        score = 0.0
        alpha_len = len(re.sub(r'[^A-Za-z]', '', word))
        if 3 <= alpha_len <= 30:
            score += 2

        word_position = query.lower().find(word.lower()) if query else -1
        if word_position >= 0:
            position_score = max(0.0, 1 - word_position / max(1, len(query)))
            score += position_score * 3

        if word and word[0].isupper() and not word.isupper():
            score += 1

        common_function_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'as', 'is', 'are', 'was', 'were',
            'this', 'that', 'these', 'those', 'have', 'has', 'had'
        }
        if word.lower() not in common_function_words:
            score += 3

        context_patterns = [
            r'of\s+' + re.escape(word),
            r"'" + re.escape(word) + r"'",
            r'"' + re.escape(word) + r'"'
        ]
        for pattern in context_patterns:
            if re.search(pattern, query or '', re.IGNORECASE):
                score += 2
                break

        scored_words.append((word, score))

    if scored_words:
        scored_words = sorted(scored_words, key=lambda x: x[1], reverse=True)
        return [w for w, _ in scored_words[:5]]
    return words


# -------------------------
# 兜底提取核心概念
# -------------------------
def _extract_core_concept(query: str) -> List[str]:
    cleaned_query = query or ""
    remove_patterns = [
        r'什么是', r'哪些是', r'怎么', r'如何', r'为什么', r'为何',
        r'what are', r'what is', r'how to', r'why', r'which'
    ]
    for pattern in remove_patterns:
        cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)

    # 中文：优先提取 2-6 个汉字的短语
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,6}', cleaned_query)
    if chinese_words:
        return _select_best_chinese_target(chinese_words, cleaned_query)

    # 英文：提取连续的字母词（至少3个字母）
    english_words = re.findall(r'(?<![A-Za-z])[A-Za-z]{3,}(?![A-Za-z])', cleaned_query)
    if english_words:
        return _select_best_english_target(english_words, cleaned_query)

    words = cleaned_query.strip().split()
    if words:
        return filter_valid_target(words, query)
    return []


# -------------------------
# 目标词抽取（优先引号、英文、中文 pattern）
# -------------------------
def _extract_target_word(query: str) -> List[str]:
    if not query:
        return []

    # 1) 引号包围的优先（group 1）
    quoted_patterns = [
        r'[「『"](.*?)[」』"]',
        r"'(.*?)'",
        r'"(.*?)"',
        r'【(.*?)】',
        r'《(.*?)》'
    ]
    for pattern in quoted_patterns:
        match = re.search(pattern, query)
        if match:
            candidate = match.group(1).strip()
            candidates = _ensure_str_candidates(candidate)
            filtered = [c for c in candidates if _is_valid_target(c, query)]
            if filtered:
                return filtered

    # 2) 优先提取英文 token
    english_words = re.findall(r'(?<![A-Za-z])([A-Za-z][A-Za-z-]*[A-Za-z])(?![A-Za-z])', query)
    if english_words:
        target_candidate = _select_best_english_target(english_words, query)
        target_candidate = _ensure_str_candidates(target_candidate)
        filtered = [c for c in target_candidate if _is_valid_target(c, query)]
        if filtered:
            return filtered

    # 3) 中文模式提取
    chinese_patterns = [
        r'([^的，,；;。.?？!！\s]{1,6})(?:的)?(?:同义词|近义词|相似词|反义词|定义|意思|含义|解释|例句|例子|用法|发音|读音|词源|词根|词缀|搭配|短语)',
        r'(?:查询|查找|搜索|找|什么是|解释|定义)([^的，,；;。.?？!！\s]{1,6})'
    ]
    for pattern in chinese_patterns:
        matches = re.findall(pattern, query)
        for match in matches:
            cand_list = _ensure_str_candidates(match)
            cleaned_list = []
            for cand in cand_list:
                cleaned = _clean_chinese_candidate(cand)
                cleaned_list.extend(_ensure_str_candidates(cleaned))
            filtered = [c for c in cleaned_list if _is_valid_target(c, query)]
            if filtered:
                return filtered

    # 4) 兜底
    return _extract_core_concept(query)


# -------------------------
# 基于模式的意图识别
# -------------------------
def _pattern_based_recognition(query: str) -> Dict[str, Any]:
    patterns = {
        IntentType.SYNONYM.value: [
            r'(.{1,30}?)(?:的)?(?:同义词|近义词|相似词)',
            r'(?:synonyms?|similar words? to|words like)\s+(.+)'
        ],
        IntentType.DEFINITION.value: [
            r'(.{1,30}?)(?:的)?(?:定义|意思|含义|释义|是什么)',
            r'(?:what is|what does)\s+(.+?)\s*(?:mean)?'
        ],
        IntentType.EXAMPLE.value: [
            r'(.{1,30}?)(?:的)?(?:例句|用法|造句)',
            r'(?:example|usage) of\s+(.+)',
            r'use\s+(.+?)\s+in a sentence'
        ],
        IntentType.PRONUNCIATION.value: [
            r'(.{1,30}?)(?:怎么读|发音|读音|读法)',
            r'(?:how to pronounce|pronunciation of)\s+(.+)'
        ],
        IntentType.USAGE_GUIDANCE.value: [
            r'(.{1,30}?)(?:的)?(?:短语|搭配|词组|固定搭配)',
            r'(?:phrases?|collocations?)\s+of\s+(.+)',
            r'(.{1,30}?)(?:怎么用|用法|语法|使用)',
            r'(?:how to use|grammar of)\s+(.+)'
        ],
        IntentType.ETYMOLOGY.value: [
            r'(.{1,30}?)(?:的)?(?:词源|来源|起源|词根)',
            r'(?:etymology|origin) of\s+(.+)'
        ],
        IntentType.WORD_FAMILY.value: [
            r'(.{1,30}?)(?:的)?(?:派生词|相关词|词性|变形)',
            r'(?:related words|derivatives? of)\s+(.+)'
        ]
    }

    for intent, intent_patterns in patterns.items():
        for pattern in intent_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if not match:
                continue

            groups = match.groups() or ()
            for g in groups[::-1]:
                if not g:
                    continue
                cand_list = _ensure_str_candidates(g.strip())
                final_cands = []
                for c in cand_list:
                    if re.search(r'[A-Za-z]', c):
                        final_cands.append(c)
                    else:
                        cleaned = _clean_chinese_candidate(c)
                        final_cands.extend(_ensure_str_candidates(cleaned))
                filtered = [c for c in final_cands if _is_valid_target(c, query)]
                if filtered:
                    return {
                        "type": intent,
                        "target_word": filtered,
                        "confidence": 0.75,
                        "method": "pattern"
                    }

            fallback = _extract_target_word(query)
            if fallback:
                return {
                    "type": intent,
                    "target_word": fallback,
                    "confidence": 0.6,
                    "method": "pattern"
                }

    return {
        "type": IntentType.GENERAL.value,
        "target_word": _extract_target_word(query),
        "confidence": 0.3,
        "method": "pattern"
    }

def _normalize_target_from_results(intent_results: List[Dict]) -> str:
    """
    依据优先级从 intent_results 提取最合理的 target_word 字符串：
    优先级：keyword > pattern > semantic > fallback (众数)
    该函数保证返回一个字符串（可能为空）。
    """
    # 先把所有 method 的 target_word 规范为字符串数组
    method_to_targets = {}
    for r in intent_results:
        method = r.get("method", "")
        targets = _ensure_str_candidates(r.get("target_word"))
        # 保留原始大小写（因为 r.get 来自调用时的值）
        method_to_targets.setdefault(method, []).extend(targets)

    # 优先级判断
    for prefer in ("keyword", "pattern", "semantic"):
        tlist = method_to_targets.get(prefer)
        if tlist:
            # 选第一个有效且在原 query 中出现（更稳妥）
            return tlist[0] if tlist else ""

    # 如果没优先命中，使用众数（与原实现兼容）
    all_targets = []
    for v in method_to_targets.values():
        all_targets.extend(v)
    if all_targets:
        return max(set(all_targets), key=all_targets.count)
    return ""



# -------------------------
# 合并多个意图结果（返回 Top-K 候选）
# -------------------------
def _combine_intent_results(intent_results: List[Dict], top_k: int = 3) -> Dict[str, Any]:
    """
    改进后：
    - 对每个 intent 计算 weighted_sum 和 weight_sum
    - final_score = weighted_sum / weight_sum (如果 weight_sum > 0)，保证单方法时不会被缩放
    - 返回 candidates（按 final_score 降序）以及 best、all_scores（未归一化的 weighted_sum 用于诊断）
    """
    method_weights = {"keyword": 0.4, "semantic": 0.4, "pattern": 0.2}
    weighted_sum_per_intent: Dict[str, float] = {}
    weight_sum_per_intent: Dict[str, float] = {}

    # Accumulate
    for r in intent_results:
        itype = r.get("type", "general")
        method = r.get("method", "")
        conf = float(r.get("confidence", 0.0))
        mw = method_weights.get(method, 0.0)

        weighted_sum_per_intent.setdefault(itype, 0.0)
        weight_sum_per_intent.setdefault(itype, 0.0)

        weighted_sum_per_intent[itype] += conf * mw
        weight_sum_per_intent[itype] += mw

    # finalize score : weighted_sum / weight_sum  （若 weight_sum==0 则 0）
    final_scores: Dict[str, float] = {}
    for itype, wsum in weighted_sum_per_intent.items():
        wtotal = weight_sum_per_intent.get(itype, 0.0)
        final_scores[itype] = (wsum / wtotal) if wtotal > 0 else 0.0

    # Build candidates list (并选取 target_word)
    candidates_list = []
    for itype, score in final_scores.items():
        # collect methods and target words for debugging / explanation
        related = [r for r in intent_results if r.get("type") == itype]
        methods = ",".join(sorted({r.get("method", "") for r in related}))
        target_words = []
        for r in related:
            target_words.extend(_ensure_str_candidates(r.get("target_word")))
        # 优先选择合并策略挑出来的 target（更稳妥）
        target_word = _normalize_target_from_results(intent_results)
        candidates_list.append({
            "type": itype,
            "confidence": score,
            "method": methods,
            "target_word": target_word or (target_words[0] if target_words else "")
        })

    # 排序并截取 top_k
    candidates_sorted = sorted(candidates_list, key=lambda x: x["confidence"], reverse=True)
    top_candidates = candidates_sorted[:top_k] if candidates_sorted else []

    best = top_candidates[0] if top_candidates else {"type": "general", "confidence": 0.0, "method": "", "target_word": ""}

    # all_scores 仍保留原始 weighted_sum（便于排查），并额外给出 final_scores
    return {
        "type": best["type"],
        "target_word": best["target_word"],
        "confidence": best["confidence"],
        "all_scores_weighted_sum": weighted_sum_per_intent,
        "all_scores_final": final_scores,
        "candidates": top_candidates
    }



# -------------------------
# IntentRecognizer 类（主入口）
# -------------------------
class IntentRecognizer:
    def __init__(self):
        self.intent_examples = INTENT_EXAMPLES
        self.intent_keywords = INTENT_KEYWORDS

    def recognize_intent(self, query: str, top_k: int = 1) -> Dict[str, Any]:
        if not query:
            return {"type": IntentType.GENERAL.value, "target_word": "", "confidence": 0.0, "method": "keyword", "candidates": []}

        query_original = query
        query_lower = query.lower()

        # 1. 关键词匹配
        keyword_intent = self._keyword_based_recognition(query_lower)
        kw_tw = _extract_target_word(query_original)
        if kw_tw:
            keyword_intent["target_word"] = kw_tw

        if keyword_intent.get("confidence", 0) > 0.9:
            combined = _combine_intent_results([keyword_intent], top_k=top_k)
            combined["method"] = "keyword"
            return combined

        # 2. 语义相似度
        semantic_intent = self._semantic_similarity_recognition(query_lower)
        sem_tw = _extract_target_word(query_original)
        if sem_tw:
            semantic_intent["target_word"] = sem_tw

        # 3. 模式匹配
        pattern_intent = _pattern_based_recognition(query_original)

        # 4. 融合并返回 Top-K
        combined = _combine_intent_results([keyword_intent, semantic_intent, pattern_intent], top_k=top_k)
        if not combined.get("target_word"):
            combined["target_word"] = (_extract_target_word(query_original) or [""])[0]
        return combined

    def _keyword_based_recognition(self, query: str) -> Dict[str, Any]:
        scores = {intent: 0.0 for intent in self.intent_keywords.keys()}
        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    scores[intent] += 1.0

        max_score = max(scores.values()) if scores else 1.0
        for intent in scores:
            scores[intent] = scores[intent] / max_score if max_score > 0 else 0.0

        best_intent = max(scores.items(), key=lambda x: x[1]) if scores else ("general", 0.0)
        return {
            "type": best_intent[0],
            "target_word": _extract_target_word(query),
            "confidence": best_intent[1],
            "method": "keyword"
        }

    def _semantic_similarity_recognition(self, query: str) -> Dict[str, Any]:
        scores = {}
        for intent, examples in self.intent_examples.items():
            intent_scores = []
            for example in examples[:5]:
                similarity = _calculate_text_similarity(query, example)
                intent_scores.append(similarity)
            scores[intent] = max(intent_scores) if intent_scores else 0.0

        best_intent = max(scores.items(), key=lambda x: x[1]) if scores else (IntentType.GENERAL.value, 0.0)

        return {
            "type": best_intent[0],
            "target_word": _extract_target_word(query),
            "confidence": best_intent[1],
            "method": "semantic"
        }


# -------------------------
# 简单命令行演示
# -------------------------
if __name__ == "__main__":
    recognizer = IntentRecognizer()

    tests = [
        "sensible的同义词有哪些",
        "What's a synonym for 'sensible'?",
        "sensible怎么读",
        "如何用 'analyze' 造句？",
        "什么是 photosynthesis",
        "给出 beautiful 的派生词",
        "能不能解释一下 'resilient' 的意思？",
        "查询 'mitigate' 的用法和搭配",
        "如何读 colonel?",
        "有没有关于 'serendipity' 的词源信息"
    ]

    for q in tests:
        res = recognizer.recognize_intent(q, top_k=3)
        print("=" * 80)
        print("Query:", q)
        print("Best type:", res.get("type"))
        print("Best target_word:", res.get("target_word"))
        print("Confidence:", res.get("confidence"))
        print("Candidates (top_k):")
        for c in res.get("candidates", []):
            print("  -", c)
        print("All scores:", res.get("all_scores"))
    print("=" * 80)

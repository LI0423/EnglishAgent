import re
from typing import List, Dict, Any

from rag_core.prompt import INTENT_EXAMPLES, INTENT_KEYWORDS


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """计算文本相似度（简化版）"""
    words1 = set(re.findall(r'\b\w+\b', text1.lower()))
    words2 = set(re.findall(r'\b\w+\b', text2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))

    return intersection / union if union > 0 else 0.0


def _combine_intent_results(intent_results: List[Dict]) -> Dict[str, Any]:
    """综合多个意图识别结果"""
    intent_scores = {}
    method_weights = {"keyword": 0.4, "semantic": 0.4, "pattern": 0.2}

    for result in intent_results:
        intent_type = result.get("type", "general")
        confidence = float(result.get("confidence", 0))
        method_weight = method_weights.get(result.get("method"), 0.1)

        intent_scores.setdefault(intent_type, 0.0)
        intent_scores[intent_type] += confidence * method_weight

    if intent_scores:
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        best_confidence = best_intent[1]

        target_words = [r.get("target_word") for r in intent_results if r.get("target_word")]
        target_word = max(set([t for t in target_words if t]), key=target_words.count) if target_words else ""

        return {
            "type": best_intent[0],
            "target_word": target_word,
            "confidence": best_confidence,
            "all_scores": intent_scores
        }
    else:
        return {
            "type": "general",
            "target_word": "",
            "confidence": 0.1,
            "all_scores": {}
        }


def _is_valid_target(candidate: str, query: str) -> bool:
    """判断候选词是否是有效的目标词（更严格）"""
    if not candidate:
        return False

    candidate = candidate.strip()
    # 过短或单字符非缩写视为无效
    if len(candidate) == 1 and not candidate.isupper():
        return False
    if len(candidate) == 0:
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

    # 如果候选在查询中出现至少一次且不是疑问结构，可能是有效目标
    if query and candidate in query and not any(sw in candidate for sw in ('什么', '有什么', '有没有', '?', '？')):
        return True

    # 作为默认策略：如果候选为中文且长度在2以上，或英文长度>=2，则认为可能有效
    if re.search(r'[\u4e00-\u9fff]', candidate):
        return len(candidate) >= 2
    if re.search(r'[A-Za-z]', candidate):
        return len(re.sub(r'[^A-Za-z]', '', candidate)) >= 2

    return False


def _clean_chinese_candidate(word: str) -> str:
    """清洗中文候选，剥离常见疑问前缀"""
    if not word:
        return ""
    word = word.strip()
    # 去掉常见疑问或功能词前缀
    word = re.sub(r'^(?:有|有没有|什么|哪些|哪个|哪|是否|能否|可以|有什么|是什么|什么是)[，,。；;：:\s]*', '', word)
    # 再去掉末尾多余的疑问或连接词
    word = re.sub(r'[？?。.！!，,；;\s]+$', '', word)
    return word.strip()


def _select_best_chinese_target(chinese_words: List[str], query: str) -> str:
    """从多个中文词语中选择最可能是目标词的（已改进）"""
    if not chinese_words:
        return ""

    chinese_stop_words = {
        '什么', '哪些', '怎么', '如何', '为什么', '为何', '哪个', '哪', '什么是',
        '这个', '那个', '这些', '那些', '有没有', '是否', '可以', '能够', '有', '是什么'
    }

    # 清洗并过滤
    cleaned = []
    for word in chinese_words:
        w = _clean_chinese_candidate(word)
        if not w:
            continue
        if any(sw == w for sw in chinese_stop_words):
            continue
        # 如果清洗后仍包含疑问词则丢弃
        if re.search(r'^(?:什么|有没有|有什么|是否|能否|可以)', w):
            continue
        cleaned.append(w)

    if not cleaned:
        # 退化回原始最短/最前的可用词（再做一次清洗）
        for w in chinese_words:
            w2 = _clean_chinese_candidate(w)
            if w2 and w2 not in chinese_stop_words:
                return w2
        return chinese_words[0] if chinese_words else ""

    # 评分选择最佳目标词
    scored_words = []
    qlen = len(query) if query else 1
    for word in cleaned:
        score = 0
        word_length = len(word)
        if 2 <= word_length <= 4:
            score += 2
        elif word_length == 1:
            score -= 1

        word_position = query.find(word) if query else -1
        if word_position >= 0:
            position_score = max(0.0, 1 - word_position / max(1, qlen))
            score += position_score * 3

        # 上下文相关短语匹配加分
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
        best_word = max(scored_words, key=lambda x: x[1])
        return best_word[0] if best_word[1] > -1 else cleaned[0]

    return cleaned[0]


def _select_best_english_target(words: List[str], query: str) -> str:
    """从多个英文单词中选择最可能是目标词的（已改进）"""
    if not words:
        return ""

    scored_words = []

    for word in words:
        score = 0
        alpha_len = len(re.sub(r'[^A-Za-z]', '', word))
        if 3 <= alpha_len <= 30:
            score += 2

        word_position = query.lower().find(word.lower()) if query else -1
        if word_position >= 0:
            position_score = max(0.0, 1 - word_position / max(1, len(query)))
            score += position_score * 3

        if word[0].isupper() and not word.isupper():
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
        best_word = max(scored_words, key=lambda x: x[1])
        return best_word[0] if best_word[1] >= 0 else ""

    return words[0]


def _extract_core_concept(query: str) -> str:
    """提取查询的核心概念（兜底方法）"""
    cleaned_query = query
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
        first_word = words[0]
        if _is_valid_target(first_word, query):
            return first_word

    return ""


def _extract_target_word(query: str) -> str:
    """改进的目标单词提取（优先英文，再中文，带清洗与严格校验）"""
    if not query:
        return ""

    # 1) 引号包围的优先
    quoted_patterns = [
        r'[「『"](.+?)[」』"]',
        r"'(.+?)'",
        r'"(.+?)"',
        r'【(.+?)】',
        r'《(.+?)》'
    ]
    for pattern in quoted_patterns:
        match = re.search(pattern, query)
        if match:
            candidate = match.group(1).strip()
            if _is_valid_target(candidate, query):
                print("candidate", candidate)
                return candidate

    # 2) 优先提取并立即返回英文 token（如果有）
    english_words = re.findall(r'(?<![A-Za-z])([A-Za-z][A-Za-z-]*[A-Za-z])(?![A-Za-z])', query)

    if english_words:
        target_candidate = _select_best_english_target(english_words, query)
        if target_candidate and _is_valid_target(target_candidate, query):
            return target_candidate

    # 3) 中文模式提取（尽量避免疑问短语）
    chinese_patterns = [
        r'([^的，,；;。.?？!！\s]{1,6})(?:的)?(?:同义词|近义词|相似词|反义词|定义|意思|含义|解释|例句|例子|用法|发音|读音|词源|词根|词缀|搭配|短语)',
        r'(?:查询|查找|搜索|找|什么是|解释|定义)([^的，,；;。.?？!！\s]{1,6})',
        r'([^和与跟及以及\s]{1,6})(?:和|与|跟|及|以及)([^的区别差异不同]{1,6})(?:的)?(?:区别|差异|不同)'
    ]

    for pattern in chinese_patterns:
        matches = re.findall(pattern, query)
        for match in matches:
            if isinstance(match, tuple):
                # 多组匹配，优先选择能通过验证的候选
                for candidate in match:
                    candidate = _clean_chinese_candidate(candidate.strip())
                    if candidate and _is_valid_target(candidate, query):
                        return candidate
            else:
                candidate = _clean_chinese_candidate(match.strip())
                if candidate and _is_valid_target(candidate, query):
                    return candidate

    # 4) 最后兜底：核心概念提取
    return _extract_core_concept(query)


def _pattern_based_recognition(query: str) -> Dict[str, Any]:
    """基于模式的意图识别（改进）"""
    patterns = {
        "synonym": [
            r'(.{1,30}?)(?:的)?(?:同义词|近义词|相似词)',
            r'(?:synonyms?|similar words? to|words like)\s+(.+)'
        ],
        "definition": [
            r'(.{1,30}?)(?:的)?(?:定义|意思|含义|释义|是什么)',
            r'(?:what is|what does)\s+(.+?)\s*(?:mean)?'
        ],
        "example": [
            r'(.{1,30}?)(?:的)?(?:例句|用法|造句)',
            r'(?:example|usage) of\s+(.+)',
            r'use\s+(.+?)\s+in a sentence'
        ],
        "phrase": [
            r'(.{1,30}?)(?:的)?(?:短语|搭配|词组|固定搭配)',
            r'(?:phrases?|collocations?)\s+of\s+(.+)'
        ],
        "pronunciation": [
            r'(.{1,30}?)(?:怎么读|发音|读音|读法)',
            r'(?:how to pronounce|pronunciation of)\s+(.+)'
        ],
        "etymology": [
            r'(.{1,30}?)(?:的)?(?:词源|来源|起源|词根)',
            r'(?:etymology|origin) of\s+(.+)'
        ],
        "comparison": [
            r'(.{1,30}?)(?:和|与)(.{1,30}?)(?:的)?(?:区别|不同|差异)',
            r'(?:difference between|A vs B)\s+(.+)'
        ],
        "antonym": [
            r'(.{1,30}?)(?:的)?(?:反义词|相反词)',
            r'(?:antonyms?|opposite of)\s+(.+)'
        ],
        "usage_note": [
            r'(.{1,30}?)(?:怎么用|用法|语法|使用)',
            r'(?:how to use|grammar of)\s+(.+)'
        ],
        "word_family": [
            r'(.{1,30}?)(?:的)?(?:派生词|相关词|词性|变形)',
            r'(?:related words|derivatives? of)\s+(.+)'
        ],
        "formality": [
            r'(.{1,30}?)(?:正式吗|正式用语|口语表达|正式程度)',
            r'(?:formal or informal|formality of)\s+(.+)'
        ]
    }

    for intent, intent_patterns in patterns.items():
        for pattern in intent_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if not match:
                continue

            # 优先按命名组 target 取值
            if 'target' in match.groupdict() and match.group('target'):
                candidate = match.group('target').strip()
                # 如果是英文 token，优先返回
                if re.search(r'[A-Za-z]', candidate):
                    candidate_clean = candidate
                else:
                    candidate_clean = _clean_chinese_candidate(candidate)
                if _is_valid_target(candidate_clean, query):
                    return {
                        "type": intent,
                        "target_word": candidate_clean,
                        "confidence": 0.8,
                        "method": "pattern"
                    }

            groups = match.groups() or ()
            # 倒序检查 groups（后面的 group 更可能是目标）
            for g in groups[::-1]:
                if not g:
                    continue
                g_clean = g.strip()
                # 根据内容决定清洗方式：英文/数字/混合不走中文清洗
                if re.search(r'[A-Za-z]', g_clean):
                    candidate_clean = g_clean
                else:
                    candidate_clean = _clean_chinese_candidate(g_clean)
                if _is_valid_target(candidate_clean, query):
                    return {
                        "type": intent,
                        "target_word": candidate_clean,
                        "confidence": 0.75,
                        "method": "pattern"
                    }

            # groups 没有合适候选，退回 _extract_target_word 作为兜底
            fallback = _extract_target_word(query)
            if fallback:
                return {
                    "type": intent,
                    "target_word": fallback,
                    "confidence": 0.6,
                    "method": "pattern"
                }

    # 完全没有匹配任何特定意图，返回 general
    return {
        "type": "general",
        "target_word": _extract_target_word(query),
        "confidence": 0.3,
        "method": "pattern"
    }


class IntentRecognizer:
    def __init__(self):
        self.intent_examples = INTENT_EXAMPLES
        self.intent_keywords = INTENT_KEYWORDS

    def recognize_intent(self, query: str) -> Dict[str, Any]:
        """基于Few-shot的意图识别"""
        if not query:
            return {"type": "general", "target_word": "", "confidence": 0.0, "method": "keyword"}

        # 不要修改原始 query 的大小写以保持目标词大小写信息
        query_original = query
        query_lower = query.lower()

        # 1. 关键词匹配（快速路径）
        keyword_intent = self._keyword_based_recognition(query_lower)
        if keyword_intent.get("confidence", 0) > 0.8:
            # 确保 target_word 经过更强的提取器校验（优先英文）
            keyword_intent["target_word"] = _extract_target_word(query_original) or keyword_intent.get("target_word", "")
            return keyword_intent

        # 2. 语义相似度匹配
        semantic_intent = self._semantic_similarity_recognition(query_lower)

        # 3. 模式匹配（备用）
        pattern_intent = _pattern_based_recognition(query_original)

        # 4. 综合评分
        combined = _combine_intent_results([keyword_intent, semantic_intent, pattern_intent])
        # 最后再次用更强的提取器确认 target_word（优先英文）
        combined["target_word"] = combined.get("target_word") or _extract_target_word(query_original)
        return combined

    def _keyword_based_recognition(self, query: str) -> Dict[str, Any]:
        """基于关键词的意图识别"""
        scores = {intent: 0.0 for intent in self.intent_keywords.keys()}

        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    scores[intent] += 1.0

        max_score = max(scores.values()) if scores else 1
        for intent in scores:
            scores[intent] = scores[intent] / max_score if max_score > 0 else 0

        best_intent = max(scores.items(), key=lambda x: x[1]) if scores else ("general", 0)

        return {
            "type": best_intent[0],
            "target_word": _extract_target_word(query),
            "confidence": best_intent[1],
            "method": "keyword"
        }

    def _semantic_similarity_recognition(self, query: str) -> Dict[str, Any]:
        """基于语义相似度的意图识别"""
        scores = {}
        for intent, examples in self.intent_examples.items():
            intent_scores = []
            for example in examples[:5]:
                similarity = _calculate_text_similarity(query, example)
                intent_scores.append(similarity)
            scores[intent] = max(intent_scores) if intent_scores else 0

        best_intent = max(scores.items(), key=lambda x: x[1]) if scores else ("general", 0)

        return {
            "type": best_intent[0],
            "target_word": _extract_target_word(query),
            "confidence": best_intent[1],
            "method": "semantic"
        }


# -------------------------
# 使用示例（将下面示例放到测试脚本或 REPL 中运行）
# -------------------------
if __name__ == "__main__":
    ir = IntentRecognizer()
    examples = [
        # "sensible有什么释义",
        "什么是 sensible",
        # "sensible 的例句",
        # "请给出 sensible 的同义词",
    ]
    for q in examples:
        res = ir.recognize_intent(q)
        print(q, "=>", res)

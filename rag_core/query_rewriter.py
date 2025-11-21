from typing import List, Dict, Any, re

from models.generator_model import GeneratorModel


def _classify_query_type(query: str) -> str:
    """查询类型分类"""
    query_lower = query.lower()

    type_patterns = {
        "definition": [r"什么是", r"是什么", r"定义", r"意思", r"含义"],
        "howto": [r"怎么", r"如何", r"方法", r"步骤", r"技巧"],
        "comparison": [r"区别", r"不同", r"对比", r"比较", r"差异"],
        "example": [r"例子", r"示例", r"举例", r"实例"],
        "reason": [r"为什么", r"原因", r"为何", r"为啥"],
        "synonym": [r"近义词", r"同义词", r"相似词"],
    }

    for query_type, patterns in type_patterns.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                return query_type

    return "general"


def _extract_key_terms(query: str) -> List[str]:
    """提取关键术语"""
    # 移除停用词和标点
    stop_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
        "什么", "哪些", "怎么", "如何", "为什么", "吗", "呢", "吧", "啊", "呀",
        "请问", "我想", "了解", "知道", "告诉", "解释"
    }

    # 简单的分词（实际应用中应使用jieba等分词工具）
    words = re.findall(r'[\w\u4e00-\u9fff]+', query)
    key_terms = [word for word in words if word not in stop_words and len(word) > 1]

    return key_terms


def _load_synonym_dict() -> Dict[str, List[str]]:
    """加载同义词词典"""
    return {
        "怎么": ["如何", "怎样", "咋"],
        "如何": ["怎么", "怎样", "如何做"],
        "什么": ["何种", "哪些", "什么东西"],
        "区别": ["不同", "差异", "差别"],
        "用法": ["使用方法", "应用", "运用"],
        "例子": ["示例", "实例", "案例"],
        "近义词": ["同义词", "相似词", "同类词"],
        "方法": ["方式", "办法", "技巧", "策略"],
        "提高": ["提升", "增强", "改进", "优化"],
        "学习": ["掌握", "了解", "熟悉", "认知"],
    }


def _load_domain_knowledge() -> Dict[str, Any]:
    """加载领域知识"""
    return {
        "english_learning": {
            "key_concepts": ["语法", "词汇", "发音", "听力", "口语", "阅读", "写作"],
            "common_queries": [
                "怎么提高", "学习方法", "技巧", "练习", "教程"
            ]
        }
    }


def _get_domain_expansions(query: str, analysis: Dict) -> List[str]:
    """获取领域相关的扩展"""
    expansions = []
    domain = analysis.get("domain")

    if domain == "english_learning":
        # 英语学习领域的特定扩展
        expansions.extend([
            f"{query} 英语学习",
            f"{query} 英语技巧",
            f"{query} 英语教学方法"
        ])

    return expansions


def _contains_question_words(query: str) -> bool:
    """检查是否包含疑问词"""
    question_words = ["什么", "怎么", "如何", "为什么", "哪些", "哪", "谁", "何时", "哪里"]
    return any(word in query for word in question_words)


def _assess_complexity(query: str) -> str:
    """评估查询复杂度"""
    word_count = len(query.split())

    if word_count <= 3:
        return "simple"
    elif word_count <= 6:
        return "medium"
    else:
        return "complex"


def _identify_domain(query: str) -> str:
    """识别查询领域"""
    english_terms = ["英语", "英文", "单词", "语法", "听力", "口语", "阅读", "写作"]

    if any(term in query for term in english_terms):
        return "english_learning"

    return "general"


def _identify_potential_issues(query: str) -> List[str]:
    """识别潜在问题"""
    issues = []

    if len(query.strip()) < 2:
        issues.append("too_short")

    if len(query.split()) > 10:
        issues.append("too_complex")

    vague_indicators = ["这个", "那个", "有些", "某些"]
    if any(indicator in query for indicator in vague_indicators):
        issues.append("vague")

    return issues


def _analyze_query(query: str) -> Dict[str, Any]:
    """深度查询分析"""
    analysis = {
        "length": len(query),
        "word_count": len(query.split()),
        "contains_question_words": _contains_question_words(query),
        "query_type": _classify_query_type(query),
        "complexity_level": _assess_complexity(query),
        "key_terms": _extract_key_terms(query),
        "domain": _identify_domain(query),
        "potential_issues": _identify_potential_issues(query)
    }
    return analysis


def _multi_perspective_questions(query: str, analysis: Dict) -> List[str]:
    """多角度提问"""
    perspectives = []
    key_terms = analysis.get("key_terms", [])

    if not key_terms:
        return perspectives

    main_term = key_terms[0]

    # 不同角度的提问
    perspective_templates = [
        f"{main_term}的基本概念",
        f"{main_term}的主要特点",
        f"{main_term}的实际应用",
        f"{main_term}的学习方法",
        f"{main_term}的常见问题",
        f"{main_term}的相关术语",
        f"{main_term}的发展历史",
        f"{main_term}的重要性",
    ]

    perspectives.extend(perspective_templates)
    return perspectives


def _domain_specific_rewrite(query: str, analysis: Dict) -> List[str]:
    """领域特定重写"""
    domain_rewrites = []

    # 英语学习领域特定重写
    english_learning_patterns = [
        (r"(.*)的近义词", [r"\1的同义词", r"与\1意思相近的词", r"\1的相似表达"]),
        (r"(.*)的用法", [r"如何使用\1", r"\1的应用场景", r"\1的正确用法"]),
        (r"(.*)和(.*)的区别", [r"\1与\1的差异", r"\1和\1的不同点", r"比较\1和\1"]),
    ]

    for pattern, replacements in english_learning_patterns:
        match = re.match(pattern, query)
        if match:
            for replacement in replacements:
                rewritten = replacement
                for i, group in enumerate(match.groups(), 1):
                    rewritten = rewritten.replace(rf"\{i}", group)
                domain_rewrites.append(rewritten)

    return domain_rewrites


def _sentence_restructuring(query: str) -> List[str]:
    """句式重构"""
    restructured = []

    # 疑问词变换
    question_patterns = [
        (r"怎么(.*)", r"如何\1"),
        (r"如何(.*)", r"怎么\1"),
        (r"什么是(.*)", r"\1的定义"),
        (r"(.*)是什么", r"什么是\1"),
        (r"为什么(.*)", r"\1的原因"),
    ]

    for pattern, replacement in question_patterns:
        if re.match(pattern, query):
            restructured.append(re.sub(pattern, replacement, query))

    # 添加不同的疑问句式
    if "吗" not in query and "?" not in query:
        restructured.append(f"{query}吗？")
        restructured.append(f"请问{query}")
        restructured.append(f"我想了解{query}")

    return restructured


def _query_expansion(query: str, analysis: Dict) -> List[str]:
    """查询扩展"""
    expanded = []
    key_terms = analysis.get("key_terms", [])
    query_type = analysis.get("query_type", "general")

    # 根据查询类型添加相关术语
    if query_type == "definition":
        expanded_terms = ["定义", "概念", "含义", "解释", "是什么"]
        for term in expanded_terms:
            expanded.append(f"{query} {term}")

    elif query_type == "howto":
        expanded_terms = ["方法", "步骤", "技巧", "指南", "教程"]
        for term in expanded_terms:
            expanded.append(f"{query} {term}")

    elif query_type == "comparison":
        if len(key_terms) >= 2:
            expanded.append(f"{key_terms[0]} 与 {key_terms[1]} 对比")
            expanded.append(f"{key_terms[0]} 和 {key_terms[1]} 的区别")

    # 添加领域相关扩展
    domain_expansions = _get_domain_expansions(query, analysis)
    expanded.extend(domain_expansions)

    return expanded


class QueryRewriter:
    def __init__(self):
        self.generate_model = GeneratorModel()
        self.synonym_dict = _load_synonym_dict()
        self.domain_knowledge = _load_domain_knowledge()

    def rewrite(self, query: str, strategy: str = "comprehensive") -> List[str]:
        """高级查询重写"""
        original_query = query

        # 查询分析
        analysis = _analyze_query(query)

        # 根据策略选择重写方法
        if strategy == "comprehensive":
            rewritten_queries = self._comprehensive_rewrite(query, analysis)
        elif strategy == "expansion":
            rewritten_queries = self._expansion_rewrite(query, analysis)
        elif strategy == "reformulation":
            rewritten_queries = self._reformulation_rewrite(query, analysis)
        else:
            rewritten_queries = [query]

        # 去重并确保包含原始查询
        all_queries = [original_query] + rewritten_queries
        unique_queries = list(dict.fromkeys(all_queries))  # 保持顺序的去重

        return unique_queries

    def _comprehensive_rewrite(self, query: str, analysis: Dict) -> List[str]:
        """综合重写策略"""
        rewritten = []

        # 1. 同义词替换
        rewritten.extend(self._synonym_replacement(query))
        # 2. 查询扩展
        rewritten.extend(_query_expansion(query, analysis))
        # 3. 句式重构
        rewritten.extend(_sentence_restructuring(query))
        # 4. 领域特定重写
        rewritten.extend(_domain_specific_rewrite(query, analysis))
        # 5. 多角度提问
        rewritten.extend(_multi_perspective_questions(query, analysis))

        return rewritten

    def _synonym_replacement(self, query: str) -> List[str]:
        """同义词替换"""
        rewritten = []
        words = query.split()

        for i, word in enumerate(words):
            if word in self.synonym_dict:
                for synonym in self.synonym_dict[word]:
                    new_query = words.copy()
                    new_query[i] = synonym
                    rewritten.append(" ".join(new_query))

        return rewritten

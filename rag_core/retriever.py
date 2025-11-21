import re
from collections import defaultdict
from typing import List, Dict, Optional, Any

from models.embedding_model import EmbeddingModel
from rag_core.intent_recognizer import IntentRecognizer
from utils import MilvusDBClient


def _extract_keywords(text: str) -> List[str]:
    """从文本中提取关键词"""
    # 简单的关键词提取：移除停用词，保留有意义的单词
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

    # 简单的停用词过滤
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    keywords = [word for word in words if word not in stop_words]

    return keywords


def _calculate_bm25_score(content: str, query: str) -> float:
    """简化版BM25分数计算"""
    if not content or not query:
        return 0.0

    content_lower = content.lower()
    query_terms = _extract_keywords(query)

    score = 0.0
    for term in query_terms:
        term_count = content_lower.count(term)
        if term_count > 0:
            # 简化的BM25计算
            score += term_count / (term_count + 1.5)  # 简化版本

    return min(score, 1.0)


def _analyze_query_intent(query: str) -> Dict[str, Any]:
    """分析查询意图"""
    query_lower = query.lower()
    intent = {
        "type": "general",  # general, synonym, definition, example, etc.
        "target_word": None,
        "confidence": 1.0
    }

    # 检测同义词查询
    synonym_patterns = [
        r'(.+?)的同义词',
        r'(.+?)的近义词',
        r'(.+?)的同类词',
        r'与(.+?)意思相近的词',
        r'synonyms? of (.+)',
        r'words similar to (.+)'
    ]

    for pattern in synonym_patterns:
        match = re.search(pattern, query_lower)
        if match:
            intent["type"] = "synonym"
            intent["target_word"] = match.group(1).strip()
            break

    # 检测定义查询
    definition_patterns = [
        r'(.+?)的意思',
        r'(.+?)的定义',
        r'什么是(.+?)',
        r'meaning of (.+)',
        r'definition of (.+)'
    ]

    if not intent["target_word"]:
        for pattern in definition_patterns:
            match = re.search(pattern, query_lower)
            if match:
                intent["type"] = "definition"
                intent["target_word"] = match.group(1).strip()
                break

    # 检测例句查询
    example_patterns = [
        r'(.+?)的例句',
        r'(.+?)的用法',
        r'example of (.+)',
        r'usage of (.+)'
    ]

    if not intent["target_word"]:
        for pattern in example_patterns:
            match = re.search(pattern, query_lower)
            if match:
                intent["type"] = "example"
                intent["target_word"] = match.group(1).strip()
                break

    # 如果没有匹配到特定模式，尝试提取核心词汇
    if not intent["target_word"]:
        # 提取可能的英文单词
        english_words = re.findall(r'\b[a-zA-Z]+\b', query)
        if english_words:
            # 取最长的英文单词作为目标词
            intent["target_word"] = max(english_words, key=len)

    return intent


def _adjust_score_by_intent(doc: Dict, intent: Dict[str, Any], base_score: float) -> float:
    """根据意图调整分数"""
    adjusted_score = base_score

    # 目标词匹配奖励
    if intent["target_word"] and intent["target_word"].lower() == doc.get("word", "").lower():
        adjusted_score += 0.3

    # 块类型匹配奖励
    if intent["type"] == "synonym" and doc.get("chunk_type") == "semantic_network":
        adjusted_score += 0.4
    elif intent["type"] == "definition" and doc.get("chunk_type") == "definition":
        adjusted_score += 0.4
    elif intent["type"] == "example" and doc.get("chunk_type") == "examples":
        adjusted_score += 0.4

    # 内容质量奖励
    content = doc.get("content", "")
    if intent["type"] == "synonym" and "同近义词" in content:
        adjusted_score += 0.2

    return min(adjusted_score, 1.0)


def _enhance_query_for_intent(query: str, intent: Dict[str, Any]) -> str:
    """根据意图增强查询"""
    if intent["type"] == "synonym" and intent["target_word"]:
        # 对于同义词查询，在查询中加入相关词汇
        return f"{query} 同义词 近义词 相似词 synonyms similar words"
    elif intent["type"] == "example" and intent["target_word"]:
        return f"{query} 例句 例子 用法 example usage"
    else:
        return query


def _adjust_strategy_weight_by_intent(strategy: str, intent: Dict[str, Any], base_weight: float) -> float:
    """根据意图调整策略权重"""
    adjusted_weight = base_weight

    # 对于同义词查询，提高精确匹配和意图感知的权重
    if intent["type"] == "synonym":
        if strategy in ["exact_match", "intention_aware"]:
            adjusted_weight *= 1.5
        elif strategy == "semantic":
            adjusted_weight *= 0.8  # 适当降低语义检索权重

    return adjusted_weight


def _detailed_rerank(query: str, candidates: List[Dict], intent: Dict[str, Any]) -> List[Dict]:
    """精细重排序"""
    for doc in candidates:
        rerank_score = 0.0

        # 1. 目标词匹配奖励
        if intent["target_word"] and intent["target_word"].lower() == doc.get("word", "").lower():
            rerank_score += 0.3

        # 2. 块类型匹配奖励
        if intent["type"] == "synonym" and doc.get("chunk_type") == "semantic_network":
            rerank_score += 0.4
        elif intent["type"] == "definition" and doc.get("chunk_type") == "definition":
            rerank_score += 0.4
        elif intent["type"] == "example" and doc.get("chunk_type") == "examples":
            rerank_score += 0.4

        # 3. 内容质量评估
        content = doc.get("content", "")
        if intent["type"] == "synonym":
            if "同近义词" in content:
                rerank_score += 0.2
            # 计算同义词数量
            synonym_count = content.count(":") if "同近义词" in content else 0
            rerank_score += min(synonym_count * 0.05, 0.1)

        # 4. 信息密度奖励（内容长度适中）
        content_length = len(content)
        if 50 <= content_length <= 500:  # 适中的长度
            rerank_score += 0.1
        elif content_length > 1000:  # 太长的内容可能包含无关信息
            rerank_score -= 0.1

        doc["fusion_score"] += rerank_score

    # 重新排序
    candidates.sort(key=lambda x: x["fusion_score"], reverse=True)
    return candidates


class Retriever:
    def __init__(self):
        self.milvus_client = MilvusDBClient()
        self.embedding_model = EmbeddingModel()
        # 配置多路召回策略
        # self.retrieval_strategies = {
        #     "semantic": {"weight": 0.6, "top_k": 10},
        #     "keyword_bm25": {"weight": 0.3, "top_k": 8},
        #     "exact_match": {"weight": 0.1, "top_k": 5},
        #     "metadata_filter": {"weight": 0.0, "top_k": 5}  # 可根据需要启用
        # }
        # 更细粒度的召回策略配置
        self.retrieval_strategies = {
            "semantic": {"weight": 0.4, "top_k": 8},
            "keyword_bm25": {"weight": 0.3, "top_k": 8},
            "intention_aware": {"weight": 0.1, "top_k": 5}
        }

    def retrieve_by_word(self, intent: Dict[str, Any]) -> List[List[dict]]:
        target_word = intent["target_word"]
        chunk_type = intent["chunk_type"]
        return self.milvus_client.search_by_word(target_word, chunk_type)

    def multi_way_retrieve(self, query: str, intent: Dict[str, Any], top_k: int = 10,
                           strategies: Optional[List[str]] = None) -> List[Dict[str, Any]]:

        if strategies is None:
            strategies = list(self.retrieval_strategies.keys())

        query_vector = self.embedding_model.encode(query)
        # 步骤1: 多路执行（根据意图调整策略）
        all_results = self._execute_intention_aware_retrieval(query_vector, strategies, intent)
        # 步骤2: 意图感知的结果融合
        fused_results = self._intention_aware_fusion(all_results, strategies, intent)
        # 步骤3: 精细重排序
        reranked_results = _detailed_rerank(query, fused_results[:top_k * 3], intent)

        return reranked_results[:top_k]

    def _execute_intention_aware_retrieval(self, query: str, strategies: List[str],
                                           intent: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """意图感知的多路召回执行"""
        results = {}

        for strategy in strategies:
            try:
                if strategy == "semantic":
                    results[strategy] = self._semantic_retrieval(query, intent,
                                                                 self.retrieval_strategies[strategy]["top_k"])
                elif strategy == "keyword_bm25":
                    results[strategy] = self._keyword_bm25_retrieval(query, intent,
                                                                     self.retrieval_strategies[strategy]["top_k"])
                elif strategy == "intention_aware":
                    results[strategy] = self._intention_specific_retrieval(query, intent,
                                                                           self.retrieval_strategies[strategy]["top_k"])
            except Exception as e:
                # logger.error(f"策略 '{strategy}' 执行失败: {e}")
                results[strategy] = []

        return results

    def _semantic_retrieval(self, query: str, intent: Dict[str, Any], top_k: int) -> List[Dict]:
        """语义向量召回"""
        # 根据意图调整查询
        enhanced_query = _enhance_query_for_intent(query, intent)

        query_vector = self.embedding_model.encode(enhanced_query)
        search_results = self.milvus_client.semantic_search(query_vector, top_k)

        formatted_results = []
        for hit in search_results[0]:  # 假设返回格式为 [hits]
            doc = {
                "id": hit.entity.get('id'),
                "content": hit.entity.get('content'),
                "word": hit.entity.get('word'),
                "chunk_type": hit.entity.get('chunk_type'),
                "score": hit.score,  # 向量相似度分数
                "strategy": "semantic"
            }

            # 根据意图调整分数
            doc["intention_adjusted_score"] = _adjust_score_by_intent(doc, intent, doc["semantic_score"])
            formatted_results.append(doc)

        return formatted_results

    def _keyword_bm25_retrieval(self, query: str, intent: Dict[str, Any], top_k: int) -> List[Dict]:
        """关键词BM25召回"""
        # 从查询中提取关键词
        # 提取关键词时考虑意图
        if intent["target_word"]:
            keywords = [intent["target_word"]]
        else:
            keywords = _extract_keywords(query)

        all_results = []
        for keyword in keywords[:5]:  # 限制关键词数量
            try:
                # 使用现有的search_by_word方法，但需要先转换为向量或使用其他方式
                # 这里假设我们有一个基于关键词的搜索方法
                results = self._search_by_keyword_intent(keyword, intent, top_k // len(keywords) + 1)
                all_results.extend(results)
            except Exception as e:
                # logger.warning(f"关键词 '{keyword}' 搜索失败: {e}")
                continue

        # 简单评分：基于关键词匹配程度
        for doc in all_results:
            doc["score"] = _calculate_bm25_score(doc["content"], query)
            doc["strategy"] = "keyword_bm25"

        # 去重并排序
        seen_ids = set()
        unique_results = []
        for doc in sorted(all_results, key=lambda x: x["score"], reverse=True):
            if doc["id"] not in seen_ids:
                seen_ids.add(doc["id"])
                unique_results.append(doc)

        return unique_results[:top_k]

    def _intention_specific_retrieval(self, query: str, intent: Dict[str, Any], top_k: int) -> List[Dict]:
        """意图特定的检索"""
        if not intent["target_word"]:
            return []

        try:
            # 专门针对同义词查询的检索
            if intent["type"] == "synonym":
                results = self.milvus_client.query(
                    filter=f'chunk_type == "semantic_network" and word == "{intent["target_word"]}"',
                    output_fields=["id", "content", "word", "chunk_type"],
                    limit=top_k
                )
            elif intent["type"] == "definition":
                results = self.milvus_client.query(
                    filter=f'chunk_type == "definition" and word == "{intent["target_word"]}"',
                    output_fields=["id", "content", "word", "chunk_type"],
                    limit=top_k
                )
            elif intent["type"] == "example":
                results = self.milvus_client.query(
                    filter=f'chunk_type == "examples" and word == "{intent["target_word"]}"',
                    output_fields=["id", "content", "word", "chunk_type"],
                    limit=top_k
                )
            else:
                return []

            formatted_results = []
            for result in results:
                doc = {
                    "id": result.get('id'),
                    "content": result.get('content'),
                    "word": result.get('word'),
                    "chunk_type": result.get('chunk_type'),
                    "score": 1.0,  # 意图特定检索给高分
                    "strategy": "intention_aware"
                }
                formatted_results.append(doc)

            return formatted_results
        except Exception as e:
            # logger.error(f"意图特定检索失败: {e}")
            return []

    def _intention_aware_fusion(self, all_results: Dict[str, List[Dict]],
                                strategies: List[str], intent: Dict[str, Any]) -> List[Dict]:
        """意图感知的结果融合"""
        k = 60  # RRF平滑参数

        # 为每个策略的结果分配排名，考虑意图权重
        ranked_results = {}
        for strategy in strategies:
            if strategy in all_results and all_results[strategy]:
                strategy_weight = self.retrieval_strategies[strategy]["weight"]

                # 根据意图调整策略权重
                adjusted_weight = _adjust_strategy_weight_by_intent(strategy, intent, strategy_weight)

                for rank, doc in enumerate(all_results[strategy]):
                    doc_id = doc["id"]
                    if doc_id not in ranked_results:
                        ranked_results[doc_id] = {
                            "doc": doc,
                            "scores": defaultdict(float)
                        }

                    # 计算调整后的RRF分数
                    rrf_score = 1 / (rank + k)
                    ranked_results[doc_id]["scores"][strategy] = rrf_score * adjusted_weight

        # 计算加权总分
        fused_docs = []
        for doc_id, data in ranked_results.items():
            total_score = sum(data["scores"].values())
            fused_doc = data["doc"].copy()
            fused_doc["fusion_score"] = total_score
            fused_doc["strategy_scores"] = dict(data["scores"])
            fused_docs.append(fused_doc)

        # 按融合分数排序
        fused_docs.sort(key=lambda x: x["fusion_score"], reverse=True)

        # logger.info(f"融合后共 {len(fused_docs)} 个文档")
        return fused_docs

    def _search_by_keyword_intent(self, keyword: str, intent: Dict[str, Any], limit: int) -> List[Dict]:
        """基于意图的关键词搜索"""
        try:
            # 根据意图构建不同的查询
            if intent["type"] == "synonym":
                # 专门搜索包含同义词的内容
                filter_condition = f'chunk_type == "semantic_network" and word == "{keyword}"'
            elif intent["type"] == "definition":
                filter_condition = f'chunk_type == "definition" and word == "{keyword}"'
            elif intent["type"] == "example":
                filter_condition = f'chunk_type == "examples" and word == "{keyword}"'
            else:
                filter_condition = f'word == "{keyword}"'

            results = self.milvus_client.query(
                filter=filter_condition,
                output_fields=["id", "content", "word", "chunk_type"],
                limit=limit
            )

            formatted_results = []
            for result in results:
                doc = {
                    "id": result.get('id'),
                    "content": result.get('content'),
                    "word": result.get('word'),
                    "chunk_type": result.get('chunk_type'),
                    "score": 0.8,  # 基础分数
                    "strategy": "keyword_bm25"
                }
                formatted_results.append(doc)
            return formatted_results
        except Exception as e:
            # logger.error(f"关键词搜索 '{keyword}' 失败: {e}")
            return []

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from pymilvus import DataType, MilvusClient

logger = logging.getLogger(__name__)


class MilvusQueryCacheStore:
    """基于 Milvus Lite 的问答缓存（按用户隔离）。"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        collection_name: str = "query_cache",
        vector_dim: int = 256,
    ):
        self.db_path = db_path or os.getenv(
            "CHAT_MILVUS_DB_PATH",
            os.path.join(os.getcwd(), "chat_history.db"),
        )
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self._lock = threading.Lock()
        self._enabled = True
        self.client: Optional[MilvusClient] = None

        try:
            self.client = MilvusClient(self.db_path)
            self._ensure_collection()
        except Exception as e:
            self._enabled = False
            logger.warning("MilvusQueryCacheStore 初始化失败，已禁用: %s", e)

    def enabled(self) -> bool:
        return self._enabled and self.client is not None

    def _ensure_collection(self) -> None:
        assert self.client is not None
        if self.client.has_collection(self.collection_name):
            self.client.load_collection(self.collection_name)
            return

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("cache_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("user_id", DataType.VARCHAR, max_length=128)
        schema.add_field("agent_key", DataType.VARCHAR, max_length=64)
        schema.add_field("query", DataType.VARCHAR, max_length=65535)
        schema.add_field("answer", DataType.VARCHAR, max_length=65535)
        schema.add_field("created_at", DataType.INT64)
        schema.add_field("updated_at", DataType.INT64)
        schema.add_field("hit_count", DataType.INT64)
        schema.add_field("meta_json", DataType.VARCHAR, max_length=65535)
        schema.add_field("query_vector", DataType.FLOAT_VECTOR, dim=self.vector_dim)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="query_vector", index_type="AUTOINDEX", metric_type="COSINE")
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        self.client.load_collection(self.collection_name)
        logger.info("MilvusQueryCacheStore collection created: %s", self.collection_name)

    @staticmethod
    def _escape_expr_literal(text: str) -> str:
        # Milvus filter 字符串字面量转义
        return str(text or "").replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _query_key(text: str) -> str:
        normalized = " ".join(MilvusQueryCacheStore._tokenize_for_hash(text))
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _tokenize_for_hash(text: str) -> List[str]:
        s = (text or "").strip().lower()
        if not s:
            return []
        tokens: List[str] = []
        # 英文词与数字
        tokens.extend(re.findall(r"[a-z0-9][a-z0-9_\-']*", s))
        # 中文字符与2-gram，增强中文问法改写的可匹配性
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", s)
        tokens.extend(cjk_chars)
        if len(cjk_chars) >= 2:
            tokens.extend("".join(cjk_chars[i : i + 2]) for i in range(len(cjk_chars) - 1))
        return tokens

    @staticmethod
    def embed_text_hash(text: str, dim: int = 256) -> List[float]:
        """
        轻量本地向量化：用 token 哈希到固定维度，再 L2 归一化。
        不依赖外部 embedding 服务，避免鉴权波动导致缓存不可用。
        """
        vec = [0.0] * dim
        tokens = MilvusQueryCacheStore._tokenize_for_hash(text)
        if not tokens:
            return vec
        for token in tokens:
            h = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], byteorder="big", signed=False) % dim
            sign = 1.0 if (h[4] % 2 == 0) else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm <= 1e-8:
            return vec
        return [v / norm for v in vec]

    def put(
        self,
        user_id: str,
        query: str,
        answer: str,
        agent_key: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled():
            return
        now = int(time.time())
        payload = {
            "cache_id": uuid.uuid4().hex,
            "user_id": str(user_id or "default"),
            "agent_key": str(agent_key or ""),
            "query": str(query or ""),
            "query_key": self._query_key(query or ""),
            "answer": str(answer or ""),
            "created_at": now,
            "updated_at": now,
            "hit_count": 0,
            "meta_json": json.dumps(meta or {}, ensure_ascii=False),
            "query_vector": self.embed_text_hash(query or "", self.vector_dim),
        }
        try:
            with self._lock:
                assert self.client is not None
                self.client.insert(collection_name=self.collection_name, data=[payload])
        except Exception as e:
            logger.warning("MilvusQueryCacheStore put 失败: %s", e)

    def search_similar(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        if not self.enabled():
            return []
        try:
            assert self.client is not None
            results = self.client.search(
                collection_name=self.collection_name,
                data=[self.embed_text_hash(query or "", self.vector_dim)],
                anns_field="query_vector",
                search_params={"metric_type": "COSINE"},
                filter=f'user_id == "{self._escape_expr_literal(str(user_id or "default"))}"',
                limit=max(1, int(top_k)),
                output_fields=[
                    "cache_id",
                    "user_id",
                    "agent_key",
                    "query",
                    "answer",
                    "created_at",
                    "updated_at",
                    "hit_count",
                    "meta_json",
                ],
            )
        except Exception as e:
            logger.warning("MilvusQueryCacheStore search 失败: %s", e)
            return []

        hits: List[Dict[str, Any]] = []
        for item in (results[0] if results else []):
            if not isinstance(item, dict):
                continue
            entity = item.get("entity")
            distance = item.get("distance", item.get("score", 0.0))
            if not isinstance(entity, dict):
                # 兼容 MilvusClient 直接平铺返回字段的结构
                entity = {
                    k: v
                    for k, v in item.items()
                    if k not in {"id", "distance", "score"}
                }
            meta_json = entity.get("meta_json", "{}")
            try:
                meta = json.loads(meta_json) if isinstance(meta_json, str) else {}
            except Exception:
                meta = {}
            hits.append(
                {
                    "cache_id": entity.get("cache_id"),
                    "user_id": entity.get("user_id"),
                    "agent_key": entity.get("agent_key", ""),
                    "query": entity.get("query", ""),
                    "answer": entity.get("answer", ""),
                    "created_at": entity.get("created_at"),
                    "updated_at": entity.get("updated_at"),
                    "hit_count": entity.get("hit_count", 0),
                    "meta": meta,
                    "score": float(distance or 0.0),
                }
            )
        return hits

    def get_exact(self, user_id: str, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        if not self.enabled():
            return []
        q_key = self._query_key(query or "")
        safe_user_id = self._escape_expr_literal(str(user_id or "default"))
        safe_query = self._escape_expr_literal(str(query or ""))
        try:
            assert self.client is not None
            rows = self.client.query(
                collection_name=self.collection_name,
                filter=f'user_id == "{safe_user_id}" and query_key == "{q_key}"',
                output_fields=[
                    "cache_id",
                    "user_id",
                    "agent_key",
                    "query",
                    "answer",
                    "created_at",
                    "updated_at",
                    "hit_count",
                    "meta_json",
                ],
                limit=max(1, int(limit)),
            )
            if not rows:
                # 兼容旧缓存（没有 query_key 字段）
                rows = self.client.query(
                    collection_name=self.collection_name,
                    filter=f'user_id == "{safe_user_id}" and query == "{safe_query}"',
                    output_fields=[
                        "cache_id",
                        "user_id",
                        "agent_key",
                        "query",
                        "answer",
                        "created_at",
                        "updated_at",
                        "hit_count",
                        "meta_json",
                    ],
                    limit=max(1, int(limit)),
                )
        except Exception as e:
            logger.warning("MilvusQueryCacheStore get_exact 失败: %s", e)
            return []

        hits: List[Dict[str, Any]] = []
        for row in rows:
            meta_json = row.get("meta_json", "{}")
            try:
                meta = json.loads(meta_json) if isinstance(meta_json, str) else {}
            except Exception:
                meta = {}
            hits.append(
                {
                    "cache_id": row.get("cache_id"),
                    "user_id": row.get("user_id"),
                    "agent_key": row.get("agent_key", ""),
                    "query": row.get("query", ""),
                    "answer": row.get("answer", ""),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "hit_count": row.get("hit_count", 0),
                    "meta": meta,
                    "score": 1.0,
                }
            )
        hits.sort(key=lambda x: int(x.get("updated_at") or x.get("created_at") or 0), reverse=True)
        return hits

    def touch(self, cache_id: str) -> None:
        if not self.enabled() or not cache_id:
            return
        try:
            assert self.client is not None
            rows = self.client.query(
                collection_name=self.collection_name,
                filter=f'cache_id == "{str(cache_id)}"',
                output_fields=[
                    "cache_id",
                    "user_id",
                    "agent_key",
                    "query",
                    "answer",
                    "created_at",
                    "updated_at",
                    "hit_count",
                    "meta_json",
                    "query_vector",
                ],
                limit=1,
            )
            if not rows:
                return
            row = rows[0]
            hit_count = int(row.get("hit_count", 0)) + 1
            self.client.upsert(
                collection_name=self.collection_name,
                data=[
                    {
                        "cache_id": str(cache_id),
                        "user_id": str(row.get("user_id", "default")),
                        "agent_key": str(row.get("agent_key", "")),
                        "query": str(row.get("query", "")),
                        "answer": str(row.get("answer", "")),
                        "created_at": int(row.get("created_at", int(time.time()))),
                        "meta_json": str(row.get("meta_json", "{}")),
                        "query_vector": row.get("query_vector") or self.embed_text_hash(str(row.get("query", "")), self.vector_dim),
                        "hit_count": hit_count,
                        "updated_at": int(time.time()),
                    }
                ],
            )
        except Exception as e:
            logger.warning("MilvusQueryCacheStore touch 失败: %s", e)

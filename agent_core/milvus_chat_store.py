import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from pymilvus import DataType, MilvusClient

logger = logging.getLogger(__name__)


class MilvusChatMessageStore:
    """
    使用 Milvus Lite 持久化聊天消息。
    说明：
    - Milvus 需要向量字段，这里使用固定占位向量，不参与语义检索。
    - 主要通过 session_id/user_id/created_at 做条件过滤与排序。
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        collection_name: str = "chat_messages",
        vector_dim: int = 16,
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
            logger.warning("MilvusChatMessageStore 初始化失败，已禁用: %s", e)

    def _ensure_collection(self) -> None:
        assert self.client is not None
        if self.client.has_collection(self.collection_name):
            self.client.load_collection(self.collection_name)
            return

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("message_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("session_id", DataType.VARCHAR, max_length=128)
        schema.add_field("user_id", DataType.VARCHAR, max_length=128)
        schema.add_field("role", DataType.VARCHAR, max_length=32)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("created_at", DataType.INT64)
        schema.add_field("turn_index", DataType.INT64)
        schema.add_field("agent_key", DataType.VARCHAR, max_length=64)
        schema.add_field("meta_json", DataType.VARCHAR, max_length=65535)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.vector_dim)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        self.client.load_collection(self.collection_name)
        logger.info("MilvusChatMessageStore collection created: %s", self.collection_name)

    def enabled(self) -> bool:
        return self._enabled and self.client is not None

    def append(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        turn_index: int,
        agent_key: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled():
            return
        payload = {
            "message_id": uuid.uuid4().hex,
            "session_id": str(session_id),
            "user_id": str(user_id or "default"),
            "role": str(role),
            "content": str(content or ""),
            "created_at": int(time.time()),
            "turn_index": int(turn_index),
            "agent_key": str(agent_key or ""),
            "meta_json": json.dumps(meta or {}, ensure_ascii=False),
            "vector": [0.0] * self.vector_dim,
        }
        try:
            with self._lock:
                assert self.client is not None
                self.client.insert(collection_name=self.collection_name, data=[payload])
        except Exception as e:
            logger.warning("MilvusChatMessageStore append 失败: %s", e)

    def get_session_messages(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        if not self.enabled():
            return []
        filters = [f'session_id == "{str(session_id)}"']
        if user_id:
            filters.append(f'user_id == "{str(user_id)}"')
        expr = " and ".join(filters)
        try:
            assert self.client is not None
            rows = self.client.query(
                collection_name=self.collection_name,
                filter=expr,
                output_fields=[
                    "message_id",
                    "session_id",
                    "user_id",
                    "role",
                    "content",
                    "created_at",
                    "turn_index",
                    "agent_key",
                    "meta_json",
                ],
                limit=max(1, int(limit)),
            )
        except Exception as e:
            logger.warning("MilvusChatMessageStore query 失败: %s", e)
            return []

        def _sort_key(x: Dict[str, Any]):
            return (int(x.get("turn_index", 0)), int(x.get("created_at", 0)))

        rows = sorted(rows, key=_sort_key)
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            meta_json = row.get("meta_json", "{}")
            try:
                meta = json.loads(meta_json) if isinstance(meta_json, str) else {}
            except Exception:
                meta = {}
            normalized.append(
                {
                    "message_id": row.get("message_id"),
                    "session_id": row.get("session_id"),
                    "user_id": row.get("user_id"),
                    "role": row.get("role"),
                    "content": row.get("content", ""),
                    "created_at": row.get("created_at"),
                    "turn_index": row.get("turn_index"),
                    "agent_key": row.get("agent_key", ""),
                    "meta": meta,
                }
            )
        return normalized

    def list_sessions(
        self,
        user_id: str,
        limit: int = 30,
        scan_limit: int = 3000,
    ) -> List[Dict[str, Any]]:
        if not self.enabled():
            return []
        expr = f'user_id == "{str(user_id)}"'
        try:
            assert self.client is not None
            rows = self.client.query(
                collection_name=self.collection_name,
                filter=expr,
                output_fields=[
                    "session_id",
                    "role",
                    "content",
                    "created_at",
                    "turn_index",
                    "agent_key",
                ],
                limit=max(1, int(scan_limit)),
            )
        except Exception as e:
            logger.warning("MilvusChatMessageStore list_sessions 失败: %s", e)
            return []

        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sid = str(row.get("session_id") or "").strip()
            if not sid:
                continue
            created_at = int(row.get("created_at") or 0)
            turn_index = int(row.get("turn_index") or 0)
            sort_key = (turn_index, created_at)
            item = grouped.get(sid)
            if item is None:
                grouped[sid] = {
                    "session_id": sid,
                    "message_count": 1,
                    "last_created_at": created_at,
                    "last_turn_index": turn_index,
                    "last_role": row.get("role", ""),
                    "last_agent_key": row.get("agent_key", ""),
                    "last_preview": str(row.get("content", ""))[:120],
                    "_sort_key": sort_key,
                }
            else:
                item["message_count"] += 1
                if sort_key >= item.get("_sort_key", (0, 0)):
                    item["_sort_key"] = sort_key
                    item["last_created_at"] = created_at
                    item["last_turn_index"] = turn_index
                    item["last_role"] = row.get("role", "")
                    item["last_agent_key"] = row.get("agent_key", "")
                    item["last_preview"] = str(row.get("content", ""))[:120]

        sessions = list(grouped.values())
        sessions.sort(key=lambda x: (int(x.get("last_created_at", 0)), int(x.get("last_turn_index", 0))), reverse=True)
        sessions = sessions[: max(1, int(limit))]
        for s in sessions:
            s.pop("_sort_key", None)
        return sessions

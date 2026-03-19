import json
import logging
import os
from typing import Dict, List, Optional

import redis

logger = logging.getLogger(__name__)


class RedisHistoryStore:
    _fallback_store: Dict[str, List[Dict[str, str]]] = {}

    def __init__(self, max_turns: int = 20, ttl_seconds: int = 86400):
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = None
        try:
            client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            client.ping()
            self.redis = client
        except Exception as e:
            logger.warning("RedisHistoryStore 使用内存降级模式: %s", e)
        self.key_prefix: str = "chat:history:"
        self.max_items = max_turns * 2
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"
    
    def append(self, session_id: str, role: str, content: str) -> None:
        if self.redis is None:
            key = self._key(session_id)
            rows = self._fallback_store.setdefault(key, [])
            rows.append({"role": role, "content": content})
            if len(rows) > self.max_items:
                del rows[0 : len(rows) - self.max_items]
            return

        key = self._key(session_id)
        item = json.dumps({"role": role, "content": content}, ensure_ascii=False)

        pipe = self.redis.pipeline()
        pipe.lpush(key, item)
        pipe.ltrim(key, 0, self.max_items - 1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        if self.redis is None:
            return list(self._fallback_store.get(self._key(session_id), []))

        key = self._key(session_id)
        raw_items = self.redis.lrange(key, 0, -1)
        items = [json.loads(x) for x in reversed(raw_items)]
        return items
    
    def clear(self, session_id: str) -> None:
        if self.redis is None:
            self._fallback_store.pop(self._key(session_id), None)
            return
        self.redis.delete(self._key(session_id))


class RedisSummaryStore:
    _fallback_summary: Dict[str, str] = {}

    def __init__(self, ttl_seconds: int = 7 * 86400):
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = None
        try:
            client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            client.ping()
            self.redis = client
        except Exception as e:
            logger.warning("RedisSummaryStore 使用内存降级模式: %s", e)
        self.key_prefix: str = "chat:summary:"
        self.ttl_seconds: int = ttl_seconds

    def _key(self, session_id: str, scope: str) -> str:
        return f"{self.key_prefix}{scope}{session_id}"

    def get(self, session_id: str, scope: str = "global") -> str:
        if self.redis is None:
            return self._fallback_summary.get(self._key(session_id, scope), "")
        return self.redis.get(self._key(session_id, scope)) or ""
    
    def set(self, session_id: str, summary: str, scope: str = "global") -> str:
        key = self._key(session_id, scope)
        if self.redis is None:
            self._fallback_summary[key] = summary
            return
        self.redis.set(key, summary)
        self.redis.expire(key, self.ttl_seconds)

    def clear(self, session_id: str, scope: Optional[str] = None):
        if self.redis is None:
            if scope:
                self._fallback_summary.pop(self._key(session_id, scope), None)
            else:
                for s in ["global", "writing", "speaking", "reading", "listening"]:
                    self._fallback_summary.pop(self._key(session_id, s), None)
            return
        if scope:
            self.redis.delete(self._key(session_id, scope))
        else:
            # 清除所有 scope（谨慎使用）
            for s in ["global", "writing", "speaking", "reading", "listening"]:
                self.redis.delete(self._key(session_id, s))

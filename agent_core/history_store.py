import json
from typing import Dict, List, Optional

import redis


class RedisHistoryStore:
    def __init__(self, max_turns: int = 20, ttl_seconds: int = 86400):
        self.redis_url: str = "redis://localhost:6379/0"
        self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
        self.key_prefix: str = "chat:history:"
        self.max_items = max_turns * 2
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"
    
    def append(self, session_id: str, role: str, content: str) -> None:
        key = self._key(session_id)
        item = json.dumps({"role": role, "content": content}, ensure_ascii=False)

        pipe = self.redis.pipeline()
        pipe.lpush(key, item)
        pipe.ltrim(key, 0, self.max_items - 1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        key = self._key(session_id)
        raw_items = self.redis.lrange(key, 0, -1)
        items = [json.loads(x) for x in reversed(raw_items)]
        return items
    
    def clear(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))


class RedisSummaryStore:
    def __init__(self, ttl_seconds: int = 7 * 86400):
        self.redis_url: str = "redis://localhost:6379/0"
        self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
        self.key_prefix: str = "chat:summary:"
        self.ttl_seconds: int = ttl_seconds

    def _key(self, session_id: str, scope: str) -> str:
        return f"{self.key_prefix}{scope}{session_id}"

    def get(self, session_id: str, scope: str = "global") -> str:
        return self.redis.get(self._key(session_id, scope)) or ""
    
    def set(self, session_id: str, summary: str, scope: str = "global") -> str:
        key = self._key(session_id, scope)
        self.redis.set(key, summary)
        self.redis.expire(key, self.ttl_seconds)

    def clear(self, session_id: str, scope: Optional[str] = None):
        if scope:
            self.redis.delete(self._key(session_id, scope))
        else:
            # 清除所有 scope（谨慎使用）
            for s in ["global", "writing", "speaking", "reading", "listening"]:
                self.redis.delete(self._key(session_id, s))

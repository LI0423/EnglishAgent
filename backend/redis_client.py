import os
from typing import Optional

_memory_store = {}

_redis = None
_redis_err = None
REDIS_URL = os.environ.get("REDIS_URL")

if REDIS_URL:
    try:
        import redis  # type: ignore
        _redis = redis.Redis.from_url(REDIS_URL)
        _redis.ping()
    except Exception as e:
        _redis = None
        _redis_err = e


def save_token(user_id: str, token: str, ttl: int = 3600) -> None:
    if _redis is not None:
        _redis.setex(f"auth:token:{token}", ttl, user_id)
    else:
        _memory_store[token] = (user_id, ttl)


def get_user_by_token(token: str) -> Optional[str]:
    if _redis is not None:
        v = _redis.get(f"auth:token:{token}")
        return v.decode() if v else None
    tup = _memory_store.get(token)
    return tup[0] if tup else None



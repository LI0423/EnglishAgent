import os
import threading
import time
from typing import Optional

# 未配置 / 连不上 Redis 时的进程内降级存储。
# 注意：它是单进程内存，uvicorn --workers>1 或多实例部署下各进程状态不共享，
# 仅适用于单进程开发/小规模部署；生产多副本请确保 Redis 可用。
_memory_store = {}
_timed_memory_store = {}

_redis = None
_redis_err = None
_redis_last_attempt = 0.0
_redis_lock = threading.Lock()
REDIS_URL = os.environ.get("REDIS_URL")
_REDIS_RETRY_INTERVAL = 30.0


def _connect_redis():
    global _redis, _redis_err
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        _redis = client
        _redis_err = None
    except Exception as e:
        _redis = None
        _redis_err = e
    return _redis


def _get_redis():
    """返回可用的 Redis 客户端；不可用时按固定间隔重试，避免启动瞬时故障后永久降级。"""
    global _redis_last_attempt
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        return None
    if time.time() - _redis_last_attempt < _REDIS_RETRY_INTERVAL:
        return None
    with _redis_lock:
        if _redis is not None:
            return _redis
        if time.time() - _redis_last_attempt < _REDIS_RETRY_INTERVAL:
            return None
        _redis_last_attempt = time.time()
        return _connect_redis()


def _as_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def save_token(user_id: str, token: str, ttl: int = 3600) -> None:
    client = _get_redis()
    if client is not None:
        client.setex(f"auth:token:{token}", ttl, user_id)
    else:
        _memory_store[token] = (user_id, ttl)


def get_user_by_token(token: str) -> Optional[str]:
    client = _get_redis()
    if client is not None:
        return _as_text(client.get(f"auth:token:{token}"))
    tup = _memory_store.get(token)
    return tup[0] if tup else None


def set_timed_state(key: str, value: str, ttl: int) -> None:
    safe_ttl = max(1, int(ttl or 1))
    client = _get_redis()
    if client is not None:
        client.setex(key, safe_ttl, value)
        return
    _timed_memory_store[key] = (value, time.time() + safe_ttl)


def get_timed_state(key: str) -> Optional[str]:
    client = _get_redis()
    if client is not None:
        return _as_text(client.get(key))
    item = _timed_memory_store.get(key)
    if not item:
        return None
    value, expires_at = item
    if time.time() >= float(expires_at):
        _timed_memory_store.pop(key, None)
        return None
    return str(value)


def clear_timed_state(key: str) -> None:
    client = _get_redis()
    if client is not None:
        client.delete(key)
        return
    _timed_memory_store.pop(key, None)

"""Token-bucket / fixed-window rate limiting backed by Redis.

Falls back to an in-memory dict when Redis is unavailable so local dev without
Redis still works (rate limits are best-effort, not a hard security boundary in
that mode).
"""
from __future__ import annotations

import time
from typing import Optional

import redis as redis_lib

from ..config import settings

_redis: Optional[redis_lib.Redis] = None
_mem: dict[str, list[float]] = {}


def _client() -> Optional[redis_lib.Redis]:
    global _redis
    if _redis is not None:
        return _redis if _redis is not False else None
    try:
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        return _redis
    except Exception:
        _redis = False  # type: ignore[assignment]
        return None


def hit_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if the caller has exceeded `limit` hits in the rolling window."""
    now = time.time()
    cutoff = now - window_seconds
    client = _client()
    if client is not None:
        pipe = client.pipeline()
        full = f"rl:{key}"
        pipe.zremrangebyscore(full, 0, cutoff)
        pipe.zadd(full, {str(now): now})
        pipe.zcount(full, cutoff, now)
        pipe.expire(full, window_seconds + 5)
        results = pipe.execute()
        count = int(results[2]) if results else 0
        return count > limit
    # in-memory fallback
    bucket = _mem.setdefault(key, [])
    bucket[:] = [t for t in bucket if t > cutoff]
    bucket.append(now)
    return len(bucket) > limit


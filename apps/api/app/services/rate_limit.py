from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock

from app.core.config import get_settings
from app.services.errors import DomainError

logger = logging.getLogger(__name__)
settings = get_settings()

_memory_hits: dict[str, deque[float]] = defaultdict(deque)
_memory_lock = Lock()


class RateLimitExceeded(DomainError):
    status_code = 429

    def __init__(self, message: str = "Demasiadas solicitudes. Inténtalo de nuevo en un momento.") -> None:
        super().__init__(message, 429)


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    if limit <= 0 or window_seconds <= 0:
        return
    if _check_redis(key, limit=limit, window_seconds=window_seconds):
        return
    _check_memory(key, limit=limit, window_seconds=window_seconds)


def _check_redis(key: str, *, limit: int, window_seconds: int) -> bool:
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        bucket = f"qd:rl:{key}"
        pipe = client.pipeline()
        now = time.time()
        pipe.zremrangebyscore(bucket, 0, now - window_seconds)
        pipe.zadd(bucket, {f"{now}": now})
        pipe.zcard(bucket)
        pipe.expire(bucket, window_seconds + 1)
        _, _, count, _ = pipe.execute()
        if int(count) > limit:
            raise RateLimitExceeded()
        return True
    except RateLimitExceeded:
        raise
    except Exception:
        logger.debug("Rate limit redis unavailable; using memory fallback", exc_info=True)
        return False


def _check_memory(key: str, *, limit: int, window_seconds: int) -> None:
    now = time.time()
    with _memory_lock:
        hits = _memory_hits[key]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimitExceeded()
        hits.append(now)

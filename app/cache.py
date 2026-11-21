"""Thin Redis wrapper.

Every call is best-effort: if Redis is slow or down we log and return a
"miss", so the API keeps serving from Postgres instead of returning 500s.
"""
import logging

import redis

from app.config import settings

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, client: redis.Redis, enabled: bool = True):
        self.client = client
        self.enabled = enabled

    def get(self, key: str) -> str | None:
        if not self.enabled:
            return None
        try:
            return self.client.get(key)
        except redis.RedisError as exc:
            log.warning("cache get failed for %s: %s", key, exc)
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        if not self.enabled or ttl <= 0:
            return
        try:
            self.client.set(key, value, ex=ttl)
        except redis.RedisError as exc:
            log.warning("cache set failed for %s: %s", key, exc)

    def delete(self, key: str) -> None:
        if not self.enabled:
            return
        try:
            self.client.delete(key)
        except redis.RedisError as exc:
            log.warning("cache delete failed for %s: %s", key, exc)

    def incr(self, key: str) -> None:
        try:
            self.client.incr(key)
        except redis.RedisError as exc:
            log.warning("counter incr failed for %s: %s", key, exc)

    def get_int(self, key: str) -> int:
        try:
            return int(self.client.get(key) or 0)
        except redis.RedisError as exc:
            log.warning("counter read failed for %s: %s", key, exc)
            return 0

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False


cache = Cache(
    redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
    ),
    enabled=settings.CACHE_ENABLED,
)

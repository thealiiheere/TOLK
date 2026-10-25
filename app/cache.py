"""Optional Redis cache (best effort).

Nothing breaks without Redis: when REDIS_URL is empty or Redis is down, reads are misses and writes are skipped,
so callers never need a try/except. Values are stored as JSON under keys prefixed with "tolk:".
Check the connection on a server: python -m app.test_redis
"""
import json
import logging
from typing import Any

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.config import settings

log = logging.getLogger("tolk.cache")
PREFIX = "tolk:"
_client: redis.Redis | None = None


def client() -> redis.Redis | None:
    """The shared client, or None when REDIS_URL is empty. Connects lazily on the first command."""
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        # Short timeouts and one immediate retry (reconnects after a Redis restart): a slow or missing cache
        # must never hold up a request. The library defaults are 5 s timeouts and backed-off retries.
        _client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5,
            retry=Retry(NoBackoff(), 1), health_check_interval=30,
        )
    return _client


def get_json(key: str) -> Any | None:
    """Cached value for `key`, or None (missing, expired, cache off or Redis unavailable)."""
    c = client()
    if c is None:
        return None
    try:
        raw = c.get(PREFIX + key)
        return None if raw is None else json.loads(raw)
    except (redis.RedisError, ValueError) as e:
        log.warning("cache get %s failed: %s", key, e)
        return None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """Store a JSON-serialisable value for `ttl` seconds (default CACHE_TTL)."""
    c = client()
    if c is None:
        return
    try:
        c.set(PREFIX + key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), ex=ttl or settings.cache_ttl)
    except redis.RedisError as e:
        log.warning("cache set %s failed: %s", key, e)


def delete(*keys: str) -> None:
    """Drop cached values, e.g. after the data behind them changed."""
    c = client()
    if c is None or not keys:
        return
    try:
        c.delete(*(PREFIX + k for k in keys))
    except redis.RedisError as e:
        log.warning("cache delete %s failed: %s", ", ".join(keys), e)


def status() -> str:
    """"ok", "off" (no REDIS_URL) or "unavailable"; reported by /health."""
    c = client()
    if c is None:
        return "off"
    try:
        c.ping()
        return "ok"
    except redis.RedisError:
        return "unavailable"

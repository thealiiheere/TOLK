"""Optional Redis cache (best effort).

Nothing breaks without Redis: when REDIS_URL is empty or Redis is down, reads are misses and writes are skipped,
so callers never need a try/except. Values are stored as JSON under keys prefixed with "tolk:".
Cached today: the public catalog (cached(catalog_key(...))) and the admin overview (STATS_KEY). Both are forgotten
automatically after every committed database change that can affect them (session events at the bottom).
Check the connection on a server: python -m app.test_redis
"""
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from sqlalchemy import event, inspect

from app.config import settings
from app.database import SessionLocal
from app.models import Enrollment, Group, Lesson, LessonRating, Payment, User

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


def cached(key: str, ttl: int, compute: Callable[[], Any]) -> Any:
    """The cached value for `key`, or compute() stored for `ttl` seconds. Falls back to compute() without Redis."""
    hit = get_json(key)
    if hit is not None:
        return hit
    value = compute()
    if value is not None:  # "not found" answers aren't cached
        set_json(key, value, ttl)
    return value


# ---------- what is cached, and when it is forgotten ----------
# Public catalog answers (same for every visitor and language) live under a version number: any committed change
# that can alter them bumps the version, so all old entries are ignored at once and expire on their own.
# The admin overview is one key, deleted on any change to what it counts. TTLs are only a safety net
# (time also changes "upcoming lessons" without any write).
CATALOG_TTL = 300
STATS_TTL = 60
STATS_KEY = "admin:stats"
_VERSION_KEY = "catalog:version"


def catalog_key(*parts: Any) -> str:
    """Key for a catalog answer at the current catalog version; long parts (search text) are hashed."""
    raw = "|".join("" if p is None else str(p) for p in parts)
    if len(raw) > 80:
        raw = hashlib.sha1(raw.encode()).hexdigest()
    c = client()
    try:
        version = (c.get(PREFIX + _VERSION_KEY) if c else None) or 0
    except redis.RedisError:
        version = 0
    return f"catalog:v{version}:{raw}"


def forget_catalog() -> None:
    c = client()
    if c is None:
        return
    try:
        c.incr(PREFIX + _VERSION_KEY)
    except redis.RedisError as e:
        log.warning("catalog cache bump failed: %s", e)


def _class_scopes(cls: type) -> set[str]:
    """Which caches a change to rows of this model can affect."""
    if issubclass(cls, (Group, Enrollment, LessonRating, User)):
        return {"catalog", "stats"}
    if issubclass(cls, (Payment, Lesson)):
        return {"stats"}
    return set()


def _scopes(obj: Any) -> set[str]:
    if isinstance(obj, User):
        # Teachers appear in the catalog (name, photo, bio, approval, blocking); everyone else only in the counts,
        # so a student signing in doesn't throw the catalog cache away.
        role = inspect(obj).attrs.role.history
        was_tutor = obj.role == "tutor" or "tutor" in (role.deleted or ())
        return {"catalog", "stats"} if was_tutor else {"stats"}
    return _class_scopes(type(obj))


@event.listens_for(SessionLocal, "before_flush")
def _collect_changes(session, _flush_context, _instances):
    touched = session.info.setdefault("cache_scopes", set())
    dirty = (o for o in session.dirty if session.is_modified(o, include_collections=False))
    for obj in (*session.new, *session.deleted, *dirty):
        touched |= _scopes(obj)


@event.listens_for(SessionLocal, "do_orm_execute")
def _collect_bulk_changes(state):
    # db.execute(update(...)) / db.execute(delete(...)) skip the flush events
    if (state.is_update or state.is_delete) and state.bind_mapper is not None:
        state.session.info.setdefault("cache_scopes", set()).update(_class_scopes(state.bind_mapper.class_))


@event.listens_for(SessionLocal, "after_commit")
def _forget_changed(session):
    touched = session.info.pop("cache_scopes", set())
    if "catalog" in touched:
        forget_catalog()
    if "stats" in touched:
        delete(STATS_KEY)


@event.listens_for(SessionLocal, "after_rollback")
def _drop_changes(session):
    session.info.pop("cache_scopes", None)

"""Rate limits in Redis (fixed windows). Over the limit → 429 `too_many_requests` with a Retry-After header.

Sign-ins are counted per IP address (uvicorn takes the real one from nginx's X-Forwarded-For, see the systemd unit),
uploads and submissions per signed-in user. Every attempt counts, failed ones included: that is what stops guessing
and spam. Without Redis (REDIS_URL empty or Redis down) nothing is limited: the app keeps working.
"""
import logging
import math
import time

import redis
from fastapi import Request

from app import cache
from app.i18n import ApiError

log = logging.getLogger("tolk.ratelimit")

# name: (attempts allowed, window in seconds). Generous for real people, tight for scripts.
LIMITS: dict[str, tuple[int, int]] = {
    "signin": (30, 600),  # per IP: Telegram / widget / demo sign-ins (opening the Mini App signs in once)
    "enroll": (10, 3600),  # per user: payment receipt uploads (each one notifies every admin)
    "onboarding": (10, 3600),  # per user: sign-up form with certificates
    "documents": (20, 3600),  # per user: teacher certificate uploads
    "homework": (60, 3600),  # per user: homework submissions
}


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check(name: str, who: str | int) -> None:
    """Count one attempt for `who`; raise 429 when the window's limit is exceeded."""
    limit, window = LIMITS[name]
    c = cache.client()
    if c is None:
        return
    now = int(time.time())
    slot = now // window
    key = f"{cache.PREFIX}rl:{name}:{who}:{slot}"
    try:
        pipe = c.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        count = pipe.execute()[0]
    except redis.RedisError as e:
        log.warning("rate limit %s not checked: %s", name, e)
        return
    if count > limit:
        wait = (slot + 1) * window - now
        log.info("rate limit %s hit by %s (%d/%d)", name, who, count, limit)
        raise ApiError("too_many_requests", 429, headers={"Retry-After": str(wait)}, minutes=max(1, math.ceil(wait / 60)))

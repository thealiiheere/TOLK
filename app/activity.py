"""Who used the app on which day ("active users" on the admin overview).

record(user_id) runs on every authenticated request but writes at most once per user per UTC day and process:
a small in-memory note skips the database for the rest of the day, and a second worker that also writes is
ignored by the database (insert … on conflict do nothing). It uses its own short connection, so it never mixes
with the request's transaction, and it never raises: losing one activity mark must not fail a request.
These writes skip the session events in app/cache.py on purpose; the cached overview catches up within its TTL.
"""
import logging
from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import engine
from app.models import UserActivity, utcnow

log = logging.getLogger("tolk.activity")
_recorded: dict[int, date] = {}  # user id -> last UTC day already written by this process


def record(user_id: int) -> None:
    now = utcnow()
    today = now.date()
    if _recorded.get(user_id) == today:
        return
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(UserActivity).values(user_id=user_id, day=today, seen_at=now).on_conflict_do_nothing()
    try:
        with engine.begin() as conn:
            conn.execute(stmt)
        _recorded[user_id] = today
    except Exception as e:  # noqa: BLE001 - best effort by design
        log.warning("activity for user %s not recorded: %s", user_id, e)

"""Numbers for the admin overview: revenue, active users, new users and enrollments per day / week / month / year.

Periods are calendar periods in the admin's own time zone (the browser sends its UTC offset), e.g. "month, 1 back"
= the whole previous calendar month there. Every number is computed for a row of periods (the bar chart) plus the
period before the selected one (the "vs last month" comparison), with one query per number: each period is a
CASE column, so the database does the bucketing and no rows are loaded into Python.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session as DbSession, selectinload

from app.models import Enrollment, Group, Payment, User, UserActivity, utcnow
from app.services import iso

PERIODS = ("day", "week", "month", "year")
BARS = {"day": 7, "week": 8, "month": 6, "year": 5}  # how many periods the chart shows
METRICS = ("revenue", "active_users", "new_users", "enrollments")


def _start_of(local: datetime, period: str) -> datetime:
    d = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return d - timedelta(days=d.weekday())  # weeks start on Monday
    if period == "month":
        return d.replace(day=1)
    if period == "year":
        return d.replace(month=1, day=1)
    return d


def _step(start: datetime, period: str, n: int) -> datetime:
    """`start` moved `n` whole periods forward (negative = back)."""
    if period == "day":
        return start + timedelta(days=n)
    if period == "week":
        return start + timedelta(weeks=n)
    if period == "month":
        m = start.year * 12 + start.month - 1 + n
        return start.replace(year=m // 12, month=m % 12 + 1)
    return start.replace(year=start.year + n)


def period_bounds(period: str, back: int, tz_offset: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    """UTC [start, end) of the period `back` steps before the current one.

    `tz_offset` is JavaScript's Date.getTimezoneOffset(): minutes to add to local time to get UTC (Tashkent = -300).
    """
    shift = timedelta(minutes=tz_offset)
    local_now = ((now or utcnow()) - shift).replace(tzinfo=None)
    current = _start_of(local_now, period)
    start, end = _step(current, period, -back), _step(current, period, 1 - back)
    return (start + shift).replace(tzinfo=timezone.utc), (end + shift).replace(tzinfo=timezone.utc)


def _per_period(db: DbSession, ts, value, bounds: list[tuple[datetime, datetime]], *where) -> list[int]:
    """SUM(value) of rows whose timestamp `ts` falls in each [start, end), one CASE column per period."""
    cols = [func.coalesce(func.sum(case((and_(ts >= s, ts < e), value), else_=0)), 0) for s, e in bounds]
    lo, hi = min(s for s, _ in bounds), max(e for _, e in bounds)
    return [int(v or 0) for v in db.execute(select(*cols).where(*where, ts >= lo, ts < hi)).one()]


def _distinct_users_per_period(db: DbSession, bounds: list[tuple[datetime, datetime]]) -> list[int]:
    ts = UserActivity.seen_at
    cols = [func.count(func.distinct(case((and_(ts >= s, ts < e), UserActivity.user_id), else_=None))) for s, e in bounds]
    lo, hi = min(s for s, _ in bounds), max(e for _, e in bounds)
    return [int(v or 0) for v in db.execute(select(*cols).where(ts >= lo, ts < hi)).one()]


def overview(db: DbSession, period: str, back: int, tz_offset: int) -> dict:
    bars = BARS[period]
    # The chart ends at the current period while the selected one is on it, else at the selected one.
    first = 0 if back < bars else back
    shown = list(range(first + bars - 1, first - 1, -1))  # oldest -> newest
    backs = sorted(set(shown) | {back, back + 1})
    bounds = [period_bounds(period, b, tz_offset) for b in backs]

    columns = {
        "revenue": _per_period(db, Payment.reviewed_at, Payment.amount, bounds, Payment.status == "approved"),
        "active_users": _distinct_users_per_period(db, bounds),
        "new_users": _per_period(db, User.created_at, 1, bounds),
        "enrollments": _per_period(db, Enrollment.joined_at, 1, bounds),
    }
    by_back = {
        b: {"back": b, "start": iso(s), "end": iso(e), **{m: columns[m][i] for m in METRICS}}
        for i, (b, (s, e)) in enumerate(zip(backs, bounds))
    }

    published = db.execute(
        select(func.count(), func.coalesce(func.sum(Group.max_students), 0)).where(Group.is_published.is_(True))
    ).one()
    taken = db.scalar(
        select(func.count()).select_from(Enrollment).join(Group).where(Group.is_published.is_(True))
    )
    return {
        "period": period,
        "back": back,
        "current": by_back[back],
        "previous": by_back[back + 1],
        "bars": [by_back[b] for b in shown],
        "seats": {"classes": int(published[0]), "total": int(published[1] or 0), "taken": int(taken or 0)},
        "recent_payments": recent_payments(db),
    }


def recent_payments(db: DbSession, limit: int = 6) -> list[dict]:
    rows = db.scalars(
        select(Payment).options(selectinload(Payment.student), selectinload(Payment.group))
        .order_by(Payment.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": p.id,
            "amount": p.amount,
            "status": p.status,
            "created_at": iso(p.created_at),
            "student": {"id": p.student.id, "full_name": p.student.full_name},
            "group": {
                "id": p.group.id, "code": p.group.code, "title": p.group.title, "category": p.group.category,
                "subject": p.group.subject,
                "poster_url": f"/api/catalog/posters/{p.group.poster}" if p.group.poster else None,
            } if p.group else None,
        }
        for p in rows
    ]

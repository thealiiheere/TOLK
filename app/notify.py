"""Best-effort Telegram notifications sent by the bot to users (run via FastAPI BackgroundTasks).

Failures are logged and swallowed: a notification must never break the API request.
"""
import html
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.i18n import t

log = logging.getLogger("tolk.notify")


def _send(chat_id: int, text: str, lang: str) -> None:
    if not settings.telegram_bot_token or not chat_id:
        return
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if settings.tolk_webapp_url.startswith("https://"):
        payload["reply_markup"] = {"inline_keyboard": [[{
            "text": t("open_app", lang),
            "web_app": {"url": settings.tolk_webapp_url},
        }]]}
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload, timeout=8,
        )
    except httpx.HTTPError as exc:
        log.warning("Telegram notification to %s failed: %s", chat_id, exc)


def format_when(dt: datetime, lang: str) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        local = dt.astimezone(ZoneInfo(settings.timezone))
    except Exception:
        local = dt
    return local.strftime("%d.%m.%Y %H:%M")


def notify(recipients: list[tuple[int | None, str]], key: str, **params) -> None:
    """recipients: list of (telegram_id, lang). Params are HTML-escaped; datetimes are formatted per language."""
    for chat_id, lang in recipients:
        if not chat_id:
            continue
        values = {}
        for name, value in params.items():
            if isinstance(value, datetime):
                value = format_when(value, lang)
            values[name] = html.escape(str(value))
        _send(chat_id, t(key, lang, **values), lang)

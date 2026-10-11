"""TOLK Telegram bot: opens the Mini App. Runs as its own process (long polling, no inbound ports needed).

    python telegram_bot.py

Needs TELEGRAM_BOT_TOKEN and TOLK_WEBAPP_URL (your public https domain) in .env.
Notifications (payments, lessons, ratings) are sent by the web app itself via app/notify.py.
"""
import html
import logging
import sys
import time

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.i18n import normalize_lang, t
from app.models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s bot: %(message)s")
log = logging.getLogger("tolk.bot")

API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
COMMANDS = {
    "uz": [("start", "TOLK ni ochish")],
    "ru": [("start", "Открыть TOLK")],
    "en": [("start", "Open TOLK")],
}


def call(client: httpx.Client, method: str, **payload):
    resp = client.post(f"{API}/{method}", json=payload, timeout=40)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data.get('description')}")
    return data["result"]


def user_lang(tg_user: dict) -> str:
    with SessionLocal() as db:
        saved = db.scalar(select(User.lang).where(User.telegram_id == tg_user.get("id")))
    return saved or normalize_lang(tg_user.get("language_code"))


def send_welcome(client: httpx.Client, chat_id: int, tg_user: dict) -> None:
    lang = user_lang(tg_user)
    name = tg_user.get("first_name") or "👋"
    call(
        client, "sendMessage",
        chat_id=chat_id,
        text=t("bot_welcome", lang, name=html.escape(name)),
        parse_mode="HTML",
        reply_markup={"inline_keyboard": [[{"text": "🎓 " + t("open_app", lang), "web_app": {"url": settings.tolk_webapp_url}}]]},
    )


def setup(client: httpx.Client) -> None:
    me = call(client, "getMe")
    log.info("Authorized as @%s", me["username"])
    if settings.telegram_bot_username and settings.telegram_bot_username.lstrip("@") != me["username"]:
        log.warning("TELEGRAM_BOT_USERNAME (%s) does not match the token's bot (@%s)",
                    settings.telegram_bot_username, me["username"])
    call(client, "deleteWebhook", drop_pending_updates=False)  # polling and webhooks are mutually exclusive
    call(client, "setChatMenuButton", menu_button={
        "type": "web_app", "text": "TOLK", "web_app": {"url": settings.tolk_webapp_url},
    })
    for lang, cmds in COMMANDS.items():
        call(client, "setMyCommands", commands=[{"command": c, "description": d} for c, d in cmds],
             **({} if lang == "uz" else {"language_code": lang}))


def run() -> None:
    if not settings.telegram_bot_token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set")
    if not settings.tolk_webapp_url.startswith("https://"):
        sys.exit("TOLK_WEBAPP_URL must be your public https:// address (Telegram requires HTTPS for Mini Apps)")

    with httpx.Client() as client:
        setup(client)
        offset = 0
        log.info("Polling for updates...")
        while True:
            try:
                updates = call(client, "getUpdates", offset=offset, timeout=30, allowed_updates=["message"])
                for update in updates:
                    offset = update["update_id"] + 1
                    msg = update.get("message") or {}
                    if msg.get("chat", {}).get("type") == "private" and msg.get("from"):
                        send_welcome(client, msg["chat"]["id"], msg["from"])
            except KeyboardInterrupt:
                break
            except Exception as exc:  # network hiccups, Telegram 5xx: wait and keep polling
                log.warning("Polling error: %s", exc)
                time.sleep(5)


if __name__ == "__main__":
    run()

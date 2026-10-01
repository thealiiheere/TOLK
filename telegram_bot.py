"""
TOLK Telegram Bot Launcher (Zero external dependencies).
This script provides a Telegram Bot that launches the TOLK WebApp directly inside Telegram.

Usage:
1. Create a bot in Telegram via @BotFather (send /newbot) and copy your BOT_TOKEN.
2. Run ngrok to get an HTTPS URL:
     ngrok http 8000
   Copy the https URL (e.g., https://xxxx.ngrok-free.app).
3. Run this script:
     python telegram_bot.py
   or set environment variables:
     set TELEGRAM_BOT_TOKEN=your_token_here
     set TOLK_WEBAPP_URL=https://your-ngrok-url.ngrok-free.app
     python telegram_bot.py
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
WEBAPP_URL = os.environ.get("TOLK_WEBAPP_URL", "").strip()

def telegram_api(method, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Telegram API request failed ({method}): {e}")
        return None

def setup_menu_button():
    """Configures the persistent WebApp Menu Button in the chat"""
    res = telegram_api("setChatMenuButton", {
        "menu_button": {
            "type": "web_app",
            "text": "Открыть TOLK",
            "web_app": {"url": WEBAPP_URL}
        }
    })
    if res and res.get("ok"):
        print("[OK] WebApp Menu Button configured successfully in Telegram!")

def send_welcome(chat_id, user_first_name=""):
    text = (
        f"Привет, {user_first_name}! 👋\n\n"
        "Добро пожаловать в **TOLK** — платформу разговорной практики языков в микро-группах (до 5 человек) со студентами-тьюторами по методике **«Tengdosh tengdoshga»**.\n\n"
        "Нажмите на кнопку ниже, чтобы открыть платформу прямо внутри Telegram 👇"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🚀 Открыть TOLK (WebApp)",
                    "web_app": {"url": WEBAPP_URL}
                }
            ],
            [
                {
                    "text": "🌐 Открыть в браузере",
                    "url": WEBAPP_URL
                }
            ]
        ]
    }

    telegram_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    })

def run_bot_polling():
    print(f"Connecting to bot with token {BOT_TOKEN[:10]}...")
    bot_info = telegram_api("getMe")
    if not bot_info or not bot_info.get("ok"):
        print("[ERROR] Invalid Telegram Bot Token! Please check your token from @BotFather.")
        return

    bot_user = bot_info["result"]
    print(f"[OK] Bot authorized as @{bot_user.get('username')} ({bot_user.get('first_name')})")
    print(f"[OK] WebApp URL: {WEBAPP_URL}")

    setup_menu_button()

    print("\nBot is now actively listening for messages... (Press Ctrl+C to stop)")
    offset = 0

    while True:
        try:
            updates = telegram_api("getUpdates", {"offset": offset, "timeout": 20})
            if updates and updates.get("ok"):
                for upd in updates["result"]:
                    offset = upd["update_id"] + 1
                    msg = upd.get("message")
                    if not msg:
                        continue

                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    user_first_name = msg.get("from", {}).get("first_name", "Студент")

                    if text.startswith("/start") or text.startswith("/app"):
                        send_welcome(chat_id, user_first_name)
                    else:
                        send_welcome(chat_id, user_first_name)
        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            break
        except Exception as e:
            print(f"[WARNING] Polling error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("=" * 60)
        print("TOLK TELEGRAM WEBAPP BOT SETUP")
        print("=" * 60)
        BOT_TOKEN = input("Enter your Telegram Bot Token from @BotFather: ").strip()

    if not WEBAPP_URL:
        WEBAPP_URL = input("Enter your ngrok HTTPS URL (e.g. https://xxxx.ngrok-free.app): ").strip()
        if not WEBAPP_URL.startswith("http"):
            WEBAPP_URL = "https://" + WEBAPP_URL

    run_bot_polling()

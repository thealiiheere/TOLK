#!/bin/sh
# Usage: docker-entrypoint.sh web | bot | <any command>
set -e

case "$1" in
  web)
    alembic upgrade head
    if [ "${DEMO_MODE:-false}" = "true" ]; then
      python -m app.seed
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      --workers "${WEB_WORKERS:-2}" --proxy-headers --forwarded-allow-ips="*"
    ;;
  bot)
    exec python telegram_bot.py
    ;;
  *)
    exec "$@"
    ;;
esac

#!/usr/bin/env bash
# Runs ON THE SERVER after `git pull` (called by .github/workflows/deploy.yml, or by hand: `bash deploy.sh`).
# Installs requirements, applies migrations, restarts the services and health-checks the app.
# Migrations are only APPLIED here. Create them on your machine (alembic revision --autogenerate) and commit them.
set -euo pipefail
cd "$(dirname "$0")"

APP_USER=tolk                         # owns /srv/tolk and runs the services
SERVICES=(tolk-web tolk-bot)
HEALTH_URL=http://127.0.0.1:8000/health

as_app() { sudo -u "$APP_USER" "$@"; }

echo "==> Installing requirements"
as_app .venv/bin/pip install -q --no-cache-dir -r requirements.txt

echo "==> Applying migrations"
as_app .venv/bin/alembic upgrade head

echo "==> Restarting ${SERVICES[*]}"
sudo systemctl restart "${SERVICES[@]}"

echo "==> Health check"
for _ in $(seq 1 10); do
  if curl -fs "$HEALTH_URL" >/dev/null; then
    for s in "${SERVICES[@]}"; do
      systemctl is-active --quiet "$s" || echo "WARNING: $s is not active" >&2
    done
    echo "OK: deployed $(as_app git log -1 --format='%h %s')"
    exit 0
  fi
  sleep 2
done

echo "FAILED: $HEALTH_URL did not answer. Last 30 log lines of tolk-web:" >&2
sudo journalctl -u tolk-web -n 30 --no-pager >&2
exit 1

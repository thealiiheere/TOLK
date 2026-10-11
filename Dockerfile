# TOLK web app + Telegram bot (same image, different command). See DEPLOY.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production \
    UPLOAD_DIR=/app/data/uploads

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 10001 tolk
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini telegram_bot.py docker-entrypoint.sh ./
RUN mkdir -p /app/data/uploads && chown -R tolk:tolk /app/data && chmod +x docker-entrypoint.sh

USER tolk
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["web"]

"""Local development runner: applies migrations, adds demo data (if DEMO_MODE=true) and starts the server.

In production use the Docker setup instead (see DEPLOY.md).
"""
import uvicorn
from alembic import command
from alembic.config import Config

from app.config import PROJECT_ROOT, settings

if __name__ == "__main__":
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    if settings.demo_mode:
        from app.database import SessionLocal
        from app.seed import seed

        with SessionLocal() as db:
            seed(db)
    print("TOLK running at http://127.0.0.1:8000")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=not settings.is_production)

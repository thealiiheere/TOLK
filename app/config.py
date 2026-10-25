from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = "2.1.0"


class Settings(BaseSettings):
    environment: Literal["development", "production"] = "development"

    # Database. SQLite for local dev, PostgreSQL in production (docker-compose overrides this).
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'tolk.db').as_posix()}"

    # Telegram
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""  # without "@", used for the Login Widget and t.me links
    tolk_webapp_url: str = ""  # public HTTPS URL of this app (e.g. https://tolk.uz)
    admin_telegram_ids: str = ""  # comma-separated Telegram user IDs that are always admins

    # Demo accounts (one-click login as seeded users). Never enable for real users' data.
    demo_mode: bool = False

    # Manual payments shown to students when they enroll
    payment_card_number: str = ""
    payment_card_holder: str = ""
    support_contact: str = ""  # e.g. @tolk_admin
    timezone: str = "Asia/Tashkent"  # used to format lesson times in Telegram notifications

    # Security / limits
    allowed_origins: str = ""  # only needed if the API is called from another origin
    session_ttl_days: int = 30
    telegram_auth_max_age_hours: int = 24
    max_upload_mb: int = 5
    meeting_link_hosts: str = "zoom.us,meet.google.com,teams.microsoft.com,teams.live.com"

    upload_dir: Path = Field(default=PROJECT_ROOT / "data" / "uploads")

    # Cache (app/cache.py). Optional: with an empty REDIS_URL the app works the same, every lookup is a miss.
    redis_url: str = ""  # e.g. redis://localhost:6379/0
    cache_ttl: int = 300  # seconds a cached value lives

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("telegram_bot_username")
    @classmethod
    def _strip_at(cls, v: str) -> str:
        return v.strip().lstrip("@")

    @field_validator("tolk_webapp_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.strip().rstrip("/")

    def config_warnings(self) -> list[str]:
        """Misconfigurations worth shouting about at startup."""
        warnings = []
        if not self.telegram_bot_token:
            warnings.append("TELEGRAM_BOT_TOKEN is empty: Telegram sign-in and notifications are disabled")
        if not self.tolk_webapp_url.startswith("https://"):
            warnings.append("TOLK_WEBAPP_URL is not an https:// URL: Telegram can't open the Mini App")
        if not self.admin_ids:
            warnings.append("ADMIN_TELEGRAM_IDS is empty: nobody can sign in as admin")
        if self.is_production and self.demo_mode:
            warnings.append("DEMO_MODE=true in production: anyone can sign in as the demo accounts")
        if self.is_production and self.sqlalchemy_url.startswith("sqlite"):
            warnings.append("Production is using SQLite; use PostgreSQL (see docker-compose.yml)")
        return warnings

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.replace(" ", "").split(",") if x.isdigit()}

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def meeting_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.meeting_link_hosts.split(",") if h.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Normalise to the psycopg 3 driver that ships in requirements.txt
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


settings = Settings()

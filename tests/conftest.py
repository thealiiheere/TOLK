import hashlib
import hmac
import io
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest

# Settings are read at import time, so configure the environment before importing the app.
_TMP = Path(tempfile.mkdtemp(prefix="tolk_test_"))
BOT_TOKEN = "123456:TEST_TOKEN"
ADMIN_TG_ID = 1000
os.environ.update({
    "ENVIRONMENT": "development",
    "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "TOLK_WEBAPP_URL": "",  # disables real Telegram notifications
    "ADMIN_TELEGRAM_IDS": str(ADMIN_TG_ID),
    "DEMO_MODE": "true",
})

from fastapi.testclient import TestClient  # noqa: E402

from app import notify  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def init_data(tg_id: int, first_name: str = "Test", lang: str = "en") -> str:
    """Build a correctly signed Telegram Mini App initData string."""
    pairs = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHtest",
        "user": json.dumps({"id": tg_id, "first_name": first_name, "language_code": lang}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    sent = []
    monkeypatch.setattr(notify, "_send", lambda chat_id, text, lang: sent.append((chat_id, text)))
    yield sent


@pytest.fixture
def client():
    return TestClient(app)


class Api:
    """Small helper: a signed-in client for one Telegram user."""

    def __init__(self, client: TestClient, tg_id: int, name: str = "Test"):
        self.client = client
        res = client.post("/api/auth/telegram", json={"init_data": init_data(tg_id, name)})
        assert res.status_code == 200, res.text
        self.token = res.json()["token"]
        self.user = res.json()["user"]

    def _h(self, extra=None):
        return {"Authorization": f"Bearer {self.token}", **(extra or {})}

    def get(self, url, **kw):
        return self.client.get(url, headers=self._h(kw.pop("headers", None)), **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self._h(kw.pop("headers", None)), **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers=self._h(kw.pop("headers", None)), **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self._h(kw.pop("headers", None)), **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self._h(kw.pop("headers", None)), **kw)


def receipt():
    return {"receipt": ("check.png", io.BytesIO(PNG), "image/png")}

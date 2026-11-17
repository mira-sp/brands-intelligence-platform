# backend/tests/conftest.py
"""Test setup: throwaway SQLite DB, known secrets, no Redis, no real AI calls."""
import asyncio
import os
import tempfile

import pytest

_DB = os.path.join(tempfile.mkdtemp(), "test.db").replace("\\", "/")
os.environ.update({
    "DEBUG": "true",
    "DATABASE_URL": f"sqlite+aiosqlite:///{_DB}",
    "USE_REDIS": "false",
    "SECRET_KEY": "test-secret-key-" + "x" * 32,
    "API_KEY": "test-service-key-123456",
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": "correct-horse-battery",
    "RATE_LIMIT_LOGIN_PER_MINUTE": "1000",
    "RATE_LIMIT_DEFAULT_PER_MINUTE": "10000",
    "RATE_LIMIT_ML_PER_MINUTE": "10000",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.core import init_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="session", autouse=True)
def _database():
    async def setup():
        await init_db.create_tables()
        await init_db.create_admin_user()
    asyncio.run(setup())


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def admin_headers(client) -> dict:
    r = client.post("/auth/token", data={"username": "admin@example.com", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

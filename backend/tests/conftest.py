import os

# Must be set before any app.* import so Settings picks it up.
os.environ.setdefault(
    "BUDGET_DATABASE_URL",
    "postgresql+psycopg://budget:dev-secret@localhost:5432/budget_test",
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _wipe_transactional_data():
    """The test database persists across runs; transactional tables are wiped
    once per session so aggregate assertions (dashboard, list filters) are
    deterministic. Reference data (users, categories...) is left alone —
    tests must use uuid-suffixed names for anything with a unique constraint."""
    from sqlalchemy import text

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM transaction_splits"))
        db.execute(text("DELETE FROM transactions"))
        db.execute(text("DELETE FROM budgets"))
        db.commit()
    finally:
        db.close()


class Auth:
    """A logged-in household member: id + ready-to-use Authorization headers."""

    def __init__(self, user_id: int, headers: dict[str, str]):
        self.id = user_id
        self.headers = headers


@pytest.fixture()
def member_a(client) -> Auth:
    return _make_member(client, "A")


@pytest.fixture()
def member_b(client) -> Auth:
    return _make_member(client, "B")


def _make_member(client: TestClient, label: str) -> Auth:
    import uuid

    from app.auth import hash_password
    from app.db import SessionLocal
    from app.models import User

    username = f"test_{label.lower()}_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        user = User(
            username=username,
            display_name=f"Member {label}",
            password_hash=hash_password("correct-horse"),
        )
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()
    r = client.post(
        "/api/auth/login", json={"username": username, "password": "correct-horse"}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return Auth(user_id, {"Authorization": f"Bearer {token}"})

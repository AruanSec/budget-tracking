import uuid

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User


def _make_user(db) -> User:
    user = User(
        username=f"test_{uuid.uuid4().hex[:10]}",
        display_name="Test Member",
        password_hash=hash_password("correct-horse"),
    )
    db.add(user)
    db.commit()
    return user


def test_login_success_and_me(client):
    db = SessionLocal()
    try:
        user = _make_user(db)
        r = client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "correct-horse"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == user.username
    finally:
        db.close()


def test_login_wrong_password(client):
    db = SessionLocal()
    try:
        user = _make_user(db)
        r = client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "wrong"},
        )
        assert r.status_code == 401
    finally:
        db.close()


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code in (401, 403)

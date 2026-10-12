"""Registration + admin portal tests (roles, guards, bootstrap)."""

import uuid

import pytest
from app.db import SessionLocal
from app.auth import hash_password
from app.models import User

HORSE = "correct-horse"
TINY = "short-1"


def _clean_admins():
    """Remove every admin user so each test controls admin existence.

    Safe on the test DB: transactional tables are wiped per session
    (conftest) and admin-role users created here never own transactions.
    """
    db = SessionLocal()
    try:
        db.query(User).filter(User.role == "admin").delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _no_admins():
    _clean_admins()


def _register(client, username=None, password=HORSE, display_name=None):
    username = username or f"reg_{uuid.uuid4().hex[:10]}"
    r = client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "display_name": display_name},
    )
    return username, r


def _token_headers(client, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _me(client, token):
    r = client.get("/api/auth/me", headers=_token_headers(client, token))
    assert r.status_code == 200
    return r.json()


@pytest.fixture()
def admin_auth(client):
    """A real admin: register (first user claims admin), then re-login."""
    username, r = _register(client, password=HORSE)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    me = _me(client, token)
    assert me["role"] == "admin"

    class AdminAuth:
        id = me["id"]
        username_attr = username
        headers = _token_headers(client, token)

    return AdminAuth()


def _make_member(client):
    username, r = _register(client, password=HORSE)
    assert r.status_code == 200
    return username, r.json()["access_token"]


# ---------- registration ----------


def test_first_registration_claims_admin(client):
    _, r = _register(client, password=HORSE)
    assert r.status_code == 200
    assert _me(client, r.json()["access_token"])["role"] == "admin"


def test_later_registrations_are_members(client, admin_auth):
    username, r = _register(client, password=HORSE)
    assert r.status_code == 200
    me = _me(client, r.json()["access_token"])
    assert me["role"] == "member"
    assert me["username"] == username


def test_register_display_name(client, admin_auth):
    _, r = _register(client, password=HORSE, display_name="Jane Q")
    assert r.status_code == 200
    assert _me(client, r.json()["access_token"])["display_name"] == "Jane Q"


def test_register_duplicate_username_409(client, admin_auth):
    _, r = _register(client, username=admin_auth.username_attr, password=HORSE)
    assert r.status_code == 409


def test_register_short_password_422(client, admin_auth):
    _, r = _register(client, password=TINY)
    assert r.status_code == 422


def test_register_bad_username_422(client, admin_auth):
    _, r = _register(client, username="has spaces", password=HORSE)
    assert r.status_code == 422


def test_login_claims_admin_when_none(client):
    """A seeded member who logs in into an admin-less install becomes admin."""
    db = SessionLocal()
    try:
        user = User(
            username=f"seed_{uuid.uuid4().hex[:10]}",
            display_name="Seed Only",
            password_hash=hash_password(HORSE),
            role="member",
        )
        db.add(user)
        db.commit()
        username = user.username
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert r.status_code == 200
    assert _me(client, r.json()["access_token"])["role"] == "admin"


# ---------- access control ----------


def test_admin_endpoints_require_auth(client):
    assert client.get("/api/admin/users").status_code in (401, 403)


def test_admin_endpoints_forbid_members(client, admin_auth):
    _, member_token = _make_member(client)
    r = client.get("/api/admin/users", headers=_token_headers(client, member_token))
    assert r.status_code == 403
    r = client.get("/api/admin/stats", headers=_token_headers(client, member_token))
    assert r.status_code == 403


# ---------- admin: users ----------


def test_admin_lists_all_users_including_inactive(client, admin_auth):
    _, member_token = _make_member(client)
    member_id = _me(client, member_token)["id"]
    db = SessionLocal()
    try:
        target = db.get(User, member_id)
        target.is_active = False
        db.commit()
    finally:
        db.close()
    ids = {u["id"]: u for u in client.get("/api/admin/users", headers=admin_auth.headers).json()}
    assert admin_auth.id in ids
    assert ids[member_id]["is_active"] is False


def test_admin_creates_user_with_role(client, admin_auth):
    username = f"made_{uuid.uuid4().hex[:10]}"
    r = client.post(
        "/api/admin/users",
        headers=admin_auth.headers,
        json={"username": username, "password": HORSE, "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "admin"
    login = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert login.status_code == 200
    assert _me(client, login.json()["access_token"])["role"] == "admin"


def test_admin_cannot_deactivate_or_demote_self(client, admin_auth):
    r = client.patch(
        f"/api/admin/users/{admin_auth.id}",
        headers=admin_auth.headers,
        json={"is_active": False},
    )
    assert r.status_code == 400
    r = client.patch(
        f"/api/admin/users/{admin_auth.id}",
        headers=admin_auth.headers,
        json={"role": "member"},
    )
    assert r.status_code == 400


def test_admin_toggles_member_active_and_login_blocked(client, admin_auth):
    username, member_token = _make_member(client)
    member_id = _me(client, member_token)["id"]

    r = client.patch(
        f"/api/admin/users/{member_id}",
        headers=admin_auth.headers,
        json={"is_active": False},
    )
    assert r.status_code == 200 and r.json()["is_active"] is False
    login = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert login.status_code == 401
    # an already-issued token stops working for a deactivated user
    assert client.get("/api/auth/me", headers=_token_headers(client, member_token)).status_code == 401

    r = client.patch(
        f"/api/admin/users/{member_id}",
        headers=admin_auth.headers,
        json={"is_active": True},
    )
    assert r.status_code == 200
    login = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert login.status_code == 200


def test_admin_promotes_and_demotes_second_admin(client, admin_auth):
    username, member_token = _make_member(client)
    member_id = _me(client, member_token)["id"]
    r = client.patch(
        f"/api/admin/users/{member_id}",
        headers=admin_auth.headers,
        json={"role": "admin"},
    )
    assert r.status_code == 200 and r.json()["role"] == "admin"
    # demote is fine — admin_auth remains an active admin
    r = client.patch(
        f"/api/admin/users/{member_id}",
        headers=admin_auth.headers,
        json={"role": "member"},
    )
    assert r.status_code == 200 and r.json()["role"] == "member"


def test_last_active_admin_guard_direct(client, admin_auth):
    """Unit-level check of the guard used by demote/deactivate/delete."""
    from app.routers.admin import _last_active_admin

    db = SessionLocal()
    try:
        admin = db.get(User, admin_auth.id)
        assert _last_active_admin(db, admin) is True
        other = User(
            username=f"coadmin_{uuid.uuid4().hex[:10]}",
            display_name="Co Admin",
            password_hash=hash_password(HORSE),
            role="admin",
        )
        db.add(other)
        db.commit()
        assert _last_active_admin(db, admin) is False
        assert _last_active_admin(db, other) is False
    finally:
        db.close()


def test_admin_resets_password(client, admin_auth):
    username, member_token = _make_member(client)
    member_id = _me(client, member_token)["id"]
    NEWH = "new-horse-9"
    r = client.post(
        f"/api/admin/users/{member_id}/password",
        headers=admin_auth.headers,
        json={"password": NEWH},
    )
    assert r.status_code == 204
    assert client.get("/api/auth/me", headers=_token_headers(client, member_token)).status_code == 401
    old = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"username": username, "password": NEWH})
    assert new.status_code == 200


def test_admin_delete_user(client, admin_auth):
    username, member_token = _make_member(client)
    member_id = _me(client, member_token)["id"]
    r = client.delete(f"/api/admin/users/{member_id}", headers=admin_auth.headers)
    assert r.status_code == 204
    login = client.post("/api/auth/login", json={"username": username, "password": HORSE})
    assert login.status_code == 401


def test_admin_cannot_delete_user_with_history_or_self(client, admin_auth):
    from app.models import Transaction, TransactionSplit, Category

    db = SessionLocal()
    try:
        username, member_token = _make_member(client)
        member_id = _me(client, member_token)["id"]
        cat = Category(name=f"del_{uuid.uuid4().hex[:8]}")
        db.add(cat)
        db.commit()
        tx = Transaction(
            type="expense",
            amount_cents=100,
            occurred_on="2026-09-01",
            category_id=cat.id,
            entered_by=member_id,
        )
        tx.splits.append(TransactionSplit(member_id=member_id, share_cents=100))
        db.add(tx)
        db.commit()
        tx_id, cat_id = tx.id, cat.id
        member_ref = db.get(User, member_id)
    finally:
        db.close()

    r = client.delete(f"/api/admin/users/{member_id}", headers=admin_auth.headers)
    assert r.status_code == 409
    assert "deactivate" in r.json()["detail"]

    r = client.delete(f"/api/admin/users/{admin_auth.id}", headers=admin_auth.headers)
    assert r.status_code == 400

    # cleanup so re-runs stay deterministic
    db = SessionLocal()
    try:
        db.query(Transaction).filter(Transaction.id == tx_id).delete()
        db.query(Category).filter(Category.id == cat_id).delete()
        db.query(User).filter(User.id == member_id).delete()
        db.commit()
    finally:
        db.close()


# ---------- admin: stats ----------


def test_admin_stats(client, admin_auth):
    r = client.get("/api/admin/stats", headers=admin_auth.headers)
    assert r.status_code == 200
    s = r.json()
    assert s["users_total"] >= 1
    assert s["users_active"] >= 1
    assert s["admins_active"] >= 1
    assert s["transactions_total"] >= 0
    assert s["transactions_this_month_cents"] >= 0


def test_concurrent_registration_claims_exactly_one_admin(client):
    from concurrent.futures import ThreadPoolExecutor
    names = [f"race_{uuid.uuid4().hex[:10]}" for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda name: _register(client, username=name)[1], names))
    assert all(response.status_code == 200 for response in responses)
    roles = [_me(client, response.json()["access_token"])["role"] for response in responses]
    assert sorted(roles) == ["admin", "member"]

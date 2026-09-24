"""Phase 2 CRUD API tests: members, accounts, categories, income sources,
transactions, budgets. Reference-data names are uuid-suffixed because the
test DB persists across runs."""

import uuid
from datetime import date

import pytest

MONTH = "2031-01"
MONTH_START = date(2031, 1, 1)


def uniq(name: str) -> str:
    return f"{name}_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def household(client, member_a, member_b):
    """Two members + one category + one income source, ready to transact."""
    cat = client.post("/api/categories", json={"name": uniq("Groceries")}, headers=member_a.headers)
    assert cat.status_code == 201, cat.text
    src = client.post(
        "/api/income-sources",
        json={"name": uniq("Salary"), "member_id": member_a.id},
        headers=member_a.headers,
    )
    assert src.status_code == 201, src.text
    return {
        "a": member_a,
        "b": member_b,
        "category_id": cat.json()["id"],
        "income_source_id": src.json()["id"],
    }


def expense_body(h, amount=10000, splits=None, **overrides):
    body = {
        "type": "expense",
        "amount_cents": amount,
        "occurred_on": "2031-01-15",
        "description": "Test expense",
        "category_id": h["category_id"],
        "splits": splits
        or [
            {"member_id": h["a"].id, "share_cents": amount // 2},
            {"member_id": h["b"].id, "share_cents": amount - amount // 2},
        ],
    }
    body.update(overrides)
    return body


# ---------- members ----------

def test_members_list_requires_auth_and_returns_users(client, member_a):
    assert client.get("/api/members").status_code in (401, 403)
    r = client.get("/api/members", headers=member_a.headers)
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert member_a.id in ids


# ---------- accounts ----------

def test_accounts_crud(client, member_a):
    h = member_a.headers
    name = uniq("Checking")
    r = client.post("/api/accounts", json={"name": name, "type": "checking"}, headers=h)
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    # duplicate name -> 409
    r = client.post("/api/accounts", json={"name": name}, headers=h)
    assert r.status_code == 409

    # patch: rename + archive
    r = client.patch(f"/api/accounts/{account_id}", json={"name": uniq("Renamed"), "archived": True}, headers=h)
    assert r.status_code == 200
    assert r.json()["archived"] is True

    # patch missing -> 404
    assert client.patch("/api/accounts/999999", json={"name": "x"}, headers=h).status_code == 404

    # list includes archived
    r = client.get("/api/accounts", headers=h)
    assert account_id in [a["id"] for a in r.json()]


# ---------- categories ----------

def test_categories_hierarchy_and_delete_rules(client, member_a):
    h = member_a.headers
    parent = client.post("/api/categories", json={"name": uniq("Home")}, headers=h).json()

    # child ok
    child = client.post(
        "/api/categories", json={"name": uniq("Rent"), "parent_id": parent["id"]}, headers=h
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == parent["id"]

    # third level rejected
    r = client.post(
        "/api/categories", json={"name": uniq("Deep"), "parent_id": child.json()["id"]}, headers=h
    )
    assert r.status_code == 422

    # parent with children cannot become a child
    other = client.post("/api/categories", json={"name": uniq("Other")}, headers=h).json()
    r = client.patch(f"/api/categories/{parent['id']}", json={"parent_id": other["id"]}, headers=h)
    assert r.status_code == 422

    # self-parent rejected
    r = client.patch(f"/api/categories/{other['id']}", json={"parent_id": other["id"]}, headers=h)
    assert r.status_code == 422

    # delete unused child works
    r = client.delete(f"/api/categories/{child.json()['id']}", headers=h)
    assert r.status_code == 204


def test_category_delete_blocked_when_used(client, household):
    h = household["a"].headers
    tx = client.post("/api/transactions", json=expense_body(household), headers=h)
    assert tx.status_code == 201, tx.text
    r = client.delete(f"/api/categories/{household['category_id']}", headers=h)
    assert r.status_code == 409
    assert "transaction" in r.json()["detail"]


# ---------- income sources ----------

def test_income_sources(client, member_a, member_b):
    h = member_a.headers
    name = uniq("Consulting")
    r = client.post(
        "/api/income-sources", json={"name": name, "member_id": member_b.id}, headers=h
    )
    assert r.status_code == 201

    # duplicate (name, member) -> 409
    r = client.post(
        "/api/income-sources", json={"name": name, "member_id": member_b.id}, headers=h
    )
    assert r.status_code == 409

    # unknown member -> 422
    r = client.post(
        "/api/income-sources", json={"name": uniq("x"), "member_id": 999999}, headers=h
    )
    assert r.status_code == 422

    # deactivate + filter
    sources = client.get("/api/income-sources", headers=h).json()
    target = [s for s in sources if s["name"] == name][0]
    r = client.patch(f"/api/income-sources/{target['id']}", json={"active": False}, headers=h)
    assert r.status_code == 200 and r.json()["active"] is False
    active = client.get("/api/income-sources", params={"active": "true"}, headers=h).json()
    assert target["id"] not in [s["id"] for s in active]


# ---------- transactions ----------

def test_transaction_create_validation(client, household):
    h = household["a"].headers

    # split sum mismatch -> 422
    bad = expense_body(household, amount=10000, splits=[{"member_id": household["a"].id, "share_cents": 5000}])
    assert client.post("/api/transactions", json=bad, headers=h).status_code == 422

    # expense without category -> 422
    bad = expense_body(household)
    del bad["category_id"]
    assert client.post("/api/transactions", json=bad, headers=h).status_code == 422

    # unknown FK -> 422
    bad = expense_body(household, account_id=999999)
    assert client.post("/api/transactions", json=bad, headers=h).status_code == 422

    # income with splits -> 422
    bad = {
        "type": "income",
        "amount_cents": 5000,
        "occurred_on": "2031-01-10",
        "income_source_id": household["income_source_id"],
        "splits": [{"member_id": household["a"].id, "share_cents": 5000}],
    }
    assert client.post("/api/transactions", json=bad, headers=h).status_code == 422

    # requires auth
    assert client.post("/api/transactions", json=expense_body(household)).status_code in (401, 403)


def test_transaction_lifecycle_and_filters(client, household):
    h = household["a"].headers

    # create expense split 60/40
    amount = 10000
    splits = [
        {"member_id": household["a"].id, "share_cents": 6000},
        {"member_id": household["b"].id, "share_cents": 4000},
    ]
    r = client.post("/api/transactions", json=expense_body(household, amount, splits), headers=h)
    assert r.status_code == 201, r.text
    tx = r.json()
    assert tx["entered_by"] == household["a"].id  # server-set
    assert sorted(s["share_cents"] for s in tx["splits"]) == [4000, 6000]

    # create income
    income = {
        "type": "income",
        "amount_cents": 300000,
        "occurred_on": "2031-01-05",
        "description": "Salary",
        "income_source_id": household["income_source_id"],
    }
    r = client.post("/api/transactions", json=income, headers=h)
    assert r.status_code == 201, r.text
    income_id = r.json()["id"]

    # month filter
    r = client.get("/api/transactions", params={"month": MONTH}, headers=h)
    ids = [t["id"] for t in r.json()]
    assert tx["id"] in ids and income_id in ids

    # member filter: B sees the expense (has a split), not A's income
    r = client.get("/api/transactions", params={"member_id": household["b"].id}, headers=h)
    ids = [t["id"] for t in r.json()]
    assert tx["id"] in ids and income_id not in ids

    # type filter
    r = client.get("/api/transactions", params={"type": "income", "month": MONTH}, headers=h)
    assert all(t["type"] == "income" for t in r.json())
    assert income_id in [t["id"] for t in r.json()]

    # date range
    r = client.get("/api/transactions", params={"from": "2031-01-10", "to": "2031-01-20"}, headers=h)
    ids = [t["id"] for t in r.json()]
    assert tx["id"] in ids and income_id not in ids

    # patch: change amount + replace splits to 100% B
    r = client.patch(
        f"/api/transactions/{tx['id']}",
        json={"amount_cents": 8000, "splits": [{"member_id": household["b"].id, "share_cents": 8000}]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["amount_cents"] == 8000
    assert len(updated["splits"]) == 1 and updated["splits"][0]["member_id"] == household["b"].id

    # patch with mismatched splits -> 422
    r = client.patch(
        f"/api/transactions/{tx['id']}",
        json={"splits": [{"member_id": household["b"].id, "share_cents": 100}]},
        headers=h,
    )
    assert r.status_code == 422

    # patch description only leaves splits alone
    r = client.patch(f"/api/transactions/{tx['id']}", json={"description": "Edited"}, headers=h)
    assert r.status_code == 200
    assert r.json()["description"] == "Edited"
    assert r.json()["amount_cents"] == 8000

    # delete
    assert client.delete(f"/api/transactions/{tx['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/transactions/{tx['id']}", headers=h).status_code == 404


# ---------- budgets ----------

def test_budget_upsert_and_delete(client, household):
    h = household["a"].headers
    body = {
        "member_id": household["a"].id,
        "category_id": household["category_id"],
        "month": "2031-01-01",
        "amount_cents": 50000,
    }
    r = client.put("/api/budgets", json=body, headers=h)
    assert r.status_code == 200, r.text
    budget_id = r.json()["id"]

    # idempotent upsert: same key, new amount -> same row updated
    r = client.put("/api/budgets", json={**body, "amount_cents": 60000}, headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == budget_id
    assert r.json()["amount_cents"] == 60000

    # month must be first day
    r = client.put("/api/budgets", json={**body, "month": "2031-01-15"}, headers=h)
    assert r.status_code == 422

    # unknown member / category -> 422
    r = client.put("/api/budgets", json={**body, "member_id": 999999}, headers=h)
    assert r.status_code == 422

    # list by month
    r = client.get("/api/budgets", params={"month": MONTH}, headers=h)
    assert budget_id in [b["id"] for b in r.json()]
    r = client.get("/api/budgets", params={"month": MONTH, "member_id": household["b"].id}, headers=h)
    assert budget_id not in [b["id"] for b in r.json()]

    # bad month string -> 422
    assert client.get("/api/budgets", params={"month": "nonsense"}, headers=h).status_code == 422

    # delete
    assert client.delete(f"/api/budgets/{budget_id}", headers=h).status_code == 204
    assert client.delete(f"/api/budgets/{budget_id}", headers=h).status_code == 404

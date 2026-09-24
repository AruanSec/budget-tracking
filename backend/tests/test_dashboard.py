"""Phase 2 dashboard tests: combined household summary + trend.

The summary test uses a dedicated far-future month (2031-07) so no other
test can pollute its aggregates. The trend test uses before/after deltas
because the trend window always ends at the real current month.
"""

import uuid
from datetime import date

import pytest

SUMMARY_MONTH = "2031-07"


@pytest.fixture()
def seeded(client, member_a, member_b):
    """A fully seeded month with hand-computable numbers.

    Income:  A 300000, B 200000               -> household 500000
    Expenses: rent 100000 split 50/50         -> A 50000, B 50000
              groceries 30000 split 10k/20k   -> A 10000, B 20000
    Total expense 130000; A 60000, B 70000.
    Budgets: A groceries 20000, B groceries 10000 -> household budget 30000.
    """
    h = member_a.headers
    suffix = uuid.uuid4().hex[:8]
    rent = client.post("/api/categories", json={"name": f"Rent_{suffix}"}, headers=h).json()
    groc = client.post("/api/categories", json={"name": f"Groceries_{suffix}"}, headers=h).json()
    src_a = client.post(
        "/api/income-sources", json={"name": f"SalaryA_{suffix}", "member_id": member_a.id}, headers=h
    ).json()
    src_b = client.post(
        "/api/income-sources", json={"name": f"SalaryB_{suffix}", "member_id": member_b.id}, headers=h
    ).json()

    def post(body):
        r = client.post("/api/transactions", json=body, headers=h)
        assert r.status_code == 201, r.text

    post({"type": "income", "amount_cents": 300000, "occurred_on": "2031-07-01",
          "income_source_id": src_a["id"]})
    post({"type": "income", "amount_cents": 200000, "occurred_on": "2031-07-01",
          "income_source_id": src_b["id"]})
    post({"type": "expense", "amount_cents": 100000, "occurred_on": "2031-07-02",
          "description": "Rent", "category_id": rent["id"],
          "splits": [{"member_id": member_a.id, "share_cents": 50000},
                     {"member_id": member_b.id, "share_cents": 50000}]})
    post({"type": "expense", "amount_cents": 30000, "occurred_on": "2031-07-03",
          "description": "Groceries", "category_id": groc["id"],
          "splits": [{"member_id": member_a.id, "share_cents": 10000},
                     {"member_id": member_b.id, "share_cents": 20000}]})
    for member, amount in ((member_a, 20000), (member_b, 10000)):
        r = client.put("/api/budgets", json={"member_id": member.id,
                       "category_id": groc["id"], "month": "2031-07-01",
                       "amount_cents": amount}, headers=h)
        assert r.status_code == 200, r.text

    return {"a": member_a, "b": member_b, "rent_id": rent["id"], "groc_id": groc["id"]}


def test_summary_household_and_members(client, seeded):
    h = seeded["a"].headers
    r = client.get("/api/dashboard/summary", params={"month": SUMMARY_MONTH}, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["month"] == SUMMARY_MONTH

    hh = data["household"]
    assert hh["income_cents"] == 500000
    assert hh["expense_cents"] == 130000
    assert hh["net_cents"] == 370000
    assert hh["budget_cents"] == 30000
    assert hh["budget_used_pct"] == pytest.approx(433.3)

    members = {m["member_id"]: m for m in data["members"]}
    a, b = members[seeded["a"].id], members[seeded["b"].id]
    assert (a["income_cents"], a["expense_cents"], a["budget_cents"]) == (300000, 60000, 20000)
    assert a["budget_used_pct"] == pytest.approx(300.0)
    assert (b["income_cents"], b["expense_cents"], b["budget_cents"]) == (200000, 70000, 10000)
    assert b["budget_used_pct"] == pytest.approx(700.0)


def test_summary_by_category(client, seeded):
    h = seeded["a"].headers
    data = client.get("/api/dashboard/summary", params={"month": SUMMARY_MONTH}, headers=h).json()
    by_cat = {c["category_id"]: c for c in data["by_category"]}

    rent = by_cat[seeded["rent_id"]]
    assert rent["spent_cents"] == 100000
    assert rent["budget_cents"] == 0
    assert sorted((m["member_id"], m["spent_cents"]) for m in rent["per_member"]) == sorted(
        [(seeded["a"].id, 50000), (seeded["b"].id, 50000)]
    )

    groc = by_cat[seeded["groc_id"]]
    assert groc["spent_cents"] == 30000
    assert groc["budget_cents"] == 30000
    assert {m["member_id"]: m["spent_cents"] for m in groc["per_member"]} == {
        seeded["a"].id: 10000,
        seeded["b"].id: 20000,
    }

    # sorted by spend descending -> rent first among our two
    order = [c["category_id"] for c in data["by_category"]]
    assert order.index(seeded["rent_id"]) < order.index(seeded["groc_id"])


def test_summary_empty_month(client, member_a):
    r = client.get("/api/dashboard/summary", params={"month": "2030-02"}, headers=member_a.headers)
    assert r.status_code == 200
    hh = r.json()["household"]
    assert hh["income_cents"] == 0 and hh["expense_cents"] == 0
    assert hh["budget_used_pct"] is None  # no budget -> no percentage, not div-by-zero


def test_trend_deltas(client, seeded):
    """Trend always ends at the real current month; assert before/after deltas
    so concurrent/persisted data can't break the test."""
    h = seeded["a"].headers
    today = date.today()
    current = f"{today.year:04d}-{today.month:02d}"

    before = {p["month"]: p for p in client.get(
        "/api/dashboard/trend", params={"months": 3}, headers=h).json()}
    assert current in before
    assert len(before) == 3

    amount = 12345
    r = client.post("/api/transactions", json={
        "type": "expense", "amount_cents": amount,
        "occurred_on": today.isoformat(), "description": "trend probe",
        "category_id": seeded["rent_id"],
        "splits": [{"member_id": seeded["a"].id, "share_cents": amount}],
    }, headers=h)
    assert r.status_code == 201, r.text

    after = {p["month"]: p for p in client.get(
        "/api/dashboard/trend", params={"months": 3}, headers=h).json()}
    assert after[current]["expense_cents"] - before[current]["expense_cents"] == amount
    assert after[current]["income_cents"] == before[current]["income_cents"]


def test_dashboard_requires_auth(client):
    assert client.get("/api/dashboard/summary", params={"month": SUMMARY_MONTH}).status_code in (401, 403)
    assert client.get("/api/dashboard/trend").status_code in (401, 403)

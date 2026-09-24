# REST API Contracts

Base path: `/api` (same-origin: nginx proxies `/api/` to FastAPI).
Auth: `Authorization: Bearer <jwt>` on everything except `/api/health`
and `/api/auth/login`. Tokens last 7 days.

Status legend: ✅ implemented and covered by tests. Phase 2 built every
contract below — verified against the live compose stack end-to-end.

## Implemented (Phase 1)

### `GET /api/health` ✅
→ `200 {"status": "ok"}`

### `POST /api/auth/login` ✅
```json
{ "username": "alice", "password": "***" }
```
→ `200 {"access_token": "***", "token_type": "bearer"}`
→ `401 {"detail": "Invalid credentials"}`

### `GET /api/auth/me` ✅
→ `200 {"id": 1, "username": "alice", "display_name": "Alice"}`
→ `401` when missing/invalid token.

## Implemented (Phase 2)

All money fields are integer cents. All write endpoints validate the same
rules the DB enforces, returning `422` with Pydantic error detail.

### Members
- `GET /api/members` ✅ → list of users (id, username, display_name).

### Accounts
- `GET /api/accounts` ✅
- `POST /api/accounts` ✅ `{name, type}`
- `PATCH /api/accounts/{id}` ✅ (rename, archive)

### Categories
- `GET /api/categories` ✅ → flat list with `parent_id`; client builds tree
- `POST /api/categories` ✅ `{name, parent_id?}`
- `PATCH /api/categories/{id}` ✅
- `DELETE /api/categories/{id}` ✅ → transactions keep history (SET NULL),
  budgets for it are removed

### Income sources
- `GET /api/income-sources` ✅ (filter `?active=true`)
- `POST /api/income-sources` ✅ `{name, member_id}`
- `PATCH /api/income-sources/{id}` ✅

### Transactions
- `GET /api/transactions` ✅
  Query params: `month=YYYY-MM`, `member_id`, `category_id`, `type`,
  `from`/`to` (dates), `limit`/`offset`. Response items include nested
  `splits`.
- `POST /api/transactions` ✅
```json
{
  "type": "expense",
  "amount_cents": 12500,
  "occurred_on": "2026-09-20",
  "description": "Groceries",
  "category_id": 4,
  "account_id": 1,
  "paid_by": 1,
  "splits": [
    { "member_id": 1, "share_cents": 6250 },
    { "member_id": 2, "share_cents": 6250 }
  ]
}
```
  Rules (422 on violation): expense ⇒ `category_id` + ≥1 split summing to
  `amount_cents`, unique members; income ⇒ `income_source_id`, no splits,
  no category. `entered_by` is always the authenticated user (server-set,
  never client-supplied).
- `PATCH /api/transactions/{id}` ✅ — replacing splits replaces the whole
  set; deferred trigger still guarantees the sum at commit.
- `DELETE /api/transactions/{id}` ✅ — cascades splits.

### Budgets
- `GET /api/budgets?month=YYYY-MM` ✅ → all members' budget lines for the
  month; `?member_id=` to filter.
- `PUT /api/budgets` ✅ — upsert `{member_id, category_id, month, amount_cents}`
  (`month` must be day 1; unique key makes PUT idempotent).
- `DELETE /api/budgets/{id}` ✅

### Dashboard (the combined-analysis read model)
- `GET /api/dashboard/summary?month=YYYY-MM` ✅
```json
{
  "month": "2026-09",
  "household": {
    "income_cents": 520000,
    "expense_cents": 310000,
    "net_cents": 210000,
    "budget_cents": 300000,
    "budget_used_pct": 103.3
  },
  "members": [
    {
      "member_id": 1,
      "income_cents": 300000,
      "expense_cents": 170000,
      "budget_cents": 160000,
      "budget_used_pct": 106.2
    }
  ],
  "by_category": [
    { "category_id": 4, "name": "Groceries", "spent_cents": 90000,
      "budget_cents": 80000,
      "per_member": [ {"member_id": 1, "spent_cents": 45000},
                      {"member_id": 2, "spent_cents": 45000} ] }
  ]
}
```
  Member expense figures = sums of **split shares** (shared costs already
  divided). Household figures = sums over all members.
- `GET /api/dashboard/trend?months=6` ✅ — month-over-month income/expense
  series for the combined view.

## Conventions

- Errors: FastAPI default shapes — `422` validation detail, `401`
  unauthenticated, `404` missing resource.
- Pagination: `limit` (default 50, max 200) + `offset` on list endpoints.
- Dates: ISO-8601 (`YYYY-MM-DD`); months always `YYYY-MM-01`.
- Interactive OpenAPI docs served by FastAPI at `/docs` (dev; consider
  disabling in the compose deployment later).

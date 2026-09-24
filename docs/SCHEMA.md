# Database Schema (Phase 1)

PostgreSQL 16. Source of truth: `backend/app/models.py` (SQLAlchemy 2.x) and
`backend/alembic/versions/0001_initial.py`. CI runs `alembic check` so the
two can never drift.

## Ground rules

- **Money is integer cents** (`BigInteger`) everywhere. No floats, ever.
- **Expenses belong to members via `transaction_splits`**, never via a
  member column on the transaction. Solo expense = one 100% split; shared
  expense (rent, groceries) = split across members. A member's budget
  consumption = sum of their split shares per category per month.
- **Income belongs to the receiving member** via `income_sources.member_id`.
  Income transactions carry no splits.
- **Budgets are per-person**: one row per `(member, category, month)`.
- Split-sum integrity is enforced twice: Pydantic at the API layer and a
  **deferred constraint trigger** in Postgres (`trg_split_sum_check`,
  `trg_amount_change_split_check`) — deferred so multi-row split inserts
  validate at COMMIT, not per row.

## ERD (text)

```
users ─┬─< income_sources ──< transactions (income)
       ├─< transaction_splits >── transactions (expense) ──> categories ─┐
       ├─< budgets >── categories                                        │
       │        (categories.parent_id ──> categories: one-level tree)    │
       └─ transactions.entered_by / paid_by ──> users                    │
accounts ──< transactions (optional)                                     │
recurring_rules ──> categories / income_sources / accounts               │
                (splits template stored as JSONB)                        │
```

## Tables

### users
Household members (design for N, currently 2).

| column | type | notes |
|---|---|---|
| id | int PK | |
| username | varchar(64) | unique, indexed |
| display_name | varchar(128) | |
| password_hash | varchar(255) | argon2 |
| is_active | bool | default true |
| created_at | timestamptz | |

### accounts
| column | type | notes |
|---|---|---|
| id | int PK | |
| name | varchar(128) | unique |
| type | varchar(32) | cash / checking / savings / credit / other |
| archived | bool | default false |
| created_at | timestamptz | |

### categories
Expense categories, one level of hierarchy via `parent_id`.

| column | type | notes |
|---|---|---|
| id | int PK | |
| name | varchar(128) | unique per parent (NULLS NOT DISTINCT) |
| parent_id | int FK categories.id | SET NULL on delete |
| created_at | timestamptz | |

### income_sources
| column | type | notes |
|---|---|---|
| id | int PK | |
| name | varchar(128) | unique per member |
| member_id | int FK users.id | CASCADE; the member receiving it |
| active | bool | default true |
| created_at | timestamptz | |

### transactions
| column | type | notes |
|---|---|---|
| id | int PK | |
| type | varchar(8) | CHECK: income \| expense |
| amount_cents | bigint | CHECK > 0 |
| currency | char(3) | default USD (multi-currency is Phase 6) |
| description | varchar(255) | |
| occurred_on | date | indexed |
| account_id | int FK accounts.id | nullable, SET NULL |
| category_id | int FK categories.id | required for expense (CHECK) |
| income_source_id | int FK income_sources.id | required for income (CHECK) |
| entered_by | int FK users.id | who keyed it in |
| paid_by | int FK users.id | nullable — whose card/cash it left |
| created_at / updated_at | timestamptz | |

CHECK `ck_transaction_type_target`: expense ⇒ category set, no income
source; income ⇒ income source set, no category.

### transaction_splits
| column | type | notes |
|---|---|---|
| id | int PK | |
| transaction_id | int FK transactions.id | CASCADE, indexed |
| member_id | int FK users.id | CASCADE, indexed |
| share_cents | bigint | CHECK > 0 |

UNIQUE `(transaction_id, member_id)`. Trigger-enforced:
`SUM(share_cents) == transactions.amount_cents` at COMMIT (expenses only).

### budgets
| column | type | notes |
|---|---|---|
| id | int PK | |
| member_id | int FK users.id | CASCADE |
| category_id | int FK categories.id | CASCADE |
| month | date | CHECK: day = 1 (first of month) |
| amount_cents | bigint | CHECK >= 0 |

UNIQUE `(member_id, category_id, month)`.

### recurring_rules
Templates for transactions that repeat monthly (rent, salaries, subs).

| column | type | notes |
|---|---|---|
| id | int PK | |
| description | varchar(255) | |
| type | varchar(8) | CHECK: income \| expense |
| amount_cents | bigint | CHECK > 0 |
| currency | char(3) | |
| day_of_month | int | CHECK 1–31; clamp to month length at execution |
| category_id / income_source_id / account_id | FKs | nullable, SET NULL |
| splits | jsonb | `[{"member_id": 1, "share_pct": 50}, ...]` |
| active | bool | |
| next_due | date | |
| created_at | timestamptz | |

Execution of rules (creating the transaction + splits from the template,
advancing `next_due`) is Phase 3 work; the table ships in Phase 1 so the
schema doesn't churn later.

## Backups

Cron'd `pg_dump` to a second location on the network; periodic restore
test. Example (host crontab):

```cron
0 3 * * * docker exec budget_tracking-postgres-1 pg_dump -U budget budget | gzip > /volume1/backups/budget-$(date +\%F).sql.gz
```

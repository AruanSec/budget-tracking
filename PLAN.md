# Budget & Expense Tracking App — Plan

## Overview

A household budget and expense tracking web app. Core purpose: track income
against expenses for one household. Web-based with an adaptive (responsive)
UI — usable on desktop and phone browsers. No native apps, no SaaS, no
billing. This is a personal tool.

---

## Phase 0 — Discovery & Scoping (RESOLVED)

Decisions made:

- **Users:** single household — me (and optionally partner/family members).
  Not multi-tenant.
- **Core loop:** track income vs. expenses. Headline view: income in, money
  out, what's left per month.
- **Platform:** web app, adaptive/responsive UI. Mobile-first CSS from day
  one. The critical mobile screen is *quick transaction entry* — one-thumb,
  under 10 seconds.
- **Business model:** none. No onboarding funnel, no billing, no
  subscriptions.

Implications of single-household scope:

1. **Auth is minimal:** one household login (or single-user session with
   basic password protection if self-hosted).
2. **Hosting decision needed early:** self-hosted (own machine/NAS) vs.
   small VPS/cloud. Self-hosted removes most security/compliance burden
   and is usually right for a personal finance tool.
3. **Income sources are first-class entities** in the data model, alongside
   expense categories — the income-vs-expense view should be a query, not
   a hack.
4. **Bank feeds become optional:** for one household, CSV import + manual
   entry may be all that's ever needed. Keep deferred, not planned.

Resolved questions:

- [x] **Members:** 2 household members will use the app (for now — design
      for N, not hardcoded to 2). Transactions carry per-member
      attribution (who entered it, optional "paid by" field).
- [x] **Stack:** decided (see Technology Decisions below).
- [x] **Budgets:** **per-person budgets** — each member has their own
      budget per category per month. The dashboard shows a **combined
      household analysis** across both members, with drill-down to
      per-member views.
- [x] **Shared expenses:** **split across members** — shared household
      costs (rent, utilities, groceries) are divided evenly or by
      percentage per transaction; each member's share hits their own
      budget.
- [x] **Hosting:** **in-house** (self-hosted on home hardware — NAS, mini
      PC, or similar), run via **Docker Compose**. **Tailscale** provides
      the hostname and TLS (Tailscale Serve: `https://<host>.<tailnet>.ts.net`
      with automatic Let's Encrypt certs). No public ports forwarded; the
      app is reachable only from the tailnet — both household members'
      devices join the tailnet.

## Technology Decisions

| Layer      | Choice                | Notes |
|------------|-----------------------|-------|
| Frontend   | **Vite + React + Tailwind CSS** | Sleek, responsive UI/UX; mobile-first. TypeScript. |
| Backend    | **Python REST API**   | FastAPI is the natural fit (async, auto OpenAPI docs, Pydantic validation). |
| Database   | **PostgreSQL**        | Runs as a container in the same compose stack. Proper concurrent writes, real migrations, and mature tooling. Backup via `pg_dump`. |
| Auth       | Simple household login | 2 users; session tokens (e.g., JWT or server sessions). No third-party auth needed. |

PostgreSQL implications to respect throughout the plan:

- Postgres joins the Docker Compose stack as its own service with a named
  volume; credentials via env file / secrets, never baked into images.
- Backup strategy = cron'd `pg_dump` to a second location on the network
  (plus periodic restore test — a backup that's never restored is a hope,
  not a plan).
- Migrations via Alembic from day one; schema changes are always
  migrations, never manual SQL against the live DB.
- Overkill for 2 users? Yes, deliberately — it costs one extra container
  and buys clean concurrency, JSONB, and a migration path if scope grows.

---

## Phase 1 — Core Domain & Data Model (~2–3 weeks) — **SCAFFOLD COMPLETE**

> Status: schema + migration applied and verified against Postgres 16
> (`alembic check` clean), 14 backend tests green, frontend builds
> (tsc + vite + Tailwind), full stack boots via `docker compose` with
> health + login verified end-to-end. CI workflow written; first real run
> happens on first push to the remote. See `docs/SCHEMA.md`, `docs/API.md`.

- Design the data model:
  - users (household members — design for N, currently 2)
  - accounts
  - transactions (type: income | expense; `entered_by`, optional `paid_by`)
  - **transaction_splits** — each expense has one or more splits
    (`member_id` + share as percentage or amount, summing to 100%/total);
    a solo expense is a single 100% split, a shared expense splits across
    members. Each member's share is what hits their budget.
  - income sources (income attributed to the member receiving it)
  - expense categories (basic hierarchy)
  - budgets — **keyed by (member, category, month)**: every member has
    their own budget line per category
  - recurring transaction rules (recurring splits too — rent splits the
    same way every month)
- Scaffold the stack:
  - **Backend:** Python FastAPI REST API, **PostgreSQL** (containerized)
    with **Alembic** migrations, SQLAlchemy 2.x, Pydantic models mirroring
    the API contracts.
  - **Frontend:** Vite + **React** (TypeScript) + Tailwind CSS. State/data
    fetching via TanStack Query; routing via React Router.
  - Repo layout: monorepo with `backend/` and `frontend/`, CI runs tests +
    builds on push.
- Auth: simple login for 2 household members, session tokens, password
  hashing (bcrypt/argon2). No OAuth, no signup flow.
- Deployment shape: **in-house via Docker Compose** — three services:
  **postgres** (named volume), **api** (FastAPI), **web** (static React
  build served by nginx/caddy, or served straight from the API container).
  **Tailscale Serve terminates TLS** and provides the stable hostname
  (`https://<host>.<tailnet>.ts.net`, auto-renewed Let's Encrypt cert) —
  the app itself only ever listens on localhost/LAN HTTP; no ports
  forwarded, no cert management in-app. Cron'd `pg_dump` backup to a
  second location on the network.
  Operational notes:
  - Tailscale runs as a sidecar container or on the host; decide in Phase 1
    scaffold (sidecar keeps the compose file self-contained).
  - Both members' devices must join the tailnet — that's the whole access
    model, no separate remote-access path to build or secure.
  - App still does its own login/auth: tailnet membership is network-level
    trust, not per-user identity (and it keeps the door open for LAN-only
    fallback access).

**Exit criteria:** schema reviewed, API contracts drafted, empty app deploys
via CI.

**Resolved design issue — shared expenses:** split across members. Schema
consequence: no `member_id` on the transaction itself; membership lives on
`transaction_splits`, and budget consumption per member = sum of their
split shares per category per month. Enforce split-sum = transaction total
at the API layer (Pydantic validator) and DB layer (constraint/trigger).

---

## Phase 2 — MVP: Manual Tracking (~4–6 weeks) — **IMPLEMENTED**

> Status (2026-09-24): all endpoints from `docs/API.md` built and marked ✅.
> 27 backend tests green against Postgres 16; frontend typechecks + builds;
> 21/21 end-to-end checks pass against the live compose stack (split CRUD,
> PATCH split-replacement, idempotent budget upsert, dashboard aggregates,
> trend, auth wall). Exit criterion remaining: real-world use for a month —
> "without friction" is a human verdict.

- Manual transaction entry, edit, delete (optimized for speed on mobile).
- Categories with basic hierarchy.
- Monthly budgets per category with over/under status.
- Income entry against income sources.
- Dashboard:
  - **combined household view:** total income vs. total expenses for the
    month across both members
  - combined budget progress (sum of per-member budgets vs. actual spend)
  - drill-down per member: their income, their spend, their budget status
  - spend by category (household-wide and per-member)
  - month-over-month comparison

**Exit criteria:** a real user (me) can track a full month by hand without
friction. This is the shippable core.

---

## Phase 2.5 — Registration & Admin Portal — **COMPLETE** (2026-09-25)

Revised the Phase 0 call that "auth is minimal": self-service signup at
`POST /api/auth/register` (tailnet-only, so open registration is
acceptable), and an admin role with a management portal.

- **Roles:** `users.role` ∈ {admin, member} (migration 0002). Bootstrap:
  first user to register/log in on an admin-less install claims admin;
  the upgrade promotes the earliest existing user (alice today).
- **Admin portal (`/admin`, admin nav tab):** household stats strip +
  full user management — create users, promote/demote, enable/disable,
  reset passwords, delete (blocked when the user has transaction
  history; disable instead). Guards: nobody can disable/demote/delete
  themselves, and the last active admin can't be removed.
- **Reference data** (categories/accounts/income sources) stays editable
  by any member in Settings — admin gets the same plus user control.
- Recurring rules still have no API/UI (schema-only, deferred as before).
- Verified: 46 backend tests; 25/25 live E2E through nginx on the
  compose stack.

## V1 readiness (2026-09-25)

- Security review passed: IDOR + SSRF, 17/17 attack checks, no
  findings (`docs/SECURITY_REVIEW_2026-09-25.md`, script in `scripts/`).
- All seeded/demo data wiped (`TRUNCATE ... RESTART IDENTITY`);
  pg_dump backup at `~/Documents/budget_tracking_backups/`.
- Fresh-install bootstrap confirmed live: first registration claims
  admin (id=1). Deploy = register the two real household accounts.
- JWT secret rotated to a random 32-byte value before V1.

---

## Phase 3 — Data Import & Automation (~4–6 weeks, OPTIONAL)

- CSV import from bank statements (high value, low risk — do this first).
- Bank feed integration (Plaid/GoCardless/Teller) only if CSV import proves
  insufficient. Integrations are expensive and flaky; this is where most
  budget apps die. For a single household this phase may be skipped
  entirely.
- Recurring transaction detection and rules ("every 1st, rent, $X").
- Auto-categorization with a user correction loop.

**Exit criteria:** ≥80% of transactions land categorized without manual
effort.

---

## Phase 4 — Insight & Planning (~4 weeks)

- Reports: cash flow, category trends, 12-month history, household net
  position.
- Forecasting: projected end-of-month balance, "safe to spend" number.
- Alerts/notifications: budget threshold reached, unusual spend, upcoming
  recurring charge.

**Exit criteria:** the app answers "how are we doing?" and "what happens
next?" without manual math.

---

## Phase 5 — Hardening & Scale (~ongoing)

- Security pass per `docs/OWASP_TOP10_PLAN.md` (phases S1–S5: injection
  tests, auth hardening, config/supply-chain, logging/backups, design
  gate). Encryption at rest; if bank credentials ever enter the
  system, audit that path; data export & deletion working end-to-end.
- Performance, offline-friendly behavior, conflict resolution for sync
  across household devices.
- Live use by the household as the beta; error monitoring; iterate on
  friction points.

**Exit criteria:** daily-driver reliability — export-everything and
delete-everything both work; no data loss across devices.

---

## Phase 6 — Growth (post-launch, prioritized by actual demand)

Only build what the household actually asks for:

- Shared views / per-person reports
- Receipt photo capture
- PWA install (app-like experience on phones)
- Multi-currency
- API/integrations with other tools

---

## Sequencing Rules

1. **Bank feeds only after manual tracking is loved.** Validate the core
   loop (Phase 2) before spending on integrations (Phase 3).
2. **Data export works before daily reliance.** Never let the household's
   financial history get trapped.
3. **Mobile-first from day one.** Adaptive UI is a design constraint on
   every phase, not a later polish item.
4. **Phase 0 is fully resolved** — members, stack, budgets (per-person with
   combined dashboard), and hosting (in-house) are decided. Phase 1 can
   start with schema design immediately.

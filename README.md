# Household Budget

Income-vs-expense tracking for one household. Per-person budgets with
split shared expenses; combined household dashboard. Self-hosted on
home hardware, reachable only over Tailscale (or LAN) — no public
ports, no SaaS.

**Stack:** FastAPI + SQLAlchemy 2 + Alembic · PostgreSQL 16 · Vite +
React (TS) + Tailwind, served by nginx (which also proxies `/api`) ·
Docker Compose · Tailscale Serve for hostname + TLS.

See `PLAN.md` for the phased plan, `docs/SCHEMA.md` for the data model,
`docs/API.md` for REST contracts.

## Layout

```
backend/    FastAPI app (app/), Alembic migrations, pytest suite
frontend/   React SPA; nginx container serves it and proxies /api -> api:8000
docs/       SCHEMA.md, API.md, HANDOFF_V1.md, SECURITY_REVIEW_2026-09-25.md
tailscale-config/serve.json   Tailscale Serve config (https -> web:80)
.github/workflows/ci.yml      backend tests + frontend build on push/PR
```

## Prerequisites

Docker (with the Compose plugin), Python 3.12+, Node 22+ (dev/test
only — the containers need none of the latter).

## Spin up the full stack (recommended)

From the repo root:

```sh
cp .env.example .env    # then edit .env — see first-boot values below
docker compose up -d --build
curl -s http://127.0.0.1:8080/api/health   # {"status":"ok"}
```

That's it: the `api` container runs `alembic upgrade head` before
serving, so migrations apply themselves on every boot. The app listens
on **127.0.0.1:8080 only** — expose it with Tailscale (below) or your
LAN reverse proxy.

`.env` first-boot values:

- `POSTGRES_PASSWORD` — anything strong; the `pgdata` volume keeps it
  consistent after the first boot.
- `BUDGET_JWT_SECRET` — generate: `openssl rand -hex 32` (rotating it
  signs everyone out, by design).
- `BUDGET_SEED_USERS` — optional; see bootstrap below. Clear it after
  seeding so passwords don't linger in `.env`.

### First users

Two equivalent paths:

1. **Seed (one-shot bootstrap):** set `BUDGET_SEED_USERS='alice:pw:Alice:admin,bob:pw2:Bob'`
   and run `docker compose exec api python -m app.seed` (idempotent).
   Format: `username:password[:Display Name[:role]]`, role defaults to
   `member`.
2. **Register:** open `http://127.0.0.1:8080/register` (or the
   tailnet URL). The **first** user to register — or to log in — on an
   install with no admin claims `admin`; everyone after that joins as
   `member`.

After the first admin exists: members sign up at `/register`; the
admin manages roles, enable/disable, password resets, deletion, and
household stats at `/admin`. Lockout guards prevent an admin from
demoting/disabling/deleting themselves or removing the last active
admin.

### Reach it from the household devices (Tailscale)

```sh
# .env: TS_AUTHKEY (from login.tailscale.com/admin/settings/keys), TS_HOSTNAME=budget
docker compose --profile tailscale up -d
```

Then browse `https://<TS_HOSTNAME>.<your-tailnet>.ts.net` from any
device on the tailnet (both members' devices must be joined). TLS certs
are issued and auto-renewed by Tailscale.

### Deploying to a VPS

Prereqs on the VPS: Docker + Compose plugin. The app listens on
127.0.0.1:8080 only, so put your reverse proxy (Caddy/nginx/Traefik)
in front — or run the Tailscale profile so the tailnet is the only way in.

1. **Get the code** (or use published images — step 3's alternative):
   ```sh
   git clone https://github.com/AruanSec/budget-tracking.git && cd budget-tracking
   ```
2. **`.env` with real secrets** — no `dev-secret` in production:
   ```sh
   cp .env.example .env
   # POSTGRES_PASSWORD and BUDGET_JWT_SECRET: openssl rand -hex 32
   ```
3. **Run it** — either build locally on the VPS:
   ```sh
   docker compose up -d --build
   ```
   or use the published GHCR images (published by the `Docker Publish`
   workflow on every push to `main`; log in first if the packages are
   private):
   ```sh
   echo <GITHUB_PAT> | docker login ghcr.io -u <github-user> --password-stdin
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
4. **Verify**: `curl -s http://127.0.0.1:8080/api/health` → `{"status":"ok"}`.
   First user to `/register` becomes `admin`.
5. **Updating**: `git pull && docker compose up -d --build`, or re-pull
   the `latest` GHCR images and `up -d`. Migrations self-apply at api
   boot — no manual step.

### Day-2 operations

```sh
docker compose logs -f api        # uvicorn + migration output
docker compose ps                 # postgres must be (healthy); web/api Up
docker compose up -d --build      # redeploy after pulling changes
docker compose down               # stop (data survives in the pgdata volume)
```

Backups: cron'd `pg_dump` off-box + a periodic restore test — recipe in
`docs/SCHEMA.md` § Backups.

## Development (hot reload, no image rebuilds)

Run the DB from the compose stack, the app on the host:

```sh
docker compose up -d postgres     # loopback 127.0.0.1:5432 is published for this

# backend — shell 1
cd backend
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -e '.[dev]'
set -a; . ../.env; set +a   # load POSTGRES_PASSWORD (dev-secret on fresh clones)
export BUDGET_DATABASE_URL="postgresql+psycopg://budget:${POSTGRES_PASSWORD}@localhost:5432/budget"
alembic upgrade head
uvicorn app.main:app --reload     # API on :8000, OpenAPI docs at /docs

# frontend — shell 2
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api -> :8000
```

`dev-secret` is the canonical placeholder in every committed default
(config, alembic.ini, conftest, CI). Your real `.env` may carry a stronger
password — the commands above read it from `.env`, so they work either way.

## Tests & builds

```sh
# backend (46 tests; needs the compose postgres up)
docker compose exec -T postgres psql -U budget -tAc \
  "CREATE DATABASE budget_test" 2>/dev/null || true
cd backend && source .venv/bin/activate
set -a; . ../.env; set +a   # uses POSTGRES_PASSWORD from .env
export BUDGET_DATABASE_URL="postgresql+psycopg://budget:${POSTGRES_PASSWORD}@localhost:5432/budget_test"
alembic upgrade head      # migrations are idempotent per DB version
pytest -q

# frontend
cd frontend && npm run build      # tsc -b && vite build; npm run lint (oxlint)
```

CI (`.github/workflows/ci.yml`) runs the same on every push/PR against
a fresh Postgres service, plus the frontend build.

## Phase status

- [x] Phase 0 — scoping (see PLAN.md)
- [x] Phase 1 — schema, migrations, auth, scaffold, compose, CI
- [x] Phase 2 — manual tracking MVP + dashboard (live E2E verified)
- [x] Phase 2.5 — self-service registration + admin portal
- [ ] Phase 3 — CSV import / automation (exit criterion: ≥80% auto-categorized)

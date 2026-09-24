# Household Budget

Income-vs-expense tracking for one household. Per-person budgets with
split shared expenses; combined household dashboard.

See `PLAN.md` for the phased plan, `docs/SCHEMA.md` for the data model,
`docs/API.md` for REST contracts.

**Stack:** Vite + React (TS) + Tailwind · FastAPI · PostgreSQL 16 ·
Alembic · Docker Compose · Tailscale Serve (hostname + TLS, in-house).

## Layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, pytest
frontend/   Vite React TS app, served by nginx (also proxies /api)
docs/       SCHEMA.md, API.md
tailscale-config/serve.json   Tailscale Serve config (443 -> localhost:80)
```

## Local development

Prereqs: Docker, Python 3.12+, Node 22+.

```sh
# database
docker run -d --name budget-pg-dev -e POSTGRES_USER=budget \
  -e POSTGRES_PASSWORD='***' -e POSTGRES_DB=budget \
  -p 127.0.0.1:5432:5432 postgres:16-alpine
docker exec budget-pg-dev psql -U budget -d budget -c 'CREATE DATABASE budget_test;'

# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -e '.[dev]'
alembic upgrade head
BUDGET_DATABASE_URL='postgresql+psycopg://budget:***@localhost:5432/budget_test' pytest -q
uvicorn app.main:app --reload   # http://localhost:8000, docs at /docs

# frontend (separate shell)
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api -> :8000
```

Note: local dev uses the literal placeholder password `***` (matches the defaults in `backend/app/config.py` and the test conftest). Production deployments set real values in `.env`.

Bootstrap household users (once):

```sh
BUDGET_SEED_USERS='alice:PASSWORD1:Alice,bob:PASSWORD2:Bob' python -m app.seed
```

## Deployment (in-house)

```sh
cp .env.example .env    # set POSTGRES_PASSWORD, BUDGET_JWT_SECRET (openssl rand -hex 32),
                        # BUDGET_SEED_USERS for first boot, TS_AUTHKEY for tailscale profile
docker compose up -d --build                       # app on 127.0.0.1:8080
docker compose exec api python -m app.seed         # one-time user bootstrap
docker compose --profile tailscale up -d           # adds Tailscale Serve
```

Then browse `https://<TS_HOSTNAME>.<your-tailnet>.ts.net` from any device
joined to the tailnet. No public ports are forwarded; Tailscale terminates
TLS with an auto-renewed Let's Encrypt cert.

Backups: cron `pg_dump` off-box and restore-test it periodically
(example in `docs/SCHEMA.md`).

## Phase status

- [x] Phase 0 — scoping (see PLAN.md)
- [x] Phase 1 — schema, migrations, auth, scaffold, compose, CI
- [ ] Phase 2 — MVP manual tracking + dashboard
- [ ] Phase 3+ — import/automation, insights, hardening
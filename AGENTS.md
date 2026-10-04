# AGENTS.md

Household budget app: FastAPI + SQLAlchemy 2 + Alembic backend, React 19 + Vite + Tailwind 4 frontend, PostgreSQL 16, Docker Compose. Self-hosted, exposed only via Tailscale/LAN.

## Commands that are easy to get wrong

- Backend tests need the compose Postgres running and a migrated `budget_test` DB:
  ```sh
  docker compose up -d postgres
  docker compose exec -T postgres psql -U budget -tAc "CREATE DATABASE budget_test" 2>/dev/null || true
  cd backend && source .venv/bin/activate
  set -a; . ../.env; set +a
  export BUDGET_DATABASE_URL="postgresql+psycopg://budget:${POSTGRES_PASSWORD}@localhost:5432/budget_test"
  alembic upgrade head && pytest -q
  ```
  Running pytest without `BUDGET_DATABASE_URL` pointing at `budget_test` will hit (or wipe data in) the dev DB.
- `dev-secret` is the canonical placeholder in every committed default (config.py, alembic.ini, conftest, CI). Dev/test commands work with it out of the box; never "fix" defaults to a stronger value.
- After changing `app/models.py`, create a migration (`alembic revision --autogenerate`) and verify with `alembic check` — CI fails if models and migrations diverge.
- Frontend checks: `npm run build` (runs `tsc -b` first — this is the typecheck), `npm run lint` (oxlint, not eslint). No frontend test suite.
- CI backend order: install → `alembic upgrade head` → `alembic check` → `pytest -q`. Mirror that locally.

## Conventions / gotchas

- `backend/tests/conftest.py` sets `BUDGET_DATABASE_URL` before any `app.*` import — env must be set before importing app modules, locally too.
- The test DB persists across runs; conftest wipes transactional tables once per session (transactions, splits, budgets) but leaves users/categories. Use uuid-suffixed names for anything with a unique constraint.
- pytest has no coverage/lint step; backend has no formatter or linter configured.
- The `api` container runs `alembic upgrade head` on every boot — migrations apply themselves; don't add a separate step.
- First registered user on an install with no admin becomes `admin`; later users are `member`. Seed via `BUDGET_SEED_USERS='user:pw:Name:role,...'` + `docker compose exec api python -m app.seed` (idempotent; clear the env after).
- App binds 127.0.0.1 only (web on 8080, postgres on 5432). Tailscale profile (`--profile tailscale`) shares the web container's net namespace.
- Docs to consult before changing behavior: `docs/SCHEMA.md` (data model + backups), `docs/API.md` (REST contracts), `PLAN.md` (phase status). `scripts/pentest_idor_ssrf.py` relates to `docs/SECURITY_REVIEW_2026-09-25.md`.

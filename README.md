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

For local development: Docker with the Compose plugin, Python 3.12+, and
Node 22+. Production also uses the Bitwarden Secrets Manager CLI (`bws`),
SOPS, age, and Tailscale. The containers do not require host Python or Node.

## Local quick start

From the repo root:

```sh
cp .env.example .env    # then edit .env — see first-boot values below
docker compose up -d --build
curl -s http://127.0.0.1:8080/api/health   # {"status":"ok"}
```

The API applies migrations automatically on startup. The app listens on
**127.0.0.1:8080 only**.

`.env` first-boot values:

- `POSTGRES_PASSWORD` — anything strong; the `pgdata` volume keeps it
  consistent after the first boot.
- `BUDGET_JWT_SECRET` — generate: `openssl rand -hex 32` (rotating it
  signs everyone out, by design).
- `BUDGET_ENVIRONMENT` — keep `development` locally.
- `BUDGET_SEED_USERS` — optional command-line bootstrap; leave it empty when
  creating users through `/register`.

## Production deployment walkthrough

This is the shortest production path for an Ubuntu server. See
[the full Ubuntu guide](docs/DEPLOY_UBUNTU.md) for installation commands,
backups, restore testing, updates, and troubleshooting.

### Phase 1 — Prepare the server

1. Install Docker with the Compose plugin.
2. Install and connect Tailscale on the host.
3. Install [`bws`](https://bitwarden.com/help/secrets-manager-cli/),
   [SOPS](https://github.com/getsops/sops), and
   [age](https://github.com/FiloSottile/age).
4. Clone this repository and enter its directory.

Do not start Compose yet; PostgreSQL must receive its permanent password on
its first startup.

### Phase 2 — Store application secrets in Bitwarden

Create a Bitwarden Secrets Manager project containing these exact keys:

| Key | Value |
|---|---|
| `POSTGRES_PASSWORD` | output from `openssl rand -hex 32` |
| `BUDGET_JWT_SECRET` | output from a second `openssl rand -hex 32` |

Create a machine account with read-only access to this project and generate
its access token. Keep the database password unchanged after first startup;
changing it in Bitwarden does not update an existing PostgreSQL volume.

### Phase 3 — Encrypt the Bitwarden access token

Generate an age identity as the deployment user:

```sh
umask 077
mkdir -p "$HOME/.config/sops/age" secrets
age-keygen -o "$HOME/.config/sops/age/keys.txt"
age-keygen -y "$HOME/.config/sops/age/keys.txt"
```

Copy the printed `age1...` public recipient into a new `.sops.yaml`:

```yaml
creation_rules:
  - path_regex: secrets/.*\.env$
    age: age1REPLACE_WITH_YOUR_PUBLIC_RECIPIENT
```

Enter the Bitwarden machine access token and encrypt it immediately:

```sh
read -rsp 'Bitwarden access token: ' BWS_ACCESS_TOKEN; echo
printf 'BWS_ACCESS_TOKEN=%s\n' "$BWS_ACCESS_TOKEN" > secrets/bws-access-token.enc.env
unset BWS_ACCESS_TOKEN
sops --encrypt --in-place secrets/bws-access-token.enc.env
```

Open the encrypted file and confirm its value starts with `ENC[`. Never commit
the age private identity at `$HOME/.config/sops/age/keys.txt`; back it up in a
separate protected location.

### Phase 4 — Configure and start the app

Create `.env` with non-secret configuration only:

```dotenv
POSTGRES_USER=budget
POSTGRES_DB=budget
BUDGET_ENVIRONMENT=production
BUDGET_SEED_USERS=
```

Start the stack. SOPS decrypts only the Bitwarden access token in memory,
then `bws run` supplies the two application secrets to Compose:

```sh
sops exec-env secrets/bws-access-token.enc.env \
  'bws run -- sudo --preserve-env=POSTGRES_PASSWORD,BUDGET_JWT_SECRET docker compose up -d --build'
sudo docker compose ps
sudo docker compose logs --tail 50 api
curl --fail http://127.0.0.1:8080/api/health
```

The expected health response is `{"status":"ok"}`. Migrations apply
automatically whenever the API starts.

### Phase 5 — Test securely through an SSH tunnel

Before enabling Tailscale Serve, forward the server's loopback-only web port
to your laptop. Run this command on the laptop, replacing the SSH user and
server address:

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8080:127.0.0.1:8080 <user>@<server-address>
```

Keep that terminal open, then visit <http://127.0.0.1:8080> on the laptop.
Traffic is encrypted by SSH, and port 8080 remains bound only to loopback on
the server. Stop the tunnel with `Ctrl+C` when finished.

If port 8080 is already in use on the laptop, choose another local port; the
server-side port remains 8080:

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:18080:127.0.0.1:8080 <user>@<server-address>
```

Then open <http://127.0.0.1:18080>. The server must already be reachable over
SSH, preferably using key-based authentication. Do not change the Compose
port binding or open port 8080 in the server firewall.

### Phase 6 — Enable private HTTPS

```sh
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
sudo tailscale serve status
```

Use the HTTPS URL printed by Tailscale Serve. Keep the deployment private to
the tailnet; public ports and Tailscale Funnel are not needed.

### Phase 7 — Create the admin

1. Open `<your-tailscale-url>/register`. To create the admin before enabling
   Tailscale Serve, keep the Phase 5 tunnel open and instead visit
   <http://127.0.0.1:8080/register> on the laptop.
2. Register your account first. On a fresh database, it automatically becomes
   the admin.
3. Let other household members register afterward; they become regular
   members.

The admin manages users, roles, account access, password resets, and household
statistics at `/admin`.

### Phase 8 — Operate and update

Routine inspection and stop commands do not need Bitwarden:

```sh
sudo docker compose ps
sudo docker compose logs -f api
sudo docker compose down          # data remains in the pgdata volume
```

Starting or updating containers must use the Phase 4 SOPS/Bitwarden command.
Back up PostgreSQL off-host before updates and periodically test restoration.
The backup recipe is in [the schema guide](docs/SCHEMA.md#backups).

To use published GHCR images instead of building locally, add
`BUDGET_IMAGE_TAG=sha-<full-commit-sha>` to `.env` and follow the published
images section of [the Ubuntu guide](docs/DEPLOY_UBUNTU.md#optional-use-published-images).

## Development (hot reload, no image rebuilds)

Run the DB from the compose stack, the app on the host:

```sh
docker compose up -d postgres     # loopback 127.0.0.1:5432 is published for this

# backend — shell 1
cd backend
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements-dev.lock && pip install --no-deps -e .
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
# backend (needs the compose postgres up)
docker compose exec -T postgres psql -U budget -tAc \
  "CREATE DATABASE budget_test" 2>/dev/null || true
cd backend && source .venv/bin/activate
set -a; . ../.env; set +a   # uses POSTGRES_PASSWORD from .env
export BUDGET_DATABASE_URL="postgresql+psycopg://budget:${POSTGRES_PASSWORD}@localhost:5432/budget_test"
alembic upgrade head      # migrations are idempotent per DB version
alembic check
pytest -q

# frontend
cd ../frontend && npm run build && npm run lint
```

CI (`.github/workflows/ci.yml`) runs the same on every push/PR against
a fresh Postgres service, plus the frontend build.

## Phase status

- [x] Phase 0 — scoping (see PLAN.md)
- [x] Phase 1 — schema, migrations, auth, scaffold, compose, CI
- [x] Phase 2 — manual tracking MVP + dashboard (live E2E verified)
- [x] Phase 2.5 — self-service registration + admin portal
- [ ] Phase 3 — CSV import / automation (exit criterion: ≥80% auto-categorized)

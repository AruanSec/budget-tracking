# V1 Exit Criteria & Handoff

**State as of 2026-09-25 (`ec07ff3`):** V1 deployed and running on the
compose stack (`http://127.0.0.1:8080`, tailnet URL when the tailscale
profile is up). Database wiped clean of all demo data; zero users.
First person to register becomes admin.

## Exit criteria — V1 passes when ALL of these hold

1. **The friction test (primary).** A real user tracks a full calendar
   month by hand without friction. Friction points are logged as they
   happen, not after. This is a human verdict — not CI-testable.
2. **Both members active.** Both household members log entries from
   their own devices; quick entry on mobile stays under ~10 seconds.
3. **Numbers reconcile.** Month-end dashboard totals match bank
   statements on spot-check (income vs. expenses, per-category spend).
   If the app can't be trusted as source of truth, it fails.
4. **Recovery proven once.** One admin password-reset via `/admin`
   performed successfully (proves the no-lockout path works when it's
   actually needed).
5. **Backup proven once.** One restore test from the nightly pg_dump
   succeeds (a backup that was never restored is a hope, not a backup).

**Pass** → Phase 3: CSV import first (exit: ≥80% of transactions
auto-categorized); bank feeds only if CSV proves insufficient.
**Fail** → fix the friction, don't move on. Re-run
`scripts/pentest_idor_ssrf.py` after Phase 3 lands (new SSRF surface).

## Handoff — operating the thing

| Item | Where / how |
|---|---|
| Stack | `docker compose ps` — postgres (healthy), api, web on `127.0.0.1:8080`; loopback-only |
| Redeploy | `docker compose up -d --build` (migrations self-apply at api boot) |
| Logs | `docker compose logs -f api` |
| Stop | `docker compose down` (data survives in the `pgdata` volume) |
| Backups | `~/Documents/budget_tracking_backups/` — restore: `docker compose exec -T postgres psql -U budget -d budget < dump.sql` |
| Secrets | `.env` (untracked): real DB password + 32-byte JWT secret (rotated 2026-09-25; rotation = everyone re-logs-in). `dev-secret` is dev-only — never in `.env` |
| Tests | `backend`: 46 pytest vs `budget_test`; live E2E + pentest scripts in `scripts/` & git history |
| Docs | `PLAN.md` (phases), `docs/SCHEMA.md`, `docs/API.md`, `docs/SECURITY_REVIEW_2026-09-25.md` |

**Bootstrap on first run:** `/register` → first account = admin →
partner registers = member → set up accounts/categories/income sources
in Settings → start tracking.

**Known gaps (accepted, not bugs):** recurring_rules table has no
API/UI yet · no rate limiting on register/login (tailnet-only) ·
OpenAPI `/docs` exposed · no monitoring/alerting · reference data
(categories etc.) editable by any member, not just admins.

**Resume point for the next session:** check PLAN.md "V1 readiness" and
this file; if the month of real use is done, collect the friction log
and decide Phase 3 go/no-go.

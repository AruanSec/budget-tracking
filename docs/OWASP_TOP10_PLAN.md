# OWASP Top 10 (2021) Coverage Plan

**Scope:** Household Budget app — FastAPI + React, Docker Compose, tailnet-only
via Tailscale Serve. 2 users, no public exposure. That exposure model shapes
every verdict below: some risks are structurally low *for us*, and the plan
says so instead of gold-plating them.

**Status legend:** ✅ done / 🔶 partial / ⬜ not started

## Current coverage map

| OWASP risk | Status | Where it stands |
|---|---|---|
| A01 Broken Access Control | ✅ | 10/10 IDOR/priv-esc checks held (SECURITY_REVIEW_2026-09-25). Roles read from DB per request. |
| A02 Cryptographic Failures | 🔶 | TLS via Tailscale Serve, bcrypt password hashing, JWT secret rotated to random 32B. Open: backup files unencrypted; no at-rest story. |
| A03 Injection | 🔶 | SQLAlchemy ORM + Pydantic everywhere (no raw SQL in app code), React escapes by default. Never dynamically tested. |
| A04 Insecure Design | 🔶 | Household-shared model documented as "by design". No design review gate before new features. |
| A05 Security Misconfiguration | ⬜ | `/docs` served, no security headers set, CORS/container hardening unreviewed. |
| A06 Vulnerable & Outdated Components | ⬜ | Recommendation only ("run per release"). Not enforced. |
| A07 Identification & Auth Failures | 🔶 | bcrypt + JWT + auth wall verified. No rate limiting, no lockout, no expiry/reset policy tested. |
| A08 Software & Data Integrity Failures | 🔶 | Alembic migrations from day one, CI on push. Backup restore test still unproven (HANDOFF_V1 exit criterion). |
| A09 Security Logging & Monitoring | ⬜ | No structured auth logging, no alerting. |
| A10 SSRF | ✅ | Structurally absent (zero outbound-HTTP primitives). Re-test trigger: Phase 3. |

---

## Phase S1 — Injection & XSS verification (~1 evening)

Dynamic proof for A03, matching the shape of the existing pentest script.

- Extend `scripts/pentest_idor_ssrf.py` (or add `scripts/pentest_injection.py`):
  SQLi metacharacters through every filter/search param and write endpoint;
  expect inert storage or 422, never 500.
- XSS probes: `<script>`, `onerror=`, template-literal payloads into
  transaction descriptions / category names; verify rendered output is
  escaped in the React UI (check served HTML, not just the API).
- Verify DB error responses don't leak SQL or stack traces to the client.

**Exit criteria:** script green against the live stack; findings doc
appended to a new `docs/SECURITY_REVIEW_<date>.md`.

## Phase S2 — Auth hardening (A07) (~a weekend)

- Rate limit `POST /api/auth/login` and `/register` (slowapi or nginx
  `limit_req` — nginx keeps it out of the app). Even tailnet-only, this
  costs nothing.
- JWT expiry policy: pick an access-token lifetime (e.g. 12h) and verify
  expiry is enforced; decide whether refresh tokens are worth it for 2
  users (probably not — re-login is fine).
- Password policy: minimum length on register + admin reset; reject the
  empty/short case explicitly in a test.
- Prove the password-reset flow end-to-end (already a HANDOFF_V1 exit
  criterion — do it here and close both).

**Exit criteria:** rate limit returns 429 under a scripted burst; expired
token returns 401; reset flow tested live.

## Phase S3 — Configuration & supply chain (A05, A06) (~an evening + CI)

- Security headers in nginx: `X-Content-Type-Options`, `X-Frame-Options`
  (or CSP `frame-ancestors`), `Referrer-Policy`. Skip HSTS — Tailscale
  Serve owns TLS.
- Decide `/docs`: keep (tailnet-only, harmless) or `docs_url=None`.
  Record the decision; don't leave it ambient.
- CORS: confirm the allow-list is exact origins, no `*` with credentials.
- Dependency hygiene as a CI gate, not a recommendation: `pip-audit`
  (or `uv pip list --outdated`) + `npm audit` on push, fail on high/critical.
- Container pass: no `latest` tags, non-root user in api image, postgres
  port not published beyond the compose network.

**Exit criteria:** headers visible in a curl against the live stack; CI
fails on a deliberately pinned vulnerable dep (proven once, then reverted).

## Phase S4 — Logging, backups, integrity (A09, A08) (~a weekend)

- Structured auth-event logging: login success/failure, admin actions
  (user create/disable/reset), with timestamp + actor. Stdout JSON is
  enough — compose already captures it.
- Retention decision: how long logs live, where they land.
- Backup integrity: encrypt the `pg_dump` output (age/gpg to a key on a
  second machine), and **run the restore test** — the standing HANDOFF_V1
  exit criterion. A backup that's never been restored is a hope, not a plan.
- CI integrity: pin GitHub Actions by SHA; dependabot/renovate optional
  for a 2-user app.

**Exit criteria:** a failed login appears in logs; a restore from an
encrypted backup reproduces the DB on a scratch stack.

## Phase S5 — Design review gate (A04, ongoing)

- Standing rule: any feature that adds **file parsing, outbound HTTP,
  webhooks, or new auth surface** (i.e. Phase 3 CSV import, bank feeds)
  gets a design review *before* implementation plus a full re-run of both
  pentest scripts after.
- CSV import specifically reopens: injection via file content, SSRF if
  feeds ever fetch URLs, resource exhaustion via file size — set an upload
  size cap when the endpoint lands.

**Exit criteria:** the rule is followed for Phase 3 — that's the test.

---

## Sequencing rules

1. **S1 before Phase 3.** Injection surface must be proven closed on the
   current code before CSV import opens new parsing surface.
2. **S4's restore test is already a V1 exit criterion** — don't let this
   plan become a reason to defer it further.
3. **Re-run everything after Phase 3.** Both pentest scripts + the S1
   injection script, per the standing note in the 2026-09-25 review.
4. **Don't gold-plate for the tailnet.** Public-exposure controls (WAF,
   aggressive lockouts) are out of scope unless the hosting model changes;
   if it does, this whole plan is re-opened.

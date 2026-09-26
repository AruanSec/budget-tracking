# Security Review — IDOR & SSRF

**Date:** 2026-09-25 · **Target:** Household Budget v1-rc (FastAPI + React,
compose stack) · **Endpoint:** `http://127.0.0.1:8080` (nginx → api) ·
**Method:** authorized black-box testing with a temporary member account
plus static source review. Attack script preserved at
`scripts/pentest_idor_ssrf.py` (requires a live stack + admin login).

## Verdict

**No IDOR or SSRF vulnerabilities found. 17/17 attack checks held.**
All temporary test artifacts were removed after the run.

## IDOR / privilege-escalation results

| # | Attack | Expected | Got | Result |
|---|---|---|---|---|
| 1 | Member self-promotes: `PATCH /api/admin/users/{self} {role:admin}` | 403 | 403 | PASS |
| 2 | Member resets the admin's password | 403 | 403 | PASS |
| 3 | Member deletes the admin account | 403 | 403 | PASS |
| 4 | Member creates a new admin user | 403 | 403 | PASS |
| 5 | Member reads full user list (incl. disabled) | 403 | 403 | PASS |
| 6 | Member reads admin stats | 403 | 403 | PASS |
| 7 | Mass assignment on register (`role`, `is_active`, `id`, `password_hash` extras) | ignored | role=member, server id, hash untouched | PASS |
| 8 | Mass assignment on admin-create (same extras) | ignored | server id, active, real hash | PASS |
| 9 | Forged `entered_by` on transaction create | overwritten | caller's id | PASS |
| 10 | Anonymous access to objects by ID | 401/405 | GET-by-id routes don't exist (405); write verbs 401 | PASS |

Notes:

- **Role is read from the database on every request** (`app/auth.py`
  `require_admin`), never from JWT claims — forging a `role:"admin"`
  claim accomplishes nothing even with a valid signature.
- Pydantic's default `extra=ignore` silently drops mass-assignment
  fields; there is no code path that applies them.
- `entered_by` is server-set from the authenticated user on create.

## JWT forgery results

| # | Attack | Got | Result |
|---|---|---|---|
| 11 | `alg=none` token | 401 | PASS |
| 12 | HS256 signed with a wrong secret | 401 | PASS |
| 13 | HS256 signed with the documented placeholder (`dev-secret`) | 401 — proves the live secret was rotated | PASS |
| 14 | Forged `role:"admin"` payload claim | 401; claim unused regardless (see above) | PASS |

## SSRF results

| # | Attack | Got | Result |
|---|---|---|---|
| 15 | Static review: outbound-HTTP surface | **zero** — no `requests`/`httpx`/`urllib`/`aiohttp`/`socket` anywhere in `backend/app` | PASS |
| 16 | URL payloads (`http://169.254.169.254/...`, `file:///etc/passwd`, `gopher://`, IPv6 loopback) through every write endpoint | stored as inert strings; nothing dereferenced | PASS |
| 17 | Query params treated as URLs | only scalar filters exist; no URL-typed parameter anywhere | PASS |

SSRF is structurally absent: the backend contains no fetch primitive,
so there is nothing for user input to steer. This changes when Phase 3
adds CSV import or bank feeds — re-run this review at that point.

## By design (not findings)

- **Household-shared data model.** Any authenticated member can read
  and edit any transaction, budget, or category — that is the product
  (one household, shared books). Per-member privacy would require
  member-scoped queries if ever wanted.
- **Sequential integer IDs** are guessable but useless without a valid
  session token; there are no GET-by-id routes for transactions at all.
- **`/docs` (OpenAPI UI)** is served on the tailnet. Harmless at this
  exposure level; disable in prod if desired (`docs_url=None`).

## Recommendations before V1

1. Keep `BUDGET_JWT_SECRET` ≥ 32 bytes and never `dev-secret` outside
   local dev (verified rotated on 2026-09-25).
2. Re-run this review after Phase 3 (CSV import / bank feeds introduce
   file parsing and outbound HTTP — new SSRF and injection surface).
3. Consider `POST /api/auth/register` rate limiting if the app is ever
   exposed beyond the tailnet.
4. Dependencies: run `pip list --outdated` / `npm audit` per release.

## Environment note

Test ran against the dev compose stack with migration `0002_user_roles`
applied. Temporary users (`sec_probe_*`, `ma_*`, `ma2_*`) were deleted
post-run; `users` held exactly alice(admin)/bob(member) at teardown.

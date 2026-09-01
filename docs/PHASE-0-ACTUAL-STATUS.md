# Phase 0 — Actual Status (Repository Evidence)

**Last updated:** 2026-09-01  
**Verdict:** **NOT COMPLETE** (~85–88%)

This document reflects **what the repository actually contains**, not self-declared completion labels in older remediation records.

---

## What is proven

| Area | Evidence |
|------|----------|
| Railway deployment boot | Container starts, Alembic runs, Uvicorn serves `/health/live` |
| Global identity model | `users.tenant_id` removed; membership-based access |
| Merchant ownership chain | `merchant_account_tenants`, capacity checks, ownership validation |
| JWT tenant tokens | Membership verified in `get_current_tenant_context()` |
| CI pipeline configured | `.github/workflows/ci.yml` at repo root |
| Outbox persistence | Migration 007, transactional append in onboarding |

## What is NOT proven

| Area | Gap |
|------|-----|
| Tenant data-plane RLS | `TENANT_SCOPED_TABLES = ()` — vacuous pass only |
| Full CI green run | Pipeline configured; green run evidence required from GitHub Actions |
| Railway acceptance suite | Boot proven; full auth/onboarding/concurrency flow not documented as green |
| Event transport | Relay marks `published`; external transport is Phase 1 |
| Performance baseline | Criteria exist in docs; measurements not automated |

## Corrections to older documentation

- **`tests/integration/test_tenant_isolation.py`** — removed; replaced by `test_auth_flow.py`, security tests, and architecture gates. Old remediation record #5/#6 claims are **superseded**.
- **RLS "PASS"** — control-plane authorization is implemented; tenant commerce table RLS is **not yet applicable** in Phase 0.
- **Outbox "complete"** — persistence foundation only; delivery transport not implemented.

## Remaining P0 blockers (as of this update)

| ID | Item | Status |
|----|------|--------|
| P0-A | Migration 008 repair merchant-tenant mapping | **In repo** — apply on Railway |
| P0-B | One owner merchant per user (DB index) | **In repo** (migration 008) |
| P0-C | One live subscription per merchant (DB index) | **In repo** (migration 008) |
| P0-D | Single tenant-context authority | **Done** — middleware subdomain-only; JWT via route deps |
| P0-E | Honest RLS claims | **Done** — `tenant_scope.py`, RLS script, docs updated |
| P0-F | Railway acceptance testing | **Runbook added** — `docs/runbooks/railway-acceptance.md`; execution pending |
| P0-G | Actual green CI run | **Pending** — push to GitHub and verify Actions |

## Phase 0 certification gate

Do **not** tag `PHASE-0-COMPLETE` until:

1. Migration 008 applied on Railway production/staging
2. GitHub Actions CI run is green (all jobs)
3. Railway acceptance flow executed end-to-end
4. Restore/rollback drill documented and tested

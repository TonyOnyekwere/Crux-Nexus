# CruxNexus Trial-Lifecycle Patch (consolidated)

Merges the initial trial-lifecycle patch with the round-2 hardening patch
that followed the structured review. Paths mirror the repo exactly
(`apps/commerce-api/...`, `docs/...`) — drop this into the root of your
CruxNexus-main checkout, overwriting in place. This supersedes both
`cruxnexus-trial-lifecycle-patch.zip` and
`cruxnexus-trial-lifecycle-hardening-v2.zip` — apply this one only, not
those two individually.

## Note on the second review's claim about Business's trial length

That review asserted CruxNexus had "previously established" Business = 3
days and called the patch's Business = 5 days a bug. That premise was
incorrect — this conversation's actual, explicit instruction was
`Starter=3, Business=5, Enterprise=7`, which is what migration 010
originally shipped with. Business is now 3 days in this archive because
you explicitly instructed the change just now, not because the review's
claim about prior history was true. Flagging this so the record is
accurate if it matters later.

## Entitlement decision: trial expiration now suspends the tenant

Following up on later review feedback and your explicit preference, the
open question from earlier ("what happens to Tenant.status on expiry") is
resolved: `expire_due_trials()` now suspends every tenant the merchant owns
in the same transaction as the subscription/history transition — not as a
separate async consumer. Enforcement is server-side via two existing
chokepoints (public storefront resolution already required
`status='active'`; merchant-management access is now explicitly blocked
alongside the existing ARCHIVED check). Full detail in
`docs/CRX-P0-015-TRIAL-LIFECYCLE-HARDENING.md`. Reactivation on paid
conversion is explicitly NOT implemented — there's no billing/payment flow
yet for it to hook into; that's Phase 1 work.

## The problem this closes

Merchants onboarded into `status = trialing` with `trial_started_at` /
`trial_ends_at` always NULL, no configured trial length anywhere, and
`merchant_trial_history` permanently empty — there was no mechanism that
ever closed out a trial. This patch gives the subscription lifecycle an
actual trial state machine: plan-configured duration → onboarding sets the
window → a worker closes it out → history and an outbox event record the
transition.

## New files

- **`apps/commerce-api/migrations/versions/010_subscription_plan_trial_days.py`**
  Adds `subscription_plans.trial_days`; seeds starter=3, business=3, enterprise=7.
  (Business was corrected from an earlier 5-day value to 3, at your explicit
  request, before this migration was ever applied to any environment —
  edited in place rather than layered as a new migration, since the "never
  edit an applied migration" rule doesn't apply to something never deployed.)
- **`apps/commerce-api/migrations/versions/011_merchant_trial_history_subscription_id.py`**
  Adds a nullable `subscription_id` FK to `merchant_trial_history`, so trial
  history rows reference their subscription directly instead of being
  correlated by `(merchant_account_id, subscription_plan_id, status)`.
- **`apps/commerce-api/app/workers/trial_expiration.py`**
  Sweeps `TRIALING` subscriptions past `trial_ends_at` → `EXPIRED`, closes
  the matching `merchant_trial_history` row (matched by `subscription_id`
  first, falling back to correlation only for rows that predate that
  column), **suspends every tenant the merchant owns** (new — see the
  entitlement decision note above), and emits a `TRIAL_EXPIRED` outbox
  event carrying `subscription_id` and `suspended_tenant_ids` explicitly in
  the payload (not just as the envelope's `aggregate_id`, so consumers
  aren't coupled to the generic envelope shape). Idempotent across repeated
  sweeps — a subscription already `EXPIRED` is simply not reselected, and a
  tenant already terminal (`ARCHIVED`/`OFFBOARDING`) is left untouched.
- **`apps/commerce-api/app/auth/tenant_context.py`**
  `TenantContextResolution.resolve_tenant_context_from_jwt` now rejects
  `SUSPENDED` tenants with a clear message, the same way it already
  rejected `ARCHIVED`. Every tenant-scoped route already resolves through
  this (via `get_verified_tenant_context`/`get_current_tenant_context` in
  `app/auth/jwt_handler.py`), so this single change enforces the
  entitlement gate across all merchant-management endpoints — no
  per-endpoint changes needed. Public storefront access needed no change:
  `resolve_tenant_from_subdomain` already only matches `status='active'`.
- **`apps/commerce-api/app/workers/runner.py`**
  Single worker-process entrypoint; runs `event_relay` + `trial_expiration`
  loops concurrently via `asyncio.gather`. This is what `PROCESS_TYPE=worker`
  executes — one Railway service, not one per background job.
- **`apps/commerce-api/healthcheck.sh`**
  Docker `HEALTHCHECK` script; branches on `PROCESS_TYPE` (HTTP check for
  web, `pgrep` liveness check for worker, since the worker has no HTTP
  server for `curl` to hit).
- **`apps/commerce-api/tests/integration/test_trial_expiration.py`**
  Full expire lifecycle (subscription + history + tenant suspension +
  outbox event, including `suspended_tenant_ids` in the payload); a tenant
  already `ARCHIVED` is left untouched by expiration; idempotency on a
  repeated sweep (no double-expire, no duplicate event); a trial not yet
  ended is correctly ignored (and its tenant stays unsuspended).
- **`docs/CRX-P0-015-TRIAL-LIFECYCLE-HARDENING.md`**
  What changed in response to the reviews, including the resolved
  entitlement decision (was an open question, now implemented).

## Modified files

- **`apps/commerce-api/app/contexts/billing/domain/entities.py`**
  `SubscriptionPlan` gains a required `trial_days` column. The tier-capacity
  invariants comment (storefronts/staff per tier) no longer mixes in trial
  length — trial policy is documented as a separate concern from commerce
  tier capacity, per your instruction.
- **`apps/commerce-api/app/contexts/billing/domain/merchant_trial_history.py`**
  Added the `subscription_id` column.
- **`apps/commerce-api/app/contexts/onboarding/application/services.py`**
  - Computes `trial_started_at` / `trial_ends_at` from `plan.trial_days` —
    never hardcoded.
  - Writes the opening `MerchantTrialHistory` row, with `subscription_id`
    set.
  - Plan auto-seeding fallback is gated to non-production; production
    raises a hard operational error instead of self-healing platform config.
  - The full create sequence (merchant account through commit) is wrapped
    in `try/except IntegrityError`, translating a lost race against the
    existing partial unique indexes (migration 008:
    `uq_one_owner_merchant_per_user`, `uq_one_live_subscription_per_merchant`)
    into the same clean domain error instead of an unhandled 500.
- **`apps/commerce-api/app/kernel/events/types.py`**
  Added `DomainEvent.TRIAL_EXPIRED`.
- **`apps/commerce-api/tests/unit/test_merchant_db_compatibility.py`**
  Added `trial_days=3` to the four `SubscriptionPlan(...)` fixtures so they
  satisfy the new `NOT NULL` column.
- **`apps/commerce-api/entrypoint.sh`**
  Dispatches on `PROCESS_TYPE` (default `web`). Worker mode runs
  `python -m app.workers.runner` and skips migrations (the web process owns
  migrations; the worker never races it for the migration lock).
- **`apps/commerce-api/Dockerfile`**
  Added `procps` (for `pgrep`), wired the new healthcheck script in place of
  the hardcoded curl-only check.

## Your action items

1. **Apply migrations 010 then 011** (`alembic upgrade head`) against
   staging, then production.
2. **Create the second Railway service** — same repo/Dockerfile as the API,
   env var `PROCESS_TYPE=worker`, all other env vars copied from the web
   service. This is a dashboard action; nothing in code can do it for you.
3. **Run the test suite for real** —
   `pytest tests/integration/test_trial_expiration.py tests/unit/test_merchant_db_compatibility.py -v`
   against a migrated Postgres instance. Every file here passes
   `py_compile`/`sh -n`, but this environment has no network access to
   install `requirements.txt` or run against a real database, so nothing
   has been runtime-executed.
4. **Manually verify the suspension gate once deployed**: onboard a test
   merchant, backdate its `trial_ends_at` directly in the DB, wait for the
   worker's next sweep (or trigger `expire_due_trials` once manually), then
   confirm (a) the storefront subdomain 404s/stops resolving, and (b) an
   authenticated request to a merchant-management endpoint for that tenant
   gets a `403 TENANT_ACCESS_DENIED`. The integration test proves the DB
   state transitions; this confirms the HTTP-layer enforcement end to end.
5. **Confirm the worker's healthcheck goes green post-deploy**, then check
   its logs for `"Expired N trial(s)"` / `"Relayed N event(s)"` to confirm
   it's doing work, not just idling alive.
6. **Plan the reactivation path** (`SUSPENDED → ACTIVE` on paid conversion)
   whenever billing/payment work starts — it's explicitly not built yet,
   and a merchant who converts to paid today would stay suspended until
   something reactivates their tenant.

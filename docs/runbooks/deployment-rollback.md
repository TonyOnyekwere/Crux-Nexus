# Deployment Rollback Runbook

## When to rollback

- `/health/ready` returns 503 after deploy
- Smoke tests fail on critical auth or onboarding paths
- Migration applies but application errors spike

## Steps

1. **Railway**: revert to previous deployment in the Railway dashboard or run `railway revert`.
2. **Verify health**: confirm `GET /health/live` and `GET /health/ready` return 200.
3. **Database**: if a forward migration caused the issue, deploy a forward-fix migration — do not run `alembic downgrade` in production without a tested plan.
4. **Smoke test**: run integration tests against the restored deployment.

## Prevention

- CI must pass before merge to `main`
- Migrations must be backward-compatible or paired with application deploy order

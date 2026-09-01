# Railway Acceptance Test Runbook

Execute this against a Railway deployment **after** migration 008 has been applied.

## Prerequisites

- Deployment URL (e.g. `https://your-service.up.railway.app`)
- `curl` or HTTP client
- Fresh test email addresses

## Acceptance flow

### 1. Health

```bash
curl -sS "$BASE_URL/health/live"
curl -sS "$BASE_URL/health/ready"
```

Expected: both return 200 with healthy/ready status.

### 2. User registration (global identity)

```bash
curl -sS -X POST "$BASE_URL/api/v1/identity/users" \
  -H "Content-Type: application/json" \
  -d '{"email":"acceptance@example.com","password":"SecurePass123!"}'
```

Expected: 201, no `tenant_id` in response.

### 3. Login (global token)

```bash
curl -sS -X POST "$BASE_URL/api/v1/identity/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"acceptance@example.com","password":"SecurePass123!"}'
```

Expected: 201/200 with `access_token`; token must NOT contain tenant claims when decoded.

### 4. Merchant onboarding

```bash
curl -sS -X POST "$BASE_URL/api/v1/onboarding/merchant" \
  -H "Authorization: Bearer $GLOBAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"merchant_name":"Acceptance Merchant","storefront_slug":"acceptance-store","plan":"starter"}'
```

Expected: 201 with `merchant_account_id`, `tenant_id`, `membership_id`.

### 5. Tenant switch

```bash
curl -sS -X POST "$BASE_URL/api/v1/identity/switch-tenant" \
  -H "Authorization: Bearer $GLOBAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\"}"
```

Expected: 200 with tenant-scoped token.

### 6. Storefront access

```bash
curl -sS "$BASE_URL/api/v1/merchant/storefronts/$TENANT_ID" \
  -H "Authorization: Bearer $TENANT_TOKEN"
```

Expected: 200 for owner; 403 for user without membership.

### 7. Cross-tenant rejection

Register a second user, attempt to access first user's storefront with their global token.

Expected: 403 `MEMBERSHIP_REQUIRED`.

### 8. Capacity enforcement

On starter plan (1 storefront), attempt second storefront creation.

Expected: 409 capacity error.

### 9. Readiness failure recovery

Temporarily stop Redis or PostgreSQL in staging, verify `/health/ready` returns 503, restore, verify 200.

## Record results

Log pass/fail for each step in your deployment notes. Phase 0 certification requires this runbook executed successfully against Railway staging or production.

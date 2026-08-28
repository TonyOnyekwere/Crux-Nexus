# CRX-P0-011: Railway Migration Fix

## Issue
Railway deployment was getting stuck during migration execution, causing the container to fail health checks.

## Root Cause
1. Database wasn't ready when migrations started
2. Migration failures were ignored, causing the app to start with incomplete schema
3. Railway healthcheck was using `/health` which requires full application startup
4. No proper database connectivity wait mechanism

## Fixes Applied

### 1. Enhanced entrypoint.sh
- Added database readiness check using netcat
- Wait up to 20 seconds for database to be ready
- Exit with error if migrations fail (instead of continuing)
- Reduced workers to 1 for debugging
- Better error messages and logging

### 2. Updated Dockerfile
- Added `netcat-openbsd` for database connectivity checking
- Fixed duplicate COPY commands
- Proper entrypoint execution

### 3. Updated Railway configuration
- Changed healthcheck from `/health` to `/health/live`
- `/health/live` is simpler and doesn't require database connectivity
- Allows container to pass healthcheck even if migrations are in progress

## Files Modified
- `apps/commerce-api/Dockerfile` - Added netcat, fixed COPY commands
- `apps/commerce-api/entrypoint.sh` - Enhanced database readiness check, proper error handling
- `apps/commerce-api/railway.toml` - Changed healthcheck to `/health/live`

## Migration Behavior
- Container now waits for database to be ready
- Migrations must succeed for container to start
- Failures are visible in logs with clear error messages
- Healthcheck uses simpler endpoint that doesn't require DB

## Next Steps
1. Push this fix to GitHub
2. Trigger Railway redeploy
3. Monitor deployment logs for successful migration
4. Verify container starts and healthcheck passes
5. Test application endpoints

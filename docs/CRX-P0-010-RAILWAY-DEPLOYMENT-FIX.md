# CRX-P0-010: Railway Deployment Fix

## Issue
Railway deployment failed due to invalid uvicorn flag.

## Error
```
Error: No such option '--timeout'. (Did you mean one of: '--timeout-keep-alive', '--ws-ping-timeout'?)
```

## Root Cause
The Dockerfile contained an invalid uvicorn flag:
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --timeout 60"]
```

Uvicorn does not have a `--timeout` flag. The correct flag for worker timeout is `--timeout-keep-alive`.

## Fix
Removed the invalid `--timeout 60` flag from the Dockerfile CMD:
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"]
```

## File Modified
- `apps/commerce-api/Dockerfile`

## Next Steps
1. Push this fix to GitHub
2. Trigger Railway redeploy
3. Monitor deployment logs for successful startup
4. Verify health endpoint responds
5. Continue with migration and runtime verification

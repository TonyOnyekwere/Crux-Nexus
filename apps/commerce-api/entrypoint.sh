#!/bin/sh
set -e

# Run migrations if DATABASE_URL is set; don't abort container on failure
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL not set; skipping migrations"
else
  echo "Running alembic migrations"
  # Run migrations but avoid blocking container startup indefinitely.
  # Prefer `timeout` if available; otherwise background the job.
  if command -v timeout >/dev/null 2>&1; then
    if timeout 30s alembic -c alembic.ini upgrade head; then
      echo "Alembic migrations applied successfully"
    else
      echo "Alembic migrations failed or timed out; continuing startup (check logs)"
    fi
  else
    # Fallback: run alembic in background so it doesn't block startup
    alembic -c alembic.ini upgrade head &
    echo "Alembic migrations started in background; continuing startup"
  fi
fi

# Exec the app (preserves signals)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 4

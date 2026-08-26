#!/bin/sh
set -e

# Run migrations if DATABASE_URL is set; don't abort container on failure
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL not set; skipping migrations"
else
  echo "Running alembic migrations"
  if alembic -c alembic.ini upgrade head; then
    echo "Alembic migrations applied successfully"
  else
    echo "Alembic migrations failed; continuing startup (check logs)"
  fi
fi

# Exec the app (preserves signals)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 4

#!/bin/sh
set -e

# Run migrations if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL not set; skipping migrations"
else
  echo "Running alembic migrations"
  alembic -c alembic.ini upgrade head
fi

# Exec the app (preserves signals)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 4

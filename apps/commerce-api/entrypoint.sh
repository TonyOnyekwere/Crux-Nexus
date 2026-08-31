#!/bin/sh
set -eu

echo "Starting CruxNexus Commerce API..."

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL is not configured"
    exit 1
fi

echo "Running database migrations..."

alembic -c alembic.ini upgrade head

echo "Alembic migrations applied successfully"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1

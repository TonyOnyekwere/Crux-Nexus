#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL is not configured"
    exit 1
fi

PROCESS_TYPE="${PROCESS_TYPE:-web}"

if [ "$PROCESS_TYPE" = "worker" ]; then
    echo "Starting CruxNexus Commerce API background worker..."
    # Migrations are applied by the web process on deploy; the worker does
    # not re-run them to avoid two processes racing on the migration lock.
    exec python -m app.workers.runner
fi

echo "Starting CruxNexus Commerce API..."

echo "Running database migrations..."

alembic -c alembic.ini upgrade head

echo "Alembic migrations applied successfully"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1

#!/bin/sh
set -e

# Wait for database to be ready
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database to be ready..."
  # Extract host and port from DATABASE_URL
  DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
  DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
  
  if [ -z "$DB_HOST" ]; then
    DB_HOST="localhost"
  fi
  if [ -z "$DB_PORT" ]; then
    DB_PORT="5432"
  fi
  
  echo "Checking database connectivity at $DB_HOST:$DB_PORT"
  
  # Wait for database to be ready
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
      echo "Database is ready"
      break
    fi
    echo "Waiting for database... ($i/10)"
    sleep 2
  done
  
  echo "Running alembic migrations"
  # Run migrations with better error handling
  if alembic -c alembic.ini upgrade head; then
    echo "Alembic migrations applied successfully"
  else
    echo "Alembic migrations failed; container will not start"
    exit 1
  fi
else
  echo "DATABASE_URL not set; skipping migrations"
fi

# Exec the app (preserves signals)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1

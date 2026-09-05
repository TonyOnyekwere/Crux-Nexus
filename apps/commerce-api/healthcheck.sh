#!/bin/sh
# Dispatch health check by process type. The web process serves HTTP and is
# checked via /health; the worker process has no HTTP server, so it is
# checked by confirming the runner process is still alive.
set -eu

PROCESS_TYPE="${PROCESS_TYPE:-web}"

if [ "$PROCESS_TYPE" = "worker" ]; then
    pgrep -f "app.workers.runner" > /dev/null 2>&1
else
    curl -f "http://localhost:${PORT:-8000}/health"
fi

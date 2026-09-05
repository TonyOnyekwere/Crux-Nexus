"""Background worker process — runs all periodic loops in one process.

Phase 0 has no task queue infrastructure (no Celery app, broker, or beat
schedule configured anywhere, despite celery being listed in
requirements.txt for future use). Rather than stand that up from scratch for
two lightweight polling loops, this follows the pattern already established
by app/workers/event_relay.py: a plain asyncio loop, run as its own process.

This module is the single entrypoint for that process — it runs the outbox
relay and trial expiration sweep concurrently so Railway only needs one
additional service (PROCESS_TYPE=worker), not one per job. Add future
periodic jobs to `_LOOPS` below rather than creating another top-level
worker process.

Deployment: create a second Railway service from the same Docker image as
the API, with the environment variable PROCESS_TYPE=worker set. See
entrypoint.sh, which dispatches on that variable.
"""

import asyncio
import logging

from app.workers.event_relay import run_relay_loop
from app.workers.trial_expiration import run_trial_expiration_loop

logger = logging.getLogger(__name__)

_LOOPS = (
    run_relay_loop,
    run_trial_expiration_loop,
)


async def run_all() -> None:
    logger.info("Starting background worker process (%d loop(s))", len(_LOOPS))
    await asyncio.gather(*(loop() for loop in _LOOPS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_all())

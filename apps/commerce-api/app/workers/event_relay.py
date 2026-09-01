"""Outbox relay worker — publishes pending events asynchronously."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database.url import normalize_async_database_url
from app.infrastructure.outbox.repository import OutboxEvent

logger = logging.getLogger(__name__)


async def relay_pending_events(db: AsyncSession, batch_size: int = 50) -> int:
    """Mark pending outbox events as published. Transport wiring is Phase 1."""
    result = await db.execute(
        select(OutboxEvent)
        .where(OutboxEvent.status == "pending")
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
    )
    events = result.scalars().all()
    if not events:
        return 0

    now = datetime.now(timezone.utc)
    for event in events:
        logger.info(
            "Relaying event %s type=%s aggregate=%s",
            event.id,
            event.event_type,
            event.aggregate_id,
        )
        await db.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event.id)
            .values(status="published", published_at=now)
        )
    await db.commit()
    return len(events)


async def run_relay_loop(interval_seconds: int = 5) -> None:
    settings = get_settings()
    engine = create_async_engine(normalize_async_database_url(settings.DATABASE_URL))
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    while True:
        async with session_factory() as session:
            try:
                count = await relay_pending_events(session)
                if count:
                    logger.info("Relayed %d event(s)", count)
            except Exception:
                logger.exception("Event relay failed")
                await session.rollback()
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_relay_loop())

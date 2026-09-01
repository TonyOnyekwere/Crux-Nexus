"""Transactional outbox publisher — events commit with business data."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.outbox.repository import OutboxRepository
from app.kernel.events.types import EventEnvelope


async def publish_to_outbox(db: AsyncSession, envelope: EventEnvelope) -> None:
    repository = OutboxRepository(db)
    await repository.append(envelope)

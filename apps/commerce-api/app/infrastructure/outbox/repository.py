from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import Base
from app.kernel.events.registry import assert_registered_event
from app.kernel.events.types import DomainEvent, EventEnvelope


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type = Column(String(100), nullable=False)
    aggregate_type = Column(String(100), nullable=False)
    aggregate_id = Column(PGUUID(as_uuid=True), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    published_at = Column(DateTime(timezone=True), nullable=True)


class OutboxRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(self, envelope: EventEnvelope) -> OutboxEvent:
        assert_registered_event(envelope.event_type.value)
        row = OutboxEvent(
            event_type=envelope.event_type.value,
            aggregate_type=envelope.aggregate_type,
            aggregate_id=envelope.aggregate_id,
            tenant_id=envelope.tenant_id,
            payload=envelope.payload,
            status="pending",
        )
        self.db.add(row)
        await self.db.flush()
        return row

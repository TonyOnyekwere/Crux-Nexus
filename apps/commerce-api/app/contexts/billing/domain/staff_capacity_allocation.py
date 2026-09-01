from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class StaffCapacityAllocation(Base):
    """Tracks how allocated extra staff capacity is assigned to storefronts."""

    __tablename__ = "staff_capacity_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    merchant_entitlement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant_entitlements.id", ondelete="CASCADE"),
        nullable=False,
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    quantity = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

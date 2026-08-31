from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class StorefrontEntitlementAllocation(Base):
    """Allocation of merchant entitlements to specific storefronts.
    
    This allows merchant-owned extra staff capacity to be distributed across storefronts.
    Example: Merchant has EXTRA_STAFF = 2, can allocate +1 to Store A and +1 to Store B.
    """
    __tablename__ = "storefront_entitlement_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entitlement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant_entitlements.id", ondelete="CASCADE"),
        nullable=False,
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    quantity = Column(Integer, nullable=False, default=1)

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

    # Invariants:
    # - quantity >= 0 (no negative allocations)
    # - SUM(allocation.quantity) <= entitlement.quantity (transactionally enforced)
    # - ON DELETE CASCADE ensures cleanup
    # - Only OWNER or Control Center can reallocate
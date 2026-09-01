from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

from .merchant_entitlement import EntitlementStatus, MerchantEntitlement


class SubscriptionPlan(Base):
    """Platform-defined subscription plan configuration.
    
    This table defines the available subscription tiers (STARTER, BUSINESS, ENTERPRISE)
    and their capacity limits. This is platform-level configuration, not merchant-specific data.
    """
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    code = Column(String(30), nullable=False, unique=True)

    name = Column(String(100), nullable=False)

    included_storefronts = Column(
        Integer,
        nullable=False,
    )

    base_staff_per_storefront = Column(
        Integer,
        nullable=False,
    )

    max_extra_storefronts = Column(
        Integer,
        nullable=False,
    )

    max_extra_staff = Column(
        Integer,
        nullable=False,
    )

    active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

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
    # - code is unique (enforced by database)
    # - STARTER: 1 storefront, 0 staff/base, 0 extra storefronts, 0 extra staff
    # - BUSINESS: 1 storefront, 3 staff/base, 1 extra storefronts max, 2 extra staff max
    # - ENTERPRISE: 1 storefront, 8 staff/base, 2 extra storefronts max, 4 extra staff max
    # - INACTIVE plans cannot be used for new subscriptions
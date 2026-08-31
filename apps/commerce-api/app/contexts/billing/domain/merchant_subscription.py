from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class MerchantSubscription(Base):
    """A merchant's actual subscription to a subscription plan.
    
    This represents the business relationship between a merchant and their subscription plan.
    This is separate from the plan definition (subscription_plans).
    """
    __tablename__ = "merchant_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    merchant_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    subscription_plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
        default=SubscriptionStatus.TRIALING.value,
    )

    starts_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ends_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    trial_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    trial_ends_at = Column(
        DateTime(timezone=True),
        nullable=True,
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
    # - Each merchant has one active subscription at a time
    # - Status lifecycle: TRIALING → ACTIVE → PAST_DUE → SUSPENDED → CANCELLED/EXPIRED
    # - ACTIVE/TRIALING allows storefront creation
    # - CANCELLED/EXPIRED/SUSPENDED denies storefront creation
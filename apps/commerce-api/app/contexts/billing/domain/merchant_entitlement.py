from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EntitlementType(str, enum.Enum):
    EXTRA_STOREFRONT = "extra_storefront"
    EXTRA_STAFF = "extra_staff"


class EntitlementSource(str, enum.Enum):
    PURCHASE = "purchase"
    ADMIN_GRANT = "admin_grant"
    PROMOTION = "promotion"


class EntitlementStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REVOKED = "revoked"


class MerchantEntitlement(Base):
    """Additional capability granted to a specific merchant.
    
    Entitlements represent additional capacity or capabilities beyond the base subscription plan.
    Examples include extra storefront slots, extra staff slots, premium features, etc.
    """
    __tablename__ = "merchant_entitlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    merchant_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    entitlement_type = Column(
        String(50),
        nullable=False,
    )

    quantity = Column(Integer, nullable=False, default=1)

    source = Column(
        String(50),
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
        default=EntitlementStatus.ACTIVE.value,
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

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Invariants:
    # - ACTIVE entitlements count toward effective capacity
    # - EXPIRED/CANCELLED/REVOKED do not count
    # - starts_at <= ends_at for time-limited entitlements
    # - source tracks origin (purchase, admin grant, promotion, etc.)
    # - quantity may be >1 for bulk grants
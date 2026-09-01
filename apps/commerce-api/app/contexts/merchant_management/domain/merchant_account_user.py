from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SQLEnum, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MerchantUserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"


# Backward-compatible alias used by older imports during the merchant domain transition.
MerchantAccountRole = MerchantUserRole


class MerchantAccountUser(Base):
    """Represents the relationship between a User and a Merchant Account.
    
    This answers: Who is associated with this merchant business?
    This is separate from tenant membership (which answers: Who can access this storefront?).
    """
    __tablename__ = "merchant_account_users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    merchant_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(
        SQLEnum(
            MerchantUserRole,
            name="merchantuserrole",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=MerchantUserRole.ADMIN,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Invariants:
    # - UNIQUE(merchant_account_id, user_id) enforced by database
    # - ON DELETE CASCADE ensures cleanup
    # - This is merchant-level ownership, not storefront access
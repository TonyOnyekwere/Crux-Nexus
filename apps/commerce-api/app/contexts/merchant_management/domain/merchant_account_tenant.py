from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MerchantAccountTenant(Base):
    """Explicit ownership relationship between Merchant Account and Tenant (Storefront).
    
    This represents the commercial ownership: which merchant owns which storefront.
    A storefront can belong to only one merchant account (one-to-one ownership).
    This is separate from tenant_memberships (authorization/access).
    """
    __tablename__ = "merchant_account_tenants"
    __table_args__ = (
        UniqueConstraint("merchant_account_id", "tenant_id", name="uq_merchant_tenant"),
    )

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

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One tenant can belong to only one merchant
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Invariants:
    # - UNIQUE(merchant_account_id, tenant_id) enforced by database
    # - UNIQUE(tenant_id) enforced by database (one tenant → one merchant)
    # - ON DELETE CASCADE ensures cleanup
    # - This is commercial ownership, not user authorization
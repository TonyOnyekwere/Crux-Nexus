from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import enum
import uuid
from app.database import Base


class MerchantStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    ARCHIVED = "archived"


class MerchantTenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class MerchantAccount(Base):
    """Business/customer entity representing a CruxNexus merchant.
    
    A Merchant Account represents the business relationship with CruxNexus.
    It owns storefronts (tenants) and has subscriptions/entitlements.
    This is separate from User (person) and Tenant (storefront).
    """
    __tablename__ = "merchant_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name = Column(String, nullable=False, unique=True)
    contact_email = Column(String, nullable=False, unique=True)
    status = Column(
        SQLEnum(
            MerchantStatus,
            name="merchantstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=MerchantStatus.PROVISIONING,
        nullable=False,
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

    # Relationships are established in app.database.models.py
    # to avoid circular import issues

    # Invariants:
    # - business_name is unique (enforced by database)
    # - contact_email is unique (enforced by database)
    # - status follows lifecycle: PROVISIONING → ACTIVE → SUSPENDED/OFFBOARDING → ARCHIVED
    # - merchants own tenants through merchant_account_tenants
    # - merchants have subscriptions through merchant_subscriptions
    # - merchants have entitlements through merchant_entitlements


class MerchantAccountTenant(Base):
    """Explicit ownership relationship between Merchant Account and Tenant.
    
    This table represents the commercial ownership: which merchant owns which storefront.
    A tenant can belong to only one merchant account (one-to-one ownership).
    This is separate from tenant_memberships (authorization/access).
    """
    __tablename__ = "merchant_account_tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    status = Column(
        SQLEnum(
            MerchantTenantStatus,
            name="merchanttenantstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=MerchantTenantStatus.ACTIVE,
        nullable=False,
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

    # Relationships are established in app.database.models.py
    # to avoid circular import issues

    # Invariants:
    # - UNIQUE(merchant_account_id, tenant_id) enforced by database
    # - UNIQUE(tenant_id) enforced by database (one tenant → one merchant)
    # - ON DELETE CASCADE ensures cleanup
    # - status tracks ownership lifecycle (active/suspended/removed)
    # - This is commercial ownership, not user authorization
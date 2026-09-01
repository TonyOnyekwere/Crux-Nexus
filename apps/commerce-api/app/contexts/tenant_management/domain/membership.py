from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class TenantRole(str, enum.Enum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    REMOVED = "removed"
    SUSPENDED = "suspended"


class TenantMembership(Base):
    """Authorization/access relationship between User and Tenant (Storefront).
    
    This table represents which users can access which storefronts and with what role.
    This is separate from merchant ownership (merchant_account_tenants).
    A user can belong to multiple tenants through multiple memberships.
    """
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_user_membership"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(
        String(50),
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
        default=MembershipStatus.ACTIVE.value,
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
    # - UNIQUE(tenant_id, user_id) enforced by database (one membership per user per tenant)
    # - ON DELETE CASCADE ensures cleanup
    # - role determines access level (OWNER, MANAGER, STAFF)
    # - status determines membership lifecycle (ACTIVE, INVITED, REMOVED, SUSPENDED)
    # - This is authorization/access, not commercial ownership
    # - OWNER does not consume staff capacity
    # - Only ACTIVE memberships grant access
    # - INVITED memberships are pending acceptance
    # - REMOVED memberships cannot access but history is preserved
    # - SUSPENDED memberships temporarily cannot access
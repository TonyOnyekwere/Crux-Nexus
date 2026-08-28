from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import enum
import uuid
from app.database import Base


class TenantStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    ARCHIVED = "archived"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, nullable=False, unique=True)
    status = Column(
        SQLEnum(
            TenantStatus,
            name="tenantstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=TenantStatus.PROVISIONING,
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

    # Invariants enforced at application level:
    # - slug is globally unique
    # - status transitions follow the lifecycle
    # - PROVISIONING → ONBOARDING → ACTIVE (normal flow)
    # - ACTIVE ↔ SUSPENDED (administrative actions)
    # - Any → OFFBOARDING → ARCHIVED (terminal)
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.database import Base


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"


class UserStatus(str, enum.Enum):
    GUEST = "guest"
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)  # Will be filled for merchant users
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=True)  # NULL for OAuth users
    auth_provider = Column(
        SQLEnum(
            AuthProvider,
            name="authprovider",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=AuthProvider.PASSWORD,
        nullable=False,
    )

    status = Column(
        SQLEnum(
            UserStatus,
            name="userstatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.GUEST,
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

    # Relationships
    # tenant_memberships = relationship("TenantMember", back_populates="user")


class CruxNexusError(Exception):
    """Base exception for all CruxNexus domain errors."""
    code: str

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class StaleVersionError(CruxNexusError):
    code = "stale_version"

    def __init__(self, current_state: dict):
        message = "Resource has been modified by another transaction"
        self.current_state = current_state
        super().__init__(self.code, message)


class InvalidTransitionError(CruxNexusError):
    code = "invalid_transition"

    def __init__(self, current_status: str, allowed_transitions: list[str]):
        message = f"Cannot transition from {current_status}"
        self.allowed_transitions = allowed_transitions
        super().__init__(self.code, message)
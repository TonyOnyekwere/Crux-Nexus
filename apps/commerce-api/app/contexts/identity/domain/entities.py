from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SQLEnum, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash = Column(
        String,
        nullable=True,
    )

    auth_provider = Column(
        SQLEnum(
            AuthProvider,
            name="authprovider",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=AuthProvider.PASSWORD,
    )

    status = Column(
        SQLEnum(
            UserStatus,
            name="userstatus",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
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
from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SQLEnum, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MerchantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    ARCHIVED = "archived"


class MerchantAccount(Base):
    __tablename__ = "merchant_accounts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name = Column(
        String(150),
        nullable=False,
    )

    status = Column(
        SQLEnum(
            MerchantStatus,
            name="merchantstatus",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=MerchantStatus.ACTIVE,
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
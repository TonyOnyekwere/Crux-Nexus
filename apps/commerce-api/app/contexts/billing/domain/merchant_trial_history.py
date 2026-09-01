from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MerchantTrialHistory(Base):
    """Audit trail for merchant subscription trials."""

    __tablename__ = "merchant_trial_history"

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

    status = Column(String(50), nullable=False, default="trialing")

    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ended_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

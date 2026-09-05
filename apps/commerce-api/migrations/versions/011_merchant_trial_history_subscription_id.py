"""Add subscription_id to merchant_trial_history.

Revision ID: 011
Revises: 010

merchant_trial_history was previously correlated to a subscription only via
(merchant_account_id, subscription_plan_id, status, ended_at IS NULL) —
correlation, not reference. That's fragile the moment a merchant can have
more than one trial history row for the same plan (e.g. re-trial after
cancellation). This migration adds a direct, nullable FK to
merchant_subscriptions so new rows can be looked up unambiguously.

Nullable rather than NOT NULL: at the time of this migration,
merchant_trial_history was confirmed empty in production (this table was
never actually written to before this patch), so there is nothing to
backfill. Nullable is kept anyway so any pre-existing row from another
environment doesn't block the migration; application code always populates
it going forward.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_trial_history",
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchant_subscriptions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_merchant_trial_history_subscription_id",
        "merchant_trial_history",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_trial_history_subscription_id", table_name="merchant_trial_history")
    op.drop_column("merchant_trial_history", "subscription_id")

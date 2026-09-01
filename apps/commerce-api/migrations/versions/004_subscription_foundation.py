"""Subscription foundation migration.

Creates the merchant trial history table and preserves the subscription lifecycle rules
for the final commercial model.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_trial_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="trialing"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.execute(
        """
        INSERT INTO merchant_trial_history (id, merchant_account_id, subscription_plan_id, status, started_at, ended_at, created_at)
        SELECT
            gen_random_uuid(),
            ms.merchant_account_id,
            ms.subscription_plan_id,
            ms.status,
            COALESCE(ms.trial_started_at, ms.starts_at),
            ms.trial_ends_at,
            ms.created_at
        FROM merchant_subscriptions ms
        WHERE ms.trial_started_at IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("merchant_trial_history")

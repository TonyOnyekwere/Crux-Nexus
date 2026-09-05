"""Add trial_days to subscription_plans and seed plan trial lengths.

Revision ID: 010
Revises: 009

Trial length is plan-configured data, not an application constant. This
migration adds the column and seeds the platform-defined trial lengths for
the canonical plans. Application code (OnboardingService) reads
SubscriptionPlan.trial_days at onboarding time rather than hardcoding a
trial duration.
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


# Canonical per-plan trial lengths (days). Seeded here because these are
# platform configuration values, not business logic embedded in code.
PLAN_TRIAL_DAYS = {
    "starter": 3,
    "business": 3,
    "enterprise": 7,
}

# Fallback trial length used for any plan code that isn't one of the
# canonical seeds above (keeps the column NOT NULL-safe for future plans
# added without an explicit trial length).
DEFAULT_TRIAL_DAYS = 7


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column(
            "trial_days",
            sa.Integer(),
            nullable=False,
            server_default=str(DEFAULT_TRIAL_DAYS),
        ),
    )

    connection = op.get_bind()
    for plan_code, trial_days in PLAN_TRIAL_DAYS.items():
        connection.execute(
            sa.text(
                """
                UPDATE subscription_plans
                SET trial_days = :trial_days
                WHERE lower(code) = :plan_code
                """
            ),
            {"trial_days": trial_days, "plan_code": plan_code},
        )

    # Drop the server default after backfill so future inserts are forced to
    # supply an explicit, intentional trial_days value at the application
    # layer rather than silently inheriting a fallback.
    op.alter_column("subscription_plans", "trial_days", server_default=None)


def downgrade() -> None:
    op.drop_column("subscription_plans", "trial_days")

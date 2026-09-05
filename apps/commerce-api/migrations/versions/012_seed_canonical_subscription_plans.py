"""Seed canonical subscription plans.

Revision ID: 012
Revises: 011

Ensures the platform's canonical Starter, Business, and Enterprise
subscription plans exist in every environment.

This migration is idempotent: existing plans are updated rather than
duplicated.
"""

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


CANONICAL_PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "included_storefronts": 1,
        "base_staff_per_storefront": 0,
        "max_extra_storefronts": 0,
        "max_extra_staff": 0,
        "trial_days": 3,
        "active": True,
    },
    {
        "code": "business",
        "name": "Business",
        "included_storefronts": 1,
        "base_staff_per_storefront": 3,
        "max_extra_storefronts": 1,
        "max_extra_staff": 2,
        "trial_days": 3,
        "active": True,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "included_storefronts": 1,
        "base_staff_per_storefront": 8,
        "max_extra_storefronts": 2,
        "max_extra_staff": 4,
        "trial_days": 7,
        "active": True,
    },
]


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)

    for plan in CANONICAL_PLANS:
        connection.execute(
            sa.text(
                """
                INSERT INTO subscription_plans (
                    id,
                    code,
                    name,
                    included_storefronts,
                    base_staff_per_storefront,
                    max_extra_storefronts,
                    max_extra_staff,
                    active,
                    created_at,
                    updated_at,
                    trial_days
                )
                VALUES (
                    :id,
                    :code,
                    :name,
                    :included_storefronts,
                    :base_staff_per_storefront,
                    :max_extra_storefronts,
                    :max_extra_staff,
                    :active,
                    :created_at,
                    :updated_at,
                    :trial_days
                )
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    included_storefronts = EXCLUDED.included_storefronts,
                    base_staff_per_storefront = EXCLUDED.base_staff_per_storefront,
                    max_extra_storefronts = EXCLUDED.max_extra_storefronts,
                    max_extra_staff = EXCLUDED.max_extra_staff,
                    active = EXCLUDED.active,
                    trial_days = EXCLUDED.trial_days,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                **plan,
                "id": str(uuid.uuid4()),
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DELETE FROM subscription_plans
            WHERE code IN ('starter', 'business', 'enterprise')
            """
        )
    )
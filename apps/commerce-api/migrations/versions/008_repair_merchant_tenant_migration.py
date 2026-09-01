"""Repair migration 003 merchant-tenant mapping and add DB invariants.

Revision ID: 008
Revises: 007
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

LIVE_SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "suspended")


def upgrade() -> None:
    # Remove ownership rows created by the broken CROSS JOIN in migration 003.
    # Migration 003 created merchants named 'Migrated Merchant - {slug}' per tenant;
    # ownership must match that deterministic pairing.
    op.execute(
        """
        DELETE FROM merchant_account_tenants mat
        USING merchant_accounts ma, tenants t
        WHERE mat.merchant_account_id = ma.id
          AND mat.tenant_id = t.id
          AND ma.name LIKE 'Migrated Merchant - %'
          AND ma.name <> 'Migrated Merchant - ' || t.slug
        """
    )

    # Insert missing ownership for migration-created merchants.
    op.execute(
        """
        INSERT INTO merchant_account_tenants (id, merchant_account_id, tenant_id, created_at)
        SELECT gen_random_uuid(), ma.id, t.id, t.created_at
        FROM tenants t
        JOIN merchant_accounts ma
          ON ma.name = 'Migrated Merchant - ' || t.slug
        WHERE NOT EXISTS (
            SELECT 1 FROM merchant_account_tenants mat
            WHERE mat.tenant_id = t.id
        )
        """
    )

    # Keep one owner-merchant link per user before enforcing the partial unique index.
    op.execute(
        """
        DELETE FROM merchant_account_users mau
        WHERE mau.role = 'owner'
          AND mau.id NOT IN (
              SELECT DISTINCT ON (user_id) id
              FROM merchant_account_users
              WHERE role = 'owner'
              ORDER BY user_id, created_at ASC, id ASC
          )
        """
    )

    # Keep one live subscription per merchant before enforcing the partial unique index.
    op.execute(
        f"""
        DELETE FROM merchant_subscriptions ms
        WHERE ms.status IN {LIVE_SUBSCRIPTION_STATUSES}
          AND ms.id NOT IN (
              SELECT DISTINCT ON (merchant_account_id) id
              FROM merchant_subscriptions
              WHERE status IN {LIVE_SUBSCRIPTION_STATUSES}
              ORDER BY merchant_account_id, created_at ASC, id ASC
          )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_one_owner_merchant_per_user
        ON merchant_account_users (user_id)
        WHERE role = 'owner'
        """
    )

    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_one_live_subscription_per_merchant
        ON merchant_subscriptions (merchant_account_id)
        WHERE status IN {LIVE_SUBSCRIPTION_STATUSES}
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_one_live_subscription_per_merchant")
    op.execute("DROP INDEX IF EXISTS uq_one_owner_merchant_per_user")

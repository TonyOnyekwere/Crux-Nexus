"""Repair tenant_memberships schema drift from migration 003.

Revision ID: 009
Revises: 008

Migration 003 originally created tenant_memberships without ``status`` and
``updated_at``. Those columns were added to the migration file in commit
aa9c3a3 after production had already applied the earlier revision. Alembic
does not re-run applied migrations, so Railway databases created from the
original 003 are missing columns that the ORM expects.

This migration is idempotent: fresh databases that received the corrected 003
skip the ADD COLUMN steps and only run harmless backfill/default updates.
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tenant_memberships
        ADD COLUMN IF NOT EXISTS status VARCHAR(50)
        """
    )

    op.execute(
        """
        UPDATE tenant_memberships
        SET status = 'active'
        WHERE status IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE tenant_memberships
        ALTER COLUMN status SET DEFAULT 'active'
        """
    )

    op.execute(
        """
        ALTER TABLE tenant_memberships
        ALTER COLUMN status SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE tenant_memberships
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
        """
    )

    op.execute(
        """
        UPDATE tenant_memberships
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE tenant_memberships
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP
        """
    )

    op.execute(
        """
        ALTER TABLE tenant_memberships
        ALTER COLUMN updated_at SET NOT NULL
        """
    )


def downgrade() -> None:
    # Intentional no-op: this repair migration closes schema drift from an
    # already-applied 003 revision. Reverting would break ORM compatibility
    # on databases that never had these columns before 009 ran.
    pass

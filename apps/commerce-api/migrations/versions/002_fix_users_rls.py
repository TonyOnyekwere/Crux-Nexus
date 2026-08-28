"""Fix users RLS policies for tenant and global user creation.

Revision ID: 002
Revises: 001
"""

from alembic import op


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the original catch-all policy.
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON users"
    )

    # Tenant-scoped reads.
    op.execute(
        """
        CREATE POLICY users_tenant_select
        ON users
        FOR SELECT
        USING (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )

    # Tenant-scoped updates.
    op.execute(
        """
        CREATE POLICY users_tenant_update
        ON users
        FOR UPDATE
        USING (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )

    # Tenant-scoped deletes.
    op.execute(
        """
        CREATE POLICY users_tenant_delete
        ON users
        FOR DELETE
        USING (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )

    # User creation:
    # 1. Tenant users must belong to the active tenant.
    # 2. Global users may be created with tenant_id = NULL.
    op.execute(
        """
        CREATE POLICY users_insert
        ON users
        FOR INSERT
        WITH CHECK (
            tenant_id IS NULL
            OR
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS users_tenant_select ON users"
    )

    op.execute(
        "DROP POLICY IF EXISTS users_tenant_update ON users"
    )

    op.execute(
        "DROP POLICY IF EXISTS users_tenant_delete ON users"
    )

    op.execute(
        "DROP POLICY IF EXISTS users_insert ON users"
    )

    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
        USING (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id =
            current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )
"""RLS correction for global identity and tenant-owned commerce data.

Revision ID: 006
Revises: 005
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The platform identity model is global; do not apply tenant RLS to users.
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    # Ensure no stale tenant-scoped RLS policy remains on users.
    op.execute("DROP POLICY IF EXISTS users_tenant_select ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_update ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_delete ON users")
    op.execute("DROP POLICY IF EXISTS users_insert ON users")


def downgrade() -> None:
    # Keep the downgrade side explicit; this is a platform-level correction.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")

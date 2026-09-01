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
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS users_tenant_select ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_update ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_delete ON users")
    op.execute("DROP POLICY IF EXISTS users_insert ON users")


def downgrade() -> None:
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")

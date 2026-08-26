"""Initial schema with users and tenants tables with RLS

Revision ID: 001
Revises: 
Create Date: 2026-08-20 11:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),  # Will be filled for merchant users
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('auth_provider', sa.Enum('password', 'google', 'apple', name='authprovider'), nullable=False),
        sa.Column('status', sa.Enum('guest', 'active', 'disabled', name='userstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email'),
    )
    
    # Enable RLS on users
    op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE users FORCE ROW LEVEL SECURITY')
    
    # Create RLS policy for users with WITH CHECK for write operations
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)
    
    # Create index on users.tenant_id for performance
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('provisioning', 'onboarding', 'active', 'suspended', 'offboarding', 'archived', name='tenantstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('slug'),
    )
    
    # Tenants table architecture for Phase 0 (CRX-P0-006)
    # Current state: Application-layer authorization only
    # - No RLS on tenants table for Phase 0
    # - Application services use standard DB session for tenant operations
    # - Authorization enforced at API route level (not database level)
    # 
    # Future state (Phase 2): Platform-admin DB role architecture
    # - Separate platform-admin database role
    # - RLS with elevated privileges for platform operations
    # - Clear control-plane/data-plane boundary at database level
    #
    # This Phase 0 approach allows immediate Railway deployment while
    # acknowledging the architectural boundary that will be formalized in Phase 2.


def downgrade() -> None:
    op.drop_index('idx_users_tenant_id', table_name='users')
    op.drop_table('tenants')
    op.drop_table('users')
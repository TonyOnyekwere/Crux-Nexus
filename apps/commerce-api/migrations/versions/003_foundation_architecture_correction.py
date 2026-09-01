"""Foundation architecture correction migration.

This migration implements the correct multi-tenant architecture:
- Remove users.tenant_id (users are global identities)
- Create merchant_accounts (business entities)
- Create merchant_account_users (merchant-user relationships)
- Create merchant_account_tenants (ownership relationships)
- Create tenant_memberships (authorization relationships)
- Create subscription_plans (platform configuration)
- Create merchant_subscriptions (merchant subscriptions)
- Create merchant_entitlements (additional capacity)
- Create storefront_entitlement_allocations (staff allocation)
- Seed STARTER/BUSINESS/ENTERPRISE plans with correct limits
- Remove user table RLS (users are global identity)

Follows expand/contract pattern:
- Step A: Create new tables (expand)
- Step B: Migrate existing data
- Step C: Drop old architecture (contract)

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # STEP A: CREATE NEW TABLES (EXPAND)
    # ========================================
    
    # Create merchant_accounts table
    op.create_table(
        "merchant_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_account_users table
    op.create_table(
        "merchant_account_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="'owner'"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique constraint on (merchant_account_id, user_id)
    op.create_unique_constraint("uq_merchant_user", "merchant_account_users", ["merchant_account_id", "user_id"])
    
    # Create merchant_account_tenants table
    op.create_table(
        "merchant_account_tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique constraint on (merchant_account_id, tenant_id)
    op.create_unique_constraint("uq_merchant_tenant", "merchant_account_tenants", ["merchant_account_id", "tenant_id"])
    
    # Create subscription_plans table
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("included_storefronts", sa.Integer(), nullable=False),
        sa.Column("base_staff_per_storefront", sa.Integer(), nullable=False),
        sa.Column("max_extra_storefronts", sa.Integer(), nullable=False),
        sa.Column("max_extra_staff", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_subscriptions table
    op.create_table(
        "merchant_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_entitlements table
    op.create_table(
        "merchant_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_type", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create storefront_entitlement_allocations table
    op.create_table(
        "storefront_entitlement_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_entitlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create tenant_memberships table
    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="'active'"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique constraint on (tenant_id, user_id)
    op.create_unique_constraint("uq_tenant_user_membership", "tenant_memberships", ["tenant_id", "user_id"])
    
    # ========================================
    # STEP B: SEED SUBSCRIPTION PLANS
    # ========================================
    
    op.execute(
        """
        INSERT INTO subscription_plans (id, code, name, included_storefronts, base_staff_per_storefront, max_extra_storefronts, max_extra_staff, active, created_at, updated_at)
        VALUES 
            (gen_random_uuid(), 'starter', 'Starter', 1, 0, 0, 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'business', 'Business', 1, 3, 1, 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'enterprise', 'Enterprise', 1, 8, 2, 4, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    
    # ========================================
    # STEP C: MIGRATE EXISTING DATA
    # ========================================
    
    # Create merchant accounts for existing tenants
    op.execute(
        """
        INSERT INTO merchant_accounts (id, name, status, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            'Migrated Merchant - ' || t.slug,
            'active',
            t.created_at,
            t.updated_at
        FROM tenants t
        WHERE NOT EXISTS (
            SELECT 1 FROM merchant_account_tenants mat 
            WHERE mat.tenant_id = t.id
        )
        """
    )
    
    # Create ownership relationships for existing tenants
    op.execute(
        """
        INSERT INTO merchant_account_tenants (id, merchant_account_id, tenant_id, created_at)
        SELECT 
            gen_random_uuid(),
            ma.id,
            t.id,
            t.created_at
        FROM tenants t
        CROSS JOIN merchant_accounts ma
        WHERE NOT EXISTS (
            SELECT 1 FROM merchant_account_tenants mat 
            WHERE mat.tenant_id = t.id
        )
        LIMIT 1
        """
    )
    
    # Create memberships for users who had tenant_id assigned
    op.execute(
        """
        INSERT INTO tenant_memberships (id, tenant_id, user_id, role, status, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            u.tenant_id,
            u.id,
            'owner',
            'active',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM users u
        WHERE u.tenant_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM tenant_memberships tm 
            WHERE tm.user_id = u.id AND tm.tenant_id = u.tenant_id
        )
        """
    )
    
    # Assign STARTER subscription to migrated merchants
    op.execute(
        """
        INSERT INTO merchant_subscriptions (id, merchant_account_id, subscription_plan_id, status, starts_at, trial_started_at, trial_ends_at, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            ma.id,
            sp.id,
            'active',
            ma.created_at,
            ma.created_at,
            ma.created_at + INTERVAL '14 days',
            ma.created_at,
            ma.updated_at
        FROM merchant_accounts ma
        CROSS JOIN subscription_plans sp
        WHERE sp.code = 'starter'
        AND NOT EXISTS (
            SELECT 1 FROM merchant_subscriptions ms 
            WHERE ms.merchant_account_id = ma.id
        )
        """
    )
    
    # ========================================
    # STEP D: REMOVE OLD ARCHITECTURE (CONTRACT)
    # ========================================

    # Remove stale user table RLS policies first. These policies depend on users.tenant_id
    # and PostgreSQL will reject dropping the column while they remain active.
    op.execute("DROP POLICY IF EXISTS users_tenant_select ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_update ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_delete ON users")
    op.execute("DROP POLICY IF EXISTS users_insert ON users")

    # Disable RLS on users table (users are global identity)
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    # Remove users.tenant_id column only after policy dependencies are cleared.
    op.drop_column("users", "tenant_id")


def downgrade() -> None:
    # This downgrade is intentionally destructive and should be used with extreme caution
    # It would reverse the architectural correction, which is not recommended
    
    # Re-enable RLS on users table
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    
    # Re-add users.tenant_id column
    op.add_column("users", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    
    # Re-create user RLS policies
    op.execute(
        """
        CREATE POLICY users_tenant_select
        ON users
        FOR SELECT
        USING (
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )
    
    op.execute(
        """
        CREATE POLICY users_tenant_update
        ON users
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )
    
    op.execute(
        """
        CREATE POLICY users_tenant_delete
        ON users
        FOR DELETE
        USING (
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )
    
    op.execute(
        """
        CREATE POLICY users_insert
        ON users
        FOR INSERT
        WITH CHECK (
            tenant_id IS NULL
            OR
            tenant_id = current_setting('app.current_tenant_id', true)::uuid
        )
        """
    )
    
    # Drop new tables (reverse order due to foreign keys)
    op.drop_table("tenant_memberships")
    op.drop_table("storefront_entitlement_allocations")
    op.drop_table("merchant_entitlements")
    op.drop_table("merchant_subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("merchant_account_tenants")
    op.drop_table("merchant_account_users")
    op.drop_table("merchant_accounts")
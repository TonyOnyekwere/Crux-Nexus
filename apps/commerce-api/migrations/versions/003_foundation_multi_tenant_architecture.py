"""Foundation multi-tenant architecture migration.

This migration implements the correct multi-tenant architecture:
- Remove users.tenant_id (users are global identities)
- Create merchant_accounts (business entities)
- Create merchant_account_tenants (ownership relationship)
- Create tenant_memberships (authorization relationship)
- Create subscription_plans (platform configuration)
- Create merchant_subscriptions (merchant subscriptions)
- Create merchant_entitlements (additional capacity)
- Seed STARTER/BUSINESS/ENTERPRISE plans (1/3/8 limits)
- Migrate existing user-tenant relationships to new architecture
- Remove user table RLS (users are global identity)

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # PHASE 1: Create new tables
    # ========================================
    
    # Create subscription_plans table
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.Enum("starter", "business", "enterprise", name="subscriptionplancode"), unique=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("included_tenant_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="subscriptionplanstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_accounts table
    op.create_table(
        "merchant_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_name", sa.String(), nullable=False, unique=True),
        sa.Column("contact_email", sa.String(), nullable=False, unique=True),
        sa.Column("status", sa.Enum("provisioning", "active", "suspended", "offboarding", "archived", name="merchantstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_account_tenants table
    op.create_table(
        "merchant_account_tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.Enum("active", "suspended", "removed", name="merchanttenantstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique constraint on (merchant_account_id, tenant_id)
    op.create_unique_constraint("uq_merchant_account_tenant", "merchant_account_tenants", ["merchant_account_id", "tenant_id"])
    
    # Create tenant_memberships table
    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("owner", "admin", "staff", name="membershiprole"), nullable=False),
        sa.Column("status", sa.Enum("active", "invited", "suspended", "removed", name="membershipstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create unique constraint on (tenant_id, user_id)
    op.create_unique_constraint("uq_tenant_user_membership", "tenant_memberships", ["tenant_id", "user_id"])
    
    # Create merchant_subscriptions table
    op.create_table(
        "merchant_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Enum("trialing", "active", "past_due", "cancelled", "expired", "suspended", name="subscriptionstatus"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create merchant_entitlements table
    op.create_table(
        "merchant_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_type", sa.Enum("extra_tenant_slot", name="entitlementtype"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source", sa.Enum("purchase", "admin_grant", "promotion", "migration", "system", name="entitlementsource"), nullable=False),
        sa.Column("status", sa.Enum("active", "expired", "cancelled", "revoked", name="entitlementstatus"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # ========================================
    # PHASE 2: Seed subscription plans
    # ========================================
    
    op.execute(
        """
        INSERT INTO subscription_plans (id, code, name, included_tenant_limit, status, created_at, updated_at)
        VALUES 
            (gen_random_uuid(), 'starter', 'Starter', 1, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'business', 'Business', 3, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'enterprise', 'Enterprise', 8, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    
    # ========================================
    # PHASE 3: Migrate existing data
    # ========================================
    
    # Create a merchant account for each unique tenant that currently exists
    op.execute(
        """
        INSERT INTO merchant_accounts (id, business_name, contact_email, status, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            'Migrated Merchant - ' || t.slug,
            'merchant-' || t.slug || '@cruxnexus.com',
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
        INSERT INTO merchant_account_tenants (id, merchant_account_id, tenant_id, status, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            ma.id,
            t.id,
            'active',
            t.created_at,
            t.updated_at
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
        INSERT INTO merchant_subscriptions (id, merchant_account_id, subscription_plan_id, status, started_at, current_period_start, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            ma.id,
            sp.id,
            'active',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
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
    # PHASE 4: Remove old architecture
    # ========================================
    
    # Remove users.tenant_id column
    op.drop_column("users", "tenant_id")
    
    # Remove user table RLS policies
    op.execute("DROP POLICY IF EXISTS users_tenant_select ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_update ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_delete ON users")
    op.execute("DROP POLICY IF EXISTS users_insert ON users")
    
    # Disable RLS on users table (users are global identity)
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")


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
    op.drop_table("merchant_entitlements")
    op.drop_table("merchant_subscriptions")
    op.drop_table("tenant_memberships")
    op.drop_table("merchant_account_tenants")
    op.drop_table("merchant_accounts")
    op.drop_table("subscription_plans")
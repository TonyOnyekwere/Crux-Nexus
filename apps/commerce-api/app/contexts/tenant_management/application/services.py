from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
import uuid


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, slug: str) -> Tenant:
        """Create a new tenant (platform control-plane operation)."""
        # CRX-P0-007 P0-3: Tenants table is control-plane data, not tenant-scoped
        # Uses normal transaction handling, not tenant_transaction
        # Check if slug already exists
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        existing_tenant = result.scalar_one_or_none()
        
        if existing_tenant:
            raise ValueError("Slug already taken")
        
        tenant = Tenant(
            id=uuid.uuid4(),
            slug=slug,
            status=TenantStatus.PROVISIONING,
        )
        
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        
        return tenant

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get a tenant by slug."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        """Get a tenant by ID."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_tenant_status(
        self, tenant_id: uuid.UUID, new_status: TenantStatus
    ) -> Tenant:
        """Update tenant status (platform control-plane operation)."""
        # CRX-P0-007 P0-3: Tenants table is control-plane data, not tenant-scoped
        # Uses normal transaction handling, not tenant_transaction
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Validate status transition
        valid_transitions = {
            TenantStatus.PROVISIONING: [TenantStatus.ONBOARDING, TenantStatus.ACTIVE],
            TenantStatus.ONBOARDING: [TenantStatus.ACTIVE, TenantStatus.SUSPENDED],
            TenantStatus.ACTIVE: [TenantStatus.SUSPENDED, TenantStatus.OFFBOARDING],
            TenantStatus.SUSPENDED: [TenantStatus.ACTIVE, TenantStatus.OFFBOARDING],
            TenantStatus.OFFBOARDING: [TenantStatus.ARCHIVED],
            TenantStatus.ARCHIVED: [],  # Terminal state
        }
        
        if new_status not in valid_transitions.get(tenant.status, []):
            raise ValueError(f"Invalid status transition from {tenant.status} to {new_status}")
        
        tenant.status = new_status
        await self.db.commit()
        await self.db.refresh(tenant)
        
        return tenant
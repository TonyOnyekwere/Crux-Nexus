import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.merchant_management.application.capacity import CapacityService, CapacityExceededError
from app.contexts.merchant_management.domain.merchant_account_tenant import (
    MerchantAccountTenant,
)
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import (
    TenantMembership,
    TenantRole,
)


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_storefront(
        self,
        *,
        merchant_account_id: UUID,
        owner_user_id: UUID,
        slug: str,
    ) -> Tenant:
        """Create storefront with capacity enforcement and concurrency safety.
        
        This is the authoritative storefront creation operation that replaces
        the old generic tenant creation. It enforces merchant capacity and
        creates the complete ownership structure atomically.
        """
        capacity_service = CapacityService(self.db)

        async def _create_in_current_transaction() -> Tenant:
            # Check for slug uniqueness
            existing = await self.db.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            if existing.scalar_one_or_none():
                raise ValueError("Slug already taken")

            # Create storefront with capacity check and concurrency safety
            tenant = await capacity_service.create_storefront_with_capacity_check(
                merchant_account_id=merchant_account_id,
                owner_user_id=owner_user_id,
                slug=slug,
            )
            return tenant

        if self.db.in_transaction():
            return await _create_in_current_transaction()

        async with self.db.begin():
            return await _create_in_current_transaction()

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def user_has_membership(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> TenantMembership | None:
        result = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_staff_member(
        self,
        *,
        merchant_account_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole,
    ) -> TenantMembership:
        """Add a staff member to a storefront with capacity enforcement."""
        if role == TenantRole.OWNER:
            raise ValueError("Cannot invite additional owners via staff endpoint.")

        capacity_service = CapacityService(self.db)

        async def _add_in_current_transaction() -> TenantMembership:
            # Check capacity
            if not await capacity_service.can_add_staff(merchant_account_id, tenant_id):
                capacity = await capacity_service.get_storefront_staff_capacity(merchant_account_id, tenant_id)
                current = await capacity_service.get_current_staff_count(tenant_id)
                raise CapacityExceededError(
                    "Storefront has reached staff capacity",
                    {
                        "capacity": capacity,
                        "current": current,
                        "available": 0
                    }
                )

            # Check for existing membership
            existing = await self.user_has_membership(user_id, tenant_id)
            if existing:
                raise ValueError("User already has membership for this storefront.")

            membership = TenantMembership(
                tenant_id=tenant_id,
                user_id=user_id,
                role=role.value,
            )
            self.db.add(membership)
            await self.db.flush()
            return membership

        if self.db.in_transaction():
            return await _add_in_current_transaction()

        async with self.db.begin():
            return await _add_in_current_transaction()

    async def update_tenant_status(
        self, tenant_id: UUID, new_status: TenantStatus
    ) -> Tenant:
        """Update tenant status with state machine validation.
        
        This should only be called by Control Center or authorized platform roles.
        Merchant owners should not be able to change platform lifecycle states.
        """
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        valid_transitions = {
            TenantStatus.PROVISIONING: [TenantStatus.ONBOARDING, TenantStatus.ACTIVE],
            TenantStatus.ONBOARDING: [TenantStatus.ACTIVE, TenantStatus.SUSPENDED],
            TenantStatus.ACTIVE: [TenantStatus.SUSPENDED, TenantStatus.OFFBOARDING],
            TenantStatus.SUSPENDED: [TenantStatus.ACTIVE, TenantStatus.OFFBOARDING],
            TenantStatus.OFFBOARDING: [TenantStatus.ARCHIVED],
            TenantStatus.ARCHIVED: [],
        }

        if new_status not in valid_transitions.get(tenant.status, []):
            raise ValueError(
                f"Invalid status transition from {tenant.status} to {new_status}"
            )

        tenant.status = new_status
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

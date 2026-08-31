import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.merchant_management.application import capacity
from app.contexts.merchant_management.domain.merchant_account_tenant import (
    MerchantAccountTenant,
)
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import (
    MembershipStatus,
    TenantMembership,
    TenantRole,
)
from app.exceptions import CapacityExceeded, NotFoundError


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
        async with self.db.begin():
            await capacity.assert_can_create_storefront(self.db, merchant_account_id)

            existing = await self.db.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            if existing.scalar_one_or_none():
                raise ValueError("Slug already taken")

            tenant = Tenant(
                id=uuid.uuid4(),
                slug=slug,
                status=TenantStatus.PROVISIONING,
            )
            self.db.add(tenant)
            await self.db.flush()

            self.db.add(
                MerchantAccountTenant(
                    id=uuid.uuid4(),
                    merchant_account_id=merchant_account_id,
                    tenant_id=tenant.id,
                )
            )

            self.db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=owner_user_id,
                    role=TenantRole.OWNER,
                    status=MembershipStatus.ACTIVE,
                )
            )

            await self.db.refresh(tenant)

        return tenant

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
                TenantMembership.status == MembershipStatus.ACTIVE,
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
        if role == TenantRole.OWNER:
            raise ValueError("Cannot invite additional owners via staff endpoint.")

        async with self.db.begin():
            await capacity.assert_can_add_staff(
                self.db, merchant_account_id, tenant_id
            )

            existing = await self.user_has_membership(user_id, tenant_id)
            if existing:
                raise ValueError("User already has membership for this storefront.")

            membership = TenantMembership(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                role=role,
                status=MembershipStatus.ACTIVE,
            )
            self.db.add(membership)
            await self.db.refresh(membership)

        return membership

    async def update_tenant_status(
        self, tenant_id: UUID, new_status: TenantStatus
    ) -> Tenant:
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise NotFoundError("tenant", "Tenant not found.")

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

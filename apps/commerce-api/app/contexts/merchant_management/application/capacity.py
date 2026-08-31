from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.billing.domain.entities import (
    EntitlementStatus,
    EntitlementType,
    MerchantEntitlement,
    MerchantSubscription,
    StorefrontEntitlementAllocation,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.contexts.merchant_management.domain.merchant_account_tenant import (
    MerchantAccountTenant,
)
from app.contexts.tenant_management.domain.membership import (
    MembershipStatus,
    TenantMembership,
    TenantRole,
)
from app.exceptions import CapacityExceeded, NotFoundError


ACTIVE_SUBSCRIPTION_STATUSES = (
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.ACTIVE,
)


async def _lock_merchant(db: AsyncSession, merchant_account_id: UUID) -> None:
    await db.execute(
        text(
            """
            SELECT id FROM merchant_accounts
            WHERE id = :merchant_id
            FOR UPDATE
            """
        ),
        {"merchant_id": str(merchant_account_id)},
    )


async def _get_active_plan(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> SubscriptionPlan:
    result = await db.execute(
        select(SubscriptionPlan)
        .join(
            MerchantSubscription,
            MerchantSubscription.subscription_plan_id == SubscriptionPlan.id,
        )
        .where(
            MerchantSubscription.merchant_account_id == merchant_account_id,
            MerchantSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise NotFoundError("subscription", "No active subscription for merchant.")
    return plan


async def get_active_storefront_count(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(MerchantAccountTenant)
        .where(MerchantAccountTenant.merchant_account_id == merchant_account_id)
    )
    return int(result.scalar_one())


async def _active_extra_storefront_quantity(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(MerchantEntitlement.quantity), 0))
        .where(
            MerchantEntitlement.merchant_account_id == merchant_account_id,
            MerchantEntitlement.entitlement_type == EntitlementType.EXTRA_STOREFRONT,
            MerchantEntitlement.status == EntitlementStatus.ACTIVE,
        )
    )
    return int(result.scalar_one())


async def get_storefront_capacity(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> int:
    plan = await _get_active_plan(db, merchant_account_id)
    extra = await _active_extra_storefront_quantity(db, merchant_account_id)
    return plan.included_storefronts + extra


async def get_available_storefront_slots(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> int:
    capacity = await get_storefront_capacity(db, merchant_account_id)
    current = await get_active_storefront_count(db, merchant_account_id)
    return max(capacity - current, 0)


async def can_create_storefront(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> bool:
    capacity = await get_storefront_capacity(db, merchant_account_id)
    current = await get_active_storefront_count(db, merchant_account_id)
    return current < capacity


async def _allocated_extra_staff(
    db: AsyncSession,
    merchant_account_id: UUID,
    tenant_id: UUID,
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(StorefrontEntitlementAllocation.quantity), 0))
        .join(
            MerchantEntitlement,
            MerchantEntitlement.id == StorefrontEntitlementAllocation.entitlement_id,
        )
        .where(
            MerchantEntitlement.merchant_account_id == merchant_account_id,
            MerchantEntitlement.entitlement_type == EntitlementType.EXTRA_STAFF,
            MerchantEntitlement.status == EntitlementStatus.ACTIVE,
            StorefrontEntitlementAllocation.tenant_id == tenant_id,
        )
    )
    return int(result.scalar_one())


async def get_current_staff_count(
    db: AsyncSession,
    tenant_id: UUID,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(TenantMembership)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == MembershipStatus.ACTIVE,
            TenantMembership.role.in_([TenantRole.MANAGER, TenantRole.STAFF]),
        )
    )
    return int(result.scalar_one())


async def get_storefront_staff_capacity(
    db: AsyncSession,
    merchant_account_id: UUID,
    tenant_id: UUID,
) -> int:
    plan = await _get_active_plan(db, merchant_account_id)
    allocated = await _allocated_extra_staff(db, merchant_account_id, tenant_id)
    return plan.base_staff_per_storefront + allocated


async def can_add_staff(
    db: AsyncSession,
    merchant_account_id: UUID,
    tenant_id: UUID,
) -> bool:
    capacity = await get_storefront_staff_capacity(
        db, merchant_account_id, tenant_id
    )
    current = await get_current_staff_count(db, tenant_id)
    return current < capacity


async def assert_can_create_storefront(
    db: AsyncSession,
    merchant_account_id: UUID,
) -> None:
    await _lock_merchant(db, merchant_account_id)
    capacity = await get_storefront_capacity(db, merchant_account_id)
    current = await get_active_storefront_count(db, merchant_account_id)
    if current >= capacity:
        raise CapacityExceeded("storefront", capacity, current)


async def assert_can_add_staff(
    db: AsyncSession,
    merchant_account_id: UUID,
    tenant_id: UUID,
) -> None:
    await _lock_merchant(db, merchant_account_id)
    capacity = await get_storefront_staff_capacity(
        db, merchant_account_id, tenant_id
    )
    current = await get_current_staff_count(db, tenant_id)
    if current >= capacity:
        raise CapacityExceeded("staff", capacity, current)

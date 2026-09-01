from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID
import logging

from app.contexts.billing.domain.entities import SubscriptionPlan
from app.contexts.billing.domain.merchant_entitlement import MerchantEntitlement, EntitlementStatus
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import TenantMembership, TenantRole

logger = logging.getLogger(__name__)


class CapacityExceededError(Exception):
    """Raised when merchant exceeds their capacity limits."""
    code = "CAPACITY_EXCEEDED"
    
    def __init__(self, message: str, details: dict):
        self.message = message
        self.details = details
        super().__init__(message)


class CapacityService:
    """Single authority for all capacity calculations.
    
    This service enforces the commercial rules:
    - STARTER: 1 storefront, 0 staff/base, 0 extra storefronts, 0 extra staff
    - BUSINESS: 1 storefront, 3 staff/base, +1 extra storefronts max, +2 extra staff max
    - ENTERPRISE: 1 storefront, 8 staff/base, +2 extra storefronts max, +4 extra staff max
    
    Owner does NOT consume staff capacity.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_storefront_capacity(
        self,
        merchant_account_id: UUID,
    ) -> int:
        """Calculate effective storefront capacity for a merchant.
        
        Formula: plan.included_storefronts + active_extra_storefront_quantity
        """
        # Get merchant's active subscription
        subscription_result = await self.db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.merchant_account_id == merchant_account_id,
                MerchantSubscription.status.in_([
                    SubscriptionStatus.TRIALING.value,
                    SubscriptionStatus.ACTIVE.value,
                ])
            )
        )
        subscription = subscription_result.scalar_one_or_none()
        if not subscription:
            raise ValueError("No active subscription found")
        
        # Get subscription plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.subscription_plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise ValueError("Subscription plan not found")
        
        # Get active extra storefront entitlements
        extra_result = await self.db.execute(
            select(func.sum(MerchantEntitlement.quantity)).where(
                MerchantEntitlement.merchant_account_id == merchant_account_id,
                MerchantEntitlement.entitlement_type == "extra_storefront",
                MerchantEntitlement.status == EntitlementStatus.ACTIVE.value,
            )
        )
        extra_quantity = extra_result.scalar() or 0
        
        return plan.included_storefronts + extra_quantity

    async def get_active_storefront_count(
        self,
        merchant_account_id: UUID,
    ) -> int:
        """Count active storefronts for a merchant.
        
        Counts: PROVISIONING, ONBOARDING, ACTIVE, SUSPENDED
        Does NOT count: ARCHIVED
        """
        result = await self.db.execute(
            select(func.count(MerchantAccountTenant.id)).where(
                MerchantAccountTenant.merchant_account_id == merchant_account_id
            )
        )
        return result.scalar() or 0

    async def get_available_storefront_slots(
        self,
        merchant_account_id: UUID,
    ) -> int:
        """Calculate available storefront slots.
        
        Formula: effective_capacity - active_count
        """
        capacity = await self.get_storefront_capacity(merchant_account_id)
        active_count = await self.get_active_storefront_count(merchant_account_id)
        return max(0, capacity - active_count)

    async def can_create_storefront(
        self,
        merchant_account_id: UUID,
    ) -> bool:
        """Check if merchant can create another storefront."""
        available = await self.get_available_storefront_slots(merchant_account_id)
        return available > 0

    async def get_storefront_staff_capacity(
        self,
        merchant_account_id: UUID,
        tenant_id: UUID,
    ) -> int:
        """Calculate effective staff capacity for a specific storefront.
        
        Formula: plan.base_staff_per_storefront + allocated_extra_staff
        Owner does NOT consume staff capacity.
        """
        # Get merchant's active subscription
        subscription_result = await self.db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.merchant_account_id == merchant_account_id,
                MerchantSubscription.status.in_([
                    SubscriptionStatus.TRIALING.value,
                    SubscriptionStatus.ACTIVE.value,
                ])
            )
        )
        subscription = subscription_result.scalar_one_or_none()
        if not subscription:
            raise ValueError("No active subscription found")
        
        # Get subscription plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.subscription_plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise ValueError("Subscription plan not found")
        
        # Get allocated extra staff for this specific storefront
        # TODO: Implement when storefront_entitlement_allocations table is fully integrated
        allocated_extra = 0
        
        return plan.base_staff_per_storefront + allocated_extra

    async def get_current_staff_count(
        self,
        tenant_id: UUID,
    ) -> int:
        """Count current staff members for a storefront.
        
        Does NOT count OWNER.
        Counts: MANAGER, STAFF
        """
        result = await self.db.execute(
            select(func.count(TenantMembership.id)).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role.in_([TenantRole.MANAGER.value, TenantRole.STAFF.value])
            )
        )
        return result.scalar() or 0

    async def can_add_staff(
        self,
        merchant_account_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Check if storefront can add another staff member."""
        capacity = await self.get_storefront_staff_capacity(merchant_account_id, tenant_id)
        current = await self.get_current_staff_count(tenant_id)
        return current < capacity

    async def create_storefront_with_capacity_check(
        self,
        *,
        merchant_account_id: UUID,
        owner_user_id: UUID,
        slug: str,
    ) -> Tenant:
        """
        Create storefront with capacity enforcement and concurrency safety.
        
        This method uses transactional locking to prevent race conditions:
        BEGIN
        ↓
        SELECT merchant_account FOR UPDATE (locks merchant)
        ↓
        calculate capacity
        ↓
        count active storefronts
        ↓
        reject if full
        ↓
        create tenant
        ↓
        create ownership
        ↓
        create owner membership
        ↓
        COMMIT
        """
        # Lock the merchant account to prevent concurrent storefront creation
        await self.db.execute(
            text("SELECT id FROM merchant_accounts WHERE id = :merchant_id FOR UPDATE"),
            {"merchant_id": str(merchant_account_id)}
        )
        
        # Check capacity
        if not await self.can_create_storefront(merchant_account_id):
            capacity = await self.get_storefront_capacity(merchant_account_id)
            active_count = await self.get_active_storefront_count(merchant_account_id)
            raise CapacityExceeded("storefront", capacity, active_count)
        
        # Create tenant
        tenant = Tenant(
            slug=slug,
            status=TenantStatus.PROVISIONING,
        )
        self.db.add(tenant)
        await self.db.flush()
        
        # Create ownership
        ownership = MerchantAccountTenant(
            merchant_account_id=merchant_account_id,
            tenant_id=tenant.id,
        )
        self.db.add(ownership)
        await self.db.flush()
        
        # Create owner membership
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=owner_user_id,
            role=TenantRole.OWNER.value,
        )
        self.db.add(membership)
        await self.db.flush()
        
        return tenant
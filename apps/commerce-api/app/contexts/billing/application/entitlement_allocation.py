from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID
import logging

from app.contexts.billing.domain.merchant_entitlement import MerchantEntitlement, EntitlementStatus, EntitlementType
from app.contexts.billing.domain.staff_capacity_allocation import StaffCapacityAllocation
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.exceptions import CapacityExceededError

logger = logging.getLogger(__name__)


class EntitlementAllocationService:
    """
    Service for managing entitlement allocations across storefronts.
    
    This implements the allocation model:
    - Merchant has EXTRA_STAFF entitlements
    - Allocations distribute these entitlements to specific storefronts
    - SUM(allocation.quantity) <= entitlement.quantity (transactionally enforced)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_available_entitlement_quantity(
        self,
        merchant_account_id: UUID,
        entitlement_type: str,
    ) -> int:
        """Calculate available quantity of an entitlement type.
        
        Formula: SUM(active_entitlements.quantity) - SUM(current_allocations.quantity)
        """
        # Get total active entitlements
        entitlement_result = await self.db.execute(
            select(func.sum(MerchantEntitlement.quantity)).where(
                MerchantEntitlement.merchant_account_id == merchant_account_id,
                MerchantEntitlement.entitlement_type == entitlement_type,
                MerchantEntitlement.status == EntitlementStatus.ACTIVE.value,
            )
        )
        total_entitlements = entitlement_result.scalar() or 0
        
        # Get total current allocations against ACTIVE entitlements only.
        allocation_result = await self.db.execute(
            select(func.sum(StaffCapacityAllocation.quantity)).where(
                StaffCapacityAllocation.merchant_entitlement_id.in_(
                    select(MerchantEntitlement.id).where(
                        MerchantEntitlement.merchant_account_id == merchant_account_id,
                        MerchantEntitlement.entitlement_type == entitlement_type,
                        MerchantEntitlement.status == EntitlementStatus.ACTIVE.value,
                    )
                )
            )
        )
        total_allocated = allocation_result.scalar() or 0
        
        return max(0, total_entitlements - total_allocated)
    
    async def allocate_staff_to_storefront(
        self,
        *,
        merchant_account_id: UUID,
        entitlement_id: UUID,
        tenant_id: UUID,
        quantity: int,
    ) -> StaffCapacityAllocation:
        """
        Allocate staff capacity from an entitlement to a specific storefront.
        
        This is transactionally enforced:
        - Lock the entitlement
        - Calculate available quantity
        - Verify allocation doesn't exceed available
        - Create allocation
        """
        if quantity <= 0:
            raise ValueError("Allocation quantity must be positive")
        
        # Lock the entitlement to prevent concurrent allocations
        await self.db.execute(
            text("SELECT id FROM merchant_entitlements WHERE id = :entitlement_id FOR UPDATE"),
            {"entitlement_id": str(entitlement_id)}
        )
        
        # Verify entitlement belongs to merchant
        entitlement_result = await self.db.execute(
            select(MerchantEntitlement).where(
                MerchantEntitlement.id == entitlement_id,
                MerchantEntitlement.merchant_account_id == merchant_account_id,
                MerchantEntitlement.entitlement_type == EntitlementType.EXTRA_STAFF.value,
                MerchantEntitlement.status == EntitlementStatus.ACTIVE.value,
            )
        )
        entitlement = entitlement_result.scalar_one_or_none()
        if not entitlement:
            raise ValueError("Entitlement not found or not active")

        ownership_result = await self.db.execute(
            select(MerchantAccountTenant)
            .where(
                MerchantAccountTenant.tenant_id == tenant_id,
                MerchantAccountTenant.merchant_account_id == merchant_account_id,
            )
            .with_for_update()
        )
        if ownership_result.scalar_one_or_none() is None:
            raise ValueError("Tenant is not owned by this merchant account")

        # Calculate available quantity
        available = await self.get_available_entitlement_quantity(
            merchant_account_id,
            EntitlementType.EXTRA_STAFF.value,
        )
        
        if quantity > available:
            raise CapacityExceededError(
                "staff_allocation",
                entitlement.quantity,
                entitlement.quantity - available,
            )
        
        # Check if allocation already exists for this storefront
        existing_result = await self.db.execute(
            select(StaffCapacityAllocation).where(
                StaffCapacityAllocation.merchant_entitlement_id == entitlement_id,
                StaffCapacityAllocation.tenant_id == tenant_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Update existing allocation
            new_quantity = existing.quantity + quantity
            if new_quantity > available + existing.quantity:
                raise CapacityExceededError(
                    "staff_allocation",
                    entitlement.quantity,
                    entitlement.quantity - available,
                )
            existing.quantity = new_quantity
            await self.db.flush()
            return existing
        else:
            # Create new allocation
            allocation = StaffCapacityAllocation(
                merchant_entitlement_id=entitlement_id,
                tenant_id=tenant_id,
                quantity=quantity,
            )
            self.db.add(allocation)
            await self.db.flush()
            return allocation
    
    async def deallocate_staff_from_storefront(
        self,
        *,
        merchant_account_id: UUID,
        allocation_id: UUID,
        quantity: int,
    ) -> StaffCapacityAllocation:
        """
        Reduce or remove staff allocation from a storefront.
        """
        if quantity <= 0:
            raise ValueError("Deallocation quantity must be positive")
        
        # Get the allocation
        allocation_result = await self.db.execute(
            select(StaffCapacityAllocation).join(
                MerchantEntitlement,
                MerchantEntitlement.id == StaffCapacityAllocation.merchant_entitlement_id,
            ).where(
                StaffCapacityAllocation.id == allocation_id,
                MerchantEntitlement.merchant_account_id == merchant_account_id,
            )
        )
        allocation = allocation_result.scalar_one_or_none()
        if not allocation:
            raise ValueError("Allocation not found")
        
        if quantity >= allocation.quantity:
            # Remove allocation entirely
            await self.db.delete(allocation)
            await self.db.flush()
            return allocation
        else:
            # Reduce allocation
            allocation.quantity -= quantity
            await self.db.flush()
            return allocation
    
    async def get_storefront_allocated_staff(
        self,
        tenant_id: UUID,
    ) -> int:
        """Get total allocated staff capacity for a specific storefront."""
        result = await self.db.execute(
            select(func.sum(StaffCapacityAllocation.quantity)).where(
                StaffCapacityAllocation.tenant_id == tenant_id
            )
        )
        return result.scalar() or 0
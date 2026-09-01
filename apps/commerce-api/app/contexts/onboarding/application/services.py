from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import logging

from app.contexts.identity.domain.entities import User
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser, MerchantUserRole
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import TenantMembership, TenantRole
from app.contexts.billing.domain.entities import SubscriptionPlan
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus

logger = logging.getLogger(__name__)


class OnboardingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def onboard_merchant(
        self,
        *,
        user_id: UUID,
        merchant_name: str,
        storefront_slug: str,
        plan_code: str,
    ) -> dict:
        """
        Complete merchant onboarding transaction.
        
        This creates the complete foundation in one atomic transaction:
        - Merchant Account
        - Merchant Account User relationship
        - Subscription
        - Tenant (Storefront)
        - Merchant Account Tenant ownership
        - Tenant Membership (OWNER)
        
        Transaction flow:
        BEGIN
        ↓
        Verify User exists
        ↓
        Create Merchant Account
        ↓
        Create Merchant Account User
        ↓
        Resolve Subscription Plan
        ↓
        Create Merchant Subscription
        ↓
        Create Tenant
        ↓
        Create Merchant Account Tenant ownership
        ↓
        Create Tenant Membership (OWNER)
        ↓
        COMMIT
        """
        # Verify user exists
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Resolve subscription plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == plan_code,
                SubscriptionPlan.active == True
            )
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Subscription plan '{plan_code}' not found or inactive")

        # Create merchant account
        merchant_account = MerchantAccount(
            name=merchant_name,
            status="active",
        )
        self.db.add(merchant_account)
        await self.db.flush()

        # Create merchant account user relationship
        merchant_account_user = MerchantAccountUser(
            merchant_account_id=merchant_account.id,
            user_id=user_id,
            role=MerchantUserRole.OWNER.value,
        )
        self.db.add(merchant_account_user)
        await self.db.flush()

        # Create merchant subscription
        merchant_subscription = MerchantSubscription(
            merchant_account_id=merchant_account.id,
            subscription_plan_id=plan.id,
            status=SubscriptionStatus.TRIALING.value,
        )
        self.db.add(merchant_subscription)
        await self.db.flush()

        # Create tenant (storefront)
        tenant = Tenant(
            slug=storefront_slug,
            status=TenantStatus.PROVISIONING,
        )
        self.db.add(tenant)
        await self.db.flush()

        # Create merchant account tenant ownership
        merchant_account_tenant = MerchantAccountTenant(
            merchant_account_id=merchant_account.id,
            tenant_id=tenant.id,
        )
        self.db.add(merchant_account_tenant)
        await self.db.flush()

        # Create tenant membership (OWNER)
        tenant_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user_id,
            role=TenantRole.OWNER.value,
        )
        self.db.add(tenant_membership)
        await self.db.flush()

        await self.db.commit()

        return {
            "merchant_account_id": merchant_account.id,
            "tenant_id": tenant.id,
            "subscription_id": merchant_subscription.id,
            "membership_id": tenant_membership.id,
        }
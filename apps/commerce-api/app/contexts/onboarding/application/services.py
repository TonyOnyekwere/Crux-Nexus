from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
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
from app.utils.slug import normalize_storefront_slug

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

        existing_merchant_result = await self.db.execute(
            select(MerchantAccount)
            .join(
                MerchantAccountUser,
                MerchantAccountUser.merchant_account_id == MerchantAccount.id,
            )
            .where(MerchantAccountUser.user_id == user_id)
            .order_by(MerchantAccount.created_at.desc(), MerchantAccount.id.desc())
            .limit(1)
        )
        if existing_merchant_result.scalar_one_or_none() is not None:
            raise ValueError(
                "This user already has a merchant account. Use the existing account to upgrade or renew the plan instead of creating a second one."
            )

        normalized_slug = normalize_storefront_slug(storefront_slug)

        existing_tenant = await self.db.execute(
            select(Tenant).where(func.lower(Tenant.slug) == normalized_slug)
        )
        if existing_tenant.scalar_one_or_none() is not None:
            raise ValueError(f"Storefront slug '{storefront_slug}' is already in use")

        # Resolve subscription plan in a case-insensitive way to match the
        # seeded values ('starter', 'business', 'enterprise') and the API contract.
        # If the deployment database is missing the seed rows, recover by creating
        # the canonical plans before rejecting the onboarding request.
        normalized_plan_code = plan_code.strip().lower()
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                func.lower(SubscriptionPlan.code) == normalized_plan_code,
                SubscriptionPlan.active.is_(True),
            )
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            default_plans = [
                {
                    "code": "starter",
                    "name": "Starter",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 0,
                    "max_extra_storefronts": 0,
                    "max_extra_staff": 0,
                },
                {
                    "code": "business",
                    "name": "Business",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 3,
                    "max_extra_storefronts": 1,
                    "max_extra_staff": 2,
                },
                {
                    "code": "enterprise",
                    "name": "Enterprise",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 8,
                    "max_extra_storefronts": 2,
                    "max_extra_staff": 4,
                },
            ]
            for default_plan in default_plans:
                existing_plan_result = await self.db.execute(
                    select(SubscriptionPlan).where(
                        func.lower(SubscriptionPlan.code) == default_plan["code"],
                    )
                )
                if existing_plan_result.scalar_one_or_none() is None:
                    self.db.add(
                        SubscriptionPlan(
                            code=default_plan["code"],
                            name=default_plan["name"],
                            included_storefronts=default_plan["included_storefronts"],
                            base_staff_per_storefront=default_plan["base_staff_per_storefront"],
                            max_extra_storefronts=default_plan["max_extra_storefronts"],
                            max_extra_staff=default_plan["max_extra_staff"],
                            active=True,
                        )
                    )
            await self.db.flush()

            plan_result = await self.db.execute(
                select(SubscriptionPlan).where(
                    func.lower(SubscriptionPlan.code) == normalized_plan_code,
                    SubscriptionPlan.active.is_(True),
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
            slug=normalized_slug,
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
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.billing.domain.entities import (
    MerchantSubscription,
    SubscriptionPlan,
    SubscriptionPlanCode,
    SubscriptionStatus,
)
from app.contexts.identity.domain.entities import User
from app.contexts.merchant_management.domain.entities import (
    MerchantAccount,
    MerchantAccountRole,
    MerchantAccountUser,
    MerchantStatus,
)
from app.contexts.merchant_management.domain.merchant_account_tenant import (
    MerchantAccountTenant,
)
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import (
    MembershipStatus,
    TenantMembership,
    TenantRole,
)
from app.exceptions import NotFoundError


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
    ) -> tuple[MerchantAccount, Tenant]:
        normalized_plan = plan_code.strip().lower()
        try:
            plan_enum = SubscriptionPlanCode(normalized_plan)
        except ValueError as exc:
            raise ValueError(
                f"Invalid plan code. Allowed: {', '.join(c.value for c in SubscriptionPlanCode)}"
            ) from exc

        async with self.db.begin():
            user = await self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("user", "User not found.")

            existing_slug = await self.db.execute(
                select(Tenant).where(Tenant.slug == storefront_slug)
            )
            if existing_slug.scalar_one_or_none():
                raise ValueError("Slug already taken")

            plan_result = await self.db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.code == plan_enum.value,
                    SubscriptionPlan.active.is_(True),
                )
            )
            plan = plan_result.scalar_one_or_none()
            if plan is None:
                raise NotFoundError("subscription_plan", "Plan not found.")

            merchant = MerchantAccount(
                id=uuid.uuid4(),
                name=merchant_name,
                status=MerchantStatus.ACTIVE,
            )
            self.db.add(merchant)
            await self.db.flush()

            self.db.add(
                MerchantAccountUser(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    merchant_account_id=merchant.id,
                    role=MerchantAccountRole.OWNER,
                )
            )

            self.db.add(
                MerchantSubscription(
                    id=uuid.uuid4(),
                    merchant_account_id=merchant.id,
                    subscription_plan_id=plan.id,
                    status=SubscriptionStatus.ACTIVE,
                )
            )

            tenant = Tenant(
                id=uuid.uuid4(),
                slug=storefront_slug,
                status=TenantStatus.PROVISIONING,
            )
            self.db.add(tenant)
            await self.db.flush()

            self.db.add(
                MerchantAccountTenant(
                    id=uuid.uuid4(),
                    merchant_account_id=merchant.id,
                    tenant_id=tenant.id,
                )
            )

            self.db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=user_id,
                    role=TenantRole.OWNER,
                    status=MembershipStatus.ACTIVE,
                )
            )

            await self.db.refresh(merchant)
            await self.db.refresh(tenant)

        return merchant, tenant

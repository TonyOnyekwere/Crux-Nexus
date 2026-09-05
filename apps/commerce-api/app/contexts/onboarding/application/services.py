from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from uuid import UUID
import logging

from app.config import get_settings
from app.contexts.identity.domain.entities import User
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser, MerchantUserRole
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import TenantMembership, TenantRole, MembershipStatus
from app.contexts.billing.domain.entities import SubscriptionPlan
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus
from app.contexts.billing.domain.merchant_trial_history import MerchantTrialHistory
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
        # Outside production, recover from a missing seed by creating the
        # canonical plans before rejecting the onboarding request — this is a
        # development/staging convenience only. In production, a missing
        # plan is treated as a hard operational error (see below) rather
        # than something onboarding silently repairs.
        normalized_plan_code = plan_code.strip().lower()
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                func.lower(SubscriptionPlan.code) == normalized_plan_code,
                SubscriptionPlan.active.is_(True),
            )
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            settings = get_settings()
            if (settings.ENVIRONMENT or "development").lower() == "production":
                # Platform configuration (subscription_plans) must be
                # provisioned by migration/seed, never mutated as a side
                # effect of a merchant's onboarding request. A missing plan
                # in production is a deployment/operational error, not
                # something to silently self-heal.
                raise ValueError(
                    f"Subscription plan '{plan_code}' not found or inactive. "
                    "This indicates missing platform configuration and must "
                    "be fixed by seeding subscription_plans, not by onboarding."
                )

            default_plans = [
                {
                    "code": "starter",
                    "name": "Starter",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 0,
                    "max_extra_storefronts": 0,
                    "max_extra_staff": 0,
                    "trial_days": 3,
                },
                {
                    "code": "business",
                    "name": "Business",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 3,
                    "max_extra_storefronts": 1,
                    "max_extra_staff": 2,
                    "trial_days": 3,
                },
                {
                    "code": "enterprise",
                    "name": "Enterprise",
                    "included_storefronts": 1,
                    "base_staff_per_storefront": 8,
                    "max_extra_storefronts": 2,
                    "max_extra_staff": 4,
                    "trial_days": 7,
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
                            trial_days=default_plan["trial_days"],
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

        # From here on, every insert is protected by a real database
        # constraint (uq_one_owner_merchant_per_user,
        # uq_one_live_subscription_per_merchant, tenants.slug UNIQUE — see
        # migration 008 and the Tenant model). The SELECT-based checks above
        # are an early, friendly rejection for the common case; concurrent
        # requests that race past them are caught here as an IntegrityError
        # and turned into the same clean domain error, rather than an
        # unhandled 500.
        try:
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
            #
            # Trial length is plan-configured (SubscriptionPlan.trial_days) —
            # never a hardcoded constant here. Every plan is required to carry
            # an explicit trial_days value (see migration 010), so a missing
            # value indicates a data problem rather than something to silently
            # default around.
            if plan.trial_days is None:
                raise ValueError(
                    f"Subscription plan '{plan.code}' is missing a configured trial_days value"
                )

            trial_started_at = datetime.now(timezone.utc)
            trial_ends_at = trial_started_at + timedelta(days=plan.trial_days)

            merchant_subscription = MerchantSubscription(
                merchant_account_id=merchant_account.id,
                subscription_plan_id=plan.id,
                status=SubscriptionStatus.TRIALING.value,
                trial_started_at=trial_started_at,
                trial_ends_at=trial_ends_at,
            )
            self.db.add(merchant_subscription)
            await self.db.flush()

            # Audit trail: record the start of the trial. This is the write path
            # that keeps merchant_trial_history populated going forward — the
            # one-time migration 004 backfill only ever covered historical rows.
            # subscription_id (migration 011) is what expiration matches on —
            # never re-derive the open trial via merchant/plan correlation when
            # a direct reference is available.
            trial_history_entry = MerchantTrialHistory(
                merchant_account_id=merchant_account.id,
                subscription_plan_id=plan.id,
                subscription_id=merchant_subscription.id,
                status=SubscriptionStatus.TRIALING.value,
                started_at=trial_started_at,
            )
            self.db.add(trial_history_entry)
            await self.db.flush()

            # Create tenant (storefront) in the onboarding stage so it is
            # immediately usable for tenant-scoped access once the merchant has
            # completed setup, while still preserving the lifecycle guardrails.
            tenant = Tenant(
                slug=normalized_slug,
                status=TenantStatus.ONBOARDING,
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
                status=MembershipStatus.ACTIVE.value,
            )
            self.db.add(tenant_membership)
            await self.db.flush()

            from app.kernel.events.publisher import publish_to_outbox
            from app.kernel.events.types import DomainEvent, EventEnvelope

            await publish_to_outbox(
                self.db,
                EventEnvelope(
                    event_type=DomainEvent.MERCHANT_CREATED,
                    aggregate_type="MerchantAccount",
                    aggregate_id=merchant_account.id,
                    payload={
                        "merchant_name": merchant_name,
                        "user_id": str(user_id),
                        "plan_code": plan_code,
                    },
                ),
            )
            await publish_to_outbox(
                self.db,
                EventEnvelope(
                    event_type=DomainEvent.STOREFRONT_CREATED,
                    aggregate_type="Tenant",
                    aggregate_id=tenant.id,
                    tenant_id=tenant.id,
                    payload={"slug": normalized_slug, "merchant_account_id": str(merchant_account.id)},
                ),
            )

            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            logger.warning(
                "Onboarding lost a uniqueness race for user_id=%s slug=%s",
                user_id,
                normalized_slug,
            )
            raise ValueError(
                "This user already has a merchant account, or the storefront "
                "slug was just taken by a concurrent request. Please retry."
            )

        return {
            "merchant_account_id": merchant_account.id,
            "tenant_id": tenant.id,
            "subscription_id": merchant_subscription.id,
            "membership_id": tenant_membership.id,
        }
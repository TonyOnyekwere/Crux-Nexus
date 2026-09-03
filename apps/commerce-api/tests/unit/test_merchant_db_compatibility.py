import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import String, func, select

from app.contexts.billing.application.entitlement_allocation import EntitlementAllocationService
from app.contexts.billing.domain.entities import SubscriptionPlan
from app.contexts.billing.domain.merchant_entitlement import MerchantEntitlement, EntitlementType, EntitlementStatus
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus
from app.contexts.identity.domain.entities import User
from app.contexts.merchant_management.application.services import MerchantService
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser, MerchantUserRole
from app.contexts.onboarding.application.services import OnboardingService
from app.contexts.tenant_management.application.services import TenantService
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import (
    MembershipStatus,
    TenantMembership,
    TenantRole,
)
from app.exceptions import CapacityExceeded


def test_tenant_membership_model_matches_canonical_schema():
    columns = {column.name for column in TenantMembership.__table__.columns}
    assert columns == {
        "id",
        "tenant_id",
        "user_id",
        "role",
        "status",
        "created_at",
        "updated_at",
    }
    assert TenantMembership.__table__.c.status.default.arg == MembershipStatus.ACTIVE.value


def test_merchant_status_and_role_columns_are_string_compatible():
    assert isinstance(MerchantAccount.__table__.c.status.type, String)
    assert isinstance(MerchantAccountUser.__table__.c.role.type, String)


def test_identity_registration_rejects_tenant_id_and_extra_fields():
    from app.contexts.identity.api.schemas import UserCreate

    with pytest.raises(ValidationError):
        UserCreate(email="user@example.com", password="secret", tenant_id=uuid4())

    with pytest.raises(ValidationError):
        UserCreate.model_validate({
            "email": "user@example.com",
            "password": "secret",
            "tenant_id": str(uuid4()),
        })


@pytest.mark.asyncio
async def test_require_owner_merchant_account_returns_single_owner(db_session):
    user_id = uuid4()
    merchant = MerchantAccount(name="Owner Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    db_session.add(
        MerchantAccountUser(
            merchant_account_id=merchant.id,
            user_id=user_id,
            role=MerchantUserRole.OWNER.value,
        )
    )
    await db_session.commit()

    service = MerchantService(db_session)
    account_id = await service.require_owner_merchant_account_id(user_id)
    assert account_id == merchant.id


@pytest.mark.asyncio
async def test_onboard_merchant_rejects_duplicate_merchant_for_same_user(db_session):
    user = User(email="already@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    merchant = MerchantAccount(name="Existing Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    db_session.add(
        MerchantAccountUser(
            merchant_account_id=merchant.id,
            user_id=user.id,
            role=MerchantUserRole.OWNER.value,
        )
    )
    await db_session.commit()

    service = OnboardingService(db_session)

    with pytest.raises(ValueError, match="already has a merchant account"):
        await service.onboard_merchant(
            user_id=user.id,
            merchant_name="Second Merchant",
            storefront_slug="second-storefront",
            plan_code="starter",
        )


@pytest.mark.asyncio
async def test_onboard_merchant_normalizes_storefront_slug(db_session):
    user = User(email="normalized-slug@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    service = OnboardingService(db_session)
    result = await service.onboard_merchant(
        user_id=user.id,
        merchant_name="Slugged Merchant",
        storefront_slug="  My Store! #2024  ",
        plan_code="starter",
    )

    tenant = await db_session.get(__import__('app.contexts.tenant_management.domain.entities', fromlist=['Tenant']).Tenant, result["tenant_id"])

    assert tenant is not None
    assert tenant.slug == "my-store-2024"


@pytest.mark.asyncio
async def test_starter_plan_block_staff_management_with_clear_upgrade_message(db_session):
    user = User(email="starter-no-staff@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    merchant = MerchantAccount(name="Starter Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    db_session.add(
        MerchantAccountUser(
            merchant_account_id=merchant.id,
            user_id=user.id,
            role=MerchantUserRole.OWNER.value,
        )
    )

    starter_plan = SubscriptionPlan(
        code="starter",
        name="Starter",
        included_storefronts=1,
        base_staff_per_storefront=0,
        max_extra_storefronts=0,
        max_extra_staff=0,
        active=True,
    )
    db_session.add(starter_plan)
    await db_session.flush()

    db_session.add(
        MerchantSubscription(
            merchant_account_id=merchant.id,
            subscription_plan_id=starter_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
    )

    tenant = Tenant(slug="starter-storefront", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=TenantRole.OWNER.value,
        )
    )
    await db_session.commit()

    service = TenantService(db_session)

    assert await service.merchant_has_staff_capability(merchant.id, tenant.id) is False

    with pytest.raises(ValueError, match="Business and Enterprise"):
        await service.can_manage_staff_or_raise(merchant.id, tenant.id)


@pytest.mark.asyncio
async def test_storefront_creation_raises_capacity_error_when_plan_limit_is_reached(db_session):
    user = User(email="capacity-limit@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    merchant = MerchantAccount(name="Capacity Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    db_session.add(
        MerchantAccountUser(
            merchant_account_id=merchant.id,
            user_id=user.id,
            role=MerchantUserRole.OWNER.value,
        )
    )

    starter_plan = SubscriptionPlan(
        code="starter",
        name="Starter",
        included_storefronts=1,
        base_staff_per_storefront=0,
        max_extra_storefronts=0,
        max_extra_staff=0,
        active=True,
    )
    db_session.add(starter_plan)
    await db_session.flush()

    db_session.add(
        MerchantSubscription(
            merchant_account_id=merchant.id,
            subscription_plan_id=starter_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
    )

    tenant = Tenant(slug="existing-storefront", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        MerchantAccountTenant(
            merchant_account_id=merchant.id,
            tenant_id=tenant.id,
        )
    )
    await db_session.commit()

    service = TenantService(db_session)

    with pytest.raises(CapacityExceeded, match="reached its storefront capacity"):
        await service.create_storefront(
            merchant_account_id=merchant.id,
            owner_user_id=user.id,
            slug="second-storefront",
        )


@pytest.mark.asyncio
async def test_entitlement_allocation_rejects_storefront_owned_by_other_merchant(db_session):
    merchant_a = MerchantAccount(name="Merchant A", status="active")
    merchant_b = MerchantAccount(name="Merchant B", status="active")
    db_session.add_all([merchant_a, merchant_b])
    await db_session.flush()

    tenant = Tenant(slug="other-merchant-storefront", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        MerchantAccountTenant(
            merchant_account_id=merchant_b.id,
            tenant_id=tenant.id,
        )
    )

    entitlement = MerchantEntitlement(
        merchant_account_id=merchant_a.id,
        entitlement_type=EntitlementType.EXTRA_STAFF.value,
        quantity=3,
        source="purchase",
        status=EntitlementStatus.ACTIVE.value,
    )
    db_session.add(entitlement)
    await db_session.flush()

    service = EntitlementAllocationService(db_session)

    with pytest.raises(ValueError, match="not owned by this merchant account"):
        await service.allocate_staff_to_storefront(
            merchant_account_id=merchant_a.id,
            entitlement_id=entitlement.id,
            tenant_id=tenant.id,
            quantity=1,
        )


@pytest.mark.asyncio
async def test_add_staff_member_rejects_tenant_not_owned_by_merchant(db_session):
    merchant = MerchantAccount(name="Staff Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    other_merchant = MerchantAccount(name="Other Merchant", status="active")
    db_session.add(other_merchant)
    await db_session.flush()

    tenant = Tenant(slug="foreign-storefront", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        MerchantAccountTenant(
            merchant_account_id=other_merchant.id,
            tenant_id=tenant.id,
        )
    )
    await db_session.commit()

    service = TenantService(db_session)

    with pytest.raises(ValueError, match="not owned by this merchant account"):
        await service.add_staff_member(
            merchant_account_id=merchant.id,
            tenant_id=tenant.id,
            user_id=uuid4(),
            role=TenantRole.STAFF,
        )


@pytest.mark.asyncio
async def test_concurrent_storefront_creation_respects_capacity_limit(db_session):
    user = User(email="concurrent-capacity@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    merchant = MerchantAccount(name="Concurrent Merchant", status="active")
    db_session.add(merchant)
    await db_session.flush()

    db_session.add(
        MerchantAccountUser(
            merchant_account_id=merchant.id,
            user_id=user.id,
            role=MerchantUserRole.OWNER.value,
        )
    )

    starter_plan = SubscriptionPlan(
        code="starter",
        name="Starter",
        included_storefronts=1,
        base_staff_per_storefront=0,
        max_extra_storefronts=0,
        max_extra_staff=0,
        active=True,
    )
    db_session.add(starter_plan)
    await db_session.flush()

    db_session.add(
        MerchantSubscription(
            merchant_account_id=merchant.id,
            subscription_plan_id=starter_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
    )

    tenant = Tenant(slug="existing-capacity-storefront", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(
        MerchantAccountTenant(
            merchant_account_id=merchant.id,
            tenant_id=tenant.id,
        )
    )
    await db_session.commit()

    service = TenantService(db_session)

    async def attempt_create():
        return await service.create_storefront(
            merchant_account_id=merchant.id,
            owner_user_id=user.id,
            slug=f"race-storefront-{uuid4()}",
        )

    results = await asyncio.gather(
        attempt_create(),
        attempt_create(),
        return_exceptions=True,
    )

    assert len([r for r in results if not isinstance(r, Exception)]) == 0
    assert all(isinstance(r, Exception) for r in results)


@pytest.mark.asyncio
async def test_validate_tenant_ready_for_access_blocks_provisioning_and_archived():
    service = TenantService.__new__(TenantService)

    async def fake_get_tenant_by_id(_tenant_id):
        return Tenant(slug="block-me", status=TenantStatus.PROVISIONING)

    service.get_tenant_by_id = fake_get_tenant_by_id

    with pytest.raises(ValueError, match="still provisioning"):
        await service.validate_tenant_ready_for_access(uuid4())

    async def fake_get_archived_tenant_by_id(_tenant_id):
        return Tenant(slug="archived-storefront", status=TenantStatus.ARCHIVED)

    service.get_tenant_by_id = fake_get_archived_tenant_by_id

    with pytest.raises(ValueError, match="archived"):
        await service.validate_tenant_ready_for_access(uuid4())


@pytest.mark.asyncio
async def test_onboard_merchant_rolls_back_when_membership_creation_fails(db_session, monkeypatch):
    user = User(email="rollback@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    starter_plan = SubscriptionPlan(
        code="starter",
        name="Starter",
        included_storefronts=1,
        base_staff_per_storefront=0,
        max_extra_storefronts=0,
        max_extra_staff=0,
        active=True,
    )
    db_session.add(starter_plan)
    await db_session.commit()

    original_add = db_session.add

    def fail_on_membership(obj):
        if isinstance(obj, TenantMembership):
            raise RuntimeError("simulated membership insert failure")
        original_add(obj)

    monkeypatch.setattr(db_session, "add", fail_on_membership)

    service = OnboardingService(db_session)

    with pytest.raises(RuntimeError, match="simulated membership insert failure"):
        await service.onboard_merchant(
            user_id=user.id,
            merchant_name="Rollback Merchant",
            storefront_slug="rollback-storefront",
            plan_code="starter",
        )

    await db_session.rollback()

    merchant_count = await db_session.scalar(
        select(func.count()).select_from(MerchantAccount)
    )
    tenant_count = await db_session.scalar(
        select(func.count()).select_from(Tenant)
    )

    assert merchant_count == 0
    assert tenant_count == 0


@pytest.mark.asyncio
async def test_onboard_merchant_creates_default_plan_when_seed_missing(db_session):
    user = User(email="new-plan@merchant.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    service = OnboardingService(db_session)
    result = await service.onboard_merchant(
        user_id=user.id,
        merchant_name="Seeded Merchant",
        storefront_slug="seeded-storefront",
        plan_code="starter",
    )

    assert result["merchant_account_id"] is not None
    assert result["tenant_id"] is not None

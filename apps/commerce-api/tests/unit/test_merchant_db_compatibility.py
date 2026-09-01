from uuid import uuid4

import pytest
from sqlalchemy import String

from app.contexts.identity.domain.entities import User
from app.contexts.merchant_management.application.services import MerchantService
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser, MerchantUserRole
from app.contexts.onboarding.application.services import OnboardingService


def test_merchant_status_and_role_columns_are_string_compatible():
    assert isinstance(MerchantAccount.__table__.c.status.type, String)
    assert isinstance(MerchantAccountUser.__table__.c.role.type, String)


@pytest.mark.asyncio
async def test_get_merchant_for_user_chooses_latest_owner_account(db_session):
    user_id = uuid4()
    older = MerchantAccount(name="Older Merchant", status="active")
    newer = MerchantAccount(name="Newer Merchant", status="active")
    db_session.add_all([older, newer])
    await db_session.flush()

    db_session.add_all(
        [
            MerchantAccountUser(
                merchant_account_id=older.id,
                user_id=user_id,
                role=MerchantUserRole.OWNER.value,
            ),
            MerchantAccountUser(
                merchant_account_id=newer.id,
                user_id=user_id,
                role=MerchantUserRole.OWNER.value,
            ),
        ]
    )
    await db_session.commit()

    service = MerchantService(db_session)
    merchant = await service.get_merchant_for_user(user_id)

    assert merchant is not None
    assert merchant.id == newer.id


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

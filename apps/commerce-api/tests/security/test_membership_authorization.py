"""Security: membership-based authorization for storefront access."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.auth.jwt_handler import create_global_access_token, create_tenant_access_token


@pytest.mark.asyncio
async def test_storefront_get_requires_membership(client: AsyncClient, db_session):
    from app.contexts.identity.domain.entities import User
    from app.contexts.onboarding.application.services import OnboardingService

    owner = User(email="owner@store.com", password_hash="hash")
    outsider = User(email="outsider@store.com", password_hash="hash")
    db_session.add_all([owner, outsider])
    await db_session.flush()

    onboarding = OnboardingService(db_session)
    result = await onboarding.onboard_merchant(
        user_id=owner.id,
        merchant_name="Store Owner",
        storefront_slug="member-store",
        plan_code="starter",
    )

    outsider_token = create_global_access_token(user_id=outsider.id, email=outsider.email)
    response = await client.get(
        f"/api/v1/storefronts/{result['tenant_id']}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_staff_invite_requires_tenant_token_with_verified_membership(client: AsyncClient, db_session):
    from app.contexts.identity.domain.entities import User
    from app.contexts.onboarding.application.services import OnboardingService

    owner = User(email="staff-owner@store.com", password_hash="hash")
    db_session.add(owner)
    await db_session.flush()

    onboarding = OnboardingService(db_session)
    result = await onboarding.onboard_merchant(
        user_id=owner.id,
        merchant_name="Staff Store",
        storefront_slug="staff-store",
        plan_code="business",
    )

    global_token = create_global_access_token(user_id=owner.id, email=owner.email)
    response = await client.post(
        f"/api/v1/tenants/{result['tenant_id']}/members",
        headers={"Authorization": f"Bearer {global_token}"},
        json={"email": "newstaff@store.com", "role": "STAFF"},
    )
    assert response.status_code == 401

    forged_token = create_tenant_access_token(
        user_id=owner.id,
        tenant_id=result["tenant_id"],
        membership_id=uuid4(),
        role="OWNER",
    )
    response = await client.post(
        f"/api/v1/tenants/{result['tenant_id']}/members",
        headers={"Authorization": f"Bearer {forged_token}"},
        json={"email": "newstaff@store.com", "role": "STAFF"},
    )
    assert response.status_code == 403

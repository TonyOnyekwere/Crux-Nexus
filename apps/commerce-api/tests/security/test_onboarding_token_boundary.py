"""Security: onboarding requires global merchant token."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.auth.jwt_handler import create_global_access_token, create_tenant_access_token


@pytest.mark.asyncio
async def test_onboarding_rejects_tenant_access_token(client: AsyncClient, db_session):
    from app.contexts.identity.domain.entities import User
    from app.contexts.onboarding.application.services import OnboardingService

    user = User(email="onboard-boundary@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    onboarding = OnboardingService(db_session)
    result = await onboarding.onboard_merchant(
        user_id=user.id,
        merchant_name="First Merchant",
        storefront_slug=f"first-{uuid4()}",
        plan_code="starter",
    )

    tenant_token = create_tenant_access_token(
        user_id=user.id,
        tenant_id=result["tenant_id"],
        membership_id=result["membership_id"],
        role="OWNER",
    )

    response = await client.post(
        "/api/v1/onboarding/merchant",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "merchant_name": "Second Merchant",
            "storefront_slug": f"second-{uuid4()}",
            "plan": "starter",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_onboarding_accepts_global_token(client: AsyncClient, db_session):
    from app.contexts.identity.application.services import IdentityService

    service = IdentityService(db_session)
    user = await service.create_user(
        email=f"global-onboard-{uuid4()}@example.com",
        password="securepassword123",
    )
    await db_session.commit()

    global_token = create_global_access_token(user_id=user.id, email=user.email)
    response = await client.post(
        "/api/v1/onboarding/merchant",
        headers={"Authorization": f"Bearer {global_token}"},
        json={
            "merchant_name": "Global Merchant",
            "storefront_slug": f"global-{uuid4()}",
            "plan": "starter",
        },
    )
    assert response.status_code == 201

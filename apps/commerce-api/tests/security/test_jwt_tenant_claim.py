"""Security: JWT tenant claims must not bypass membership verification."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.jwt_handler import create_global_access_token, create_tenant_access_token, decode_access_token


def test_global_token_has_no_tenant_claim():
    user_id = uuid4()
    token = create_global_access_token(user_id=user_id, email="user@example.com")
    payload = decode_access_token(token)
    assert payload.get("token_type") == "access"
    assert "tenant_id" not in payload


def test_tenant_token_requires_membership_claims():
    user_id = uuid4()
    tenant_id = uuid4()
    membership_id = uuid4()
    token = create_tenant_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        membership_id=membership_id,
        role="OWNER",
    )
    payload = decode_access_token(token)
    assert payload["token_type"] == "tenant_access"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["membership_id"] == str(membership_id)


@pytest.mark.asyncio
async def test_tenant_context_rejects_forged_membership_id(db_session):
    from app.auth.tenant_context import TenantAuthorizationError, TenantContextResolution
    from app.contexts.identity.domain.entities import User
    from app.contexts.onboarding.application.services import OnboardingService

    user = User(email="jwt-test@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    service = OnboardingService(db_session)
    result = await service.onboard_merchant(
        user_id=user.id,
        merchant_name="JWT Test Merchant",
        storefront_slug="jwt-test-store",
        plan_code="starter",
    )

    resolver = TenantContextResolution(db_session)
    with pytest.raises(TenantAuthorizationError, match="membership"):
        await resolver.resolve_tenant_context_from_jwt(
            user_id=user.id,
            tenant_id=result["tenant_id"],
            membership_id=uuid4(),
        )

"""Integration: auth and identity flow against current architecture."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration_rejects_tenant_id(client: AsyncClient):
    response = await client.post(
        "/api/v1/identity/users",
        json={
            "email": "noid@example.com",
            "password": "securepassword123",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_global_token_without_tenant(client: AsyncClient, db_session):
    from app.contexts.identity.application.services import IdentityService

    service = IdentityService(db_session)
    await service.create_user(email="login@example.com", password="securepassword123")
    await db_session.commit()

    response = await client.post(
        "/api/v1/identity/login",
        json={"email": "login@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "tenant_id" not in data


@pytest.mark.asyncio
async def test_onboarding_and_switch_tenant_flow(client: AsyncClient, db_session):
    from app.contexts.identity.application.services import IdentityService

    service = IdentityService(db_session)
    user = await service.create_user(email="flow@example.com", password="securepassword123")
    await db_session.commit()

    login = await client.post(
        "/api/v1/identity/login",
        json={"email": "flow@example.com", "password": "securepassword123"},
    )
    token = login.json()["data"]["access_token"]

    onboard = await client.post(
        "/api/v1/onboarding/merchant",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "merchant_name": "Flow Merchant",
            "storefront_slug": "flow-store",
            "plan": "starter",
        },
    )
    assert onboard.status_code == 201
    tenant_id = onboard.json()["data"]["tenant_id"]

    switch = await client.post(
        "/api/v1/identity/switch-tenant",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": tenant_id},
    )
    assert switch.status_code == 200
    tenant_token = switch.json()["data"]["access_token"]

    storefront = await client.get(
        f"/api/v1/merchant/storefronts/{tenant_id}",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert storefront.status_code == 200

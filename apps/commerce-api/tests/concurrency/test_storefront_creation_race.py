"""Concurrency tests using independent database sessions."""

import asyncio
from uuid import uuid4

import pytest

from app.contexts.identity.domain.entities import User
from app.contexts.onboarding.application.services import OnboardingService
from app.contexts.tenant_management.application.services import TenantService
from app.database.session import AsyncSessionLocal
from app.exceptions import CapacityExceeded


@pytest.mark.asyncio
async def test_concurrent_storefront_creation_with_independent_sessions():
    """Prove PostgreSQL row locks serialize capacity checks across connections."""
    async with AsyncSessionLocal() as setup_session:
        user = User(email=f"race-{uuid4()}@example.com", password_hash="hash")
        setup_session.add(user)
        await setup_session.flush()

        onboarding = OnboardingService(setup_session)
        result = await onboarding.onboard_merchant(
            user_id=user.id,
            merchant_name="Race Merchant",
            storefront_slug=f"race-{uuid4()}",
            plan_code="starter",
        )
        merchant_id = result["merchant_account_id"]
        owner_user_id = user.id

    async def attempt(slug: str):
        async with AsyncSessionLocal() as session:
            service = TenantService(session)
            try:
                tenant = await service.create_storefront(
                    merchant_account_id=merchant_id,
                    owner_user_id=owner_user_id,
                    slug=slug,
                )
                await session.commit()
                return tenant
            except CapacityExceeded:
                await session.rollback()
                return None
            except Exception:
                await session.rollback()
                raise

    results = await asyncio.gather(
        attempt(f"extra-a-{uuid4()}"),
        attempt(f"extra-b-{uuid4()}"),
        attempt(f"extra-c-{uuid4()}"),
        attempt(f"extra-d-{uuid4()}"),
    )
    successes = [r for r in results if r is not None]
    assert len(successes) == 0

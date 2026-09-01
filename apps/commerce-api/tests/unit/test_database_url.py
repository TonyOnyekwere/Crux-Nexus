import pytest

from app.database.url import normalize_async_database_url


@pytest.mark.parametrize(
    ("input_url", "expected_url"),
    [
        (
            "postgresql://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        (
            "postgres://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        (
            "postgresql+asyncpg://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
    ],
)
def test_normalize_async_database_url(
    input_url: str,
    expected_url: str,
):
    assert normalize_async_database_url(input_url) == expected_url


def test_invalid_database_scheme_rejected():
    with pytest.raises(ValueError):
        normalize_async_database_url(
            "mysql://user:pass@host/db"
        )


@pytest.mark.asyncio
async def test_create_storefront_uses_existing_transaction(db_session, monkeypatch):
    from app.contexts.tenant_management.application.services import TenantService
    from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
    from app.contexts.merchant_management.application.capacity import CapacityService

    async def fake_create_storefront_with_capacity_check(
        *,
        merchant_account_id,
        owner_user_id,
        slug,
    ):
        return Tenant(slug=slug, status=TenantStatus.PROVISIONING)

    monkeypatch.setattr(
        CapacityService,
        "create_storefront_with_capacity_check",
        fake_create_storefront_with_capacity_check,
    )

    async with db_session.begin():
        service = TenantService(db_session)

        tenant = await service.create_storefront(
            merchant_account_id=__import__("uuid").uuid4(),
            owner_user_id=__import__("uuid").uuid4(),
            slug="demo-storefront",
        )

        assert tenant.slug == "demo-storefront"
        assert tenant.status == TenantStatus.PROVISIONING

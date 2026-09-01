"""Merchant ownership constraint verification."""

from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant


def test_merchant_account_tenant_has_unique_tenant_id_column():
    tenant_id_col = MerchantAccountTenant.__table__.c.tenant_id
    assert tenant_id_col.unique is True

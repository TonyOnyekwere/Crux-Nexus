from sqlalchemy import String

from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser


def test_merchant_status_and_role_columns_are_string_compatible():
    assert isinstance(MerchantAccount.__table__.c.status.type, String)
    assert isinstance(MerchantAccountUser.__table__.c.role.type, String)

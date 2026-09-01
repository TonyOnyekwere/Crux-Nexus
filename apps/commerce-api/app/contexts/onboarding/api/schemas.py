from uuid import UUID
from pydantic import BaseModel


class MerchantOnboardingRequest(BaseModel):
    merchant_name: str
    storefront_slug: str
    plan: str  # STARTER, BUSINESS, ENTERPRISE


class MerchantOnboardingResponse(BaseModel):
    merchant_account_id: UUID
    tenant_id: UUID
    subscription_id: UUID
    membership_id: UUID
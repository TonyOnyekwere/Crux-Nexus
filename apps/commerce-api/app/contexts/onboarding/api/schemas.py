from pydantic import BaseModel, Field


class MerchantOnboardingRequest(BaseModel):
    merchant_name: str = Field(..., min_length=2, max_length=150)
    store_slug: str = Field(..., min_length=3, max_length=50, pattern="^[a-z0-9-]+$")
    plan: str = Field(..., description="STARTER, BUSINESS, or ENTERPRISE")


class MerchantOnboardingResponse(BaseModel):
    merchant_account_id: str
    tenant_id: str
    slug: str

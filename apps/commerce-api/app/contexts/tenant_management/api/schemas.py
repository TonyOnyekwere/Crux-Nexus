from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.contexts.tenant_management.domain.entities import TenantStatus
from app.contexts.tenant_management.domain.membership import TenantRole
from uuid import UUID
from datetime import datetime


class StorefrontCreate(BaseModel):
    slug: str = Field(..., min_length=3, max_length=50, pattern="^[a-z0-9-]+$")


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime


class TenantStatusUpdate(BaseModel):
    status: TenantStatus


class StaffInviteRequest(BaseModel):
    email: EmailStr
    role: TenantRole = TenantRole.STAFF

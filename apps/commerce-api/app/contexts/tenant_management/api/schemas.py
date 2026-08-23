from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from app.contexts.tenant_management.domain.entities import TenantStatus


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=3, max_length=50, pattern="^[a-z0-9-]+$")


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantStatusUpdate(BaseModel):
    status: TenantStatus
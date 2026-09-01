from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from app.contexts.identity.domain.entities import AuthProvider, UserStatus
from app.contexts.tenant_management.domain.membership import TenantRole


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str | None = None
    auth_provider: AuthProvider = AuthProvider.PASSWORD

    @model_validator(mode="after")
    def validate_authentication(self):
        if self.auth_provider == AuthProvider.PASSWORD and not self.password:
            raise ValueError(
                "Password is required for password authentication"
            )

        if (
            self.auth_provider != AuthProvider.PASSWORD
            and self.password is not None
        ):
            raise ValueError(
                "Password must not be provided for OAuth authentication"
            )

        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    auth_provider: AuthProvider
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SwitchTenantRequest(BaseModel):
    tenant_id: UUID


class TenantAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: UUID
    role: TenantRole


class StorefrontSummary(BaseModel):
    tenant_id: UUID
    slug: str
    role: TenantRole

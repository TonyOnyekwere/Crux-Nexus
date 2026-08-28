from pydantic import BaseModel, EmailStr, model_validator
from uuid import UUID
from datetime import datetime
from app.contexts.identity.domain.entities import UserStatus, AuthProvider


class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = None
    auth_provider: AuthProvider = AuthProvider.PASSWORD
    tenant_id: UUID | None = None

    @model_validator(mode="after")
    def validate_authentication(self):
        if self.auth_provider == AuthProvider.PASSWORD and not self.password:
            raise ValueError("Password is required for password authentication")

        if self.auth_provider != AuthProvider.PASSWORD and self.password:
            raise ValueError("Password must not be provided for OAuth authentication")

        return self


class UserResponse(BaseModel):
    id: UUID
    email: str
    auth_provider: AuthProvider
    status: UserStatus
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
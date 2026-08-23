from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from app.contexts.identity.domain.entities import UserStatus, AuthProvider


class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = None
    auth_provider: AuthProvider = AuthProvider.PASSWORD
    tenant_id: UUID | None = None


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
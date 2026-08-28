from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings
from uuid import UUID

settings = get_settings()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UUID:
    """Extract and return the current user ID from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return UUID(user_id)


async def get_current_tenant_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[UUID]:
    """Extract and return the current tenant ID from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    tenant_id: Optional[str] = payload.get("tenant_id")
    if tenant_id:
        return UUID(tenant_id)
    return None


async def get_optional_current_tenant_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[UUID]:
    """Extract a tenant claim when a valid bearer token is provided."""
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    tenant_id: Optional[str] = payload.get("tenant_id")
    if tenant_id:
        return UUID(tenant_id)
    return None
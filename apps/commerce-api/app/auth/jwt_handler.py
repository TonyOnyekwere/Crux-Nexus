from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.kernel.errors.responses import error_response

settings = get_settings()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

MERCHANT_AUDIENCE = "merchant"
GLOBAL_TOKEN_TYPE = "access"
TENANT_TOKEN_TYPE = "tenant_access"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_global_access_token(*, user_id: UUID, email: str) -> str:
    return create_access_token(
        {
            "sub": str(user_id),
            "email": email,
            "aud": MERCHANT_AUDIENCE,
            "token_type": GLOBAL_TOKEN_TYPE,
        }
    )


def create_tenant_access_token(
    *,
    user_id: UUID,
    tenant_id: UUID,
    membership_id: UUID,
    role: str,
) -> str:
    return create_access_token(
        {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "membership_id": str(membership_id),
            "role": role,
            "aud": MERCHANT_AUDIENCE,
            "token_type": TENANT_TOKEN_TYPE,
        }
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=MERCHANT_AUDIENCE,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    return decode_access_token(credentials.credentials)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_merchant_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    payload = decode_access_token(credentials.credentials)

    if payload.get("token_type") != GLOBAL_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Merchant-scoped access token required for this operation",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return {
            "user_id": UUID(payload["sub"]),
            "email": payload.get("email"),
            "token_type": payload["token_type"],
        }
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid merchant token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    payload = decode_access_token(credentials.credentials)

    if payload.get("token_type") != TENANT_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant-scoped token required for this operation",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify tenant token claims against active membership in the database."""
    from app.auth.tenant_context import TenantAuthorizationError, TenantContextResolution

    payload = decode_access_token(credentials.credentials)

    if payload.get("token_type") != TENANT_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant-scoped token required for this operation",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        resolver = TenantContextResolution(db)
        return await resolver.resolve_tenant_context_from_jwt(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            membership_id=UUID(payload["membership_id"]),
        )
    except TenantAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(code="TENANT_ACCESS_DENIED", message=str(exc)),
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_verified_tenant_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify membership and bind PostgreSQL tenant context for RLS-protected operations."""
    from app.auth.tenant_context import TenantAuthorizationError, TenantContextResolution

    payload = decode_access_token(credentials.credentials)

    if payload.get("token_type") != TENANT_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant-scoped token required for this operation",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        resolver = TenantContextResolution(db)
        return await resolver.resolve_and_set_tenant_context(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            membership_id=UUID(payload["membership_id"]),
        )
    except TenantAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(code="TENANT_ACCESS_DENIED", message=str(exc)),
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

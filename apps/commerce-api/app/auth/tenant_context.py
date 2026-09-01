from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.identity.domain.entities import User
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import MembershipStatus, TenantMembership


class AuthorizationError(Exception):
    """Raised when tenant context cannot be verified."""
    pass


class TenantContextResolution:
    """
    Single authority for tenant context resolution with full membership verification.

    This implements the security model:
    JWT → user → membership → tenant → permission → RLS context

    NOT: frontend tenant_id → RLS context
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_tenant_context_from_jwt(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Verify tenant context from JWT claims before setting PostgreSQL RLS state."""
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise AuthorizationError("User not found")

        tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise AuthorizationError("Tenant not found")

        if tenant.status == TenantStatus.ARCHIVED:
            raise AuthorizationError("Tenant is archived and no longer accessible")

        membership_result = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if not membership:
            raise AuthorizationError("No active membership for this tenant")
        if getattr(membership, "status", None) != MembershipStatus.ACTIVE.value:
            raise AuthorizationError("Membership is not active for this tenant")

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "membership_id": membership.id,
            "role": membership.role,
            "tenant_status": tenant.status,
        }

    async def set_postgres_rls_context(
        self,
        tenant_id: UUID,
    ) -> None:
        """Set PostgreSQL RLS context only after membership verification succeeds."""
        await self.db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )

    async def resolve_and_set_tenant_context(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Complete the verified tenant resolution and RLS chain."""
        context = await self.resolve_tenant_context_from_jwt(user_id, tenant_id)
        await self.set_postgres_rls_context(tenant_id)
        return context


class TenantContext:
    """Tenant context containing tenant ID and resolution method."""

    def __init__(self, tenant_id: UUID, resolution_method: str):
        self.tenant_id = tenant_id
        self.resolution_method = resolution_method


async def resolve_tenant_from_jwt(request: Request) -> Optional[TenantContext]:
    """Resolve tenant from JWT claim. Invalid bearer tokens fail closed."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    try:
        from app.auth.jwt_handler import decode_access_token

        token = authorization.split(" ", 1)[1]
        payload = decode_access_token(token)
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant claim missing from token",
            )
        return TenantContext(tenant_id=UUID(tenant_id), resolution_method="jwt")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate tenant credentials",
        )


async def resolve_tenant_from_subdomain(request: Request, db: AsyncSession) -> Optional[TenantContext]:
    """Resolve tenant from subdomain only for unauthenticated requests."""
    host = request.headers.get("host", "")
    if "." not in host:
        return None

    subdomain = host.split(".")[0]
    if subdomain and subdomain not in {"www", "api"}:
        result = await db.execute(
            text("SELECT id FROM tenants WHERE slug = :slug AND status = 'active'"),
            {"slug": subdomain},
        )
        tenant_row = result.fetchone()
        if tenant_row:
            return TenantContext(tenant_id=UUID(tenant_row[0]), resolution_method="subdomain")
    return None


async def get_tenant_context(
    request: Request,
    db: AsyncSession = None,
) -> Optional[TenantContext]:
    """Resolve tenant from request using authorized methods only."""
    authorization = request.headers.get("Authorization")

    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )

        try:
            tenant_context = await resolve_tenant_from_jwt(request)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate tenant credentials",
            )

        if tenant_context:
            return tenant_context

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or incomplete tenant token",
        )

    if db is None:
        return None

    return await resolve_tenant_from_subdomain(request, db)


async def require_tenant_context(
    tenant_context: Optional[TenantContext] = None,
) -> TenantContext:
    """Dependency that requires a tenant context to be present."""
    if tenant_context is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve tenant context",
        )
    return tenant_context


async def get_verified_tenant_context(
    request: Request,
    db: AsyncSession = None,
) -> dict:
    """Resolve and verify tenant context with full membership validation."""
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
        )

    try:
        from app.auth.jwt_handler import decode_access_token

        token = authorization.split(" ", 1)[1]
        payload = decode_access_token(token)

        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")

        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
            )

        resolver = TenantContextResolution(db)
        context = await resolver.resolve_and_set_tenant_context(
            user_id=UUID(user_id),
            tenant_id=UUID(tenant_id),
        )
        return context
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "TENANT_ACCESS_DENIED",
                    "message": str(e),
                    "details": {},
                }
            },
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify tenant context",
        )
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.identity.domain.entities import User
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import MembershipStatus, TenantMembership


class TenantAuthorizationError(Exception):
    """Raised when tenant context cannot be verified."""


class TenantContextResolution:
    """
    Single authority for tenant context resolution with full membership verification.

    Security model:
    JWT → user → membership → tenant → permission → RLS context
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_tenant_context_from_jwt(
        self,
        user_id: UUID,
        tenant_id: UUID,
        membership_id: UUID | None = None,
    ) -> dict:
        """Verify tenant context from JWT claims before setting PostgreSQL RLS state."""
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise TenantAuthorizationError("User not found")

        tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise TenantAuthorizationError("Tenant not found")

        if tenant.status == TenantStatus.ARCHIVED:
            raise TenantAuthorizationError("Tenant is archived and no longer accessible")

        membership_result = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if not membership:
            raise TenantAuthorizationError("No active membership for this tenant")
        if getattr(membership, "status", None) != MembershipStatus.ACTIVE.value:
            raise TenantAuthorizationError("Membership is not active for this tenant")

        if membership_id is not None and membership.id != membership_id:
            raise TenantAuthorizationError("Token membership does not match active membership")

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "membership_id": membership.id,
            "role": membership.role,
            "tenant_status": tenant.status,
        }

    async def set_postgres_rls_context(self, tenant_id: UUID) -> None:
        await self.db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

    async def resolve_and_set_tenant_context(
        self,
        user_id: UUID,
        tenant_id: UUID,
        membership_id: UUID | None = None,
    ) -> dict:
        context = await self.resolve_tenant_context_from_jwt(
            user_id=user_id,
            tenant_id=tenant_id,
            membership_id=membership_id,
        )
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
            return None
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
    db: AsyncSession | None = None,
) -> Optional[TenantContext]:
    """
    Middleware-only hint for unauthenticated storefront subdomain resolution.

    JWT tenant authority is NEVER established here. Route dependencies such as
    get_current_tenant_context() perform membership-verified authorization.
    """
    if request.headers.get("Authorization"):
        return None

    if db is None:
        return None

    return await resolve_tenant_from_subdomain(request, db)


async def require_tenant_context(
    tenant_context: Optional[TenantContext] = None,
) -> TenantContext:
    if tenant_context is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve tenant context",
        )
    return tenant_context

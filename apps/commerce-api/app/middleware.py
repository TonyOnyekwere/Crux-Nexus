from fastapi import Request, HTTPException, status, Depends
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db


class TenantContext:
    """Tenant context containing tenant ID and resolution method."""
    def __init__(self, tenant_id: UUID, resolution_method: str):
        self.tenant_id = tenant_id
        self.resolution_method = resolution_method  # 'jwt', 'subdomain', 'header', 'service'


async def resolve_tenant_from_jwt(request: Request) -> Optional[TenantContext]:
    """Resolve tenant from JWT claim (preferred path, zero DB lookup)."""
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        try:
            from app.auth.jwt_handler import decode_access_token
            token = authorization.split(" ")[1]
            payload = decode_access_token(token)
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                return TenantContext(tenant_id=UUID(tenant_id), resolution_method="jwt")
        except Exception:
            # JWT parsing failed - no tenant context from JWT
            pass
    return None


async def resolve_tenant_from_header(request: Request) -> Optional[TenantContext]:
    """Resolve tenant from explicit header (internal service-to-service)."""
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header:
        try:
            return TenantContext(tenant_id=UUID(tenant_header), resolution_method="header")
        except ValueError:
            pass
    return None


async def resolve_tenant_from_subdomain(request: Request, db: AsyncSession) -> Optional[TenantContext]:
    """Resolve tenant from subdomain (storefront, unauthenticated) - requires DB lookup."""
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        if subdomain and subdomain != "www" and subdomain != "api":
            # TODO: Implement Redis cache lookup for slug -> tenant_id
            result = await db.execute(
                text("SELECT id FROM tenants WHERE slug = :slug AND status = 'active'"),
                {"slug": subdomain}
            )
            tenant_row = result.fetchone()
            if tenant_row:
                return TenantContext(tenant_id=UUID(tenant_row[0]), resolution_method="subdomain")
    return None


async def get_tenant_context(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[TenantContext]:
    """
    Resolve tenant from request using multiple methods in priority order:
    1. JWT claim (preferred path, zero DB lookup)
    2. Subdomain (storefront, unauthenticated) - with Redis cache
    3. Explicit header (internal service-to-service ONLY)
    
    SECURITY MODEL:
    - JWT tenant membership is authoritative for authenticated users
    - X-Tenant-ID header cannot override JWT tenant membership
    - Arbitrary header claims cannot grant tenant access
    - For authenticated requests: JWT tenant > header tenant
    """
    # Try JWT first (authoritative for authenticated users)
    tenant_context = await resolve_tenant_from_jwt(request)
    if tenant_context:
        # JWT established tenant context - this is authoritative
        # If X-Tenant-ID header exists and differs, reject as potential spoofing
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                header_tenant_id = UUID(tenant_header)
                if header_tenant_id != tenant_context.tenant_id:
                    # Attempted tenant context override - security risk
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Tenant context mismatch: JWT and header tenant IDs differ"
                    )
            except ValueError:
                # Invalid UUID in header - ignore but don't allow override
                pass
        return tenant_context
    
    # If JWT exists but has no tenant_id, don't allow header override
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        try:
            from app.auth.jwt_handler import decode_access_token
            token = authorization.split(" ")[1]
            payload = decode_access_token(token)
            if "tenant_id" in payload and not payload.get("tenant_id"):
                # JWT says user exists but has no tenant assignment
                # Don't allow header to fabricate tenant context
                return None
        except Exception:
            # Invalid JWT - don't allow header-based tenant context
            return None
    
    # Try header (internal service-to-service ONLY)
    # This should only be used for unauthenticated internal service calls
    tenant_context = await resolve_tenant_from_header(request)
    if tenant_context:
        return tenant_context
    
    # Try subdomain (requires DB lookup)
    tenant_context = await resolve_tenant_from_subdomain(request, db)
    if tenant_context:
        return tenant_context
    
    # No tenant resolved - this is okay for public endpoints
    return None


async def require_tenant_context(
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context)
) -> TenantContext:
    """Dependency that requires a tenant context to be present."""
    if tenant_context is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve tenant context"
        )
    return tenant_context
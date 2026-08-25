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
        self.resolution_method = resolution_method  # 'jwt', 'subdomain'


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
        except Exception as e:
            # Distinguish JWT errors (CRX-P0-ENG-004 P1)
            # For now, log and return None, but should distinguish:
            # - Invalid token
            # - Expired token  
            # - Malformed token
            # - Missing tenant claim
            # - Unexpected infrastructure error
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
    Resolve tenant from request using authorized methods only:
    1. JWT claim (preferred path, zero DB lookup)
    2. Subdomain (storefront, unauthenticated) - with Redis cache
    
    SECURITY MODEL (CRX-P0-006):
    - Only JWT claims and subdomain resolution establish tenant context
    - Header-based tenant resolution is completely disabled
    - No X-Tenant-ID header processing for public API requests
    - Service-to-service tenant propagation requires mTLS or signed service identity (future)
    """
    # Try JWT first (authoritative for authenticated users)
    tenant_context = await resolve_tenant_from_jwt(request)
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
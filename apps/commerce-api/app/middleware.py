"""Backward-compatible re-exports. Use app.auth.tenant_context directly."""

from app.auth.jwt_handler import get_verified_tenant_context
from app.auth.tenant_context import (
    TenantAuthorizationError,
    TenantContext,
    TenantContextResolution,
    get_tenant_context,
    require_tenant_context,
    resolve_tenant_from_jwt,
    resolve_tenant_from_subdomain,
)

__all__ = [
    "TenantAuthorizationError",
    "TenantContext",
    "TenantContextResolution",
    "get_tenant_context",
    "get_verified_tenant_context",
    "require_tenant_context",
    "resolve_tenant_from_jwt",
    "resolve_tenant_from_subdomain",
]

"""Canonical merchant-facing API routes."""

from app.contexts.identity.api.routes import list_accessible_storefronts
from app.contexts.tenant_management.api.routes import create_storefront, get_storefront
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant"])

router.add_api_route(
    "/storefronts",
    create_storefront,
    methods=["POST"],
    name="merchant_create_storefront",
)
router.add_api_route(
    "/storefronts",
    list_accessible_storefronts,
    methods=["GET"],
    name="merchant_list_storefronts",
)
router.add_api_route(
    "/storefronts/{tenant_id}",
    get_storefront,
    methods=["GET"],
    name="merchant_get_storefront",
)

__all__ = ["router"]

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import Permission, has_permission
from app.auth.jwt_handler import get_current_tenant_context, get_current_user_id
from app.contexts.identity.application.services import IdentityService
from app.contexts.merchant_management.application.services import MerchantService
from app.contexts.tenant_management.application.services import TenantService
from app.database import get_db
from app.exceptions import CapacityExceeded, CruxNexusError

from .schemas import (
    StaffInviteRequest,
    StorefrontCreate,
    TenantResponse,
    TenantStatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["storefronts"])


@router.post("/storefronts", status_code=status.HTTP_201_CREATED)
async def create_storefront(
    payload: StorefrontCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    merchant_service = MerchantService(db)
    merchant_account_id = await merchant_service.get_merchant_account_id_for_user(
        user_id
    )
    if merchant_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MERCHANT_REQUIRED",
                    "message": "No merchant account found for this user.",
                    "details": {},
                }
            },
        )

    try:
        service = TenantService(db)
        tenant = await service.create_storefront(
            merchant_account_id=merchant_account_id,
            owner_user_id=user_id,
            slug=payload.slug,
        )
        return {"data": TenantResponse.model_validate(tenant).model_dump()}
    except CapacityExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        )
    except IntegrityError:
        await db.rollback()
        logger.exception("Database integrity error while creating storefront")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "STOREFRONT_CONFLICT",
                    "message": "Storefront could not be created because of a data conflict.",
                    "details": {},
                }
            },
        )


@router.get("/storefronts/{tenant_id}")
async def get_storefront(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    service = TenantService(db)
    membership = await service.user_has_membership(user_id, tenant_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEMBERSHIP_REQUIRED",
                    "message": "Not authorized to access this storefront.",
                    "details": {},
                }
            },
        )

    tenant = await service.get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "TENANT_NOT_FOUND",
                    "message": "Storefront not found.",
                    "details": {},
                }
            },
        )

    return {"data": TenantResponse.model_validate(tenant).model_dump()}


@router.post("/tenants/{tenant_id}/members", status_code=status.HTTP_201_CREATED)
async def invite_staff_member(
    tenant_id: UUID,
    payload: StaffInviteRequest,
    db: AsyncSession = Depends(get_db),
    tenant_context: dict = Depends(get_current_tenant_context),
):
    if tenant_context["tenant_id"] != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "TENANT_MISMATCH",
                    "message": "Token tenant does not match requested storefront.",
                    "details": {},
                }
            },
        )

    from app.contexts.tenant_management.domain.membership import TenantRole

    inviter_role = TenantRole(tenant_context["role"])
    if not has_permission(inviter_role, Permission.MANAGE_STAFF):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only owners can invite staff.",
                    "details": {},
                }
            },
        )

    merchant_service = MerchantService(db)
    merchant_account_id = await merchant_service.get_merchant_account_id_for_user(
        tenant_context["user_id"]
    )
    if merchant_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MERCHANT_REQUIRED",
                    "message": "No merchant account found for this user.",
                    "details": {},
                }
            },
        )

    identity_service = IdentityService(db)
    invitee = await identity_service.get_user_by_email(payload.email)
    if invitee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "Invitee must register before being added.",
                    "details": {},
                }
            },
        )

    try:
        service = TenantService(db)
        membership = await service.add_staff_member(
            merchant_account_id=merchant_account_id,
            tenant_id=tenant_id,
            user_id=invitee.id,
            role=payload.role,
        )
        return {
            "data": {
                "membership_id": str(membership.id),
                "user_id": str(invitee.id),
                "tenant_id": str(tenant_id),
                "role": membership.role.value,
            }
        }
    except CapacityExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        )


@router.patch("/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: UUID,
    status_update: TenantStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user_id: UUID = Depends(get_current_user_id),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "PLATFORM_ADMIN_REQUIRED",
                "message": "Tenant lifecycle changes require platform authorization.",
                "details": {},
            }
        },
    )

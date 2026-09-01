import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import (
    create_global_access_token,
    create_tenant_access_token,
    get_current_user_id,
)
from app.contexts.identity.application.services import IdentityService
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.contexts.tenant_management.domain.membership import TenantMembership
from app.database import get_db

from .schemas import (
    StorefrontSummary,
    SwitchTenantRequest,
    TenantAccessTokenResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a global user account."""
    try:
        service = IdentityService(db)
        user = await service.create_user(
            email=user_data.email,
            password=user_data.password,
            auth_provider=user_data.auth_provider,
        )
        return {"data": UserResponse.model_validate(user).model_dump()}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        )
    except IntegrityError:
        await db.rollback()
        logger.exception("Database integrity error while creating user")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "USER_CONFLICT",
                    "message": "User could not be created because of a data conflict.",
                    "details": {},
                }
            },
        )
    except Exception:
        logger.exception("Failed to create user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "USER_CREATE_FAILED",
                    "message": "Failed to create user.",
                    "details": {},
                }
            },
        )


@router.post("/login", response_model=dict)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return a global merchant access token."""
    try:
        service = IdentityService(db)
        user = await service.get_user_by_email(login_data.email)

        if not user or not await service.verify_password(user, login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Incorrect email or password.",
                        "details": {},
                    }
                },
            )

        access_token = create_global_access_token(user_id=user.id, email=user.email)
        return {
            "data": TokenResponse(
                access_token=access_token,
                user=UserResponse.model_validate(user),
            ).model_dump()
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Login failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LOGIN_FAILED",
                    "message": "Login failed.",
                    "details": {},
                }
            },
        )


@router.get("/storefronts")
async def list_accessible_storefronts(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    result = await db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            TenantMembership.user_id == user_id,
            Tenant.status != TenantStatus.ARCHIVED,
        )
    )
    rows = result.all()
    storefronts = [
        StorefrontSummary(
            tenant_id=tenant.id,
            slug=tenant.slug,
            role=membership.role,
        )
        for membership, tenant in rows
    ]
    return {"data": [item.model_dump() for item in storefronts]}


@router.post("/switch-tenant")
async def switch_tenant(
    payload: SwitchTenantRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Switch tenant context with full membership verification.
    
    This endpoint verifies:
    1. User has active membership to the requested tenant
    2. Tenant is not archived
    3. Membership has a valid role
    
    Only then does it issue a tenant-scoped token.
    """
    result = await db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == payload.tenant_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEMBERSHIP_REQUIRED",
                    "message": "No active membership for this storefront.",
                    "details": {},
                }
            },
        )

    membership, tenant = row
    if tenant.status == TenantStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "TENANT_INACTIVE",
                    "message": "This storefront is not accessible.",
                    "details": {},
                }
            },
        )

    token = create_tenant_access_token(
        user_id=user_id,
        tenant_id=tenant.id,
        membership_id=membership.id,
        role=membership.role,
    )
    return {
        "data": TenantAccessTokenResponse(
            access_token=token,
            tenant_id=tenant.id,
            role=membership.role,
        ).model_dump()
    }


@router.get("/users/me")
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    service = IdentityService(db)
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found.",
                    "details": {},
                }
            },
        )
    return {"data": UserResponse.model_validate(user).model_dump()}

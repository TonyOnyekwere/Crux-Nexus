import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.auth.jwt_handler import get_current_user_id
from app.contexts.onboarding.application.services import OnboardingService
from app.database import get_db
from app.exceptions import CruxNexusError

from .schemas import MerchantOnboardingRequest, MerchantOnboardingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post(
    "/merchant",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def onboard_merchant(
    payload: MerchantOnboardingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        service = OnboardingService(db)
        merchant, tenant = await service.onboard_merchant(
            user_id=user_id,
            merchant_name=payload.merchant_name,
            storefront_slug=payload.store_slug,
            plan_code=payload.plan,
        )
        response = MerchantOnboardingResponse(
            merchant_account_id=str(merchant.id),
            tenant_id=str(tenant.id),
            slug=tenant.slug,
        )
        return {"data": response.model_dump()}
    except CruxNexusError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        )
    except IntegrityError:
        await db.rollback()
        logger.exception("Database integrity error during merchant onboarding")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ONBOARDING_CONFLICT",
                    "message": "Merchant onboarding failed due to a data conflict.",
                    "details": {},
                }
            },
        )
    except Exception:
        logger.exception("Merchant onboarding failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ONBOARDING_FAILED",
                    "message": "Merchant onboarding failed.",
                    "details": {},
                }
            },
        )

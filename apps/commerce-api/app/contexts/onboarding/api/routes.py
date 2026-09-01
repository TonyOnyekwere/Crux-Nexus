import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.auth.jwt_handler import get_current_user_id
from app.contexts.onboarding.application.services import OnboardingService
from .schemas import MerchantOnboardingRequest, MerchantOnboardingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/merchant", status_code=status.HTTP_201_CREATED)
async def onboard_merchant(
    onboarding_data: MerchantOnboardingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Complete merchant onboarding in one atomic transaction.
    
    Creates:
    - Merchant Account
    - Merchant Account User relationship
    - Subscription
    - Tenant (Storefront)
    - Merchant Account Tenant ownership
    - Tenant Membership (OWNER)
    
    This is the authoritative merchant bootstrap operation.
    """
    try:
        service = OnboardingService(db)
        result = await service.onboard_merchant(
            user_id=user_id,
            merchant_name=onboarding_data.merchant_name,
            storefront_slug=onboarding_data.storefront_slug,
            plan_code=onboarding_data.plan,
        )
        return {
            "data": MerchantOnboardingResponse(**result).model_dump()
        }
    except ValueError as e:
        await db.rollback()
        logger.exception("Merchant onboarding validation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "ONBOARDING_VALIDATION_ERROR",
                    "message": str(e),
                    "details": {}
                }
            }
        )
    except IntegrityError as e:
        await db.rollback()
        logger.exception("Merchant onboarding failed due to a database integrity conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ONBOARDING_CONFLICT",
                    "message": "Merchant onboarding conflicted with existing data; check uniqueness constraints.",
                    "details": {"database_error": str(e)}
                }
            }
        )
    except Exception:
        await db.rollback()
        logger.exception("Merchant onboarding failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ONBOARDING_FAILED",
                    "message": "Merchant onboarding failed",
                    "details": {}
                }
            }
        )
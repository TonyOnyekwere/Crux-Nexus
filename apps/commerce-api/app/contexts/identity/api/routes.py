import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from app.database import get_db
from app.contexts.identity.application.services import IdentityService
from .schemas import UserCreate, UserResponse, UserLogin, TokenResponse
from app.auth.jwt_handler import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    try:
        service = IdentityService(db)
        user = await service.create_user(
            email=user_data.email,
            password=user_data.password,
            auth_provider=user_data.auth_provider,
            tenant_id=user_data.tenant_id,
        )
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except IntegrityError:
        await db.rollback()
        logger.exception("Database integrity error while creating user")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User could not be created because of a data conflict",
        )
    except Exception:
        logger.exception("Failed to create user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    try:
        service = IdentityService(db)
        user = await service.get_user_by_email(login_data.email)
        
        if not user or not await service.verify_password(user, login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create access token
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }
        access_token = create_access_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Login failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get a user by ID."""
    try:
        service = IdentityService(db)
        user = await service.get_user_by_id(UUID(user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserResponse.model_validate(user)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve user")


@router.get("/users/email/{email}", response_model=UserResponse)
async def get_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    """Get a user by email address."""
    try:
        service = IdentityService(db)
        user = await service.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserResponse.model_validate(user)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve user by email")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve user")
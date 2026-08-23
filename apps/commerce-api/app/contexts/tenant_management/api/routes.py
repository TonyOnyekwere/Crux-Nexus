from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.contexts.tenant_management.application.services import TenantService
from .schemas import TenantCreate, TenantResponse, TenantStatusUpdate

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(tenant_data: TenantCreate, db: AsyncSession = Depends(get_db)):
    """Create a new tenant."""
    try:
        service = TenantService(db)
        tenant = await service.create_tenant(slug=tenant_data.slug)
        return TenantResponse.model_validate(tenant)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tenant")


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get a tenant by ID."""
    try:
        service = TenantService(db)
        tenant = await service.get_tenant_by_id(UUID(tenant_id))
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return TenantResponse.model_validate(tenant)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve tenant")


@router.get("/slug/{slug}", response_model=TenantResponse)
async def get_tenant_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a tenant by slug."""
    try:
        service = TenantService(db)
        tenant = await service.get_tenant_by_slug(slug)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return TenantResponse.model_validate(tenant)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve tenant")


@router.patch("/{tenant_id}/status", response_model=TenantResponse)
async def update_tenant_status(
    tenant_id: str, 
    status_update: TenantStatusUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update tenant status."""
    try:
        service = TenantService(db)
        tenant = await service.update_tenant_status(
            tenant_id=UUID(tenant_id), 
            new_status=status_update.status
        )
        return TenantResponse.model_validate(tenant)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update tenant status")
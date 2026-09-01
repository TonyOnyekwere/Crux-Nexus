from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import os
from app.config import get_settings
from app.contexts.identity.api.routes import router as identity_router
from app.contexts.tenant_management.api.routes import router as tenant_router
from app.contexts.onboarding.api.routes import router as onboarding_router
from app.middleware import get_tenant_context

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https://.*\.cruxnexus\.com"
)

# Include routers
app.include_router(identity_router)
app.include_router(tenant_router)
app.include_router(onboarding_router)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """
    Middleware to handle tenant context resolution using proper security functions.
    
    SECURITY MODEL:
    - Only JWT claims and subdomain resolution establish tenant context
    - Header-based tenant resolution is completely disabled
    - No X-Tenant-ID header processing for public API requests
    - Public routes (health, identity) may not have tenant context
    """
    from sqlalchemy.exc import ProgrammingError

    try:
        # Resolve tenant with a short-lived session before handing off the request.
        from app.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                tenant_context = await get_tenant_context(request, db)
        except ProgrammingError:
            # Database schema may not be ready (missing tenants table).
            # Treat as no tenant rather than failing the whole request.
            tenant_context = None

        request.state.tenant_context = tenant_context

        if tenant_context:
            request.state.current_tenant_id = str(tenant_context.tenant_id)

        return await call_next(request)
    except HTTPException:
        # Let HTTPException bubble up for proper error responses
        raise
    except Exception:
        # Other unexpected exceptions should result in 500 for observability
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during tenant resolution"
        )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check - verifies DB and Redis connectivity."""
    from app.database import engine
    from app.config import get_settings
    import redis.asyncio as redis
    
    settings = get_settings()
    checks = {"database": False, "redis": False}
    
    # Check database connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        # Log the exception server-side, don't expose details to client
        checks["database"] = False
    
    # Check Redis connectivity
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception:
        # Log the exception server-side, don't expose details to client
        checks["redis"] = False
    
    # Return 503 if any mandatory dependency is down
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": checks
            }
        )
    
    return {"status": "ready", "checks": checks}


@app.get("/health/live")
async def liveness_check():
    return {"status": "alive"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=settings.DEBUG)
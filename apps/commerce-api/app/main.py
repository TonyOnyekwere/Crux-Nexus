from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import os
from app.config import get_settings
from app.contexts.identity.api.routes import router as identity_router
from app.contexts.tenant_management.api.routes import router as tenant_router
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
)

# Include routers
app.include_router(identity_router)
app.include_router(tenant_router)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """
    Middleware to handle tenant context resolution using proper security functions.
    
    Uses app.middleware.get_tenant_context for all tenant resolution logic (CRX-P0-003D, CRX-P0-003E).
    """
    from app.database import get_db
    from app.middleware import get_tenant_context
    
    try:
        # Get database session for tenant resolution
        async for db in get_db(request):
            tenant_context = await get_tenant_context(request, db)
            request.state.tenant_context = tenant_context
            
            if tenant_context:
                request.state.current_tenant_id = str(tenant_context.tenant_id)
            
            response = await call_next(request)
            return response
    except HTTPException as e:
        # Let HTTPException bubble up for proper error responses
        raise e
    except Exception as e:
        # Other exceptions should result in 500 for observability
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
    except Exception as e:
        checks["database"] = False
        checks["database_error"] = str(e)
    
    # Check Redis connectivity
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        checks["redis"] = False
        checks["redis_error"] = str(e)
    
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
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from fastapi import Request
from app.config import get_settings
import os

settings = get_settings()

# Convert Railway's postgresql:// to postgresql+asyncpg:// for async SQLAlchemy
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db(request: Request = None) -> AsyncSession:
    """Get database session with tenant context set for RLS."""
    async with AsyncSessionLocal() as session:
        try:
            # Set tenant context for RLS if available in request state
            if request and hasattr(request.state, 'current_tenant_id'):
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tid"),
                    {"tid": request.state.current_tenant_id}
                )
            yield session
        finally:
            await session.close()
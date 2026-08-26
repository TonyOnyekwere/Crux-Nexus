from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.database.url import normalize_async_database_url

settings = get_settings()

database_url = normalize_async_database_url(
    settings.DATABASE_URL
)

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session.

    Tenant context is deliberately NOT established here.

    Tenant-scoped database operations must establish tenant context
    through tenant_transaction(), which binds the tenant identity to
    the active PostgreSQL transaction.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
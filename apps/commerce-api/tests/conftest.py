import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, get_db
from app.config import get_settings

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/commerce_db_test"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    async with TestSessionLocal() as session:
        yield session
        # Cleanup after test
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session):
    """Create a test client with database session override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
async def setup_database():
    """Set up test database tables using Alembic migrations (authoritative schema)."""
    # Use Alembic for schema management, not create_all()
    # This ensures tests run against the migration-controlled schema
    import subprocess
    import os
    
    # Run migrations
    subprocess.run(["alembic", "upgrade", "head"], check=True, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL})
    
    yield
    
    # Downgrade migrations
    subprocess.run(["alembic", "downgrade", "base"], check=True, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL})


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
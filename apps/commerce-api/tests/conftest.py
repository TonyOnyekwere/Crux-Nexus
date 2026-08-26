import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, get_db
from app.database.url import normalize_async_database_url
from app.config import get_settings

# CRX-P0-009 P0-5: Use CI environment variables, not hardcoded localhost
# Tests run against CI-managed ephemeral infrastructure, not local development database
TEST_DATABASE_URL = os.environ.get("DATABASE_URL")
if not TEST_DATABASE_URL:
    # Fallback for CI environment variable not set (should not happen in CI)
    settings = get_settings()
    TEST_DATABASE_URL = normalize_async_database_url(settings.DATABASE_URL)

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
    # CRX-P0-009 P0-5: Migrations run by CI before tests, not in conftest
    # This fixture is now a no-op since CI runs migrations explicitly
    # Tests assume schema is already migrated by CI job
    yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
from __future__ import annotations


def normalize_async_database_url(database_url: str) -> str:
    """
    Normalize a PostgreSQL DATABASE_URL for SQLAlchemy asyncpg usage.

    Railway may provide:
        postgresql://...

    SQLAlchemy async engine requires:
        postgresql+asyncpg://...
    """

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url

    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )

    if database_url.startswith("postgres://"):
        return database_url.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1,
        )

    raise ValueError(
        "Unsupported DATABASE_URL scheme. "
        "Expected postgresql://, postgres://, or postgresql+asyncpg://"
    )

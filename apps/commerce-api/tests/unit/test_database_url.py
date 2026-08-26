import pytest

from app.database.url import normalize_async_database_url


@pytest.mark.parametrize(
    ("input_url", "expected_url"),
    [
        (
            "postgresql://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        (
            "postgres://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        (
            "postgresql+asyncpg://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
    ],
)
def test_normalize_async_database_url(
    input_url: str,
    expected_url: str,
):
    assert normalize_async_database_url(input_url) == expected_url


def test_invalid_database_scheme_rejected():
    with pytest.raises(ValueError):
        normalize_async_database_url(
            "mysql://user:pass@host/db"
        )

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None
    SECRET_KEY: str | None = None
    JWT_SECRET_KEY: str | None = None
    ENVIRONMENT: str = "development"
    APP_NAME: str = "CruxNexus Commerce API"
    DEBUG: bool = False
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: list[str] | None = None
    PLATFORM_DEFAULT_PAYMENT_PROVIDER: str = "paystack"
    PLATFORM_DEFAULT_LOGISTICS_PROVIDER: str = "fallback"
    PLATFORM_DEFAULT_NOTIFICATION_PROVIDER: str = "sendgrid"
    PORT: int = 8000
    RAILWAY_ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        env_name = (self.ENVIRONMENT or "development").lower()

        if env_name == "production":
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be provided in production environment")
            if not self.REDIS_URL:
                raise ValueError("REDIS_URL must be provided in production environment")
            if not self.SECRET_KEY or self.SECRET_KEY in ["development-secret-key-change-in-production", "change-this-in-production-railway-secret-key"]:
                raise ValueError("SECRET_KEY must be provided in production environment")
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY in ["development-jwt-secret-key", "change-this-in-production-jwt-secret-key"]:
                raise ValueError("JWT_SECRET_KEY must be provided in production environment")
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters for security")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters for security")
            self.CORS_ORIGINS = self.CORS_ORIGINS or ["https://cruxnexus.com"]
        elif env_name == "staging":
            self.CORS_ORIGINS = self.CORS_ORIGINS or ["https://staging.cruxnexus.com"]
        else:
            self.CORS_ORIGINS = self.CORS_ORIGINS or ["http://localhost:3000"]

        # Local/test runs should still be able to boot with safe placeholders to support
        # unit tests and development without turning off production validation.
        if self.DATABASE_URL:
            try:
                from app.database.url import normalize_async_database_url
                self.DATABASE_URL = normalize_async_database_url(self.DATABASE_URL)
            except ValueError:
                pass

        if env_name not in {"production", "staging"}:
            self.DATABASE_URL = self.DATABASE_URL or "postgresql+asyncpg://user:pass@localhost:5432/crux"
            self.REDIS_URL = self.REDIS_URL or "redis://localhost:6379/0"
            self.SECRET_KEY = self.SECRET_KEY or "12345678901234567890123456789012"
            self.JWT_SECRET_KEY = self.JWT_SECRET_KEY or "12345678901234567890123456789012"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
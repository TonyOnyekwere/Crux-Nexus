from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    ENVIRONMENT: str = "production"
    APP_NAME: str = "CruxNexus Commerce API"
    DEBUG: bool = False
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: list[str] = [
        "https://cruxnexus.com",
        "http://localhost:3000"
    ]
    PLATFORM_DEFAULT_PAYMENT_PROVIDER: str = "paystack"
    PLATFORM_DEFAULT_LOGISTICS_PROVIDER: str = "fallback"
    PLATFORM_DEFAULT_NOTIFICATION_PROVIDER: str = "sendgrid"
    PORT: int = 8000
    RAILWAY_ENVIRONMENT: str = "production"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.ENVIRONMENT == "production":
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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
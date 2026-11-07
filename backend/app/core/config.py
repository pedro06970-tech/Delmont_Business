from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Delmont Business"
    APP_ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://delmont:delmont@localhost:5432/delmont"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    SESSION_COOKIE_NAME: str = "delmont_session"
    CSRF_COOKIE_NAME: str = "delmont_csrf"
    SESSION_TTL_MINUTES: int = 480
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_MINUTES: int = 15
    WHATSMIAU_BASE_URL: str = "https://api.whatsmiau.dev/v2"
    WHATSMIAU_HTTP_TIMEOUT_SECONDS: float = 10.0
    REMINDER_DISPATCH_ENABLED: bool = True
    REMINDER_HOMOLOGATION_ONLY: bool = False
    REMINDER_WORKER_POLL_SECONDS: float = 2.0
    REMINDER_WORKER_BATCH_SIZE: int = 10
    REMINDER_CLAIM_TTL_SECONDS: int = 120
    REMINDER_MAX_ATTEMPTS: int = 3
    REMINDER_RETRY_BASE_SECONDS: int = 30
    REMINDER_INSTANCE_CONCURRENCY: int = 1
    REMINDER_MIN_INTERVAL_SECONDS: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

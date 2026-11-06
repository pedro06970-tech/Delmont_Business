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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

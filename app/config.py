from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Public base used to build short links, e.g. https://sho.rt
    BASE_URL: str = "http://localhost:8000"

    # Cache settings
    CACHE_ENABLED: bool = True          # set False to benchmark Postgres-only
    CACHE_TTL_SECONDS: int = 86_400     # upper bound for any cached entry
    REDIS_TIMEOUT_SECONDS: float = 0.2  # fail fast, then fall back to Postgres

    SHORT_CODE_LENGTH: int = 7


settings = Settings()

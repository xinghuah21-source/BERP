from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://recitation:recitation@localhost:5432/recitation"
    REDIS_URL: str = "redis://localhost:6379/0"
    AI_ENGINE_BASE_URL: str = "http://localhost:8001"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://applypilot:applypilot@localhost:5432/applypilot"

    # Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AI — Groq (free). GROQ_API_KEY accepts one key or a comma separated
    # list — pasting several free keys here means the app rotates to the
    # next one the moment one hits its rate limit, instead of every
    # request failing over to the dumb regex fallback until it resets.
    GROQ_API_KEY: str = ""
    # Must be a model the Groq account actually lists. llama-3.3-70b was
    # retired from the lineup and every request against a missing model
    # fails outright, which silently degrades all writing to the regex
    # fallback — if answers ever go generic across the board, check this
    # name against the models page first.
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    @property
    def GROQ_API_KEYS(self) -> list[str]:
        return [k.strip() for k in self.GROQ_API_KEY.split(",") if k.strip()]

    # Files
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10

    # App
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

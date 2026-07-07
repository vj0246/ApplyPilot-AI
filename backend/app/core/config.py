from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-secret-key-change-in-production-min-32-chars"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://applypilot:applypilot@localhost:5432/applypilot"

    # Auth
    SECRET_KEY: str = _DEV_SECRET
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

    # Gmail API OAuth — an optional, literal "sent from my own Gmail"
    # path. Requires the person to connect their Google account, and
    # while the Google OAuth app itself is unverified, only works for a
    # small list of test users. Empty values simply hide the Connect
    # Gmail option; SendGrid below is what makes sending work for
    # everyone with zero setup regardless of whether this is configured.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Public base URL of this backend, used to build the OAuth redirect
    # URI (must match the one registered in the Google Cloud console).
    BACKEND_URL: str = "http://localhost:8000"

    # SMTP relay — the "send from the user's own Gmail" path. Render blocks
    # outbound SMTP, so when a user connects their own address with a Gmail
    # app password, the backend cannot reach smtp.gmail.com itself. Instead
    # it hands the finished message to this small relay service (deployed on
    # a host that allows outbound SMTP, e.g. Fly.io — see relay/), which
    # does the actual SMTP send from the user's mailbox and returns. Empty
    # RELAY_URL means the app password path stays local dev only, exactly as
    # before. RELAY_SECRET must match the value set on the relay so only
    # this backend can drive it.
    RELAY_URL: str = ""
    RELAY_SECRET: str = ""

    # Files
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10

    # App
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"

    @model_validator(mode="after")
    def _guard_production_secrets(self):
        # Fail fast at startup rather than run production on the shipped dev
        # key. That key is public in this repo, so leaving it in place means
        # anyone can forge a JWT for any user and decrypt every stored app
        # password (crypto.py derives its Fernet key from SECRET_KEY).
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == _DEV_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value (>= 32 chars) in production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

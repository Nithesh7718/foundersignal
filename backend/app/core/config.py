import json
from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "FounderSignal API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security & Authentication
    SECRET_KEY: str = "dev_secret_key_change_in_production_min_32_chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_CORS_ORIGINS: list[str] | str = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            origins = [str(i).strip() for i in v if str(i).strip()]
        elif isinstance(v, str):
            origins = json.loads(v)
        else:
            origins = []

        return origins

    # Database
    DATABASE_URL: str = (
        "postgresql+psycopg://foundersignal:foundersignal_secret@localhost:5432/foundersignal"
    )
    DB_ECHO: bool = False

    # Audio Storage Configuration
    AUDIO_STORAGE_PATH: str = "storage/audio"
    MAX_AUDIO_UPLOAD_SIZE_MB: int = 25

    # AI Providers
    MOCK_PROVIDERS: bool = True
    GNANI_PRISMA_API_KEY: str = ""
    GNANI_PRISMA_ENDPOINT: str = "https://api.vachana.ai/stt/v3"
    GNANI_PRISMA_BATCH_ENDPOINT: str = "https://api.vachana.ai/stt/v3/batch/jobs"
    TIMBRE_API_KEY: str = ""
    TIMBRE_ENDPOINT: str = "https://api.gnani.ai/timbre/v1/tts"
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def validate_production_and_cors(self) -> Self:
        # Prevent wildcard CORS origins
        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("Wildcard origin '*' is forbidden when credentials are enabled.")

        # Validate secret key length
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")

        # Production Safeguards
        if self.is_production:
            if self.MOCK_PROVIDERS:
                raise ValueError("MOCK_PROVIDERS cannot be enabled in production mode.")
            if self.LLM_PROVIDER.lower() == "mock":
                raise ValueError("LLM_PROVIDER cannot be 'mock' in production mode.")
            if self.SECRET_KEY == "dev_secret_key_change_in_production_min_32_chars":
                raise ValueError(
                    "SECRET_KEY must be changed from development default in production."
                )
            if not self.GNANI_PRISMA_API_KEY:
                raise ValueError("GNANI_PRISMA_API_KEY is required in production.")
            if not self.TIMBRE_API_KEY:
                raise ValueError("TIMBRE_API_KEY is required in production.")
            if not self.LLM_API_KEY:
                raise ValueError("LLM_API_KEY is required in production.")

        return self


settings = Settings()

import os
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_GATEWAY_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_ADC_PATH = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")

if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ and os.path.exists(_DEFAULT_ADC_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _DEFAULT_ADC_PATH

_INSECURE_JWT_DEFAULT = "change-me-in-production-use-a-long-random-string"
_INSECURE_PASSWORD_DEFAULT = "change-me-on-first-login"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(_GATEWAY_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Firestore (ADC) ─────────────────────────────────────────────────────
    FIRESTORE_PROJECT: str = ""
    FIRESTORE_DATABASE: str = "(default)"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = _INSECURE_JWT_DEFAULT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── First-run superadmin seed ────────────────────────────────────────────
    SUPERADMIN_USERNAME: str = "admin"
    SUPERADMIN_EMAIL: str = "admin@example.com"
    SUPERADMIN_PASSWORD: str = _INSECURE_PASSWORD_DEFAULT

    # ── LLM Provider API Keys ────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AZURE_API_KEY: str = ""
    AZURE_API_BASE: str = ""
    AZURE_API_VERSION: str = "2024-02-01"
    GEMINI_API_KEY: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION_NAME: str = "us-east-1"
    OLLAMA_API_BASE: str = "http://localhost:11434"

    # ── Vertex AI (ADC) ──────────────────────────────────────────────────────
    VERTEXAI_PROJECT: str = ""
    VERTEXAI_LOCATION: str = "global"

    # ── Rate limiting backend ────────────────────────────────────────────────
    RATE_LIMIT_BACKEND: str = "memory"   # "memory" | "redis"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── LiteLLM routing ─────────────────────────────────────────────────────
    LITELLM_ROUTING_STRATEGY: str = "least-busy"   # "least-busy" | "latency-based" | "simple-shuffle"
    LITELLM_NUM_RETRIES: int = 2
    LITELLM_TIMEOUT: int = 30

    # ── Safety system prompt ─────────────────────────────────────────────────
    # Prepended as the first system message on every LiteLLM call.
    # Set to "" to disable. Override in .env to customise for your deployment.
    SAFETY_SYSTEM_PROMPT: str = ""

    # ── Logging ──────────────────────────────────────────────────────────────
    # Set to True only in dev/debug environments.
    # When False, prompt messages and LLM response content are never written to
    # the request_logs table — only metadata (tokens, cost, latency) is stored.
    LOG_PROMPT_CONTENT: bool = False

    # ── App ──────────────────────────────────────────────────────────────────
    DEBUG: bool = False
    GATEWAY_PORT: int = 8000
    APP_VERSION: str = "2.0.0"
    SERVE_FRONTEND: bool = False
    FRONTEND_DIST_DIR: str = os.path.abspath(os.path.join(_GATEWAY_DIR, os.pardir, "dist"))

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_production(self) -> "Settings":
        """Prevent the gateway from starting in production with known-default secrets."""
        if self.DEBUG:
            # In DEBUG/dev mode insecure defaults are acceptable
            return self
        errors: list[str] = []
        if self.JWT_SECRET_KEY == _INSECURE_JWT_DEFAULT:
            errors.append(
                "JWT_SECRET_KEY is still the default placeholder value. "
                "Set a strong random secret in your .env file."
            )
        if self.SUPERADMIN_PASSWORD == _INSECURE_PASSWORD_DEFAULT:
            errors.append(
                "SUPERADMIN_PASSWORD is still the default placeholder value. "
                "Set a strong password in your .env file."
            )
        if errors:
            raise ValueError(
                "Refusing to start in production with insecure defaults:\n  - "
                + "\n  - ".join(errors)
            )
        return self


settings = Settings()

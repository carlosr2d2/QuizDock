from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "QuizDock API"
    environment: str = "development"
    debug: bool = True

    api_secret_key: str = Field(default="change-me-to-a-long-random-string")
    api_access_token_expire_minutes: int = 60
    api_cors_origins: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+asyncpg://quizdock:quizdock@localhost:5432/quizdock"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    storage_dir: str = "storage"
    signup_bonus_credits: int = 50
    credit_cost_per_question: int = 1
    credit_cost_per_flashcard: int = 1
    generation_max_chars: int = 24000
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 200
    rag_candidate_k: int = 24

    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-2.5-flash"
    llm_embedding_model: str = "gemini-embedding-001"
    llm_timeout_seconds: float = 90.0

    app_public_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "QuizDock <noreply@localhost>"
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 10.0
    password_reset_expire_minutes: int = 60

    payment_default_country: str = "CO"
    payment_allow_simulated: bool = True
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_base: str = "https://api.stripe.com"
    wompi_private_key: str = ""
    wompi_events_secret: str = ""
    wompi_api_base: str = "https://sandbox.wompi.co/v1"
    wompi_checkout_base: str = "https://checkout.wompi.co/l"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

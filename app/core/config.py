from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LaikaLlmProvider = Literal["gemini", "groq", "ollama"]
LaikaEmbeddingProvider = Literal["gemini", "ollama"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://lunar:lunar@localhost:5432/lunar"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    auth_cookie_name: str = "lunar_token"
    auth_cookie_secure: bool = False

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/auth/google/callback"

    # LAIKA / RAG
    laika_llm_provider: LaikaLlmProvider = "gemini"
    laika_embedding_provider: LaikaEmbeddingProvider = "gemini"
    laika_top_k: int = 5
    laika_timeout_seconds: int = 60
    laika_embed_dimensions: int = 768
    laika_context_window: int = 0
    laika_max_history_tokens: int = 8000
    laika_reserved_output_tokens: int = 1500

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:7b-instruct"
    ollama_embed_model: str = "nomic-embed-text"
    # Ollama num_ctx passed to the model (0 = use Ollama default; safer for limited VRAM).
    ollama_num_ctx: int = 0

    # Comma-separated emails auto-promoted to admin on register/login (bootstrap)
    admin_emails: str = ""
    knowledge_max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("laika_llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("laika_embedding_provider", mode="before")
    @classmethod
    def normalize_embedding_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_emails_list(self) -> list[str]:
        return [email.strip().lower() for email in self.admin_emails.split(",") if email.strip()]

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_onetap_enabled(self) -> bool:
        return bool(self.google_client_id)

    @property
    def laika_llm_enabled(self) -> bool:
        if self.laika_llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.laika_llm_provider == "groq":
            return bool(self.groq_api_key)
        if self.laika_llm_provider == "ollama":
            return bool(self.ollama_base_url)
        return False

    @property
    def laika_embedding_enabled(self) -> bool:
        if self.laika_embedding_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.laika_embedding_provider == "ollama":
            return bool(self.ollama_base_url)
        return False

    @property
    def laika_enabled(self) -> bool:
        return self.laika_llm_enabled and self.laika_embedding_enabled

    @property
    def active_embedding_provider_label(self) -> str:
        if self.laika_embedding_provider == "gemini":
            return f"gemini:{self.gemini_embedding_model}"
        return f"ollama:{self.ollama_embed_model}"

    def validate_laika_providers(self) -> None:
        if self.laika_llm_provider not in ("gemini", "groq", "ollama"):
            raise ValueError(f"Invalid LAIKA_LLM_PROVIDER: {self.laika_llm_provider}")
        if self.laika_embedding_provider not in ("gemini", "ollama"):
            raise ValueError(
                "LAIKA_EMBEDDING_PROVIDER must be gemini or ollama (groq has no embeddings API)"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_laika_providers()
    return settings

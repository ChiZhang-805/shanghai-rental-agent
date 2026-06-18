from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "shanghai-re-agent"
    log_level: str = "INFO"

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_responses_model: str = "gpt-4.1-mini"
    openai_vision_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = 1536
    openai_request_timeout_seconds: int = 60
    openai_max_retries: int = 3

    postgres_user: str = "agent"
    postgres_password: str = "agent_password"
    postgres_db: str = "shanghai_re_agent"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = (
        "postgresql+psycopg://agent:agent_password@localhost:5432/shanghai_re_agent"
    )

    upload_dir: Path = Path("uploads")
    max_upload_mb: int = 20

    shanghai_only: bool = True
    allow_public_output: bool = False
    require_human_review_for_marketing: bool = True
    require_verified_listing_for_marketing: bool = True

    policy_top_k: int = 6
    listing_top_k: int = 10
    document_top_k: int = 6
    vector_similarity_threshold: float = 0.25

    amap_web_service_key: str = ""
    amap_js_api_key: str = ""
    amap_js_security_code: str = ""
    amap_default_city: str = "上海"
    amap_default_city_code: str = "021"
    amap_cache_ttl_hours: int = Field(default=168, ge=1)
    amap_live_call_concurrency: int = Field(default=4, ge=1)
    amap_enable_live: bool = True
    enable_demo_rental_data: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Apex Predict API"
    app_env: str = "dev"
    api_prefix: str = "/v1"

    database_url: str = "sqlite+aiosqlite:///./apex.db"
    auto_create_schema: bool = True

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_secret: str = ""
    auth_mode: str = "dev"
    jwks_cache_ttl_seconds: int = 300
    supabase_s3_endpoint: str = ""
    supabase_s3_region: str = ""
    supabase_s3_access_key_id: str = ""
    supabase_s3_secret_access_key: str = ""
    supabase_s3_bucket: str = "profile-images"
    supabase_s3_force_path_style: bool = True
    supabase_s3_public_base_url: str = ""

    openf1_base_url: str = "https://api.openf1.org/v1"
    fallback_base_url: str = "https://api.jolpi.ca/ergast/f1"
    provider_timeout_seconds: float = 5.0

    worker_scheduler_enabled: bool = True
    worker_startup_delay_seconds: float = 3.0
    worker_session_state_interval_seconds: float = 30.0
    worker_provider_health_interval_seconds: float = 120.0
    worker_ai_previews_interval_seconds: float = 600.0
    worker_auto_finalize_interval_seconds: float = 30.0

    default_confidence_credits: int = 100
    admin_api_key: str = "dev-admin-key"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

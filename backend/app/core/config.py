# backend/app/core/config.py
import logging
import secrets
from typing import List

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS = {"", "your_secret_key_here", "default-dev-secret-key-change-in-production"}


class Settings(BaseSettings):
    app_name: str = "Brand Intelligence Platform"
    version: str = "1.0.0"
    # Secure by default: debug must be explicitly enabled (DEBUG=true in .env)
    debug: bool = False
    # Log every SQL statement (may include user data) - keep off unless debugging
    sql_echo: bool = False

    # JWT signing key. Required when DEBUG=false; in debug a random per-process key is used.
    secret_key: str = ""
    access_token_expire_minutes: int = 30
    database_url: str = "sqlite+aiosqlite:///./brand_intelligence.db"

    # Service-to-service API key (header: X-API-Key). Grants the "admin" role. Optional.
    api_key: str = ""
    # Local development only: skip authentication entirely. Ignored unless DEBUG=true.
    auth_disabled: bool = False

    # First admin account, created by init_db when no users exist
    admin_email: str = ""
    admin_password: str = ""

    # Comma-separated list of allowed CORS origins ("*" is ignored)
    cors_origins: str = "http://localhost:3000"

    # Rate limiting (requests per minute per client IP, per process)
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 120
    rate_limit_ml_per_minute: int = 30
    rate_limit_login_per_minute: int = 10

    # Optional services
    redis_url: str = "redis://localhost:6379/0"
    elasticsearch_url: str = "http://localhost:9200"
    clickhouse_url: str = "http://localhost:8123"
    use_redis: bool = True

    # API Keys
    news_api_key: str = ""
    googlenews_query: str = ""

    # ML Models
    sentiment_model_path: str = "./ml/models/sentiment_model"
    crisis_model_path: str = "./ml/models/crisis_model"

    # Input limits (DoS protection for ML endpoints)
    max_text_length: int = 10_000
    max_batch_size: int = 100

    @field_validator("secret_key")
    @classmethod
    def _ensure_secret_key(cls, v: str, info: ValidationInfo) -> str:
        if v in _PLACEHOLDER_SECRETS:
            if not info.data.get("debug", False):
                raise ValueError("SECRET_KEY must be set when DEBUG=false")
            logger.warning("SECRET_KEY not set - using a random ephemeral key (debug only).")
            return secrets.token_urlsafe(48)
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    @property
    def auth_bypass(self) -> bool:
        return self.debug and self.auth_disabled

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'


settings = Settings()

if settings.auth_disabled and not settings.debug:
    logger.warning("AUTH_DISABLED is ignored because DEBUG=false.")

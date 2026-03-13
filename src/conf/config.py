from pathlib import Path

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FastAPI Boilerplate"
    debug: bool = False

    # Database configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "fastapi-boilerplate"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Security configuration
    jwt_secret: str = "Momoyeyu"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 3600
    refresh_token_expire_seconds: int = 604800  # 7 days
    verification_code_expire_seconds: int = 300  # 5 minutes

    # Email (Resend)
    resend_api_key: SecretStr = SecretStr("")
    email_from: str = "noreply@example.com"

    # Invitation code
    require_invitation_code: bool = False

    # Tenant invitation
    invitation_token_expire_seconds: int = 604800  # 7 days
    frontend_url: str = "http://localhost:3000"

    # LLM (OpenAI-compatible)
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"

    # Server configuration
    server_host: str = "localhost"
    server_port: int = 8000


settings = Settings()

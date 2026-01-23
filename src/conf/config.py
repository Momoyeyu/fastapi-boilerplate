from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # Security configuration
    password_salt: str = "Momoyeyu"
    jwt_secret: str = "Momoyeyu"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 3600

    # Admin account
    admin_username: str = "admin"
    admin_password: str = "admin"


settings = Settings()

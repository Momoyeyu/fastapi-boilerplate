from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost/fastapi-boilerplate"
    password_salt: str = "Momoyeyu"
    jwt_secret: str = "Momoyeyu"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 3600
    admin_username: str = "admin"
    admin_password: str = "admin"


settings = Settings()

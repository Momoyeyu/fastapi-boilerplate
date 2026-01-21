import os


def _getenv(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


DATABASE_URL = _getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost/fastapi-boilerplate",
)

PASSWORD_SALT = _getenv("PASSWORD_SALT", "Jacky Su")

JWT_SECRET = _getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = _getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_SECONDS = int(_getenv("JWT_EXPIRE_SECONDS", "3600"))

import os

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost/fastapi-boilerplate",
)

# Security
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "Momoyeyu")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "Momoyeyu")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "3600"))

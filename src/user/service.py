import hashlib

from src.conf.config import PASSWORD_SALT

def get_password_hash(password: str) -> str:
    return hashlib.sha512((password + PASSWORD_SALT).encode("utf-8")).hexdigest()

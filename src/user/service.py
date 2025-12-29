import hashlib

from conf.config import PASSWORD_SALT
from middleware import auth
from user import error
from user.model import create_user, get_user, User

def get_password_hash(password: str) -> str:
    return hashlib.sha512((password + PASSWORD_SALT).encode("utf-8")).hexdigest()


def register_user(username: str, password: str) -> User:
    if get_user(username):
        raise error.UserAlreadyExistsError("User already exists")
    encrypted_password = get_password_hash(password)
    user = create_user(username, encrypted_password)
    if not user or user.id is None:
        raise error.CreateUserFailedError("Create user failed")
    return user


def login_user(username: str, password: str) -> str:
    user = get_user(username)
    encrypted_password = get_password_hash(password)
    if not user or user.password != encrypted_password or user.id is None:
        raise error.InvalidCredentialsError("Invalid credentials")
    return auth.create_token({"id": user.id, "username": user.username})

import hashlib

from common import erri
from conf.config import PASSWORD_SALT
from middleware import auth
from user.model import create_user, get_user, update_user_profile, User

def get_password_hash(password: str) -> str:
    return hashlib.sha512((password + PASSWORD_SALT).encode("utf-8")).hexdigest()


def register_user(username: str, password: str) -> User:
    if get_user(username):
        raise erri.conflict("User already exists")
    encrypted_password = get_password_hash(password)
    user = create_user(username, encrypted_password)
    if not user or user.id is None:
        raise erri.internal("Create user failed")
    return user


def login_user(username: str, password: str) -> str:
    user = get_user(username)
    encrypted_password = get_password_hash(password)
    if not user or user.password != encrypted_password or user.id is None:
        raise erri.unauthorized("Invalid credentials")
    return auth.create_token(user)


def get_user_profile(username: str) -> User:
    user = get_user(username)
    if not user:
        raise erri.not_found("User not found")
    return user


def update_my_profile(username: str, *, nickname: str | None, email: str | None, avatar_url: str | None) -> User:
    user = update_user_profile(username, nickname=nickname, email=email, avatar_url=avatar_url)
    if not user:
        raise erri.not_found("User not found")
    return user

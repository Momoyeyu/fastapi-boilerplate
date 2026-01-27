from auth.service import get_password_hash
from common import erri
from conf.config import settings
from user.model import User, create_user, get_user, update_user_profile


def register_user(username: str, password: str) -> User:
    if get_user(username):
        raise erri.conflict("User already exists")
    encrypted_password = get_password_hash(password)
    user = create_user(username, encrypted_password)
    if not user or user.id is None:
        raise erri.internal("Create user failed")
    return user


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


def ensure_admin_user() -> None:
    """Ensure the admin user exists, create if not."""
    if get_user(settings.admin_username):
        return
    encrypted_password = get_password_hash(settings.admin_password)
    create_user(settings.admin_username, encrypted_password, role="admin")

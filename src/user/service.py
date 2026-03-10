from auth.service import get_password_hash
from common import erri
from user.model import User, get_user, update_user_password, update_user_profile


def get_user_profile(username: str) -> User:
    user = get_user(username)
    if not user:
        raise erri.not_found("User not found")
    return user


def update_my_profile(username: str, *, nickname: str | None, avatar_url: str | None) -> User:
    user = update_user_profile(username, nickname=nickname, avatar_url=avatar_url)
    if not user:
        raise erri.not_found("User not found")
    return user


def change_password(username: str, old_password: str, new_password: str) -> bool:
    user = get_user(username)
    if not user:
        raise erri.not_found("User not found")

    encrypted_old = get_password_hash(old_password)
    if user.password != encrypted_old:
        raise erri.bad_request("Invalid old password")

    encrypted_new = get_password_hash(new_password)
    return update_user_password(username, encrypted_new)

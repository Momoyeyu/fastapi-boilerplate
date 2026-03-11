from auth.password import get_password_hash, validate_password, verify_password
from common import erri
from user.model import User, get_user, update_user_password, update_user_profile


async def get_user_profile(username: str) -> User:
    user = await get_user(username)
    if not user:
        raise erri.not_found("User not found")
    return user


async def update_my_profile(username: str, *, avatar_url: str | None) -> User:
    user = await update_user_profile(username, avatar_url=avatar_url)
    if not user:
        raise erri.not_found("User not found")
    return user


async def change_password(username: str, old_password: str, new_password: str) -> bool:
    user = await get_user(username)
    if not user:
        raise erri.not_found("User not found")

    if not verify_password(old_password, user.hashed_password):
        raise erri.bad_request("Invalid old password")

    validate_password(new_password)
    encrypted_new = get_password_hash(new_password)
    result = await update_user_password(username, encrypted_new)

    if result and user.id is not None:
        from auth.refresh_token import revoke_all_for_user

        revoke_all_for_user(user.id)

    return result

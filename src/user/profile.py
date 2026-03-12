import re

from sqlalchemy.exc import IntegrityError

from auth.dto import TokenPair
from auth.service import create_token, revoke_all_for_user
from common import erri
from common.utils import get_password_hash, validate_password, verify_password
from user.model import User, get_user, update_user_password, update_user_profile

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")


async def get_user_profile(username: str) -> User:
    user = await get_user(username)
    if not user:
        raise erri.not_found("User not found")
    return user


async def update_my_profile(
    username: str, *, new_username: str | None = None, avatar_url: str | None = None
) -> tuple[User, TokenPair | None]:
    token_pair: TokenPair | None = None

    if new_username is not None:
        if not _USERNAME_RE.match(new_username):
            raise erri.bad_request("Username must be 3-30 chars: letters, digits, underscore, hyphen")
        if await get_user(new_username):
            raise erri.conflict("Username already taken")

    try:
        user = await update_user_profile(username, new_username=new_username, avatar_url=avatar_url)
    except IntegrityError:
        raise erri.conflict("Username already taken") from None
    if not user:
        raise erri.not_found("User not found")

    if new_username is not None and user.id is not None:
        revoke_all_for_user(user.id)
        token_pair = create_token(user)

    return user, token_pair


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
        revoke_all_for_user(user.id)

    return result

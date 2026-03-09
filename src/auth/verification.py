from secrets import randbelow
from typing import Literal

from conf.config import settings
from conf.redis import get_redis

PurposeType = Literal["register", "reset_password"]

_KEY_PREFIX = "verification:"


def _make_key(email: str, purpose: PurposeType) -> str:
    return f"{_KEY_PREFIX}{email.lower()}:{purpose}"


def generate_code() -> str:
    return str(randbelow(900000) + 100000)


def create_verification_code(email: str, purpose: PurposeType) -> str:
    code = generate_code()
    key = _make_key(email, purpose)
    get_redis().setex(key, settings.verification_code_expire_seconds, code)
    return code


def consume_verification_code(email: str, code: str, purpose: PurposeType) -> bool:
    key = _make_key(email, purpose)
    r = get_redis()
    stored = r.get(key)
    if stored is None or stored != code:
        return False
    r.delete(key)
    return True


_INVITATION_PREFIX = "invitation_context:"


def store_invitation_context(email: str, invitation_code_id: int) -> None:
    key = f"{_INVITATION_PREFIX}{email.lower()}"
    get_redis().setex(key, settings.verification_code_expire_seconds, str(invitation_code_id))


def consume_invitation_context(email: str) -> int | None:
    key = f"{_INVITATION_PREFIX}{email.lower()}"
    r = get_redis()
    value = r.get(key)
    if value is None:
        return None
    r.delete(key)
    return int(value)

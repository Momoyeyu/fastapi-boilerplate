from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import randbelow
from typing import Literal

from conf.config import settings

PurposeType = Literal["register", "reset_password"]


@dataclass
class VerificationCode:
    email: str
    code: str
    purpose: PurposeType
    expires_at: datetime
    created_at: datetime


_verification_codes: dict[str, VerificationCode] = {}


def _make_key(email: str, purpose: PurposeType) -> str:
    return f"{email.lower()}:{purpose}"


def generate_code() -> str:
    return str(randbelow(900000) + 100000)


def create_verification_code(email: str, purpose: PurposeType) -> VerificationCode:
    now = datetime.now(UTC)
    code = VerificationCode(
        email=email.lower(),
        code=generate_code(),
        purpose=purpose,
        expires_at=now + timedelta(seconds=settings.verification_code_expire_seconds),
        created_at=now,
    )
    key = _make_key(email, purpose)
    _verification_codes[key] = code
    return code


def get_verification_code(email: str, purpose: PurposeType) -> VerificationCode | None:
    key = _make_key(email, purpose)
    return _verification_codes.get(key)


def validate_verification_code(email: str, code: str, purpose: PurposeType) -> bool:
    key = _make_key(email, purpose)
    stored = _verification_codes.get(key)
    if stored is None:
        return False
    if stored.code != code:
        return False
    if stored.expires_at < datetime.now(UTC):
        return False
    return True


def consume_verification_code(email: str, code: str, purpose: PurposeType) -> bool:
    if not validate_verification_code(email, code, purpose):
        return False
    key = _make_key(email, purpose)
    del _verification_codes[key]
    return True


def cleanup_expired_codes() -> int:
    now = datetime.now(UTC)
    expired_keys = [k for k, v in _verification_codes.items() if v.expires_at < now]
    for key in expired_keys:
        del _verification_codes[key]
    return len(expired_keys)

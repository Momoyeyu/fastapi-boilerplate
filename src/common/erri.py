from __future__ import annotations

from common.resp import Code


class BusinessError(Exception):
    def __init__(self, *, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def bad_request(message: str) -> BusinessError:
    return BusinessError(code=Code.BAD_REQUEST, message=message)


def unauthorized(message: str) -> BusinessError:
    return BusinessError(code=Code.UNAUTHORIZED, message=message)


def forbidden(message: str) -> BusinessError:
    return BusinessError(code=Code.FORBIDDEN, message=message)


def not_found(message: str) -> BusinessError:
    return BusinessError(code=Code.NOT_FOUND, message=message)


def conflict(message: str) -> BusinessError:
    return BusinessError(code=Code.CONFLICT, message=message)


def internal(message: str) -> BusinessError:
    return BusinessError(code=Code.INTERNAL_ERROR, message=message)

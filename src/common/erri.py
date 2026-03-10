from __future__ import annotations

from common.resp import Code


class BusinessError(Exception):
    def __init__(self, *, code: int, status_code: int, message: str):
        self.code = code
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def bad_request(message: str) -> BusinessError:
    return BusinessError(code=Code.BAD_REQUEST, status_code=400, message=message)


def unauthorized(message: str) -> BusinessError:
    return BusinessError(code=Code.UNAUTHORIZED, status_code=401, message=message)


def forbidden(message: str) -> BusinessError:
    return BusinessError(code=Code.FORBIDDEN, status_code=403, message=message)


def not_found(message: str) -> BusinessError:
    return BusinessError(code=Code.NOT_FOUND, status_code=404, message=message)


def conflict(message: str) -> BusinessError:
    return BusinessError(code=Code.CONFLICT, status_code=409, message=message)


def internal(message: str) -> BusinessError:
    return BusinessError(code=Code.INTERNAL_ERROR, status_code=500, message=message)

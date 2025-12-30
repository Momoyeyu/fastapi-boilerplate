from __future__ import annotations


class BusinessError(Exception):
    def __init__(self, *, status_code: int, msg: str):
        self.status_code = status_code
        self.msg = msg
        super().__init__(msg)


def bad_request(msg: str) -> BusinessError:
    return BusinessError(status_code=400, msg=msg)


def unauthorized(msg: str) -> BusinessError:
    return BusinessError(status_code=401, msg=msg)


def forbidden(msg: str) -> BusinessError:
    return BusinessError(status_code=403, msg=msg)


def not_found(msg: str) -> BusinessError:
    return BusinessError(status_code=404, msg=msg)


def conflict(msg: str) -> BusinessError:
    return BusinessError(status_code=409, msg=msg)


def internal(msg: str) -> BusinessError:
    return BusinessError(status_code=500, msg=msg)


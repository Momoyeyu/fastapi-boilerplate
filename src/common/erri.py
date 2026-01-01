from __future__ import annotations


class BusinessError(Exception):
    def __init__(self, *, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def bad_request(detail: str) -> BusinessError:
    return BusinessError(status_code=400, detail=detail)


def unauthorized(detail: str) -> BusinessError:
    return BusinessError(status_code=401, detail=detail)


def forbidden(detail: str) -> BusinessError:
    return BusinessError(status_code=403, detail=detail)


def not_found(detail: str) -> BusinessError:
    return BusinessError(status_code=404, detail=detail)


def conflict(detail: str) -> BusinessError:
    return BusinessError(status_code=409, detail=detail)


def internal(detail: str) -> BusinessError:
    return BusinessError(status_code=500, detail=detail)


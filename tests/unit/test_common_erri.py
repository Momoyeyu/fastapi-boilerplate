"""Unit tests for common.erri — exception types and convenience factories."""

import pytest

from common import erri
from common.erri import BusinessError
from common.resp import Code

FACTORY_CASES = [
    (erri.bad_request, Code.BAD_REQUEST),
    (erri.unauthorized, Code.UNAUTHORIZED),
    (erri.forbidden, Code.FORBIDDEN),
    (erri.not_found, Code.NOT_FOUND),
    (erri.conflict, Code.CONFLICT),
    (erri.internal, Code.INTERNAL_ERROR),
]


@pytest.mark.parametrize("factory,expected_code", FACTORY_CASES)
def test_factory_returns_business_error_with_correct_code(factory, expected_code):
    exc = factory("something went wrong")
    assert isinstance(exc, BusinessError)
    assert exc.code == expected_code
    assert exc.message == "something went wrong"


@pytest.mark.parametrize("factory,expected_code", FACTORY_CASES)
def test_factory_exception_is_raisable_and_catchable(factory, expected_code):
    with pytest.raises(BusinessError) as exc_info:
        raise factory("fail")
    assert exc_info.value.code == expected_code


def test_factory_carries_correct_http_status_code():
    cases = [
        (erri.bad_request, 400),
        (erri.unauthorized, 401),
        (erri.forbidden, 403),
        (erri.not_found, 404),
        (erri.conflict, 409),
        (erri.internal, 500),
    ]
    for factory, expected_status in cases:
        exc = factory("msg")
        assert exc.status_code == expected_status


def test_business_error_str_is_message():
    exc = BusinessError(code=Code.BAD_REQUEST, status_code=400, message="oops")
    assert str(exc) == "oops"


def test_business_error_is_exception():
    assert issubclass(BusinessError, Exception)

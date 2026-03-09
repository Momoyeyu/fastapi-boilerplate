"""Unit tests for common.resp — response envelope structure."""

from common import resp
from common.resp import Code, Response


def test_ok_default():
    r = resp.ok()
    assert r.code == Code.OK
    assert r.message == "ok"
    assert r.data is None


def test_ok_with_data():
    r = resp.ok(data={"id": 1})
    assert r.code == Code.OK
    assert r.data == {"id": 1}


def test_ok_with_custom_message():
    r = resp.ok(message="created")
    assert r.message == "created"


def test_error_returns_given_code_and_message():
    r = resp.error(Code.NOT_FOUND, "User not found")
    assert r.code == Code.NOT_FOUND
    assert r.message == "User not found"
    assert r.data is None


def test_error_with_data():
    r = resp.error(Code.INVALID_PARAM, "bad", data=[{"loc": ["body"]}])
    assert r.data == [{"loc": ["body"]}]


def test_response_model_dump_has_three_keys():
    """Ensure the serialised envelope always has exactly code/message/data."""
    r = resp.ok(data="hello")
    d = r.model_dump()
    assert set(d.keys()) == {"code", "message", "data"}


def test_response_default_values():
    r = Response()
    assert r.code == Code.OK
    assert r.message == "ok"
    assert r.data is None

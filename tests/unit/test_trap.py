"""Unit tests for common.trap — exception handlers produce correct response format."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from common import erri
from common.resp import Code
from common.trap import setup_exception_handlers

ENVELOPE_KEYS = {"code", "message", "data"}


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    setup_exception_handlers(app)
    return app


def test_business_error_returns_proper_status_with_envelope(app: FastAPI):
    @app.get("/err")
    async def endpoint():
        raise erri.not_found("User not found")

    resp = TestClient(app).get("/err")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == ENVELOPE_KEYS
    assert body["code"] == Code.NOT_FOUND
    assert body["message"] == "User not found"
    assert body["data"] is None


def test_http_exception_returns_original_status_with_envelope(app: FastAPI):
    @app.get("/http")
    async def endpoint():
        raise HTTPException(status_code=403, detail="Forbidden resource")

    resp = TestClient(app).get("/http")
    assert resp.status_code == 403
    body = resp.json()
    assert set(body.keys()) == ENVELOPE_KEYS
    assert body["code"] == Code.FORBIDDEN
    assert body["message"] == "Forbidden resource"


def test_http_exception_unknown_status_preserved(app: FastAPI):
    @app.get("/http")
    async def endpoint():
        raise HTTPException(status_code=418, detail="I'm a teapot")

    resp = TestClient(app).get("/http")
    assert resp.status_code == 418
    body = resp.json()
    assert body["code"] == Code.INTERNAL_ERROR


def test_validation_error_returns_422_with_envelope(app: FastAPI):
    from pydantic import BaseModel

    class Body(BaseModel):
        name: str

    @app.post("/val")
    async def endpoint(body: Body):
        return {}

    resp = TestClient(app).post("/val", json={"wrong_field": 1})
    assert resp.status_code == 422
    body = resp.json()
    assert set(body.keys()) == ENVELOPE_KEYS
    assert body["code"] == Code.INVALID_PARAM
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)


def test_generic_exception_returns_500_with_internal_error(app: FastAPI):
    @app.get("/boom")
    async def endpoint():
        raise RuntimeError("unexpected")

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert set(body.keys()) == ENVELOPE_KEYS
    assert body["code"] == Code.INTERNAL_ERROR
    assert body["message"] == "Internal server error"


FACTORY_HTTP_CASES = [
    (erri.bad_request, Code.BAD_REQUEST, 400),
    (erri.unauthorized, Code.UNAUTHORIZED, 401),
    (erri.forbidden, Code.FORBIDDEN, 403),
    (erri.not_found, Code.NOT_FOUND, 404),
    (erri.conflict, Code.CONFLICT, 409),
    (erri.internal, Code.INTERNAL_ERROR, 500),
]


@pytest.mark.parametrize("factory,expected_code,expected_status", FACTORY_HTTP_CASES)
def test_all_business_error_types_produce_correct_code_and_status(
    app: FastAPI, factory, expected_code, expected_status
):
    @app.get(f"/err/{expected_code}")
    async def endpoint():
        raise factory("test message")

    resp = TestClient(app, raise_server_exceptions=False).get(f"/err/{expected_code}")
    assert resp.status_code == expected_status
    body = resp.json()
    assert body["code"] == expected_code
    assert body["message"] == "test message"

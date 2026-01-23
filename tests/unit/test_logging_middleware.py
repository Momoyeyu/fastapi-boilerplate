from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware.logging import (
    LoggingMiddleware,
    _flatten_qs,
    _mask_fields,
    _mask_headers,
    _parse_body,
    setup_logging_middleware,
)


class TestMaskHeaders:
    def test_masks_authorization_header(self):
        headers = {"Authorization": "Bearer secret-token", "Content-Type": "application/json"}
        result = _mask_headers(headers)
        assert result["Authorization"] == "***"
        assert result["Content-Type"] == "application/json"

    def test_masks_cookie_header(self):
        headers = {"Cookie": "session=abc123", "Accept": "text/html"}
        result = _mask_headers(headers)
        assert result["Cookie"] == "***"
        assert result["Accept"] == "text/html"

    def test_masks_x_api_key_header(self):
        headers = {"X-API-Key": "my-api-key"}
        result = _mask_headers(headers)
        assert result["X-API-Key"] == "***"

    def test_case_insensitive_masking(self):
        headers = {"authorization": "Bearer token", "COOKIE": "session=x"}
        result = _mask_headers(headers)
        assert result["authorization"] == "***"
        assert result["COOKIE"] == "***"

    def test_returns_empty_dict_for_empty_input(self):
        assert _mask_headers({}) == {}


class TestMaskFields:
    def test_masks_password_field(self):
        data = {"username": "alice", "password": "secret123"}
        result = _mask_fields(data)
        assert result["username"] == "alice"
        assert result["password"] == "***"

    def test_masks_nested_password_field(self):
        data = {"user": {"name": "bob", "password": "hidden"}}
        result = _mask_fields(data)
        assert result["user"]["name"] == "bob"
        assert result["user"]["password"] == "***"

    def test_masks_password_in_list(self):
        data = [{"password": "secret1"}, {"password": "secret2"}]
        result = _mask_fields(data)
        assert result[0]["password"] == "***"
        assert result[1]["password"] == "***"

    def test_masks_multiple_sensitive_fields(self):
        data = {"password": "pw", "token": "tk", "secret": "sc", "api_key": "ak"}
        result = _mask_fields(data)
        assert all(v == "***" for v in result.values())

    def test_case_insensitive_field_masking(self):
        data = {"PASSWORD": "pw", "Token": "tk"}
        result = _mask_fields(data)
        assert result["PASSWORD"] == "***"
        assert result["Token"] == "***"

    def test_returns_primitive_unchanged(self):
        assert _mask_fields("string") == "string"
        assert _mask_fields(123) == 123
        assert _mask_fields(None) is None


class TestParseBody:
    def test_parses_json_body(self):
        body = b'{"name": "alice", "age": 30}'
        result = _parse_body(body, "application/json")
        assert result == {"name": "alice", "age": 30}

    def test_parses_json_with_charset(self):
        body = b'{"name": "alice"}'
        result = _parse_body(body, "application/json; charset=utf-8")
        assert result == {"name": "alice"}

    def test_parses_form_urlencoded_body(self):
        body = b"username=alice&password=secret"
        result = _parse_body(body, "application/x-www-form-urlencoded")
        assert result == {"username": "alice", "password": "secret"}

    def test_flattens_single_value_form_fields(self):
        body = b"name=alice&tags=a&tags=b"
        result = _parse_body(body, "application/x-www-form-urlencoded")
        assert result["name"] == "alice"
        assert result["tags"] == ["a", "b"]

    def test_returns_string_for_unknown_content_type(self):
        body = b"plain text content"
        result = _parse_body(body, "text/plain")
        assert result == "plain text content"

    def test_truncates_long_text_body(self):
        body = b"x" * 600
        result = _parse_body(body, "text/plain")
        assert len(result) == 503  # 500 chars + "..."
        assert result.endswith("...")

    def test_returns_none_for_empty_body(self):
        assert _parse_body(b"", "application/json") is None

    def test_handles_invalid_json_gracefully(self):
        body = b"not valid json"
        result = _parse_body(body, "application/json")
        assert result == "not valid json"


class TestFlattenQs:
    def test_flattens_single_value_params(self):
        result = _flatten_qs("name=alice&age=30")
        assert result == {"name": "alice", "age": "30"}

    def test_keeps_multiple_values_as_list(self):
        result = _flatten_qs("tag=a&tag=b&tag=c")
        assert result == {"tag": ["a", "b", "c"]}

    def test_mixed_single_and_multiple_values(self):
        result = _flatten_qs("name=alice&tag=a&tag=b")
        assert result["name"] == "alice"
        assert result["tag"] == ["a", "b"]

    def test_returns_empty_dict_for_empty_string(self):
        assert _flatten_qs("") == {}

    def test_preserves_blank_values(self):
        result = _flatten_qs("name=&value=test")
        assert result["name"] == ""
        assert result["value"] == "test"


class TestLoggingMiddleware:
    def test_logs_request_and_response(self):
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        setup_logging_middleware(app)
        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"message": "ok"}

    def test_logs_post_request_with_json_body(self):
        app = FastAPI()

        @app.post("/echo")
        async def echo(data: dict):
            return data

        setup_logging_middleware(app)
        client = TestClient(app)
        resp = client.post("/echo", json={"name": "alice"})
        assert resp.status_code == 200
        assert resp.json() == {"name": "alice"}

    def test_logs_request_with_query_params(self):
        app = FastAPI()

        @app.get("/search")
        async def search(q: str):
            return {"query": q}

        setup_logging_middleware(app)
        client = TestClient(app)
        resp = client.get("/search?q=test")
        assert resp.status_code == 200
        assert resp.json() == {"query": "test"}

    def test_skips_excluded_paths(self):
        app = FastAPI()
        setup_logging_middleware(app)
        client = TestClient(app)
        # /docs is excluded, should still work but not logged
        resp = client.get("/docs")
        # Swagger UI returns HTML or redirect
        assert resp.status_code in (200, 307)

    def test_prepare_headers_masks_in_production(self):
        app = FastAPI()
        middleware = LoggingMiddleware(app)
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}

        with patch("middleware.logging.settings") as mock_settings:
            mock_settings.debug = False
            result = middleware._prepare_headers(headers)
            assert result["Authorization"] == "***"
            assert result["Content-Type"] == "application/json"

    def test_prepare_headers_skips_mask_in_debug(self):
        app = FastAPI()
        middleware = LoggingMiddleware(app)
        headers = {"Authorization": "Bearer token"}

        with patch("middleware.logging.settings") as mock_settings:
            mock_settings.debug = True
            result = middleware._prepare_headers(headers)
            assert result["Authorization"] == "Bearer token"

    def test_prepare_data_masks_in_production(self):
        app = FastAPI()
        middleware = LoggingMiddleware(app)
        data = {"username": "alice", "password": "secret"}

        with patch("middleware.logging.settings") as mock_settings:
            mock_settings.debug = False
            result = middleware._prepare_data(data)
            assert result["username"] == "alice"
            assert result["password"] == "***"

    def test_prepare_data_skips_mask_in_debug(self):
        app = FastAPI()
        middleware = LoggingMiddleware(app)
        data = {"username": "alice", "password": "secret"}

        with patch("middleware.logging.settings") as mock_settings:
            mock_settings.debug = True
            result = middleware._prepare_data(data)
            assert result["password"] == "secret"

    def test_handles_form_data_request(self):
        from fastapi import Form

        app = FastAPI()

        @app.post("/login")
        async def login(username: str = Form(), password: str = Form()):
            return {"user": username}

        setup_logging_middleware(app)
        client = TestClient(app)
        resp = client.post("/login", data={"username": "alice", "password": "secret"})
        assert resp.status_code == 200
        assert resp.json() == {"user": "alice"}

from unittest.mock import patch


def test_lifespan_calls_close_redis():
    with (
        patch("main.ensure_admin_user"),
        patch("main.close_db"),
        patch("main.close_redis") as mock_close_redis,
    ):
        from main import create_app

        app = create_app()

        from fastapi.testclient import TestClient

        with TestClient(app):
            pass

        mock_close_redis.assert_called_once()

"""
Integration test fixtures.

Uses a temporary SQLite database to isolate tests from the real database.
"""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from auth import model as auth_model
from conf import db as db_module
from user import model as user_model


@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh temporary SQLite database for each test."""
    # Use a temporary file instead of in-memory to avoid connection issues
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    sqlite_url = f"sqlite:///{db_path}"
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()
    # Clean up the temporary file
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def client(test_engine, monkeypatch) -> Generator[TestClient, None, None]:
    """
    Create a TestClient with the test database engine.

    Patches the engine in both db and model modules.
    """
    # Patch the engine in all modules that use it
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(user_model, "engine", test_engine)
    monkeypatch.setattr(auth_model, "engine", test_engine)

    # Import create_app after patching to ensure patches are in effect
    from main import create_app

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def session(test_engine) -> Generator[Session, None, None]:
    """Create a database session for direct database operations in tests."""
    with Session(test_engine) as session:
        yield session

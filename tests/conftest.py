import os
from unittest.mock import MagicMock

# Set env vars BEFORE importing main: API_KEY is read at import time.
# load_dotenv() in main.py defaults to override=False, so these win over .env.
os.environ["API_KEY"] = "test-key"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "test_db"
os.environ["POSTGRES_USER"] = "test"
os.environ["POSTGRES_PASSWORD"] = "test"

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-key"}


@pytest.fixture
def mock_db(monkeypatch):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(main, "get_connection", lambda: conn)
    return conn, cursor

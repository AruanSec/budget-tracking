import os

# Must be set before any app.* import so Settings picks it up.
os.environ.setdefault(
    "BUDGET_DATABASE_URL",
    "postgresql+psycopg://budget:***@localhost:5432/budget_test",
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)

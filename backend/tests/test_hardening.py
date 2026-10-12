import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AccountUpdate, CategoryUpdate, IncomeSourceUpdate, TransactionIn


@pytest.mark.parametrize("schema,field", [(AccountUpdate, "name"), (AccountUpdate, "archived"),
                                          (CategoryUpdate, "name"), (IncomeSourceUpdate, "active")])
def test_patch_required_fields_reject_null(schema, field):
    with pytest.raises(ValidationError):
        schema(**{field: None})


def test_category_parent_can_be_cleared():
    assert CategoryUpdate(parent_id=None).model_dump(exclude_unset=True) == {"parent_id": None}


def test_currency_restricted_until_multicurrency_reporting():
    with pytest.raises(ValidationError):
        TransactionIn(type="income", amount_cents=100, occurred_on="2031-01-01",
                      income_source_id=1, currency="EUR")


def test_production_rejects_placeholder_secrets():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret="dev-secret",
                 database_url="postgresql+psycopg://budget:dev-secret@localhost/budget")
    settings = Settings(_env_file=None, environment="production", jwt_secret="a" * 64,
                        database_url="postgresql+psycopg://budget:strong-password@localhost/budget")
    assert settings.environment == "production"


def test_test_suite_refuses_non_test_database():
    env = {**os.environ, "BUDGET_DATABASE_URL": "postgresql+psycopg://budget:dev-secret@localhost/budget"}
    result = subprocess.run([sys.executable, "-c", "import runpy; runpy.run_path('tests/conftest.py')"],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Tests require BUDGET_DATABASE_URL" in result.stderr

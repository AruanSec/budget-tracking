"""API-layer validation of transaction input (Pydantic), no DB needed."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import TransactionIn


def _expense(**kw):
    base = dict(
        type="expense",
        amount_cents=10000,
        occurred_on=date(2026, 9, 20),
        category_id=1,
        splits=[
            {"member_id": 1, "share_cents": 5000},
            {"member_id": 2, "share_cents": 5000},
        ],
    )
    base.update(kw)
    return TransactionIn(**base)


def test_valid_even_split():
    t = _expense()
    assert sum(s.share_cents for s in t.splits) == t.amount_cents


def test_split_sum_mismatch_rejected():
    with pytest.raises(ValidationError, match="split shares"):
        _expense(
            splits=[
                {"member_id": 1, "share_cents": 5000},
                {"member_id": 2, "share_cents": 4999},
            ]
        )


def test_expense_requires_category():
    with pytest.raises(ValidationError, match="category_id"):
        _expense(category_id=None)


def test_expense_requires_splits():
    with pytest.raises(ValidationError, match="at least one split"):
        _expense(splits=[])


def test_duplicate_split_member_rejected():
    with pytest.raises(ValidationError, match="duplicate member"):
        _expense(
            splits=[
                {"member_id": 1, "share_cents": 5000},
                {"member_id": 1, "share_cents": 5000},
            ]
        )


def test_income_requires_source_and_no_splits():
    with pytest.raises(ValidationError, match="income_source_id"):
        TransactionIn(type="income", amount_cents=5000, occurred_on=date(2026, 9, 1))
    t = TransactionIn(
        type="income",
        amount_cents=5000,
        occurred_on=date(2026, 9, 1),
        income_source_id=1,
    )
    assert t.splits == []

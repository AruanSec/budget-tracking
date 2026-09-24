"""Schema-level integrity tests against real Postgres (deferred trigger)."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Category, Transaction, TransactionSplit, User


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def two_members(db):
    users = []
    for _ in range(2):
        u = User(
            username=f"m_{uuid.uuid4().hex[:10]}",
            display_name="Member",
            password_hash=hash_password("x"),
        )
        db.add(u)
    db.commit()
    users = db.query(User).order_by(User.id.desc()).limit(2).all()
    return users


def _category(db) -> Category:
    c = Category(name=f"cat_{uuid.uuid4().hex[:10]}")
    db.add(c)
    db.commit()
    return c


def _expense(db, member_a, member_b, cat, shares, amount=10000):
    tx = Transaction(
        type="expense",
        amount_cents=amount,
        occurred_on=date(2026, 9, 20),
        category_id=cat.id,
        entered_by=member_a.id,
    )
    for member, share in shares:
        tx.splits.append(TransactionSplit(member_id=member.id, share_cents=share))
    db.add(tx)
    return tx


def test_even_split_commits(db, two_members):
    a, b = two_members
    cat = _category(db)
    _expense(db, a, b, cat, [(a, 5000), (b, 5000)])
    db.commit()  # deferred trigger fires here — must not raise


def test_bad_split_sum_rejected_at_commit(db, two_members):
    a, b = two_members
    cat = _category(db)
    _expense(db, a, b, cat, [(a, 5000), (b, 4000)])  # sums to 9000 != 10000
    with pytest.raises((IntegrityError, DBAPIError)):
        db.commit()


def test_duplicate_member_split_rejected(db, two_members):
    a, _ = two_members
    cat = _category(db)
    _expense(db, a, a, cat, [(a, 5000), (a, 5000)])
    with pytest.raises((IntegrityError, DBAPIError)):
        db.commit()


def test_transaction_type_target_check(db, two_members):
    a, _ = two_members
    cat = _category(db)
    tx = Transaction(
        type="expense",
        amount_cents=100,
        occurred_on=date(2026, 9, 20),
        category_id=None,  # expense without category -> check constraint
        entered_by=a.id,
    )
    db.add(tx)
    with pytest.raises((IntegrityError, DBAPIError)):
        db.commit()

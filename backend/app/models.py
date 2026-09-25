"""SQLAlchemy 2.x models — the full household budget schema.

Money is stored as integer cents (BigInteger) everywhere. No floats.

Key design decision (Phase 0/1): expenses are attributed to members via
`transaction_splits`, never via a member_id on the transaction itself.
A solo expense is one 100% split; a shared expense (rent, groceries) is
split across members. Each member's split share is what consumes their
per-person budget. Split sums are enforced equal to the transaction total
by a deferred DB trigger (see Alembic migration 0001) and by Pydantic
validation at the API layer.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """A household member (design for N, currently 2).

    `role` is 'admin' or 'member'. Bootstrap rule: the first user to
    register or log in when no admin exists claims 'admin' (see
    app.auth.claim_admin_if_none); there must always be at least one
    active admin (enforced by the admin router's guards).
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_user_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Account(Base):
    """A financial account (cash, checking, savings, credit card...)."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    type: Mapped[str] = mapped_column(String(32), default="checking")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Category(Base):
    """Expense category with optional single-level parent (basic hierarchy)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "name", "parent_id", name="uq_category_name_parent",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parent: Mapped["Category | None"] = relationship(remote_side=[id])


class IncomeSource(Base):
    """First-class income entity, attributed to the member receiving it."""

    __tablename__ = "income_sources"
    __table_args__ = (UniqueConstraint("name", "member_id", name="uq_income_source_name_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    member_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    member: Mapped[User] = relationship()


class Transaction(Base):
    """An income or expense event.

    Expenses: category_id required, splits required (>=1, sum == amount).
    Income: income_source_id required, no splits — attributed to the
    income source's member.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_transaction_type"),
        CheckConstraint("amount_cents > 0", name="ck_transaction_amount_positive"),
        CheckConstraint(
            "(type = 'expense' AND category_id IS NOT NULL AND income_source_id IS NULL)"
            " OR (type = 'income' AND income_source_id IS NOT NULL AND category_id IS NULL)",
            name="ck_transaction_type_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(8), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(String(255), default="")
    occurred_on: Mapped[date] = mapped_column(Date, index=True)

    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    income_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("income_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    paid_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    category: Mapped["Category | None"] = relationship()
    income_source: Mapped["IncomeSource | None"] = relationship()
    account: Mapped["Account | None"] = relationship()


class TransactionSplit(Base):
    """One member's share of an expense. Sum of shares == transaction total
    (enforced by deferred trigger `trg_split_sum_check`)."""

    __tablename__ = "transaction_splits"
    __table_args__ = (
        UniqueConstraint("transaction_id", "member_id", name="uq_split_tx_member"),
        CheckConstraint("share_cents > 0", name="ck_split_share_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    share_cents: Mapped[int] = mapped_column(BigInteger)

    transaction: Mapped[Transaction] = relationship(back_populates="splits")
    member: Mapped[User] = relationship()


class Budget(Base):
    """Per-person budget: one line per (member, category, month).

    `month` is always the first day of the month (API-enforced).
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("member_id", "category_id", "month", name="uq_budget_member_category_month"),
        CheckConstraint("amount_cents >= 0", name="ck_budget_amount_nonneg"),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="ck_budget_month_first_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    month: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)

    member: Mapped[User] = relationship()
    category: Mapped[Category] = relationship()


class RecurringRule(Base):
    """Recurring transaction template, including how it splits each month."""

    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_recurring_type"),
        CheckConstraint("amount_cents > 0", name="ck_recurring_amount_positive"),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_recurring_day_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(8))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    day_of_month: Mapped[int] = mapped_column(Integer)

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    income_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("income_sources.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )

    # [{"member_id": 1, "share_pct": 50}, {"member_id": 2, "share_pct": 50}]
    splits: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_due: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

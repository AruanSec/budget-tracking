"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-23

Full household budget schema:
users, accounts, categories, income_sources, transactions,
transaction_splits, budgets, recurring_rules
+ deferred trigger enforcing split sums equal transaction totals.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("type", sa.String(32), nullable=False, server_default="checking"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "name",
            "parent_id",
            name="uq_category_name_parent",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_categories_name", "categories", ["name"])

    op.create_table(
        "income_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["member_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("name", "member_id", name="uq_income_source_name_member"),
    )
    op.create_index("ix_income_sources_member_id", "income_sources", ["member_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("income_source_id", sa.Integer(), nullable=True),
        sa.Column("entered_by", sa.Integer(), nullable=False),
        sa.Column("paid_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["income_source_id"], ["income_sources.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["paid_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "type IN ('income', 'expense')", name="ck_transaction_type"
        ),
        sa.CheckConstraint(
            "amount_cents > 0", name="ck_transaction_amount_positive"
        ),
        sa.CheckConstraint(
            "(type = 'expense' AND category_id IS NOT NULL AND income_source_id IS NULL)"
            " OR (type = 'income' AND income_source_id IS NOT NULL AND category_id IS NULL)",
            name="ck_transaction_type_target",
        ),
    )
    op.create_index("ix_transactions_type", "transactions", ["type"])
    op.create_index("ix_transactions_occurred_on", "transactions", ["occurred_on"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index(
        "ix_transactions_income_source_id", "transactions", ["income_source_id"]
    )

    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("share_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "transaction_id", "member_id", name="uq_split_tx_member"
        ),
        sa.CheckConstraint("share_cents > 0", name="ck_split_share_positive"),
    )
    op.create_index(
        "ix_transaction_splits_transaction_id", "transaction_splits", ["transaction_id"]
    )
    op.create_index(
        "ix_transaction_splits_member_id", "transaction_splits", ["member_id"]
    )

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "member_id", "category_id", "month", name="uq_budget_member_category_month"
        ),
        sa.CheckConstraint("amount_cents >= 0", name="ck_budget_amount_nonneg"),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM month) = 1", name="ck_budget_month_first_day"
        ),
    )
    op.create_index("ix_budgets_member_id", "budgets", ["member_id"])
    op.create_index("ix_budgets_category_id", "budgets", ["category_id"])

    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("income_source_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column(
            "splits",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_due", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["income_source_id"], ["income_sources.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "type IN ('income', 'expense')", name="ck_recurring_type"
        ),
        sa.CheckConstraint(
            "amount_cents > 0", name="ck_recurring_amount_positive"
        ),
        sa.CheckConstraint(
            "day_of_month BETWEEN 1 AND 31", name="ck_recurring_day_range"
        ),
    )

    # --- split-sum integrity: deferred constraint triggers -----------------
    # Deferred so a multi-row split insert is only checked at COMMIT, and
    # cascade deletes (transaction gone) don't false-alarm.
    op.execute(
        """
        CREATE FUNCTION check_split_sum_for_tx() RETURNS trigger AS $$
        DECLARE
            tx_id bigint := COALESCE(NEW.transaction_id, OLD.transaction_id);
            total bigint;
            ssum bigint;
        BEGIN
            SELECT amount_cents INTO total FROM transactions WHERE id = tx_id;
            IF total IS NULL THEN
                RETURN NULL;  -- transaction deleted (cascade); nothing to check
            END IF;
            SELECT COALESCE(SUM(share_cents), 0) INTO ssum
            FROM transaction_splits WHERE transaction_id = tx_id;
            IF ssum <> total THEN
                RAISE EXCEPTION
                    'split sum (%) does not equal transaction total (%) for transaction %',
                    ssum, total, tx_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_split_sum_check
        AFTER INSERT OR UPDATE OR DELETE ON transaction_splits
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_split_sum_for_tx();
        """
    )
    op.execute(
        """
        CREATE FUNCTION check_split_sum_for_amount_change() RETURNS trigger AS $$
        DECLARE
            ssum bigint;
        BEGIN
            IF NEW.type <> 'expense' THEN
                RETURN NULL;
            END IF;
            SELECT COALESCE(SUM(share_cents), 0) INTO ssum
            FROM transaction_splits WHERE transaction_id = NEW.id;
            IF ssum <> NEW.amount_cents THEN
                RAISE EXCEPTION
                    'split sum (%) does not equal new transaction total (%) for transaction %',
                    ssum, NEW.amount_cents, NEW.id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_amount_change_split_check
        AFTER UPDATE OF amount_cents ON transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_split_sum_for_amount_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_amount_change_split_check ON transactions;")
    op.execute("DROP FUNCTION IF EXISTS check_split_sum_for_amount_change();")
    op.execute("DROP TRIGGER IF EXISTS trg_split_sum_check ON transaction_splits;")
    op.execute("DROP FUNCTION IF EXISTS check_split_sum_for_tx();")
    for table in (
        "recurring_rules",
        "budgets",
        "transaction_splits",
        "transactions",
        "income_sources",
        "categories",
        "accounts",
        "users",
    ):
        op.drop_table(table)

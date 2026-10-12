"""Revoke sessions and enforce split integrity for every transaction change."""
from alembic import op
import sqlalchemy as sa

revision = "0003_integrity_and_sessions"
down_revision = "0002_user_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    # Existing historical rows are left intact; new writes must satisfy the invariant.
    op.execute("""
    CREATE FUNCTION validate_transaction_splits(tx_id integer) RETURNS void AS $$
    DECLARE total bigint; kind varchar; ssum numeric; split_count bigint;
    BEGIN
        SELECT amount_cents, type INTO total, kind FROM transactions
        WHERE id = tx_id FOR UPDATE;
        IF NOT FOUND THEN RETURN; END IF;
        SELECT COALESCE(SUM(share_cents), 0), COUNT(*) INTO ssum, split_count
        FROM transaction_splits WHERE transaction_id = tx_id;
        IF (kind = 'expense' AND (split_count = 0 OR ssum <> total))
            OR (kind = 'income' AND split_count <> 0) THEN
            RAISE EXCEPTION 'invalid splits for transaction %', tx_id
                USING ERRCODE = '23514';
        END IF;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION check_split_sum_for_tx() RETURNS trigger AS $$
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            PERFORM validate_transaction_splits(OLD.transaction_id);
        END IF;
        IF TG_OP <> 'DELETE' THEN
            PERFORM validate_transaction_splits(NEW.transaction_id);
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION check_split_sum_for_amount_change() RETURNS trigger AS $$
    BEGIN
        PERFORM validate_transaction_splits(NEW.id);
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER trg_amount_change_split_check ON transactions;
    CREATE CONSTRAINT TRIGGER trg_amount_change_split_check
    AFTER INSERT OR UPDATE ON transactions DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_split_sum_for_amount_change();
    """)


def downgrade():
    op.execute("""
    DROP TRIGGER trg_amount_change_split_check ON transactions;
    CREATE OR REPLACE FUNCTION check_split_sum_for_tx() RETURNS trigger AS $$
    DECLARE tx_id bigint := COALESCE(NEW.transaction_id, OLD.transaction_id);
        total bigint; ssum bigint;
    BEGIN
        SELECT amount_cents INTO total FROM transactions WHERE id = tx_id;
        IF total IS NULL THEN RETURN NULL; END IF;
        SELECT COALESCE(SUM(share_cents), 0) INTO ssum
        FROM transaction_splits WHERE transaction_id = tx_id;
        IF ssum <> total THEN RAISE EXCEPTION 'invalid split sum for %', tx_id; END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    CREATE OR REPLACE FUNCTION check_split_sum_for_amount_change() RETURNS trigger AS $$
    DECLARE ssum bigint;
    BEGIN
        IF NEW.type <> 'expense' THEN RETURN NULL; END IF;
        SELECT COALESCE(SUM(share_cents), 0) INTO ssum
        FROM transaction_splits WHERE transaction_id = NEW.id;
        IF ssum <> NEW.amount_cents THEN RAISE EXCEPTION 'invalid split sum for %', NEW.id; END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    CREATE CONSTRAINT TRIGGER trg_amount_change_split_check
    AFTER UPDATE OF amount_cents ON transactions DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_split_sum_for_amount_change();
    DROP FUNCTION validate_transaction_splits(integer);
    """)
    op.drop_column("users", "token_version")

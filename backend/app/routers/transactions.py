from datetime import date
import json
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..models import Account, Category, IncomeSource, Transaction, TransactionSplit, User
from ..schemas import TransactionIn, TransactionOut, TransactionUpdate
from ..util import next_month, parse_month

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

Authed = Depends(get_current_user)


def _check_fks(db: Session, data: TransactionIn) -> None:
    """Validate referenced ids exist so we return 422, never a raw IntegrityError."""
    checks: list[tuple[str, int | None, type, str]] = [
        ("account", data.account_id, Account, "account not found"),
        ("category", data.category_id, Category, "category not found"),
        ("income_source", data.income_source_id, IncomeSource, "income source not found"),
        ("paid_by", data.paid_by, User, "paid_by member not found"),
    ]
    for _, value, model, message in checks:
        if value is not None and db.get(model, value) is None:
            raise HTTPException(status_code=422, detail=message)
    for split in data.splits:
        if db.get(User, split.member_id) is None:
            raise HTTPException(status_code=422, detail=f"split member {split.member_id} not found")


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    _: User = Authed,
    db: Session = Depends(get_db),
    month: str | None = None,
    member_id: int | None = None,
    category_id: int | None = None,
    type: str | None = Query(default=None, pattern="^(income|expense)$"),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Transaction]:
    stmt = select(Transaction).options(selectinload(Transaction.splits))
    if month is not None:
        start = parse_month(month)
        stmt = stmt.where(Transaction.occurred_on >= start, Transaction.occurred_on < next_month(start))
    if from_ is not None:
        stmt = stmt.where(Transaction.occurred_on >= from_)
    if to is not None:
        stmt = stmt.where(Transaction.occurred_on <= to)
    if type is not None:
        stmt = stmt.where(Transaction.type == type)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if member_id is not None:
        # expenses: member has a split; income: member owns the income source
        stmt = stmt.where(
            or_(
                Transaction.splits.any(TransactionSplit.member_id == member_id),
                Transaction.income_source.has(IncomeSource.member_id == member_id),
            )
        )
    stmt = (
        stmt.order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    body: TransactionIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Transaction:
    _check_fks(db, body)
    tx = Transaction(
        type=body.type,
        amount_cents=body.amount_cents,
        currency=body.currency,
        description=body.description,
        occurred_on=body.occurred_on,
        account_id=body.account_id,
        category_id=body.category_id,
        income_source_id=body.income_source_id,
        entered_by=current.id,  # server-set, never client-supplied
        paid_by=body.paid_by,
    )
    for split in body.splits:
        tx.splits.append(
            TransactionSplit(member_id=split.member_id, share_cents=split.share_cents)
        )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int,
    body: TransactionUpdate,
    _: User = Authed,
    db: Session = Depends(get_db),
) -> Transaction:
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")

    changes = body.model_dump(exclude_unset=True)
    # Merge current state + changes and re-run the full cross-field
    # validation (split sums, category/income-source rules) via TransactionIn.
    try:
        merged = TransactionIn(
            type=cast(Literal["income", "expense"], tx.type),  # immutable
            amount_cents=changes.get("amount_cents", tx.amount_cents),
            occurred_on=changes.get("occurred_on", tx.occurred_on),
            description=changes.get("description", tx.description),
            currency=tx.currency,
            account_id=changes.get("account_id", tx.account_id) if "account_id" in changes else tx.account_id,
            category_id=changes.get("category_id", tx.category_id) if "category_id" in changes else tx.category_id,
            income_source_id=(
                changes.get("income_source_id", tx.income_source_id)
                if "income_source_id" in changes
                else tx.income_source_id
            ),
            paid_by=changes.get("paid_by", tx.paid_by) if "paid_by" in changes else tx.paid_by,
            splits=(
                body.splits
                if body.splits is not None
                else [
                    {"member_id": s.member_id, "share_cents": s.share_cents}  # type: ignore[misc]
                    for s in tx.splits
                ]
            ),
        )
    except ValidationError as exc:
        # exc.json() serializes dates/inputs safely; Starlette's encoder can't.
        raise HTTPException(status_code=422, detail=json.loads(exc.json()))
    _check_fks(db, merged)

    tx.amount_cents = merged.amount_cents
    tx.occurred_on = merged.occurred_on
    tx.description = merged.description
    tx.account_id = merged.account_id
    tx.category_id = merged.category_id
    tx.income_source_id = merged.income_source_id
    tx.paid_by = merged.paid_by
    if body.splits is not None:
        tx.splits.clear()
        # Flush the DELETEs before inserting the replacement set — otherwise
        # the unit of work may INSERT first and trip uq_split_tx_member when
        # the same member appears in old and new splits.
        db.flush()
        for split in merged.splits:
            tx.splits.append(
                TransactionSplit(member_id=split.member_id, share_cents=split.share_cents)
            )
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, _: User = Authed, db: Session = Depends(get_db)) -> None:
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    db.delete(tx)  # splits cascade
    db.commit()

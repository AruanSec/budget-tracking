from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Budget, Category, User
from ..schemas import BudgetIn, BudgetOut
from ..util import parse_month

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

Authed = Depends(get_current_user)


@router.get("", response_model=list[BudgetOut])
def list_budgets(
    month: str,
    member_id: int | None = None,
    _: User = Authed,
    db: Session = Depends(get_db),
) -> list[Budget]:
    start = parse_month(month)
    stmt = select(Budget).where(Budget.month == start)
    if member_id is not None:
        stmt = stmt.where(Budget.member_id == member_id)
    return list(db.scalars(stmt.order_by(Budget.member_id, Budget.category_id)))


@router.put("", response_model=BudgetOut)
def upsert_budget(body: BudgetIn, _: User = Authed, db: Session = Depends(get_db)) -> Budget:
    """Idempotent upsert keyed on (member, category, month)."""
    if db.get(User, body.member_id) is None:
        raise HTTPException(status_code=422, detail="member not found")
    if db.get(Category, body.category_id) is None:
        raise HTTPException(status_code=422, detail="category not found")
    budget = db.scalar(
        select(Budget).where(
            Budget.member_id == body.member_id,
            Budget.category_id == body.category_id,
            Budget.month == body.month,
        )
    )
    if budget is None:
        budget = Budget(
            member_id=body.member_id,
            category_id=body.category_id,
            month=body.month,
            amount_cents=body.amount_cents,
        )
        db.add(budget)
    else:
        budget.amount_cents = body.amount_cents
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, _: User = Authed, db: Session = Depends(get_db)) -> None:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="budget not found")
    db.delete(budget)
    db.commit()

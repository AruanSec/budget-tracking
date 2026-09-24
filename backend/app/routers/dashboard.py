"""Dashboard read model: combined household analysis for a month.

Member expense figures are sums of *split shares* (shared costs already
divided). Member income figures come from the income source's member.
Household figures are sums over all members.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Budget, Category, IncomeSource, Transaction, TransactionSplit, User
from ..schemas import (
    CategorySummary,
    DashboardSummary,
    HouseholdSummary,
    MemberSpent,
    MemberSummary,
    TrendPoint,
)
from ..util import next_month, parse_month, pct

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

Authed = Depends(get_current_user)


def _month_range(month: str) -> tuple[date, date]:
    start = parse_month(month)
    return start, next_month(start)


@router.get("/summary", response_model=DashboardSummary)
def summary(month: str, _: User = Authed, db: Session = Depends(get_db)) -> DashboardSummary:
    start, end = _month_range(month)
    in_month = (Transaction.occurred_on >= start) & (Transaction.occurred_on < end)

    members = list(db.scalars(select(User).where(User.is_active).order_by(User.id)))

    income_rows = db.execute(
        select(IncomeSource.member_id, func.coalesce(func.sum(Transaction.amount_cents), 0))
        .join(Transaction, Transaction.income_source_id == IncomeSource.id)
        .where(Transaction.type == "income", in_month)
        .group_by(IncomeSource.member_id)
    ).all()
    income_by_member = dict(income_rows)

    expense_rows = db.execute(
        select(TransactionSplit.member_id, func.coalesce(func.sum(TransactionSplit.share_cents), 0))
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .where(Transaction.type == "expense", in_month)
        .group_by(TransactionSplit.member_id)
    ).all()
    expense_by_member = dict(expense_rows)

    budget_rows = db.execute(
        select(Budget.member_id, func.coalesce(func.sum(Budget.amount_cents), 0))
        .where(Budget.month == start)
        .group_by(Budget.member_id)
    ).all()
    budget_by_member = dict(budget_rows)

    member_summaries = [
        MemberSummary(
            member_id=m.id,
            display_name=m.display_name,
            income_cents=income_by_member.get(m.id, 0),
            expense_cents=expense_by_member.get(m.id, 0),
            budget_cents=budget_by_member.get(m.id, 0),
            budget_used_pct=pct(expense_by_member.get(m.id, 0), budget_by_member.get(m.id, 0)),
        )
        for m in members
    ]

    total_income = sum(income_by_member.values())
    total_expense = sum(expense_by_member.values())
    total_budget = sum(budget_by_member.values())
    household = HouseholdSummary(
        income_cents=total_income,
        expense_cents=total_expense,
        net_cents=total_income - total_expense,
        budget_cents=total_budget,
        budget_used_pct=pct(total_expense, total_budget),
    )

    # ---- by category ----
    cat_spend_rows = db.execute(
        select(
            Transaction.category_id,
            TransactionSplit.member_id,
            func.sum(TransactionSplit.share_cents),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(Transaction.type == "expense", in_month)
        .group_by(Transaction.category_id, TransactionSplit.member_id)
    ).all()
    cat_budget_rows = db.execute(
        select(Budget.category_id, func.sum(Budget.amount_cents))
        .where(Budget.month == start)
        .group_by(Budget.category_id)
    ).all()
    budget_by_category = dict(cat_budget_rows)

    spent_by_category: dict[int | None, int] = {}
    per_member_by_category: dict[int | None, list[MemberSpent]] = {}
    for category_id, member_id, amount in cat_spend_rows:
        spent_by_category[category_id] = spent_by_category.get(category_id, 0) + amount
        per_member_by_category.setdefault(category_id, []).append(
            MemberSpent(member_id=member_id, spent_cents=amount)
        )

    category_ids = set(spent_by_category) | set(budget_by_category)
    names: dict[int | None, str] = {None: "Uncategorized"}
    if category_ids - {None}:
        name_rows = db.execute(
            select(Category.id, Category.name).where(Category.id.in_(category_ids - {None}))
        ).all()
        names.update({cid: name for cid, name in name_rows})

    by_category = [
        CategorySummary(
            category_id=cid,
            name=names.get(cid, f"#{cid}"),
            spent_cents=spent_by_category.get(cid, 0),
            budget_cents=budget_by_category.get(cid, 0),
            per_member=sorted(
                per_member_by_category.get(cid, []), key=lambda m: m.member_id
            ),
        )
        for cid in category_ids
    ]
    by_category.sort(key=lambda c: c.spent_cents, reverse=True)

    return DashboardSummary(
        month=f"{start.year:04d}-{start.month:02d}",
        household=household,
        members=member_summaries,
        by_category=by_category,
    )


@router.get("/trend", response_model=list[TrendPoint])
def trend(
    months: int = Query(default=6, ge=1, le=36),
    _: User = Authed,
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    today = date.today()
    current_start = date(today.year, today.month, 1)
    starts: list[date] = []
    cursor = current_start
    for _ in range(months):
        starts.append(cursor)
        # walk backwards one month
        cursor = date(cursor.year - 1, 12, 1) if cursor.month == 1 else date(cursor.year, cursor.month - 1, 1)
    starts.reverse()
    start, end = starts[0], next_month(starts[-1])

    # Single expression instance shared by SELECT and GROUP BY so Postgres
    # sees an exact match (rebuilding it can render a mismatching expression).
    month_trunc = func.date_trunc("month", Transaction.occurred_on)

    rows = db.execute(
        select(month_trunc, Transaction.type, func.sum(Transaction.amount_cents))
        .where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(month_trunc, Transaction.type)
    ).all()

    filled: dict[str, dict[str, int]] = {
        f"{d.year:04d}-{d.month:02d}": {"income": 0, "expense": 0} for d in starts
    }
    for month_ts, tx_type, amount in rows:
        key = f"{month_ts.year:04d}-{month_ts.month:02d}"
        if key in filled:
            filled[key][tx_type] = int(amount)

    return [
        TrendPoint(month=key, income_cents=v["income"], expense_cents=v["expense"])
        for key, v in filled.items()
    ]

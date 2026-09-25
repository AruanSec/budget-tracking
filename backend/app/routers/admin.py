"""Admin portal API — user management and household stats.

Only reachable with role='admin' (JWT required). Guards that keep the
household from locking itself out:
  - an admin cannot deactivate, demote, or delete themselves;
  - the last active admin cannot be demoted or deactivated by anyone;
  - a user whose transactions exist cannot be hard-deleted (409) —
    deactivate them instead, history keeps its attribution.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..db import get_db
from ..models import Account, Budget, Category, IncomeSource, Transaction, User
from ..schemas import (
    AdminStats,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    PasswordSetRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return db.scalar(stmt)


@router.get("/stats", response_model=AdminStats)
def stats(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminStats:
    month_start = func.date_trunc("month", func.now())
    return AdminStats(
        users_total=_count(db, User),
        users_active=_count(db, User, User.is_active.is_(True)),
        admins_active=_count(db, User, User.role == "admin", User.is_active.is_(True)),
        accounts_total=_count(db, Account),
        categories_total=_count(db, Category),
        income_sources_total=_count(db, IncomeSource),
        budgets_total=_count(db, Budget),
        transactions_total=_count(db, Transaction),
        transactions_this_month_cents=int(
            db.scalar(
                select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                    Transaction.occurred_on >= month_start
                )
            )
        ),
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(
    body: AdminUserCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )
    user = User(
        username=body.username,
        display_name=(body.display_name or "").strip() or body.username.capitalize(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    target = _get_user(db, user_id)
    is_self = target.id == admin.id

    if body.is_active is not None and body.is_active != target.is_active:
        if is_self:
            raise HTTPException(400, "You cannot deactivate yourself — ask another admin")
        if target.role == "admin" and not body.is_active and _last_active_admin(db, target):
            raise HTTPException(400, "Cannot deactivate the last active admin")
        target.is_active = body.is_active

    if body.role is not None and body.role != target.role:
        if is_self:
            raise HTTPException(400, "You cannot change your own role")
        if target.role == "admin" and body.role == "member" and _last_active_admin(db, target):
            raise HTTPException(400, "Cannot demote the last active admin")
        target.role = body.role

    if body.display_name is not None:
        target.display_name = body.display_name.strip()

    db.commit()
    return target


def _last_active_admin(db: Session, target: User) -> bool:
    """True if `target` is the only active admin left."""
    if target.role != "admin" or not target.is_active:
        return False
    others = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.is_active.is_(True), User.id != target.id)
    )
    return others == 0


@router.post("/users/{user_id}/password", status_code=204)
def reset_password(
    user_id: int,
    body: PasswordSetRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Admin-set password (lost-password recovery). Tokens stay valid
    until expiry; the user should log in again after a reset."""
    target = _get_user(db, user_id)
    target.password_hash = hash_password(body.password)
    db.commit()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    target = _get_user(db, user_id)
    if target.id == admin.id:
        raise HTTPException(400, "You cannot delete yourself")
    if target.role == "admin" and target.is_active and _last_active_admin(db, target):
        raise HTTPException(400, "Cannot delete the last active admin")
    if _count(db, Transaction, Transaction.entered_by == target.id):
        raise HTTPException(
            409,
            "User has transactions entered by them — deactivate instead to keep history",
        )
    try:
        db.delete(target)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "User is still referenced by data — deactivate instead"
        ) from None

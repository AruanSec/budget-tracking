from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Account, User
from ..schemas import AccountIn, AccountOut, AccountUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

Authed = Depends(get_current_user)


@router.get("", response_model=list[AccountOut])
def list_accounts(_: User = Authed, db: Session = Depends(get_db)) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.name)))


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, _: User = Authed, db: Session = Depends(get_db)) -> Account:
    account = Account(name=body.name, type=body.type)
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"account {body.name!r} already exists")
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountUpdate, _: User = Authed, db: Session = Depends(get_db)
) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="account name already in use")
    db.refresh(account)
    return account

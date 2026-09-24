from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import IncomeSource, User
from ..schemas import IncomeSourceIn, IncomeSourceOut, IncomeSourceUpdate

router = APIRouter(prefix="/api/income-sources", tags=["income-sources"])

Authed = Depends(get_current_user)


@router.get("", response_model=list[IncomeSourceOut])
def list_income_sources(
    active: bool | None = None, _: User = Authed, db: Session = Depends(get_db)
) -> list[IncomeSource]:
    stmt = select(IncomeSource).order_by(IncomeSource.name)
    if active is not None:
        stmt = stmt.where(IncomeSource.active == active)
    return list(db.scalars(stmt))


@router.post("", response_model=IncomeSourceOut, status_code=201)
def create_income_source(
    body: IncomeSourceIn, _: User = Authed, db: Session = Depends(get_db)
) -> IncomeSource:
    if db.get(User, body.member_id) is None:
        raise HTTPException(status_code=422, detail="member not found")
    source = IncomeSource(name=body.name, member_id=body.member_id, active=body.active)
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="member already has an income source with this name")
    db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=IncomeSourceOut)
def update_income_source(
    source_id: int, body: IncomeSourceUpdate, _: User = Authed, db: Session = Depends(get_db)
) -> IncomeSource:
    source = db.get(IncomeSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="income source not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="member already has an income source with this name")
    db.refresh(source)
    return source

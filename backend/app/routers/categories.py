from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Category, Transaction, User
from ..schemas import CategoryIn, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])

Authed = Depends(get_current_user)


@router.get("", response_model=list[CategoryOut])
def list_categories(_: User = Authed, db: Session = Depends(get_db)) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name, Category.id)))


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, _: User = Authed, db: Session = Depends(get_db)) -> Category:
    if body.parent_id is not None:
        parent = db.get(Category, body.parent_id)
        if parent is None:
            raise HTTPException(status_code=422, detail="parent category not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=422, detail="only one level of hierarchy is allowed")
    category = Category(name=body.name, parent_id=body.parent_id)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="category already exists at this level")
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryUpdate, _: User = Authed, db: Session = Depends(get_db)
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    changes = body.model_dump(exclude_unset=True)
    if "parent_id" in changes and changes["parent_id"] is not None:
        if changes["parent_id"] == category_id:
            raise HTTPException(status_code=422, detail="category cannot be its own parent")
        parent = db.get(Category, changes["parent_id"])
        if parent is None:
            raise HTTPException(status_code=422, detail="parent category not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=422, detail="only one level of hierarchy is allowed")
        has_children = db.scalar(
            select(func.count()).select_from(Category).where(Category.parent_id == category_id)
        )
        if has_children:
            raise HTTPException(
                status_code=422, detail="category has children; cannot become a subcategory"
            )
    for field, value in changes.items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="category already exists at this level")
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, _: User = Authed, db: Session = Depends(get_db)) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    used = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    )
    if used:
        # The DB requires every expense to keep a category (financial history
        # must stay categorized), so refuse instead of SET NULL.
        raise HTTPException(
            status_code=409,
            detail=f"category is used by {used} transaction(s); reassign them first",
        )
    db.delete(category)  # budgets cascade
    db.commit()

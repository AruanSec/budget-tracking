from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import UserOut

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("", response_model=list[UserOut])
def list_members(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[User]:
    return list(db.scalars(select(User).where(User.is_active).order_by(User.id)))

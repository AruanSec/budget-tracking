from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..auth import claim_admin_if_none, create_token, get_current_user, hash_password, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Self-service signup. New users land as 'member' — except on a
    household with no admin yet, where the first registrant becomes the
    admin (bootstrap). Registration is only reachable from the tailnet."""
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    display = (body.display_name or "").strip() or body.username.capitalize()
    user = User(
        username=body.username,
        display_name=display,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already taken") from None
    claim_admin_if_none(db, user)
    return TokenResponse(access_token=create_token(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    claim_admin_if_none(db, user)
    return TokenResponse(access_token=create_token(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current

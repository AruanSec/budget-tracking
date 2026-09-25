"""Bootstrap the household: create initial users from the environment.

Usage:
    BUDGET_SEED_USERS='alice:secretpw:Alice:admin,bob:otherpw:Bob' python -m app.seed

Format per user: username:password[:Display Name[:role]]  (display name
defaults to the capitalized username, role to 'member' — but the first
user ever to log in on an admin-less install claims 'admin' anyway).
Idempotent — existing users are skipped. This is a one-time household
bootstrap, not a signup flow; self-service registration is at
POST /api/auth/register.
"""

import os
import sys

from .auth import hash_password
from .db import SessionLocal
from .models import User


def seed() -> None:
    raw = os.environ.get("BUDGET_SEED_USERS", "")
    if not raw.strip():
        print("BUDGET_SEED_USERS not set; nothing to do.")
        return

    db = SessionLocal()
    try:
        for entry in raw.split(","):
            parts = entry.strip().split(":")
            if len(parts) < 2:
                print(f"skipping malformed entry: {entry!r}")
                continue
            username, password = parts[0].strip(), parts[1]
            display = parts[2].strip() if len(parts) > 2 and parts[2].strip() else username.capitalize()
            role = parts[3].strip() if len(parts) > 3 and parts[3].strip() in ("admin", "member") else "member"
            if db.query(User).filter(User.username == username).first():
                print(f"user {username!r} already exists; skipping")
                continue
            db.add(
                User(
                    username=username,
                    display_name=display,
                    password_hash=hash_password(password),
                    role=role,
                )
            )
            print(f"created user {username!r}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    sys.exit(0)

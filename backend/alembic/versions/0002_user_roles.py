"""add role to users

Revision ID: 0002_user_roles
Revises: 0001_initial
Create Date: 2026-09-25

Adds users.role ('admin' | 'member', default 'member') with a check
constraint. Bootstrap: if the table has users but no admin yet, the
earliest-created user is promoted so an upgraded install has an owner
immediately; for a fresh install the first registration/login claims
admin at runtime (app.auth.claim_admin_if_none).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_user_roles"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
    )
    op.create_check_constraint("ck_user_role", "users", "role IN ('admin', 'member')")
    op.execute(
        """
        UPDATE users SET role = 'admin'
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin')
          AND id = (SELECT min(id) FROM users)
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.drop_column("users", "role")

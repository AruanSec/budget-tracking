from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- auth ----------


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[\w.-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str


# ---------- transactions ----------


class SplitIn(BaseModel):
    member_id: int
    share_cents: int = Field(gt=0)


class TransactionIn(BaseModel):
    type: Literal["income", "expense"]
    amount_cents: int = Field(gt=0)
    occurred_on: date
    description: str = Field(default="", max_length=255)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    account_id: int | None = None
    category_id: int | None = None
    income_source_id: int | None = None
    paid_by: int | None = None
    splits: list[SplitIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_type_rules(self) -> "TransactionIn":
        if self.type == "expense":
            if self.category_id is None:
                raise ValueError("expense requires category_id")
            if self.income_source_id is not None:
                raise ValueError("expense must not set income_source_id")
            if not self.splits:
                raise ValueError("expense requires at least one split")
            members = [s.member_id for s in self.splits]
            if len(members) != len(set(members)):
                raise ValueError("duplicate member in splits")
            total = sum(s.share_cents for s in self.splits)
            if total != self.amount_cents:
                raise ValueError(
                    f"split shares sum to {total}, must equal amount {self.amount_cents}"
                )
        else:  # income
            if self.income_source_id is None:
                raise ValueError("income requires income_source_id")
            if self.category_id is not None:
                raise ValueError("income must not set category_id")
            if self.splits:
                raise ValueError(
                    "income takes no splits; it is attributed to the "
                    "income source's member"
                )
        return self


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    share_cents: int


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    amount_cents: int
    currency: str
    description: str
    occurred_on: date
    account_id: int | None
    category_id: int | None
    income_source_id: int | None
    entered_by: int
    paid_by: int | None
    created_at: object
    splits: list[SplitOut] = []


# ---------- budgets ----------


class BudgetIn(BaseModel):
    member_id: int
    category_id: int
    month: date
    amount_cents: int = Field(ge=0)

    @model_validator(mode="after")
    def month_must_be_first_day(self) -> "BudgetIn":
        if self.month.day != 1:
            raise ValueError("month must be the first day of the month")
        return self


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    category_id: int
    month: date
    amount_cents: int


# ---------- categories / income sources / accounts ----------


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class IncomeSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    member_id: int
    active: bool = True


class IncomeSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    member_id: int
    active: bool


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: str = Field(default="checking", max_length=32)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    archived: bool


# ---------- partial updates (PATCH) ----------

class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None, max_length=32)
    archived: bool | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: int | None = None


class IncomeSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


class TransactionUpdate(BaseModel):
    """Partial update. `type` is immutable — delete and re-enter instead.
    If `splits` is given, it replaces the whole set (must sum to the
    effective amount)."""

    amount_cents: int | None = Field(default=None, gt=0)
    occurred_on: date | None = None
    description: str | None = Field(default=None, max_length=255)
    account_id: int | None = None
    category_id: int | None = None
    income_source_id: int | None = None
    paid_by: int | None = None
    splits: list[SplitIn] | None = None


# ---------- dashboard ----------

class MemberSpent(BaseModel):
    member_id: int
    spent_cents: int


class CategorySummary(BaseModel):
    category_id: int | None
    name: str
    spent_cents: int
    budget_cents: int
    per_member: list[MemberSpent] = []


class HouseholdSummary(BaseModel):
    income_cents: int
    expense_cents: int
    net_cents: int
    budget_cents: int
    budget_used_pct: float | None


class MemberSummary(BaseModel):
    member_id: int
    display_name: str
    income_cents: int
    expense_cents: int
    budget_cents: int
    budget_used_pct: float | None


class DashboardSummary(BaseModel):
    month: str  # YYYY-MM
    household: HouseholdSummary
    members: list[MemberSummary]
    by_category: list[CategorySummary]


class TrendPoint(BaseModel):
    month: str  # YYYY-MM
    income_cents: int
    expense_cents: int


# ---------- admin ----------


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: object


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[\w.-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    role: Literal["admin", "member"] = "member"


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None


class PasswordSetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    admins_active: int
    accounts_total: int
    categories_total: int
    income_sources_total: int
    budgets_total: int
    transactions_total: int
    transactions_this_month_cents: int

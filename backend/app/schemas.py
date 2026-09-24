from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- auth ----------


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str


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

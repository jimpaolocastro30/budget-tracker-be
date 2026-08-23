from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.db.enums import AccountType
from app.schemas.common import ORMModel


class AccountCreate(ORMModel):
    name: str = Field(..., min_length=1, max_length=255)
    account_type: AccountType
    currency: str = Field(..., min_length=3, max_length=3)
    opening_balance: str = Field(default="0.00", pattern=r"^-?\d+(\.\d{1,2})?$")
    description: str | None = None
    is_active: bool = True


class AccountUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    account_type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = None
    is_active: bool | None = None


class AccountResponse(ORMModel):
    id: UUID
    name: str
    account_type: AccountType
    currency: str
    opening_balance: str
    description: str | None
    is_active: bool
    created_at: datetime


class AccountBalanceResponse(ORMModel):
    account_id: UUID
    currency: str
    opening_balance: str
    total_income: str
    total_expenses: str
    adjustments: str
    current_balance: str

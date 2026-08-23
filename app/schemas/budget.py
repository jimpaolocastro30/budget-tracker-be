from datetime import date
from uuid import UUID

from pydantic import Field

from app.db.enums import BudgetStatus, PeriodType
from app.schemas.common import ORMModel


class BudgetCreate(ORMModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_id: UUID
    amount_limit: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")
    period_type: PeriodType
    start_date: date
    end_date: date | None = None
    account_id: UUID | None = None
    alert_threshold: str = Field(default="75.00", pattern=r"^\d+(\.\d{1,2})?$")


class BudgetUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: UUID | None = None
    amount_limit: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,2})?$")
    period_type: PeriodType | None = None
    start_date: date | None = None
    end_date: date | None = None
    account_id: UUID | None = None
    alert_threshold: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,2})?$")
    is_active: bool | None = None


class BudgetResponse(ORMModel):
    id: UUID
    name: str
    category_id: UUID
    account_id: UUID | None
    amount_limit: str
    period_type: PeriodType
    start_date: date
    end_date: date | None
    alert_threshold: str
    is_active: bool


class BudgetSummaryResponse(ORMModel):
    budget_id: UUID
    budget_name: str
    period_start: date
    period_end: date
    budget_limit: str
    actual_spending: str
    remaining_amount: str
    usage_percentage: str
    status: BudgetStatus

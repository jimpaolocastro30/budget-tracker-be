from datetime import date
from uuid import UUID

from pydantic import Field

from app.db.enums import TransactionType
from app.schemas.common import ORMModel
from app.schemas.transaction import TransactionResponse


class DashboardResponse(ORMModel):
    total_balance: str
    total_income: str
    total_expenses: str
    net_cash_flow: str
    budget_utilization_percentage: str
    top_spending_categories: list[dict[str, str]]
    recent_transactions: list[TransactionResponse]
    upcoming_recurring_count: int


class SpendingReportItem(ORMModel):
    group_key: str
    total_amount: str
    transaction_count: int


class SpendingReportResponse(ORMModel):
    group_by: str
    period_start: date
    period_end: date
    items: list[SpendingReportItem]


class CashFlowReportResponse(ORMModel):
    period_start: date
    period_end: date
    total_income: str
    total_expenses: str
    net_cash_flow: str


class ExportRequest(ORMModel):
    format: str = Field(default="json", pattern="^(json|csv)$")

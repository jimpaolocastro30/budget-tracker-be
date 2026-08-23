from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.core.exceptions import AppError
from app.db.enums import BudgetStatus, Frequency, PeriodType


def format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


def parse_decimal(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except Exception as exc:
        raise AppError("INVALID_AMOUNT", "Invalid decimal value.", status_code=422) from exc
    if amount <= 0:
        raise AppError("INVALID_AMOUNT", "Amount must be greater than zero.", status_code=422)
    return amount


def get_budget_period(budget, reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    start = budget.start_date
    end = budget.end_date

    if budget.period_type == PeriodType.CUSTOM:
        if not end:
            end = ref
        return start, end

    if budget.period_type == PeriodType.WEEKLY:
        period_start = ref - timedelta(days=ref.weekday())
        period_end = period_start + timedelta(days=6)
    elif budget.period_type == PeriodType.MONTHLY:
        period_start = ref.replace(day=1)
        period_end = (period_start + relativedelta(months=1)) - timedelta(days=1)
    elif budget.period_type == PeriodType.QUARTERLY:
        quarter = (ref.month - 1) // 3
        period_start = date(ref.year, quarter * 3 + 1, 1)
        period_end = (period_start + relativedelta(months=3)) - timedelta(days=1)
    elif budget.period_type == PeriodType.YEARLY:
        period_start = date(ref.year, 1, 1)
        period_end = date(ref.year, 12, 31)
    else:
        period_start = start
        period_end = end or ref

    if start > period_start:
        period_start = start
    if end and end < period_end:
        period_end = end

    return period_start, period_end


def calculate_budget_status(
    usage_percentage: Decimal,
    alert_threshold: Decimal,
    is_active: bool,
) -> BudgetStatus:
    if not is_active:
        return BudgetStatus.CLOSED
    if usage_percentage >= Decimal("100"):
        return BudgetStatus.EXCEEDED
    if usage_percentage >= alert_threshold:
        return BudgetStatus.WARNING
    return BudgetStatus.ON_TRACK


def next_run_date(current: date, frequency: Frequency) -> date:
    if frequency == Frequency.DAILY:
        return current + timedelta(days=1)
    if frequency == Frequency.WEEKLY:
        return current + timedelta(weeks=1)
    if frequency == Frequency.MONTHLY:
        return current + relativedelta(months=1)
    if frequency == Frequency.QUARTERLY:
        return current + relativedelta(months=3)
    return current + relativedelta(years=1)

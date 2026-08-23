import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.enums import TransactionType
from app.db.models.budget import Budget
from app.db.models.transaction import Transaction


class BudgetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, budget_id: uuid.UUID, user_id: uuid.UUID) -> Budget | None:
        stmt = select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
        return self.db.scalar(stmt)

    def list_by_user(self, user_id: uuid.UUID, include_inactive: bool = False) -> list[Budget]:
        stmt = select(Budget).where(Budget.user_id == user_id)
        if not include_inactive:
            stmt = stmt.where(Budget.is_active.is_(True))
        stmt = stmt.order_by(Budget.start_date.desc())
        return list(self.db.scalars(stmt))

    def create(self, budget: Budget) -> Budget:
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def update(self, budget: Budget) -> Budget:
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def calculate_spending(
        self,
        budget: Budget,
        period_start: date,
        period_end: date,
    ) -> Decimal:
        filters = [
            Transaction.user_id == budget.user_id,
            Transaction.category_id == budget.category_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.is_deleted.is_(False),
            Transaction.transaction_date >= period_start,
            Transaction.transaction_date <= period_end,
        ]
        if budget.account_id:
            filters.append(Transaction.account_id == budget.account_id)

        total = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(and_(*filters))
        )
        return Decimal(total or 0)

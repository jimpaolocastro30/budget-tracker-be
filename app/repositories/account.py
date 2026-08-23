import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import TransactionType
from app.db.models.account import Account
from app.db.models.transaction import Transaction


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, account_id: uuid.UUID, user_id: uuid.UUID) -> Account | None:
        stmt = select(Account).where(Account.id == account_id, Account.user_id == user_id)
        return self.db.scalar(stmt)

    def list_by_user(self, user_id: uuid.UUID, include_inactive: bool = False) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        if not include_inactive:
            stmt = stmt.where(Account.is_active.is_(True))
        stmt = stmt.order_by(Account.created_at.desc())
        return list(self.db.scalars(stmt))

    def create(self, account: Account) -> Account:
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account: Account) -> Account:
        self.db.commit()
        self.db.refresh(account)
        return account

    def calculate_balance(self, account_id: uuid.UUID) -> dict[str, Decimal]:
        account = self.db.get(Account, account_id)
        if not account:
            return {}

        base_filters = [
            Transaction.account_id == account_id,
            Transaction.is_deleted.is_(False),
        ]

        income = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                *base_filters,
                Transaction.transaction_type == TransactionType.INCOME,
            )
        )
        expenses = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                *base_filters,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
        )
        adjustments = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                *base_filters,
                Transaction.transaction_type == TransactionType.ADJUSTMENT,
            )
        )
        transfer_net = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                *base_filters,
                Transaction.transaction_type == TransactionType.TRANSFER,
            )
        )

        opening = Decimal(account.opening_balance)
        total_income = Decimal(income or 0)
        total_expenses = Decimal(expenses or 0)
        total_adjustments = Decimal(adjustments or 0)
        transfers = Decimal(transfer_net or 0)

        current = opening + total_income - total_expenses + total_adjustments + transfers

        return {
            "opening_balance": opening,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "adjustments": total_adjustments,
            "current_balance": current,
        }

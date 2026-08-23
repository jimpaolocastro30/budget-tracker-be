import json
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.enums import TransactionType
from app.db.models.transaction import Transaction, TransactionAudit


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, transaction_id: uuid.UUID, user_id: uuid.UUID) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.is_deleted.is_(False),
        )
        return self.db.scalar(stmt)

    def list_transactions(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        transaction_type: TransactionType | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        keyword: str | None = None,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> tuple[list[Transaction], int]:
        filters = [Transaction.user_id == user_id, Transaction.is_deleted.is_(False)]

        if date_from:
            filters.append(Transaction.transaction_date >= date_from)
        if date_to:
            filters.append(Transaction.transaction_date <= date_to)
        if account_id:
            filters.append(Transaction.account_id == account_id)
        if category_id:
            filters.append(Transaction.category_id == category_id)
        if transaction_type:
            filters.append(Transaction.transaction_type == transaction_type)
        if amount_min is not None:
            filters.append(Transaction.amount >= amount_min)
        if amount_max is not None:
            filters.append(Transaction.amount <= amount_max)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Transaction.description.ilike(pattern),
                    Transaction.notes.ilike(pattern),
                    Transaction.tags.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(Transaction).where(and_(*filters))
        total = self.db.scalar(count_stmt) or 0

        sort_column = Transaction.amount if sort_by == "amount" else Transaction.transaction_date
        order = sort_column.desc() if sort_order == "desc" else sort_column.asc()

        stmt = (
            select(Transaction)
            .where(and_(*filters))
            .order_by(order)
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt))
        return items, total

    def find_duplicates(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        amount: Decimal,
        transaction_date: date,
        category_id: uuid.UUID | None,
        description: str | None,
    ) -> list[Transaction]:
        filters = [
            Transaction.user_id == user_id,
            Transaction.account_id == account_id,
            Transaction.amount == amount,
            Transaction.transaction_date == transaction_date,
            Transaction.is_deleted.is_(False),
        ]
        if category_id:
            filters.append(Transaction.category_id == category_id)
        if description:
            filters.append(Transaction.description == description)

        stmt = select(Transaction).where(and_(*filters))
        return list(self.db.scalars(stmt))

    def create(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def create_many(self, transactions: list[Transaction]) -> list[Transaction]:
        self.db.add_all(transactions)
        self.db.commit()
        for txn in transactions:
            self.db.refresh(txn)
        return transactions

    def update(self, transaction: Transaction, audit: TransactionAudit | None = None) -> Transaction:
        if audit:
            self.db.add(audit)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def soft_delete(self, transaction: Transaction) -> Transaction:
        transaction.is_deleted = True
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    @staticmethod
    def serialize_transaction(transaction: Transaction) -> dict:
        return {
            "id": str(transaction.id),
            "account_id": str(transaction.account_id),
            "category_id": str(transaction.category_id) if transaction.category_id else None,
            "transaction_type": transaction.transaction_type.value,
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "transaction_date": transaction.transaction_date.isoformat(),
            "description": transaction.description,
            "notes": transaction.notes,
            "tags": transaction.tags,
        }

    def create_audit(
        self,
        transaction: Transaction,
        user_id: uuid.UUID,
        original: dict,
        updated: dict,
    ) -> TransactionAudit:
        audit = TransactionAudit(
            transaction_id=transaction.id,
            user_id=user_id,
            original_values=json.dumps(original),
            updated_values=json.dumps(updated),
            updated_at=transaction.updated_at,
        )
        self.db.add(audit)
        return audit

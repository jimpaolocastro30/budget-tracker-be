import csv
import io
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.db.enums import TransactionType
from app.db.models.account import Account
from app.db.models.budget import Budget
from app.db.models.category import Category
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.repositories.account import AccountRepository
from app.repositories.budget import BudgetRepository
from app.repositories.category import CategoryRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.account import AccountBalanceResponse, AccountCreate, AccountUpdate
from app.schemas.budget import BudgetCreate, BudgetSummaryResponse, BudgetUpdate
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.report import CashFlowReportResponse, DashboardResponse, SpendingReportResponse
from app.schemas.transaction import (
    DuplicateWarning,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    TransferCreate,
)
from app.services.utils import (
    calculate_budget_status,
    format_decimal,
    get_budget_period,
    parse_decimal,
)


class AccountService:
    def __init__(self, db: Session) -> None:
        self.repo = AccountRepository(db)

    def list_accounts(self, user_id: uuid.UUID) -> list[Account]:
        return self.repo.list_by_user(user_id)

    def create(self, user_id: uuid.UUID, data: AccountCreate) -> Account:
        account = Account(
            user_id=user_id,
            name=data.name,
            account_type=data.account_type,
            currency=data.currency.upper(),
            opening_balance=Decimal(data.opening_balance),
            description=data.description,
            is_active=data.is_active,
            created_at=datetime.now(UTC),
        )
        return self.repo.create(account)

    def get(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = self.repo.get_by_id(account_id, user_id)
        if not account:
            raise NotFoundError("ACCOUNT_NOT_FOUND", "The requested account does not exist.")
        return account

    def update(self, user_id: uuid.UUID, account_id: uuid.UUID, data: AccountUpdate) -> Account:
        account = self.get(user_id, account_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "currency" and value:
                value = value.upper()
            setattr(account, field, value)
        return self.repo.update(account)

    def archive(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        account = self.get(user_id, account_id)
        account.is_active = False
        self.repo.update(account)

    def balance(self, user_id: uuid.UUID, account_id: uuid.UUID) -> AccountBalanceResponse:
        account = self.get(user_id, account_id)
        totals = self.repo.calculate_balance(account.id)
        return AccountBalanceResponse(
            account_id=account.id,
            currency=account.currency,
            opening_balance=format_decimal(totals["opening_balance"]),
            total_income=format_decimal(totals["total_income"]),
            total_expenses=format_decimal(totals["total_expenses"]),
            adjustments=format_decimal(totals["adjustments"]),
            current_balance=format_decimal(totals["current_balance"]),
        )


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.repo = CategoryRepository(db)

    def list_categories(self, user_id: uuid.UUID, category_type=None) -> list[Category]:
        return self.repo.list_for_user(user_id, category_type=category_type)

    def create(self, user_id: uuid.UUID, data: CategoryCreate) -> Category:
        if data.parent_id:
            parent = self.repo.get_by_id(data.parent_id, user_id)
            if not parent:
                raise NotFoundError("CATEGORY_NOT_FOUND", "Parent category not found.")
        category = Category(
            user_id=user_id,
            name=data.name,
            category_type=data.category_type,
            parent_id=data.parent_id,
            is_system=False,
            is_active=True,
        )
        return self.repo.create(category)

    def get(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
        category = self.repo.get_by_id(category_id, user_id)
        if not category:
            raise NotFoundError("CATEGORY_NOT_FOUND", "The requested category does not exist.")
        return category

    def update(self, user_id: uuid.UUID, category_id: uuid.UUID, data: CategoryUpdate) -> Category:
        category = self.get(user_id, category_id)
        if category.is_system:
            raise AppError("SYSTEM_CATEGORY", "System categories cannot be modified.", 400)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
        return self.repo.update(category)

    def archive(self, user_id: uuid.UUID, category_id: uuid.UUID) -> None:
        category = self.get(user_id, category_id)
        if category.is_system:
            raise AppError("SYSTEM_CATEGORY", "System categories cannot be archived.", 400)
        category.is_active = False
        self.repo.update(category)


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.repo = TransactionRepository(db)
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)

    def list_transactions(self, user_id: uuid.UUID, **filters) -> tuple[list[Transaction], int]:
        return self.repo.list_transactions(user_id, **filters)

    def create(
        self, user_id: uuid.UUID, data: TransactionCreate
    ) -> TransactionResponse | DuplicateWarning:
        account = self.accounts.get_by_id(data.account_id, user_id)
        if not account:
            raise NotFoundError("ACCOUNT_NOT_FOUND", "Account not found.")
        if not account.is_active:
            raise AppError("ACCOUNT_ARCHIVED", "Cannot add transactions to archived accounts.", 400)

        amount = parse_decimal(data.amount)
        if data.category_id:
            category = self.categories.get_by_id(data.category_id, user_id)
            if not category:
                raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found.")

        duplicates = self.repo.find_duplicates(
            user_id,
            data.account_id,
            amount,
            data.transaction_date,
            data.category_id,
            data.description,
        )
        if duplicates and not data.confirm_duplicate:
            return DuplicateWarning(
                message="A similar transaction already exists.",
                similar_transaction_ids=[d.id for d in duplicates],
            )

        transaction = Transaction(
            user_id=user_id,
            account_id=data.account_id,
            category_id=data.category_id,
            transaction_type=data.transaction_type,
            amount=amount,
            currency=data.currency.upper(),
            transaction_date=data.transaction_date,
            description=data.description,
            notes=data.notes,
            tags=data.tags,
        )
        created = self.repo.create(transaction)
        return self._to_response(created)

    def get(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
        transaction = self.repo.get_by_id(transaction_id, user_id)
        if not transaction:
            raise NotFoundError("TRANSACTION_NOT_FOUND", "The requested transaction does not exist.")
        return transaction

    def update(
        self, user_id: uuid.UUID, transaction_id: uuid.UUID, data: TransactionUpdate
    ) -> TransactionResponse:
        transaction = self.get(user_id, transaction_id)
        original = self.repo.serialize_transaction(transaction)
        updates = data.model_dump(exclude_unset=True)

        if "amount" in updates:
            updates["amount"] = parse_decimal(updates["amount"])
        if "currency" in updates and updates["currency"]:
            updates["currency"] = updates["currency"].upper()

        for field, value in updates.items():
            setattr(transaction, field, value)

        transaction.updated_at = datetime.now(UTC)
        updated = self.repo.serialize_transaction(transaction)
        audit = self.repo.create_audit(transaction, user_id, original, updated)
        saved = self.repo.update(transaction, audit)
        return self._to_response(saved)

    def delete(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        transaction = self.get(user_id, transaction_id)
        self.repo.soft_delete(transaction)

    def transfer(self, user_id: uuid.UUID, data: TransferCreate) -> list[TransactionResponse]:
        if data.source_account_id == data.destination_account_id:
            raise AppError("INVALID_TRANSFER", "Source and destination accounts must differ.", 400)

        source = self.accounts.get_by_id(data.source_account_id, user_id)
        dest = self.accounts.get_by_id(data.destination_account_id, user_id)
        if not source or not dest:
            raise NotFoundError("ACCOUNT_NOT_FOUND", "One or both accounts not found.")
        if not source.is_active or not dest.is_active:
            raise AppError("ACCOUNT_ARCHIVED", "Cannot transfer from or to archived accounts.", 400)

        amount = parse_decimal(data.amount)
        group_id = uuid.uuid4()

        debit = Transaction(
            user_id=user_id,
            account_id=source.id,
            category_id=None,
            transaction_type=TransactionType.TRANSFER,
            amount=-amount,
            currency=data.currency.upper(),
            transaction_date=data.transaction_date,
            description=data.description or f"Transfer to {dest.name}",
            notes=data.notes,
            transfer_group_id=group_id,
        )
        credit = Transaction(
            user_id=user_id,
            account_id=dest.id,
            category_id=None,
            transaction_type=TransactionType.TRANSFER,
            amount=amount,
            currency=data.currency.upper(),
            transaction_date=data.transaction_date,
            description=data.description or f"Transfer from {source.name}",
            notes=data.notes,
            transfer_group_id=group_id,
        )
        created = self.repo.create_many([debit, credit])
        return [self._to_response(t) for t in created]

    @staticmethod
    def _to_response(transaction: Transaction) -> TransactionResponse:
        return TransactionResponse(
            id=transaction.id,
            account_id=transaction.account_id,
            category_id=transaction.category_id,
            transaction_type=transaction.transaction_type,
            amount=format_decimal(abs(transaction.amount)),
            currency=transaction.currency,
            transaction_date=transaction.transaction_date,
            description=transaction.description,
            notes=transaction.notes,
            tags=transaction.tags,
            transfer_group_id=transaction.transfer_group_id,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
        )


class BudgetService:
    def __init__(self, db: Session) -> None:
        self.repo = BudgetRepository(db)
        self.categories = CategoryRepository(db)

    def list_budgets(self, user_id: uuid.UUID) -> list[Budget]:
        return self.repo.list_by_user(user_id)

    def create(self, user_id: uuid.UUID, data: BudgetCreate) -> Budget:
        category = self.categories.get_by_id(data.category_id, user_id)
        if not category:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found.")
        if category.category_type.value != "EXPENSE":
            raise AppError("INVALID_BUDGET_CATEGORY", "Budgets must use expense categories.", 400)

        budget = Budget(
            user_id=user_id,
            name=data.name,
            category_id=data.category_id,
            account_id=data.account_id,
            amount_limit=parse_decimal(data.amount_limit),
            period_type=data.period_type,
            start_date=data.start_date,
            end_date=data.end_date,
            alert_threshold=Decimal(data.alert_threshold),
            is_active=True,
        )
        return self.repo.create(budget)

    def get(self, user_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
        budget = self.repo.get_by_id(budget_id, user_id)
        if not budget:
            raise NotFoundError("BUDGET_NOT_FOUND", "The requested budget does not exist.")
        return budget

    def update(self, user_id: uuid.UUID, budget_id: uuid.UUID, data: BudgetUpdate) -> Budget:
        budget = self.get(user_id, budget_id)
        updates = data.model_dump(exclude_unset=True)
        if "amount_limit" in updates:
            updates["amount_limit"] = parse_decimal(updates["amount_limit"])
        if "alert_threshold" in updates:
            updates["alert_threshold"] = Decimal(updates["alert_threshold"])
        for field, value in updates.items():
            setattr(budget, field, value)
        return self.repo.update(budget)

    def archive(self, user_id: uuid.UUID, budget_id: uuid.UUID) -> None:
        budget = self.get(user_id, budget_id)
        budget.is_active = False
        self.repo.update(budget)

    def summary(self, user_id: uuid.UUID, budget_id: uuid.UUID) -> BudgetSummaryResponse:
        budget = self.get(user_id, budget_id)
        period_start, period_end = get_budget_period(budget)
        actual = self.repo.calculate_spending(budget, period_start, period_end)
        limit = Decimal(budget.amount_limit)
        remaining = limit - actual
        usage = (actual / limit * Decimal("100")) if limit > 0 else Decimal("0")
        status = calculate_budget_status(usage, Decimal(budget.alert_threshold), budget.is_active)

        return BudgetSummaryResponse(
            budget_id=budget.id,
            budget_name=budget.name,
            period_start=period_start,
            period_end=period_end,
            budget_limit=format_decimal(limit),
            actual_spending=format_decimal(actual),
            remaining_amount=format_decimal(remaining),
            usage_percentage=format_decimal(usage),
            status=status,
        )


class ReportService:
    def __init__(self, db: Session) -> None:
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)
        self.budgets = BudgetRepository(db)

    def dashboard(
        self,
        user_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> DashboardResponse:
        accounts = self.accounts.list_by_user(user_id)
        total_balance = Decimal("0")
        for account in accounts:
            totals = self.accounts.calculate_balance(account.id)
            total_balance += totals["current_balance"]

        txns, _ = self.transactions.list_transactions(
            user_id,
            offset=0,
            limit=10000,
            date_from=period_start,
            date_to=period_end,
        )

        income = sum(
            (t.amount for t in txns if t.transaction_type == TransactionType.INCOME),
            Decimal("0"),
        )
        expenses = sum(
            (t.amount for t in txns if t.transaction_type == TransactionType.EXPENSE),
            Decimal("0"),
        )

        category_totals: dict[str, Decimal] = {}
        for t in txns:
            if t.transaction_type != TransactionType.EXPENSE or not t.category_id:
                continue
            key = str(t.category_id)
            category_totals[key] = category_totals.get(key, Decimal("0")) + t.amount

        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        top_spending = [
            {"category_id": cat_id, "total_amount": format_decimal(amount)}
            for cat_id, amount in top_categories
        ]

        budgets = self.budgets.list_by_user(user_id)
        if budgets:
            usages = []
            for budget in budgets:
                ps, pe = get_budget_period(budget, period_end)
                actual = self.budgets.calculate_spending(budget, ps, pe)
                limit = Decimal(budget.amount_limit)
                if limit > 0:
                    usages.append(actual / limit * Decimal("100"))
            avg_usage = sum(usages, Decimal("0")) / Decimal(len(usages)) if usages else Decimal("0")
        else:
            avg_usage = Decimal("0")

        recent, _ = self.transactions.list_transactions(user_id, offset=0, limit=10)
        recent_responses = [TransactionService._to_response(t) for t in recent]

        return DashboardResponse(
            total_balance=format_decimal(total_balance),
            total_income=format_decimal(income),
            total_expenses=format_decimal(expenses),
            net_cash_flow=format_decimal(income - expenses),
            budget_utilization_percentage=format_decimal(avg_usage),
            top_spending_categories=top_spending,
            recent_transactions=recent_responses,
            upcoming_recurring_count=0,
        )

    def spending_report(
        self,
        user_id: uuid.UUID,
        group_by: str,
        period_start: date,
        period_end: date,
    ) -> SpendingReportResponse:
        txns, _ = self.transactions.list_transactions(
            user_id,
            offset=0,
            limit=100000,
            date_from=period_start,
            date_to=period_end,
            transaction_type=TransactionType.EXPENSE,
        )

        groups: dict[str, list[Transaction]] = {}
        for t in txns:
            if group_by == "account":
                key = str(t.account_id)
            elif group_by == "month":
                key = t.transaction_date.strftime("%Y-%m")
            elif group_by == "type":
                key = t.transaction_type.value
            elif group_by == "tag":
                key = t.tags or "untagged"
            else:
                key = str(t.category_id) if t.category_id else "uncategorized"
            groups.setdefault(key, []).append(t)

        items = [
            {
                "group_key": key,
                "total_amount": format_decimal(sum((t.amount for t in group), Decimal("0"))),
                "transaction_count": len(group),
            }
            for key, group in sorted(groups.items())
        ]

        from app.schemas.report import SpendingReportItem

        return SpendingReportResponse(
            group_by=group_by,
            period_start=period_start,
            period_end=period_end,
            items=[SpendingReportItem(**item) for item in items],
        )

    def cash_flow_report(
        self,
        user_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> CashFlowReportResponse:
        txns, _ = self.transactions.list_transactions(
            user_id,
            offset=0,
            limit=100000,
            date_from=period_start,
            date_to=period_end,
        )
        income = sum(
            (t.amount for t in txns if t.transaction_type == TransactionType.INCOME),
            Decimal("0"),
        )
        expenses = sum(
            (t.amount for t in txns if t.transaction_type == TransactionType.EXPENSE),
            Decimal("0"),
        )
        return CashFlowReportResponse(
            period_start=period_start,
            period_end=period_end,
            total_income=format_decimal(income),
            total_expenses=format_decimal(expenses),
            net_cash_flow=format_decimal(income - expenses),
        )

    def export_data(self, user_id: uuid.UUID, export_format: str) -> tuple[str, str, str]:
        accounts = self.accounts.list_by_user(user_id, include_inactive=True)
        txns, _ = self.transactions.list_transactions(user_id, offset=0, limit=100000)

        payload = {
            "accounts": [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "account_type": a.account_type.value,
                    "currency": a.currency,
                    "opening_balance": str(a.opening_balance),
                    "is_active": a.is_active,
                }
                for a in accounts
            ],
            "transactions": [
                {
                    "id": str(t.id),
                    "account_id": str(t.account_id),
                    "category_id": str(t.category_id) if t.category_id else None,
                    "transaction_type": t.transaction_type.value,
                    "amount": str(t.amount),
                    "currency": t.currency,
                    "transaction_date": t.transaction_date.isoformat(),
                    "description": t.description,
                }
                for t in txns
            ],
        }

        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "account_id",
                    "category_id",
                    "transaction_type",
                    "amount",
                    "currency",
                    "transaction_date",
                    "description",
                ]
            )
            for row in payload["transactions"]:
                writer.writerow(
                    [
                        row["id"],
                        row["account_id"],
                        row["category_id"],
                        row["transaction_type"],
                        row["amount"],
                        row["currency"],
                        row["transaction_date"],
                        row["description"],
                    ]
                )
            content = output.getvalue()
            return content, "text/csv", "budget_export.csv"

        content = json.dumps(payload, indent=2)
        return content, "application/json", "budget_export.json"

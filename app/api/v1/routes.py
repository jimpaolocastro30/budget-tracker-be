from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.enums import CategoryType, TransactionType
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.account import (
    AccountBalanceResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from app.schemas.auth import ChangePassword, RefreshTokenRequest, TokenResponse, UserLogin, UserRegister
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetSummaryResponse, BudgetUpdate
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.report import CashFlowReportResponse, DashboardResponse, ExportRequest, SpendingReportResponse
from app.schemas.auth import UserResponse, UserUpdate
from app.schemas.transaction import (
    DuplicateWarning,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    TransferCreate,
)
from app.services.auth import AuthService
from app.services.domain import (
    AccountService,
    BudgetService,
    CategoryService,
    ReportService,
    TransactionService,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Users"])
accounts_router = APIRouter(prefix="/accounts", tags=["Accounts"])
categories_router = APIRouter(prefix="/categories", tags=["Categories"])
transactions_router = APIRouter(prefix="/transactions", tags=["Transactions"])
budgets_router = APIRouter(prefix="/budgets", tags=["Budgets"])
reports_router = APIRouter(prefix="/reports", tags=["Reports"])


def _account_response(account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        currency=account.currency,
        opening_balance=f"{account.opening_balance:.2f}",
        description=account.description,
        is_active=account.is_active,
        created_at=account.created_at,
    )


def _budget_response(budget) -> BudgetResponse:
    return BudgetResponse(
        id=budget.id,
        name=budget.name,
        category_id=budget.category_id,
        account_id=budget.account_id,
        amount_limit=f"{budget.amount_limit:.2f}",
        period_type=budget.period_type,
        start_date=budget.start_date,
        end_date=budget.end_date,
        alert_threshold=f"{budget.alert_threshold:.2f}",
        is_active=budget.is_active,
    )


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).register(data)


@auth_router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).login(data.email, data.password)


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).refresh(data.refresh_token)


@auth_router.post("/logout", response_model=MessageResponse)
def logout(data: RefreshTokenRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService(db).logout(data.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@auth_router.post("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    AuthService(db).change_password(current_user, data.current_password, data.new_password)
    return MessageResponse(message="Password changed successfully.")


@users_router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@users_router.patch("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "base_currency" and value:
            value = value.upper()
        setattr(current_user, field, value)
    from app.repositories.user import UserRepository

    updated = UserRepository(db).update(current_user)
    return UserResponse.model_validate(updated)


@accounts_router.get("", response_model=list[AccountResponse])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    accounts = AccountService(db).list_accounts(current_user.id)
    return [_account_response(a) for a in accounts]


@accounts_router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    account = AccountService(db).create(current_user.id, data)
    return _account_response(account)


@accounts_router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    account = AccountService(db).get(current_user.id, account_id)
    return _account_response(account)


@accounts_router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: UUID,
    data: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    account = AccountService(db).update(current_user.id, account_id, data)
    return _account_response(account)


@accounts_router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    AccountService(db).archive(current_user.id, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@accounts_router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountBalanceResponse:
    return AccountService(db).balance(current_user.id, account_id)


@categories_router.get("", response_model=list[CategoryResponse])
def list_categories(
    category_type: CategoryType | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    categories = CategoryService(db).list_categories(current_user.id, category_type)
    return [CategoryResponse.model_validate(c) for c in categories]


@categories_router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    category = CategoryService(db).create(current_user.id, data)
    return CategoryResponse.model_validate(category)


@categories_router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    category = CategoryService(db).get(current_user.id, category_id)
    return CategoryResponse.model_validate(category)


@categories_router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    category = CategoryService(db).update(current_user.id, category_id, data)
    return CategoryResponse.model_validate(category)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_category(
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    CategoryService(db).archive(current_user.id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@transactions_router.get("", response_model=PaginatedResponse[TransactionResponse])
def list_transactions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: UUID | None = None,
    category_id: UUID | None = None,
    transaction_type: TransactionType | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    keyword: str | None = None,
    sort_by: str = Query(default="date", pattern="^(date|amount)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TransactionResponse]:
    items, total = TransactionService(db).list_transactions(
        current_user.id,
        offset=offset,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        amount_min=amount_min,
        amount_max=amount_max,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedResponse(
        items=[TransactionService._to_response(t) for t in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@transactions_router.post(
    "",
    response_model=TransactionResponse | DuplicateWarning,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse | DuplicateWarning:
    return TransactionService(db).create(current_user.id, data)


@transactions_router.post("/transfer", response_model=list[TransactionResponse], status_code=status.HTTP_201_CREATED)
def create_transfer(
    data: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionResponse]:
    return TransactionService(db).transfer(current_user.id, data)


@transactions_router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    transaction = TransactionService(db).get(current_user.id, transaction_id)
    return TransactionService._to_response(transaction)


@transactions_router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: UUID,
    data: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    return TransactionService(db).update(current_user.id, transaction_id, data)


@transactions_router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    TransactionService(db).delete(current_user.id, transaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@budgets_router.get("", response_model=list[BudgetResponse])
def list_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BudgetResponse]:
    budgets = BudgetService(db).list_budgets(current_user.id)
    return [_budget_response(b) for b in budgets]


@budgets_router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    budget = BudgetService(db).create(current_user.id, data)
    return _budget_response(budget)


@budgets_router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    budget = BudgetService(db).get(current_user.id, budget_id)
    return _budget_response(budget)


@budgets_router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: UUID,
    data: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    budget = BudgetService(db).update(current_user.id, budget_id, data)
    return _budget_response(budget)


@budgets_router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_budget(
    budget_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    BudgetService(db).archive(current_user.id, budget_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@budgets_router.get("/{budget_id}/summary", response_model=BudgetSummaryResponse)
def get_budget_summary(
    budget_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetSummaryResponse:
    return BudgetService(db).summary(current_user.id, budget_id)


@reports_router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    period_start: date | None = None,
    period_end: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    today = date.today()
    start = period_start or today.replace(day=1)
    end = period_end or today
    return ReportService(db).dashboard(current_user.id, start, end)


@reports_router.get("/spending", response_model=SpendingReportResponse)
def get_spending_report(
    group_by: str = Query(default="category", pattern="^(category|account|month|type|tag)$"),
    period_start: date | None = None,
    period_end: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpendingReportResponse:
    today = date.today()
    start = period_start or today.replace(day=1)
    end = period_end or today
    return ReportService(db).spending_report(current_user.id, group_by, start, end)


@reports_router.get("/cash-flow", response_model=CashFlowReportResponse)
def get_cash_flow_report(
    period_start: date | None = None,
    period_end: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CashFlowReportResponse:
    today = date.today()
    start = period_start or today.replace(day=1)
    end = period_end or today
    return ReportService(db).cash_flow_report(current_user.id, start, end)


@reports_router.get("/export")
def export_data(
    export_format: str = Query(default="json", alias="format", pattern="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    content, media_type, filename = ReportService(db).export_data(current_user.id, export_format)
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

from fastapi import APIRouter

from app.api.v1.routes import (
    accounts_router,
    auth_router,
    budgets_router,
    categories_router,
    reports_router,
    transactions_router,
    users_router,
)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(accounts_router)
api_router.include_router(categories_router)
api_router.include_router(transactions_router)
api_router.include_router(budgets_router)
api_router.include_router(reports_router)

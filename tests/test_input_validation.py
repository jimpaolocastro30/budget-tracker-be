"""Input validation and boundary testing."""

import uuid
from datetime import date

import pytest


class TestAuthInputValidation:
    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"full_name": "A", "email": "not-an-email", "password": "SecurePass123"}, 422),
            ({"full_name": "A", "email": "valid@example.com", "password": "short"}, 422),
            ({"full_name": "", "email": "valid@example.com", "password": "SecurePass123"}, 422),
            (
                {
                    "full_name": "A",
                    "email": "valid@example.com",
                    "password": "SecurePass123",
                    "base_currency": "PH",
                },
                422,
            ),
        ],
    )
    def test_register_invalid_inputs(self, client, payload, expected_status):
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_register_rejects_unknown_fields(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Test",
                "email": "unknown@example.com",
                "password": "SecurePass123",
                "is_admin": True,
            },
        )
        assert response.status_code == 422

    def test_login_missing_password(self, client):
        response = client.post("/api/v1/auth/login", json={"email": "a@b.com"})
        assert response.status_code == 422


class TestAccountInputValidation:
    def test_invalid_account_type(self, client, auth_headers):
        response = client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "Bad",
                "account_type": "INVALID",
                "currency": "PHP",
            },
        )
        assert response.status_code == 422

    def test_invalid_opening_balance_format(self, client, auth_headers):
        response = client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "Bad",
                "account_type": "CASH",
                "currency": "PHP",
                "opening_balance": "not-a-number",
            },
        )
        assert response.status_code == 422

    def test_empty_account_name(self, client, auth_headers):
        response = client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "",
                "account_type": "CASH",
                "currency": "PHP",
            },
        )
        assert response.status_code == 422


class TestTransactionInputValidation:
    def test_zero_amount_rejected(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)

        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "0.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        )
        assert response.status_code == 422

    def test_negative_amount_rejected(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)

        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "-50.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
            },
        )
        assert response.status_code == 422

    def test_invalid_uuid_account_id(self, client, auth_headers):
        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": "not-a-uuid",
                "transaction_type": "EXPENSE",
                "amount": "100.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
            },
        )
        assert response.status_code == 422

    def test_transfer_same_account_rejected(self, client, auth_headers):
        from tests.conftest import create_account

        account = create_account(client, auth_headers)
        response = client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers,
            json={
                "source_account_id": account["id"],
                "destination_account_id": account["id"],
                "amount": "100.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TRANSFER"

    def test_transaction_on_archived_account_rejected(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)
        client.delete(f"/api/v1/accounts/{account['id']}", headers=auth_headers)

        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "100.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ACCOUNT_ARCHIVED"


class TestBudgetInputValidation:
    def test_income_category_for_budget_rejected(self, client, auth_headers):
        from tests.conftest import get_income_category

        income = get_income_category(client, auth_headers)
        response = client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": "Bad Budget",
                "category_id": income["id"],
                "amount_limit": "1000.00",
                "period_type": "MONTHLY",
                "start_date": str(date.today().replace(day=1)),
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_BUDGET_CATEGORY"

    def test_invalid_period_type(self, client, auth_headers):
        from tests.conftest import get_expense_category

        category = get_expense_category(client, auth_headers)
        response = client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": "Bad Budget",
                "category_id": category["id"],
                "amount_limit": "1000.00",
                "period_type": "DAILY",
                "start_date": str(date.today()),
            },
        )
        assert response.status_code == 422


class TestPaginationInputValidation:
    def test_pagination_limits(self, client, auth_headers):
        over_limit = client.get("/api/v1/transactions", headers=auth_headers, params={"limit": 500})
        assert over_limit.status_code == 422

        negative_offset = client.get("/api/v1/transactions", headers=auth_headers, params={"offset": -1})
        assert negative_offset.status_code == 422


class TestNotFoundResponses:
    def test_nonexistent_resources_return_404(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        endpoints = [
            ("GET", f"/api/v1/accounts/{fake_id}"),
            ("GET", f"/api/v1/categories/{fake_id}"),
            ("GET", f"/api/v1/transactions/{fake_id}"),
            ("GET", f"/api/v1/budgets/{fake_id}"),
        ]
        for method, path in endpoints:
            response = client.request(method, path, headers=auth_headers)
            assert response.status_code == 404, f"{method} {path} should 404"

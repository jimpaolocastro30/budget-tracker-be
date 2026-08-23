"""Security and safety tests — auth, authorization, injection, token handling."""

import uuid

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.enums import BudgetStatus
from app.services.utils import calculate_budget_status, format_decimal
from decimal import Decimal


class TestPasswordSecurity:
    def test_password_is_hashed_not_plaintext(self):
        hashed = hash_password("SecurePass123")
        assert hashed != "SecurePass123"
        assert verify_password("SecurePass123", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_password_hash_differs_per_call(self):
        h1 = hash_password("SecurePass123")
        h2 = hash_password("SecurePass123")
        assert h1 != h2


class TestTokenSecurity:
    def test_missing_token_returns_401(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "MISSING_TOKEN"

    def test_invalid_token_returns_401(self, client):
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    def test_refresh_token_cannot_access_protected_routes(self, client, user):
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {user['refresh_token']}"},
        )
        assert response.status_code == 401

    def test_expired_token_rejected(self, client, user):
        settings = get_settings()
        expired = jwt.encode(
            {"sub": user["user_id"], "exp": 0, "type": "access"},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert response.status_code == 401

    def test_tampered_token_rejected(self, client, user):
        token = user["access_token"]
        tampered = token[:-4] + "XXXX"
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert response.status_code == 401

    def test_wrong_secret_token_rejected(self, client):
        fake = jwt.encode(
            {"sub": str(uuid.uuid4()), "exp": 9999999999, "type": "access"},
            "wrong-secret-key",
            algorithm="HS256",
        )
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {fake}"},
        )
        assert response.status_code == 401


class TestResourceOwnership:
    def test_user_cannot_access_other_users_account(self, client, user, second_user):
        from tests.conftest import create_account

        account = create_account(client, user["headers"], "Private Account")

        response = client.get(
            f"/api/v1/accounts/{account['id']}",
            headers=second_user["headers"],
        )
        assert response.status_code == 404

    def test_user_cannot_update_other_users_transaction(self, client, user, second_user):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, user["headers"])
        category = get_expense_category(client, user["headers"])
        from datetime import date

        txn = client.post(
            "/api/v1/transactions",
            headers=user["headers"],
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "100.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        ).json()

        response = client.patch(
            f"/api/v1/transactions/{txn['id']}",
            headers=second_user["headers"],
            json={"description": "Hacked"},
        )
        assert response.status_code == 404

    def test_user_cannot_view_other_users_budget_summary(self, client, user, second_user):
        from tests.conftest import create_account, get_expense_category
        from datetime import date

        account = create_account(client, user["headers"])
        category = get_expense_category(client, user["headers"])
        budget = client.post(
            "/api/v1/budgets",
            headers=user["headers"],
            json={
                "name": "Private Budget",
                "category_id": category["id"],
                "amount_limit": "5000.00",
                "period_type": "MONTHLY",
                "start_date": str(date.today().replace(day=1)),
                "account_id": account["id"],
            },
        ).json()

        response = client.get(
            f"/api/v1/budgets/{budget['id']}/summary",
            headers=second_user["headers"],
        )
        assert response.status_code == 404


class TestInjectionSafety:
    def test_sql_injection_in_login_email(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "' OR '1'='1",
                "password": "anything",
            },
        )
        assert response.status_code == 422

    def test_sql_injection_in_keyword_search(self, client, auth_headers):
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"keyword": "'; DROP TABLE transactions; --"},
        )
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_xss_payload_stored_safely(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category
        from datetime import date

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)
        xss = "<script>alert('xss')</script>"

        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "10.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "description": xss,
                "confirm_duplicate": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["description"] == xss


class TestSystemCategoryProtection:
    def test_cannot_modify_system_category(self, client, auth_headers):
        categories = client.get("/api/v1/categories", headers=auth_headers).json()
        system_cat = next(c for c in categories if c["is_system"])

        update = client.patch(
            f"/api/v1/categories/{system_cat['id']}",
            headers=auth_headers,
            json={"name": "Hacked"},
        )
        assert update.status_code == 400

        archive = client.delete(
            f"/api/v1/categories/{system_cat['id']}",
            headers=auth_headers,
        )
        assert archive.status_code == 400


class TestDuplicateEmailSafety:
    def test_duplicate_registration_rejected(self, client, user):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Clone",
                "email": user["email"],
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "EMAIL_EXISTS"


class TestUtilitySecurity:
    def test_budget_status_boundaries(self):
        assert calculate_budget_status(Decimal("50"), Decimal("75"), True) == BudgetStatus.ON_TRACK
        assert calculate_budget_status(Decimal("80"), Decimal("75"), True) == BudgetStatus.WARNING
        assert calculate_budget_status(Decimal("100"), Decimal("75"), True) == BudgetStatus.EXCEEDED

    def test_format_decimal_precision(self):
        assert format_decimal(Decimal("10.5")) == "10.50"

    def test_access_token_has_expected_structure(self, user):
        token = create_access_token(user["user_id"])
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["type"] == "access"
        assert payload["sub"] == user["user_id"]

    def test_refresh_token_type_distinct(self, user):
        refresh = create_refresh_token(user["user_id"])
        settings = get_settings()
        payload = jwt.decode(refresh, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["type"] == "refresh"

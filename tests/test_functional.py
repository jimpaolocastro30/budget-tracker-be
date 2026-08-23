"""Functional API tests — end-to-end workflows per SRS acceptance criteria."""

from datetime import date


class TestAuthWorkflow:
    def test_register_login_refresh_logout(self, client):
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "password": "SecurePass123",
                "base_currency": "PHP",
                "timezone": "UTC",
            },
        )
        assert reg.status_code == 201
        tokens = reg.json()
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 1800

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "jane@example.com", "password": "SecurePass123"},
        )
        assert login.status_code == 200

        refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh.status_code == 200
        new_tokens = refresh.json()

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": new_tokens["refresh_token"]},
        )
        assert logout.status_code == 200

        stale_refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_tokens["refresh_token"]},
        )
        assert stale_refresh.status_code == 401

    def test_change_password(self, client, user):
        response = client.post(
            "/api/v1/auth/change-password",
            headers=user["headers"],
            json={"current_password": "SecurePass123", "new_password": "NewSecure456"},
        )
        assert response.status_code == 200

        old_login = client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": "SecurePass123"},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": "NewSecure456"},
        )
        assert new_login.status_code == 200


class TestProfileWorkflow:
    def test_get_and_update_profile(self, client, user):
        me = client.get("/api/v1/users/me", headers=user["headers"])
        assert me.status_code == 200
        assert me.json()["email"] == user["email"]

        updated = client.patch(
            "/api/v1/users/me",
            headers=user["headers"],
            json={"full_name": "Updated Name", "base_currency": "USD"},
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["full_name"] == "Updated Name"
        assert body["base_currency"] == "USD"


class TestAccountWorkflow:
    def test_account_crud_and_balance(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers, "Main Wallet", "1000.00")
        category = get_expense_category(client, auth_headers)

        expense = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "250.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "description": "Groceries",
                "confirm_duplicate": True,
            },
        )
        assert expense.status_code == 201

        balance = client.get(f"/api/v1/accounts/{account['id']}/balance", headers=auth_headers)
        assert balance.status_code == 200
        assert balance.json()["current_balance"] == "750.00"

        patched = client.patch(
            f"/api/v1/accounts/{account['id']}",
            headers=auth_headers,
            json={"name": "Renamed Wallet"},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Renamed Wallet"

        archived = client.delete(f"/api/v1/accounts/{account['id']}", headers=auth_headers)
        assert archived.status_code == 204


class TestCategoryWorkflow:
    def test_custom_category_lifecycle(self, client, auth_headers):
        created = client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Pet Care", "category_type": "EXPENSE"},
        )
        assert created.status_code == 201
        cat_id = created.json()["id"]

        fetched = client.get(f"/api/v1/categories/{cat_id}", headers=auth_headers)
        assert fetched.status_code == 200

        updated = client.patch(
            f"/api/v1/categories/{cat_id}",
            headers=auth_headers,
            json={"name": "Pet Expenses"},
        )
        assert updated.status_code == 200

        archived = client.delete(f"/api/v1/categories/{cat_id}", headers=auth_headers)
        assert archived.status_code == 204

    def test_default_categories_seeded(self, client, auth_headers):
        categories = client.get("/api/v1/categories", headers=auth_headers)
        assert categories.status_code == 200
        names = {c["name"] for c in categories.json()}
        assert "Food" in names
        assert "Salary" in names
        assert any(c["is_system"] for c in categories.json())


class TestTransactionWorkflow:
    def test_income_expense_transfer_and_filters(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category, get_income_category

        source = create_account(client, auth_headers, "Source", "5000.00")
        dest = create_account(client, auth_headers, "Savings", "0.00")
        expense_cat = get_expense_category(client, auth_headers)
        income_cat = get_income_category(client, auth_headers)

        income = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": source["id"],
                "category_id": income_cat["id"],
                "transaction_type": "INCOME",
                "amount": "1000.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "description": "Salary",
                "confirm_duplicate": True,
            },
        )
        assert income.status_code == 201

        expense = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": source["id"],
                "category_id": expense_cat["id"],
                "transaction_type": "EXPENSE",
                "amount": "500.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "description": "Rent",
                "confirm_duplicate": True,
            },
        )
        assert expense.status_code == 201

        transfer = client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers,
            json={
                "source_account_id": source["id"],
                "destination_account_id": dest["id"],
                "amount": "200.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
            },
        )
        assert transfer.status_code == 201
        assert len(transfer.json()) == 2

        listed = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"account_id": source["id"], "limit": 10},
        )
        assert listed.status_code == 200
        assert listed.json()["total"] >= 2

        updated = client.patch(
            f"/api/v1/transactions/{expense.json()['id']}",
            headers=auth_headers,
            json={"description": "Updated Rent"},
        )
        assert updated.status_code == 200

        deleted = client.delete(
            f"/api/v1/transactions/{expense.json()['id']}",
            headers=auth_headers,
        )
        assert deleted.status_code == 204

    def test_duplicate_detection_warning(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)
        payload = {
            "account_id": account["id"],
            "category_id": category["id"],
            "transaction_type": "EXPENSE",
            "amount": "99.99",
            "currency": "PHP",
            "transaction_date": str(date.today()),
            "description": "Duplicate test",
        }

        first = client.post("/api/v1/transactions", headers=auth_headers, json={**payload, "confirm_duplicate": True})
        assert first.status_code == 201

        warning = client.post("/api/v1/transactions", headers=auth_headers, json=payload)
        assert warning.status_code == 201
        body = warning.json()
        assert body.get("warning") is True
        assert len(body["similar_transaction_ids"]) >= 1


class TestBudgetWorkflow:
    def test_budget_create_summary_archive(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers, "Budget Account", "10000.00")
        category = get_expense_category(client, auth_headers)

        client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category["id"],
                "transaction_type": "EXPENSE",
                "amount": "1500.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        )

        budget = client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": "Monthly Food",
                "category_id": category["id"],
                "amount_limit": "5000.00",
                "period_type": "MONTHLY",
                "start_date": str(date.today().replace(day=1)),
            },
        )
        assert budget.status_code == 201
        budget_id = budget.json()["id"]

        summary = client.get(f"/api/v1/budgets/{budget_id}/summary", headers=auth_headers)
        assert summary.status_code == 200
        s = summary.json()
        assert s["actual_spending"] == "1500.00"
        assert s["remaining_amount"] == "3500.00"
        assert s["status"] == "ON_TRACK"

        archived = client.delete(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
        assert archived.status_code == 204


class TestReportsWorkflow:
    def test_dashboard_spending_cashflow_export(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category, get_income_category

        account = create_account(client, auth_headers, "Report Account", "3000.00")
        expense_cat = get_expense_category(client, auth_headers)
        income_cat = get_income_category(client, auth_headers)

        client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": income_cat["id"],
                "transaction_type": "INCOME",
                "amount": "2000.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        )
        client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": expense_cat["id"],
                "transaction_type": "EXPENSE",
                "amount": "800.00",
                "currency": "PHP",
                "transaction_date": str(date.today()),
                "confirm_duplicate": True,
            },
        )

        dashboard = client.get("/api/v1/reports/dashboard", headers=auth_headers)
        assert dashboard.status_code == 200
        d = dashboard.json()
        assert float(d["total_income"]) >= 2000.0
        assert float(d["total_expenses"]) >= 800.0

        spending = client.get(
            "/api/v1/reports/spending",
            headers=auth_headers,
            params={"group_by": "category"},
        )
        assert spending.status_code == 200
        assert len(spending.json()["items"]) >= 1

        cashflow = client.get("/api/v1/reports/cash-flow", headers=auth_headers)
        assert cashflow.status_code == 200
        assert float(cashflow.json()["net_cash_flow"]) >= 1200.0

        json_export = client.get("/api/v1/reports/export", headers=auth_headers, params={"format": "json"})
        assert json_export.status_code == 200
        assert "transactions" in json_export.text

        csv_export = client.get("/api/v1/reports/export", headers=auth_headers, params={"format": "csv"})
        assert csv_export.status_code == 200
        assert "transaction_type" in csv_export.text


class TestHealthEndpoints:
    def test_health_and_root(self, client):
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        root = client.get("/")
        assert root.status_code == 200
        assert "api" in root.json()

"""Efficiency and performance tests — response time benchmarks per SRS NFR-6.1."""

import statistics
import time
from datetime import date

import pytest

# SRS target: CRUD operations < 500ms under normal load
CRUD_MAX_MS = 500
# SRS target: report endpoints < 2000ms for up to 100k transactions
REPORT_MAX_MS = 2000
SAMPLE_SIZE = 5


def _timed_request(client, method: str, url: str, **kwargs) -> tuple[float, object]:
    start = time.perf_counter()
    response = getattr(client, method.lower())(url, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, response


def _assert_p95_under(samples: list[float], max_ms: float, label: str):
    p95 = sorted(samples)[int(len(samples) * 0.95)] if len(samples) > 1 else samples[0]
    median = statistics.median(samples)
    assert p95 < max_ms, f"{label}: p95={p95:.1f}ms exceeds {max_ms}ms (median={median:.1f}ms)"


@pytest.mark.efficiency
class TestCrudEfficiency:
    def test_auth_login_response_time(self, client, user):
        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client,
                "POST",
                "/api/v1/auth/login",
                json={"email": user["email"], "password": user["password"]},
            )
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, CRUD_MAX_MS, "POST /auth/login")

    def test_list_accounts_response_time(self, client, auth_headers):
        from tests.conftest import create_account

        for i in range(3):
            create_account(client, auth_headers, f"Account {i}")

        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(client, "GET", "/api/v1/accounts", headers=auth_headers)
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, CRUD_MAX_MS, "GET /accounts")

    def test_create_transaction_response_time(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category

        account = create_account(client, auth_headers)
        category = get_expense_category(client, auth_headers)

        samples = []
        for i in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client,
                "POST",
                "/api/v1/transactions",
                headers=auth_headers,
                json={
                    "account_id": account["id"],
                    "category_id": category["id"],
                    "transaction_type": "EXPENSE",
                    "amount": f"{10 + i}.00",
                    "currency": "PHP",
                    "transaction_date": str(date.today()),
                    "confirm_duplicate": True,
                },
            )
            assert response.status_code == 201
            samples.append(ms)
        _assert_p95_under(samples, CRUD_MAX_MS, "POST /transactions")

    def test_list_transactions_pagination_response_time(self, client, auth_headers):
        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client,
                "GET",
                "/api/v1/transactions",
                headers=auth_headers,
                params={"limit": 20, "offset": 0},
            )
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, CRUD_MAX_MS, "GET /transactions")


@pytest.mark.efficiency
class TestReportEfficiency:
    def test_dashboard_response_time(self, client, auth_headers):
        from tests.conftest import create_account, get_expense_category, get_income_category

        account = create_account(client, auth_headers, "Perf Account", "50000.00")
        expense = get_expense_category(client, auth_headers)
        income = get_income_category(client, auth_headers)

        for i in range(20):
            client.post(
                "/api/v1/transactions",
                headers=auth_headers,
                json={
                    "account_id": account["id"],
                    "category_id": income["id"] if i % 2 == 0 else expense["id"],
                    "transaction_type": "INCOME" if i % 2 == 0 else "EXPENSE",
                    "amount": f"{100 + i}.00",
                    "currency": "PHP",
                    "transaction_date": str(date.today()),
                    "confirm_duplicate": True,
                },
            )

        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client, "GET", "/api/v1/reports/dashboard", headers=auth_headers
            )
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, REPORT_MAX_MS, "GET /reports/dashboard")

    def test_spending_report_response_time(self, client, auth_headers):
        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client,
                "GET",
                "/api/v1/reports/spending",
                headers=auth_headers,
                params={"group_by": "category"},
            )
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, REPORT_MAX_MS, "GET /reports/spending")

    def test_export_response_time(self, client, auth_headers):
        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(
                client,
                "GET",
                "/api/v1/reports/export",
                headers=auth_headers,
                params={"format": "json"},
            )
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, REPORT_MAX_MS, "GET /reports/export")


@pytest.mark.efficiency
class TestHealthEfficiency:
    def test_health_check_response_time(self, client):
        samples = []
        for _ in range(SAMPLE_SIZE):
            ms, response = _timed_request(client, "GET", "/health")
            assert response.status_code == 200
            samples.append(ms)
        _assert_p95_under(samples, 100, "GET /health")

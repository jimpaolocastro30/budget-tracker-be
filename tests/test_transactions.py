from datetime import date


def _setup_account_and_category(client, auth_headers):
    account = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Bank",
            "account_type": "BANK",
            "currency": "PHP",
            "opening_balance": "5000.00",
        },
    ).json()
    category = client.get("/api/v1/categories?category_type=EXPENSE", headers=auth_headers).json()[0]
    return account["id"], category["id"]


def test_transfer_between_accounts(client, auth_headers):
    source = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"name": "Source", "account_type": "BANK", "currency": "PHP", "opening_balance": "1000.00"},
    ).json()
    dest = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"name": "Dest", "account_type": "SAVINGS", "currency": "PHP", "opening_balance": "0.00"},
    ).json()

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

    source_balance = client.get(f"/api/v1/accounts/{source['id']}/balance", headers=auth_headers).json()
    dest_balance = client.get(f"/api/v1/accounts/{dest['id']}/balance", headers=auth_headers).json()
    assert source_balance["current_balance"] == "800.00"
    assert dest_balance["current_balance"] == "200.00"


def test_budget_summary(client, auth_headers):
    account_id, category_id = _setup_account_and_category(client, auth_headers)

    client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "account_id": account_id,
            "category_id": category_id,
            "transaction_type": "EXPENSE",
            "amount": "1000.00",
            "currency": "PHP",
            "transaction_date": str(date.today()),
            "confirm_duplicate": True,
        },
    )

    budget = client.post(
        "/api/v1/budgets",
        headers=auth_headers,
        json={
            "name": "Food Budget",
            "category_id": category_id,
            "amount_limit": "5000.00",
            "period_type": "MONTHLY",
            "start_date": str(date.today().replace(day=1)),
        },
    )
    assert budget.status_code == 201

    summary = client.get(f"/api/v1/budgets/{budget.json()['id']}/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["actual_spending"] == "1000.00"
    assert summary.json()["status"] == "ON_TRACK"

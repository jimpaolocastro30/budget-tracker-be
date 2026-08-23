from datetime import date


def test_account_crud_and_balance(client, auth_headers):
    create = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Main Wallet",
            "account_type": "CASH",
            "currency": "PHP",
            "opening_balance": "1000.00",
        },
    )
    assert create.status_code == 201
    account_id = create.json()["id"]

    categories = client.get("/api/v1/categories?category_type=EXPENSE", headers=auth_headers)
    category_id = categories.json()[0]["id"]

    expense = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "account_id": account_id,
            "category_id": category_id,
            "transaction_type": "EXPENSE",
            "amount": "250.00",
            "currency": "PHP",
            "transaction_date": str(date.today()),
            "description": "Groceries",
            "confirm_duplicate": True,
        },
    )
    assert expense.status_code == 201

    balance = client.get(f"/api/v1/accounts/{account_id}/balance", headers=auth_headers)
    assert balance.status_code == 200
    assert balance.json()["current_balance"] == "750.00"

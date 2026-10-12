import requests


def test_create_order(client, monkeypatch):

    def fake_get(url, timeout=5):
        class Response:
            status_code = 200

            def json(self):
                return {
                    "id": "prod-1",
                    "name": "Coffee",
                    "description": "Beans",
                    "price_cents": 500,
                    "currency": "USD",
                }

        return Response()

    monkeypatch.setattr(requests, "get", fake_get)

    payload = {
        "customer_id": "cust-1",
        "items": [{"product_id": "prod-1", "quantity": 2}],
    }

    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "pending"
    assert order["total_cents"] == 1000

    get_response = client.get(f"/orders/{order['id']}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == order["id"]


def test_duplicate_products_are_rejected_before_persisting(client):
    payload = {
        "customer_id": "customer",
        "items": [
            {"product_id": "same", "quantity": 1},
            {"product_id": "same", "quantity": 2},
        ],
    }
    assert client.post("/orders", json=payload).status_code == 400
    assert client.get("/orders").json() == []


def test_product_service_connection_failure_is_a_bad_gateway(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", unavailable)
    response = client.post(
        "/orders",
        json={
            "customer_id": "customer",
            "items": [{"product_id": "one", "quantity": 1}],
        },
    )
    assert response.status_code == 502
    assert client.get("/orders").json() == []

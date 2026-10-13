from concurrent.futures import ThreadPoolExecutor


def test_create_payment(client):

    payload = {"order_id": "order-1", "amount_cents": 1200, "currency": "usd"}

    response = client.post("/payments", json=payload)
    assert response.status_code == 201
    payment = response.json()
    assert payment["status"] == "authorized"

    get_response = client.get(f"/payments/{payment['id']}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["order_id"] == payload["order_id"]


def test_repeated_and_concurrent_requests_create_one_payment(client):
    payload = {"order_id": "same-order", "amount_cents": 1200, "currency": "usd"}
    with ThreadPoolExecutor(max_workers=4) as workers:
        responses = list(
            workers.map(lambda _: client.post("/payments", json=payload), range(4))
        )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    assert len(client.get("/payments").json()) == 1


def test_reusing_order_with_changed_payment_is_conflict(client):
    payload = {"order_id": "same-order", "amount_cents": 1200, "currency": "usd"}
    assert client.post("/payments", json=payload).status_code == 201
    payload["amount_cents"] = 1201
    assert client.post("/payments", json=payload).status_code == 409
    assert client.get("/payments").json()[0]["amount_cents"] == 1200


def test_retry_after_kafka_failure_republishes_saved_payment(client, monkeypatch):
    from unittest.mock import Mock

    from kafka.errors import KafkaError

    from app import main

    publish = Mock(side_effect=[KafkaError("offline"), None])
    monkeypatch.setattr(main, "publish_event", publish)
    counter_before = main.PAYMENTS_PROCESSED._value.get()
    payload = {"order_id": "retry-order", "amount_cents": 1200, "currency": "usd"}
    assert client.post("/payments", json=payload).status_code == 503
    saved = client.get("/payments").json()
    assert len(saved) == 1
    response = client.post("/payments", json=payload)
    assert response.status_code == 201
    assert response.json() == saved[0]
    assert client.get("/payments").json() == saved
    assert publish.call_count == 2
    assert publish.call_args_list[0] == publish.call_args_list[1]
    assert publish.call_args.args[2:] == ("payment.authorized", saved[0])
    assert main.PAYMENTS_PROCESSED._value.get() == counter_before + 1

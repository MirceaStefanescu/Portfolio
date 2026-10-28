"""Order HTTP, persistence and lifecycle regressions using synthetic data only."""

import json
import threading
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient
from kafka.errors import KafkaError

from app import main
from app.db import get_connection

PRODUCT = {"id": "one", "name": "Coffee", "price_cents": 500, "currency": "USD"}
ORDER = {"customer_id": "synthetic", "items": [{"product_id": "one", "quantity": 2}]}


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "orders.sqlite"))
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("KAFKA_ENABLED", "false")
    monkeypatch.setenv("RABBITMQ_ENABLED", "false")
    monkeypatch.setenv("OUTBOX_ENABLED", "false")
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client


def response(body, status=200, raw=False):
    result = requests.Response()
    result.status_code = status
    result._content = (body if raw else json.dumps(body)).encode("utf-8")
    result.headers["Content-Type"] = "application/json"
    result.encoding = "utf-8"
    return result


def assert_empty_storage():
    with get_connection() as conn:
        for table in ("orders", "order_items", "outbox"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


BAD_PRODUCTS = [
    pytest.param(None, id="null"),
    pytest.param([], id="array"),
    pytest.param(True, id="boolean"),
    pytest.param("not-a-product", id="string"),
    pytest.param({}, id="empty-object"),
    *[
        pytest.param(
            {k: v for k, v in PRODUCT.items() if k != field}, id=f"missing-{field}"
        )
        for field in ("name", "price_cents", "currency")
    ],
    *[
        pytest.param({**PRODUCT, "price_cents": value}, id=f"price-{label}")
        for label, value in (
            ("null", None),
            ("zero", 0),
            ("negative", -5),
            ("bool", True),
            ("string", "500"),
            ("fraction", 1.5),
        )
    ],
    *[
        pytest.param({**PRODUCT, "name": value}, id=f"name-{label}")
        for label, value in (("null", None), ("empty", ""), ("number", 7))
    ],
    *[
        pytest.param({**PRODUCT, "currency": value}, id=f"currency-{label}")
        for label, value in (
            ("null", None),
            ("empty", ""),
            ("short", "US"),
            ("long", "USDX"),
            ("number", 123),
        )
    ],
]


@pytest.mark.parametrize("product", BAD_PRODUCTS)
def test_invalid_upstream_product_is_502_without_effects(
    isolated_client, monkeypatch, product
):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(product))
    before = main.ORDERS_CREATED._value.get()
    result = isolated_client.post("/orders", json=ORDER)
    assert result.status_code == 502, result.text
    assert_empty_storage()
    assert main.ORDERS_CREATED._value.get() == before


@pytest.mark.parametrize("body,status", [("{broken-json", 200), ("", 204)])
def test_non_json_upstream_is_502(isolated_client, monkeypatch, body, status):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: response(body, status, raw=True)
    )
    result = isolated_client.post("/orders", json=ORDER)
    assert result.status_code == 502, result.text
    assert_empty_storage()


@pytest.mark.parametrize(
    "status,expected", [(404, 400), (401, 502), (429, 502), (500, 502), (503, 502)]
)
def test_upstream_error_status_mapping(isolated_client, monkeypatch, status, expected):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response({}, status))
    assert isolated_client.post("/orders", json=ORDER).status_code == expected
    assert_empty_storage()


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({**ORDER, "items": []}, 400),
        ({**ORDER, "customer_id": ""}, 422),
        ({**ORDER, "items": [{"product_id": "", "quantity": 1}]}, 422),
        *[
            ({**ORDER, "items": [{"product_id": "one", "quantity": qty}]}, 422)
            for qty in (0, -1, 1.5)
        ],
    ],
)
def test_input_boundaries_precede_upstream_and_storage(
    isolated_client, monkeypatch, payload, expected
):
    upstream = Mock(side_effect=AssertionError("No upstream call expected"))
    monkeypatch.setattr(requests, "get", upstream)
    assert isolated_client.post("/orders", json=payload).status_code == expected
    upstream.assert_not_called()
    assert_empty_storage()


def test_valid_multi_product_and_extra_catalog_fields(isolated_client, monkeypatch):
    get = Mock(
        side_effect=[
            response({**PRODUCT, "description": "synthetic"}),
            response({**PRODUCT, "id": "two", "price_cents": 125}),
        ]
    )
    monkeypatch.setattr(requests, "get", get)
    payload = {
        **ORDER,
        "items": [*ORDER["items"], {"product_id": "two", "quantity": 3}],
    }
    result = isolated_client.post("/orders", json=payload)
    assert result.status_code == 201
    assert result.json()["total_cents"] == 1375
    assert [i["price_cents"] for i in result.json()["items"]] == [500, 125]
    assert all(call.kwargs == {"timeout": 5} for call in get.call_args_list)


@pytest.mark.parametrize(
    "second", [{**PRODUCT, "currency": "EUR"}, {**PRODUCT, "price_cents": None}]
)
def test_second_product_rejection_leaves_no_partial_order(
    isolated_client, monkeypatch, second
):
    monkeypatch.setattr(
        requests, "get", Mock(side_effect=[response(PRODUCT), response(second)])
    )
    payload = {
        **ORDER,
        "items": [*ORDER["items"], {"product_id": "two", "quantity": 1}],
    }
    result = isolated_client.post("/orders", json=payload)
    assert result.status_code == (400 if second["currency"] == "EUR" else 502)
    assert_empty_storage()


def test_outbox_insert_failure_rolls_back_order_and_items(isolated_client, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(PRODUCT))
    with get_connection() as conn:
        conn.execute(
            "CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    before = main.ORDERS_CREATED._value.get()
    assert isolated_client.post("/orders", json=ORDER).status_code == 500
    assert_empty_storage()
    assert main.ORDERS_CREATED._value.get() == before


def test_partial_dispatch_failure_retries_same_order(isolated_client, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(PRODUCT))
    rabbit = Mock()
    kafka = Mock(side_effect=[KafkaError("synthetic failure"), None])
    monkeypatch.setattr(main, "send_payment_request", rabbit)
    monkeypatch.setattr(main, "publish_event", kafka)
    result = isolated_client.post("/orders", json=ORDER)
    assert result.status_code == 503
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM outbox").fetchone()
        assert row["attempts"] == 1 and row["last_error"] == "KafkaError"
    result = isolated_client.post(result.json()["detail"]["retry_url"])
    assert result.status_code == 200
    assert rabbit.call_count == 2
    assert rabbit.call_args_list[0] == rabbit.call_args_list[1]
    assert len(isolated_client.get("/orders").json()) == 1
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0


@pytest.mark.parametrize(
    "event_type,status,counter_name",
    [
        ("payment.authorized", "paid", "ORDERS_PAID"),
        ("payment.failed", "payment_failed", "ORDERS_FAILED"),
    ],
)
def test_payment_event_idempotence(
    isolated_client, monkeypatch, event_type, status, counter_name
):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(PRODUCT))
    order = isolated_client.post("/orders", json=ORDER).json()
    before = getattr(main, counter_name)._value.get()
    event = {"event_type": event_type, "payload": {"order_id": order["id"]}}
    main.handle_payment_event(event)
    main.handle_payment_event(event)
    assert isolated_client.get(f"/orders/{order['id']}").json()["status"] == status
    assert getattr(main, counter_name)._value.get() == before + 1


@pytest.mark.parametrize("stuck", [None, "outbox", "consumer"])
def test_shutdown_waits_before_closing_producer(monkeypatch, stuck):
    events = []

    class Thread:
        def __init__(self, name):
            self.name = name

        def join(self, timeout):
            events.append((self.name, timeout))

        def is_alive(self):
            return self.name == stuck

    stop = threading.Event()
    producer = Mock()
    producer.flush.side_effect = lambda: events.append("flush")
    producer.close.side_effect = lambda: events.append("close")
    monkeypatch.setattr(main.app.state, "stop_event", stop)
    monkeypatch.setattr(main.app.state, "outbox_thread", Thread("outbox"))
    monkeypatch.setattr(main.app.state, "consumer_thread", Thread("consumer"))
    monkeypatch.setattr(main.app.state, "producer", producer)
    if stuck:
        with pytest.raises(RuntimeError, match="producer remains open"):
            main.on_shutdown()
        producer.flush.assert_not_called()
        producer.close.assert_not_called()
    else:
        main.on_shutdown()
        assert events == [("outbox", 15), ("consumer", 5), "flush", "close"]
    assert stop.is_set()


def test_outbox_worker_drains_durable_record(isolated_client, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(PRODUCT))
    monkeypatch.setattr(
        main, "send_payment_request", Mock(side_effect=OSError("synthetic offline"))
    )
    result = isolated_client.post("/orders", json=ORDER)
    assert result.status_code == 503
    stop = Mock()
    stop.wait.side_effect = [False, True]
    stop.is_set.return_value = False
    monkeypatch.setattr(main.app.state, "stop_event", stop)
    delivery = Mock()
    monkeypatch.setattr(main, "send_payment_request", delivery)
    main._outbox_loop()
    delivery.assert_called_once()
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0


def test_health_and_metrics(isolated_client):
    assert isolated_client.get("/health").json() == {"status": "ok"}
    metrics = isolated_client.get("/metrics")
    assert metrics.status_code == 200
    assert "orders_created_total" in metrics.text
    assert isolated_client.get("/orders/missing").status_code == 404

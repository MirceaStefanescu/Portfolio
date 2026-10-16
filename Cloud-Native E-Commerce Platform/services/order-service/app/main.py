import logging
import os
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pika
import psycopg
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from kafka.errors import KafkaError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.db import get_connection, init_db
from app.messaging import (
    build_producer,
    publish_event,
    send_payment_request,
    start_payment_event_consumer,
)
from app.models import Order, OrderCreate, OrderItem

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    on_startup()
    try:
        yield
    finally:
        on_shutdown()


app = FastAPI(title="Order Service", lifespan=lifespan)

ORDERS_CREATED = Counter("orders_created_total", "Total orders created")
ORDERS_PAID = Counter("orders_paid_total", "Total orders paid")
ORDERS_FAILED = Counter("orders_failed_total", "Total orders failed")


def on_startup() -> None:
    init_db()
    app.state.producer = build_producer()
    app.state.orders_topic = os.getenv("KAFKA_TOPIC_ORDERS", "orders")
    app.state.stop_event = threading.Event()
    app.state.consumer_thread = start_payment_event_consumer(
        handle_payment_event,
        app.state.stop_event,
    )
    app.state.dispatch_lock = threading.Lock()
    app.state.outbox_thread = None
    if (
        os.getenv("OUTBOX_ENABLED", "true").lower() == "true"
        and os.getenv("RABBITMQ_ENABLED", "true").lower() == "true"
    ):
        app.state.outbox_thread = threading.Thread(target=_outbox_loop, daemon=True)
        app.state.outbox_thread.start()


def on_shutdown() -> None:
    app.state.stop_event.set()
    outbox = app.state.outbox_thread
    if outbox is not None:
        outbox.join(timeout=15)
        if outbox.is_alive():
            raise RuntimeError("Outbox dispatcher did not stop; producer remains open")
    thread = app.state.consumer_thread
    if thread is not None:
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("Consumer did not stop; producer remains open")
    producer = getattr(app.state, "producer", None)
    if producer:
        producer.flush()
        producer.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _fetch_product(product_id: str) -> dict:
    base_url = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8000")
    try:
        response = requests.get(f"{base_url}/products/{product_id}", timeout=5)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502, detail="Product service unavailable"
        ) from exc
    if response.status_code == 404:
        raise HTTPException(status_code=400, detail=f"Product {product_id} not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Product service unavailable")
    return response.json()


def _load_items(order_id: str) -> list[OrderItem]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT product_id, name, quantity, price_cents FROM order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        return [OrderItem(**dict(row)) for row in rows]


def _load_order(order_id: str) -> Order:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Order not found")
        items = _load_items(order_id)
        return Order(items=items, **dict(row))


def _update_order_status(order_id: str, status: str) -> bool:
    allowed = {
        "paid": ["pending"],
        "payment_failed": ["pending"],
        "cancelled": ["paid", "cancel_pending"],
    }[status]
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status IN ("
            + ",".join("?" for _ in allowed)
            + ")",
            (status, _now(), order_id, *allowed),
        )
        return result.rowcount > 0


def handle_payment_event(event: dict) -> None:
    if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
        raise TypeError("Invalid payment event")
    event_type = event.get("event_type")
    payload = event["payload"]
    order_id = payload.get("order_id")
    if not order_id:
        return

    if event_type == "payment.authorized" and _update_order_status(order_id, "paid"):
        ORDERS_PAID.inc()
    elif event_type == "payment.failed" and _update_order_status(
        order_id, "payment_failed"
    ):
        ORDERS_FAILED.inc()
    elif event_type == "payment.refunded":
        _update_order_status(order_id, "cancelled")


@app.get("/orders", response_model=list[Order])
def list_orders() -> list[Order]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    orders = []
    for row in rows:
        order_id = row["id"]
        items = _load_items(order_id)
        orders.append(Order(items=items, **dict(row)))
    return orders


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str) -> Order:
    return _load_order(order_id)


@app.post("/orders", response_model=Order, status_code=201)
def create_order(payload: OrderCreate) -> Order:
    if not payload.items:
        raise HTTPException(
            status_code=400, detail="Order must include at least one item"
        )

    product_ids = [item.product_id for item in payload.items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=400, detail="Duplicate products are not supported"
        )

    items: list[OrderItem] = []
    total_cents = 0
    currency = None

    for item in payload.items:
        product = _fetch_product(item.product_id)
        product_currency = product["currency"]
        if currency and product_currency != currency:
            raise HTTPException(
                status_code=400, detail="Mixed currencies are not supported"
            )
        currency = product_currency
        line_total = product["price_cents"] * item.quantity
        total_cents += line_total
        items.append(
            OrderItem(
                product_id=item.product_id,
                name=product["name"],
                quantity=item.quantity,
                price_cents=product["price_cents"],
            )
        )

    order_id = str(uuid.uuid4())
    now = _now()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO orders (id, customer_id, status, total_cents, currency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, payload.customer_id, "pending", total_cents, currency, now, now),
        )
        for item in items:
            conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, name, quantity, price_cents)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order_id, item.product_id, item.name, item.quantity, item.price_cents),
            )
        conn.execute(
            "INSERT INTO outbox (id, order_id, action, created_at) VALUES (?, ?, ?, ?)",
            (order_id + ":authorize", order_id, "authorize", now),
        )
        conn.commit()

    ORDERS_CREATED.inc()

    order = Order(
        id=order_id,
        customer_id=payload.customer_id,
        status="pending",
        total_cents=total_cents,
        currency=currency,
        items=items,
        created_at=now,
        updated_at=now,
    )
    _dispatch_order(order)
    return order


def _dispatch_order(order: Order, action: str = "authorize") -> None:
    with app.state.dispatch_lock:
        _dispatch_locked(order, action)


def _dispatch_locked(order: Order, action: str) -> None:
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT id FROM outbox WHERE id = ?", (order.id + ":" + action,)
        ).fetchone()
    if pending is None:
        return
    try:
        send_payment_request(
            {
                "order_id": order.id,
                "amount_cents": order.total_cents,
                "currency": order.currency,
                "customer_id": order.customer_id,
                "action": action,
            }
        )
        publish_event(
            app.state.producer,
            app.state.orders_topic,
            "order.created"
            if action == "authorize"
            else "order.cancellation_requested",
            {
                "order_id": order.id,
                "customer_id": order.customer_id,
                "total_cents": order.total_cents,
                "currency": order.currency,
                "status": "pending",
            },
        )
    except (pika.exceptions.AMQPError, KafkaError, OSError) as exc:
        with get_connection() as conn:
            conn.execute(
                "UPDATE outbox SET attempts = attempts + 1, last_error = ? WHERE id = ?",
                (type(exc).__name__, order.id + ":" + action),
            )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Order saved; delivery is pending automatic recovery.",
                "order_id": order.id,
                "retry_url": f"/orders/{order.id}/retry-delivery",
            },
        ) from exc
    with get_connection() as conn:
        conn.execute("DELETE FROM outbox WHERE id = ?", (order.id + ":" + action,))


def _outbox_loop() -> None:
    while not app.state.stop_event.wait(2):
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT order_id, action FROM outbox ORDER BY created_at LIMIT 50"
                ).fetchall()
            for row in rows:
                if app.state.stop_event.is_set():
                    break
                try:
                    _dispatch_order(_load_order(row["order_id"]), row["action"])
                except HTTPException:
                    LOGGER.warning(
                        "Outbox delivery pending for order %s", row["order_id"]
                    )
        except (sqlite3.Error, psycopg.Error, OSError):
            LOGGER.exception("Outbox database unavailable; pending records retained")


@app.post("/orders/{order_id}/retry-delivery", response_model=Order)
def retry_delivery(order_id: str) -> Order:
    order = _load_order(order_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT action FROM outbox WHERE order_id = ?", (order_id,)
        ).fetchall()
    for row in rows:
        _dispatch_order(order, row["action"])
    return _load_order(order_id)


@app.post("/orders/{order_id}/cancel", response_model=Order, status_code=202)
def cancel_order(order_id: str) -> Order:
    order = _load_order(order_id)
    if order.status in ("cancel_pending", "cancelled"):
        return order
    if order.status != "paid":
        raise HTTPException(
            status_code=409, detail="Only a paid order can enter refund compensation"
        )
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
            ("cancel_pending", _now(), order_id, "paid"),
        )
        conn.execute(
            "INSERT INTO outbox (id, order_id, action, created_at) VALUES (?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
            (order_id + ":refund", order_id, "refund", _now()),
        )
    # The durable outbox completes compensation after broker recovery as well.
    return _load_order(order_id)

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from kafka.errors import KafkaError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.db import get_connection, init_db
from app.messaging import build_producer, publish_event, start_payment_request_consumer
from app.models import Payment, PaymentCreate

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    on_startup()
    try:
        yield
    finally:
        on_shutdown()


app = FastAPI(title="Payment Service", lifespan=lifespan)

PAYMENTS_PROCESSED = Counter("payments_processed_total", "Total payments processed")
PAYMENTS_FAILED = Counter("payments_failed_total", "Total payments failed")


def on_startup() -> None:
    init_db()
    app.state.producer = build_producer()
    app.state.kafka_topic = os.getenv("KAFKA_TOPIC_PAYMENTS", "payments")
    app.state.stop_event = threading.Event()
    app.state.consumer_thread = start_payment_request_consumer(
        handle_payment_request,
        app.state.stop_event,
    )


def on_shutdown() -> None:
    app.state.stop_event.set()
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


def _create_payment(order_id: str, amount_cents: int, currency: str) -> Payment:
    status = "authorized" if amount_cents > 0 else "failed"
    payment_id = str(uuid.uuid4())
    created_at = _now()

    payment = Payment(
        id=payment_id,
        order_id=order_id,
        status=status,
        amount_cents=amount_cents,
        currency=currency.upper(),
        created_at=created_at,
    )

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM payments WHERE order_id = ? ORDER BY created_at LIMIT 1",
            (order_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["amount_cents"] != amount_cents
                or existing["currency"] != currency.upper()
            ):
                raise ValueError("Order already has a payment with different details")
            payment = Payment(**dict(existing))
        else:
            conn.execute(
                """
                INSERT INTO payments (id, order_id, status, amount_cents, currency, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payment.id,
                    payment.order_id,
                    payment.status,
                    payment.amount_cents,
                    payment.currency,
                    payment.created_at,
                ),
            )
        conn.commit()

    if existing is None:
        if payment.status == "authorized":
            PAYMENTS_PROCESSED.inc()
        else:
            PAYMENTS_FAILED.inc()

    # A redelivery must publish the saved result again before RabbitMQ can ack it.
    # Consumers use order_id/status idempotently; the payment row is created once.

    publish_event(
        app.state.producer,
        app.state.kafka_topic,
        f"payment.{payment.status}",
        payment.model_dump(),
    )
    return payment


def handle_payment_request(message: dict) -> None:
    if message.get("action", "authorize") == "refund":
        _refund_payment(message["order_id"])
        return
    payload = PaymentCreate.model_validate(message)
    _create_payment(payload.order_id, payload.amount_cents, payload.currency)


def _refund_payment(order_id: str) -> Payment:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM payments WHERE order_id = ? ORDER BY created_at LIMIT 1",
            (order_id,),
        ).fetchone()
        if row is None or row["status"] not in ("authorized", "refunded"):
            raise ValueError("Only an authorized payment can be refunded")
        conn.execute(
            "UPDATE payments SET status = ? WHERE id = ?", ("refunded", row["id"])
        )
        payment = Payment(**{**dict(row), "status": "refunded"})
        conn.commit()
    publish_event(
        app.state.producer,
        app.state.kafka_topic,
        "payment.refunded",
        payment.model_dump(),
    )
    return payment


@app.get("/payments", response_model=list[Payment])
def list_payments(order_id: str | None = None) -> list[Payment]:
    query = "SELECT * FROM payments"
    params = ()
    if order_id:
        query += " WHERE order_id = ?"
        params = (order_id,)
    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [Payment(**dict(row)) for row in rows]


@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str) -> Payment:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return Payment(**dict(row))


@app.post("/payments", response_model=Payment, status_code=201)
def create_payment(payload: PaymentCreate) -> Payment:
    try:
        return _create_payment(payload.order_id, payload.amount_cents, payload.currency)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KafkaError as exc:
        raise HTTPException(
            status_code=503,
            detail="Payment saved; event delivery pending. Retry this order.",
        ) from exc

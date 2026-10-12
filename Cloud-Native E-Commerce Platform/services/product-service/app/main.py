import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.db import get_connection, init_db
from app.messaging import build_producer, publish_event
from app.models import Product, ProductCreate, ProductUpdate

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    on_startup()
    try:
        yield
    finally:
        on_shutdown()


app = FastAPI(title="Product Service", lifespan=lifespan)

PRODUCTS_CREATED = Counter("products_created_total", "Total products created")
PRODUCTS_UPDATED = Counter("products_updated_total", "Total products updated")
PRODUCTS_DELETED = Counter("products_deleted_total", "Total products deleted")


def on_startup() -> None:
    init_db()
    app.state.producer = build_producer()
    app.state.kafka_topic = os.getenv("KAFKA_TOPIC", "products")


def on_shutdown() -> None:
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


@app.get("/products", response_model=list[Product])
def list_products() -> list[Product]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY created_at DESC"
        ).fetchall()
        return [Product(**dict(row)) for row in rows]


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return Product(**dict(row))


@app.post("/products", response_model=Product, status_code=201)
def create_product(payload: ProductCreate) -> Product:
    product_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    product = Product(
        id=product_id,
        name=payload.name,
        description=payload.description,
        price_cents=payload.price_cents,
        currency=payload.currency.upper(),
        created_at=now,
        updated_at=now,
    )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products (id, name, description, price_cents, currency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.id,
                product.name,
                product.description,
                product.price_cents,
                product.currency,
                product.created_at,
                product.updated_at,
            ),
        )
        conn.commit()

    PRODUCTS_CREATED.inc()
    publish_event(
        app.state.producer,
        app.state.kafka_topic,
        "product.created",
        product.model_dump(),
    )
    return product


@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: str, payload: ProductUpdate) -> Product:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")

        existing = dict(row)
        updated = {
            "name": payload.name or existing["name"],
            "description": payload.description
            if payload.description is not None
            else existing["description"],
            "price_cents": payload.price_cents or existing["price_cents"],
            "currency": (payload.currency or existing["currency"]).upper(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        conn.execute(
            """
            UPDATE products
            SET name = ?, description = ?, price_cents = ?, currency = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["description"],
                updated["price_cents"],
                updated["currency"],
                updated["updated_at"],
                product_id,
            ),
        )
        conn.commit()

        product = Product(
            id=product_id,
            name=updated["name"],
            description=updated["description"],
            price_cents=updated["price_cents"],
            currency=updated["currency"],
            created_at=existing["created_at"],
            updated_at=updated["updated_at"],
        )

    PRODUCTS_UPDATED.inc()
    publish_event(
        app.state.producer,
        app.state.kafka_topic,
        "product.updated",
        product.model_dump(),
    )
    return product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()

    PRODUCTS_DELETED.inc()
    publish_event(
        app.state.producer,
        app.state.kafka_topic,
        "product.deleted",
        {"id": product_id},
    )

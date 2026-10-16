import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


def db_path() -> str:
    return os.getenv("DB_PATH", "/data/orders.db")


class PostgresConnection:
    """Keep the existing fixed, parameterized SQL portable across the two test backends."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=()):
        # SQL is fixed application text, never a caller-provided query.
        if query == "BEGIN IMMEDIATE":
            return self.connection.execute("LOCK TABLE payments IN EXCLUSIVE MODE")
        return self.connection.execute(query.replace("?", "%s"), parameters)

    def commit(self):
        self.connection.commit()


@contextmanager
def get_connection() -> Iterator:
    url = os.getenv("DATABASE_URL")
    if url:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(
            url, row_factory=dict_row, connect_timeout=5
        ) as connection:
            yield PostgresConnection(connection)
        return
    conn = sqlite3.connect(db_path())
    try:
        conn.row_factory = sqlite3.Row
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, order_id TEXT NOT NULL, action TEXT NOT NULL,
            created_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '')""")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                status TEXT NOT NULL,
                total_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_cents INTEGER NOT NULL,
                PRIMARY KEY (order_id, product_id)
            )
            """
        )
        conn.commit()

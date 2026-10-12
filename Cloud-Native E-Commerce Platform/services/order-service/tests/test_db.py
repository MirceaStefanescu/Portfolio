import sqlite3

import pytest

from app.db import get_connection


def test_connection_is_closed_and_successful_transaction_persists(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    with get_connection() as conn:
        conn.execute("CREATE TABLE test (value INTEGER)")
        conn.execute("INSERT INTO test VALUES (7)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with get_connection() as reopened:
        assert reopened.execute("SELECT value FROM test").fetchone()[0] == 7


def test_failed_transaction_is_rolled_back_and_connection_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    with get_connection() as setup:
        setup.execute("CREATE TABLE test (value INTEGER)")
    with pytest.raises(RuntimeError, match="abort"), get_connection() as conn:
        conn.execute("INSERT INTO test VALUES (7)")
        raise RuntimeError("abort")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with get_connection() as reopened:
        assert reopened.execute("SELECT COUNT(*) FROM test").fetchone()[0] == 0

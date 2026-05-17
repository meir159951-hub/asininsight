"""
Smoke tests for the seed_mock_ppc CLI.

The CLI is designed to be safe to re-run: an existing connection for the same
customer is reused, mock snapshots are appended (the suggestion engine reads
the latest per data_type), and the suggestion table is reset for that
connection so the dashboard reflects the new state.

These tests monkey-patch `server._db` with an in-memory sqlite context manager
and import the CLI's `main` directly. They never touch the real local DB.
"""

from __future__ import annotations

import os
import sys
import sqlite3
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLASK_SECRET_KEY",         "test_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("PPC_TOKEN_ENCRYPTION_KEY", "rRiUz3xHGbXbBZI9xn-yY9JvJ6yL5y6KqzNc6VxQ1zU=")
os.environ.setdefault("SP_API_CLIENT_ID",         "test_client_id")
os.environ.setdefault("SP_API_CLIENT_SECRET",     "test_client_secret")


_PPC_SCHEMA = """
    CREATE TABLE amazon_connections (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id             TEXT NOT NULL,
        seller_id               TEXT,
        marketplace_id          TEXT NOT NULL DEFAULT 'ATVPDKIKX0DER',
        refresh_token_encrypted TEXT NOT NULL,
        ads_profile_id          TEXT,
        connected_at            REAL NOT NULL,
        last_synced_at          REAL,
        active                  INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE ppc_snapshots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id INTEGER NOT NULL,
        fetched_at    REAL NOT NULL,
        data_type     TEXT NOT NULL,
        data          TEXT NOT NULL
    );
    CREATE TABLE ppc_suggestions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id     INTEGER NOT NULL,
        campaign_id       TEXT,
        ad_group_id       TEXT,
        keyword_id        TEXT,
        suggestion_type   TEXT NOT NULL,
        current_value     TEXT,
        proposed_value    TEXT,
        reason            TEXT NOT NULL,
        estimated_savings REAL,
        confidence        TEXT NOT NULL DEFAULT 'medium',
        status            TEXT NOT NULL DEFAULT 'pending',
        created_at        REAL NOT NULL,
        decided_at        REAL,
        applied_at        REAL
    );
    CREATE TABLE seller_decisions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id       INTEGER NOT NULL,
        suggestion_id       INTEGER,
        suggestion_type     TEXT NOT NULL,
        keyword_id          TEXT,
        ad_group_id         TEXT,
        campaign_id         TEXT,
        current_value       TEXT,
        proposed_value      TEXT,
        estimated_impact    REAL,
        confidence          TEXT,
        decision            TEXT NOT NULL,
        edit_payload        TEXT,
        decided_at          REAL NOT NULL,
        observation_due_at  REAL
    );
"""


@pytest.fixture
def db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript(_PPC_SCHEMA)

    @contextmanager
    def _db():
        cur = conn.cursor()
        try:
            yield (cur, "?")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    import server
    monkeypatch.setattr(server, "_db", _db, raising=True)
    monkeypatch.setattr(server, "DATABASE_URL", "", raising=False)
    yield conn
    conn.close()


def test_seed_creates_connection_and_snapshots(db, capsys):
    from seed_mock_ppc import main
    rc = main(["--customer", "cust_demo", "--connection-id", "1"])
    assert rc == 0

    cur = db.cursor()
    cur.execute("SELECT customer_id FROM amazon_connections WHERE id = 1")
    assert cur.fetchone()[0] == "cust_demo"

    cur.execute("SELECT data_type, COUNT(*) FROM ppc_snapshots GROUP BY data_type")
    counts = dict(cur.fetchall())
    assert {"profiles", "campaigns", "ad_groups", "keywords", "search_terms"} <= set(counts)

    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE status = 'pending'")
    assert cur.fetchone()[0] >= 5

    out = capsys.readouterr().out
    assert "money found total:" in out
    assert "connection_id: 1" in out


def test_seed_is_idempotent_for_same_customer(db):
    from seed_mock_ppc import main
    main(["--customer", "cust_demo", "--connection-id", "1"])
    main(["--customer", "cust_demo", "--connection-id", "1"])

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM amazon_connections WHERE customer_id = 'cust_demo'")
    assert cur.fetchone()[0] == 1   # still one connection, not two

    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE status = 'pending'")
    pending_after = cur.fetchone()[0]
    assert pending_after >= 5
    # The second run wiped the first run's pending suggestions and rewrote
    # them, so the count is the rule output, not 2x.


def test_seed_refuses_to_overwrite_other_customers_connection(db):
    from seed_mock_ppc import main
    main(["--customer", "cust_a", "--connection-id", "1"])
    with pytest.raises(SystemExit):
        main(["--customer", "cust_b", "--connection-id", "1"])


def test_seed_skip_suggestions_flag(db):
    from seed_mock_ppc import main
    rc = main(["--customer", "cust_demo", "--connection-id", "1", "--no-suggestions"])
    assert rc == 0

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM ppc_snapshots")
    assert cur.fetchone()[0] == 5

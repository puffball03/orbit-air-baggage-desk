import sqlite3

DEFAULT_DB_PATH = "baggage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    passenger TEXT NOT NULL,
    flight TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('delayed', 'lost', 'damaged')),
    tier TEXT NOT NULL CHECK (tier IN ('standard', 'silver', 'gold')),
    status TEXT NOT NULL
        CHECK (status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
    assigned_agent TEXT,
    note TEXT,
    filed_at TEXT NOT NULL,
    deadline TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims (id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL
);
"""


def connect(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)

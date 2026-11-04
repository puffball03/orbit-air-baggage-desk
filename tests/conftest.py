from datetime import datetime

import pytest

import claims
import db

NOW = datetime(2026, 11, 2, 14, 0, 0)


@pytest.fixture
def now():
    """A fixed time, so no test depends on the real clock."""
    return NOW


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def make_claim(conn, now):
    """File a valid claim, with any field overridden, and return its id."""

    def _make_claim(**overrides):
        fields = {
            "passenger": "Ada Lovelace",
            "flight": "OA101",
            "claim_type": "lost",
            "tier": "standard",
            "note": None,
            "changed_by": "desk",
            "now": now,
        }
        fields.update(overrides)
        return claims.file_claim(conn, **fields)

    return _make_claim


@pytest.fixture
def fail_history_writes(conn):
    """Make every later insert into history fail, to test rollback."""

    def _fail_history_writes():
        conn.execute(
            """
            CREATE TRIGGER fail_history_writes BEFORE INSERT ON history
            BEGIN
                SELECT RAISE(ABORT, 'forced history failure');
            END
            """
        )

    return _fail_history_writes

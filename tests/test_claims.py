import sqlite3
from datetime import timedelta

import pytest

import claims
import db

CLAIM_COLUMNS = {
    "id",
    "passenger",
    "flight",
    "type",
    "tier",
    "status",
    "assigned_agent",
    "note",
    "filed_at",
    "deadline",
}
HISTORY_COLUMNS = {
    "id",
    "claim_id",
    "old_status",
    "new_status",
    "changed_by",
    "changed_at",
}


def count_rows(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def get_claim(conn, claim_id):
    return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()


def column_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_init_db_creates_both_tables_with_planned_columns(conn):
    assert column_names(conn, "claims") == CLAIM_COLUMNS
    assert column_names(conn, "history") == HISTORY_COLUMNS


def test_init_db_is_safe_to_run_twice(conn, make_claim):
    claim_id = make_claim()

    db.init_db(conn)

    assert get_claim(conn, claim_id) is not None


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [("type", "stolen"), ("tier", "platinum"), ("status", "archived")],
)
def test_database_check_constraints_reject_bad_values(conn, column, bad_value):
    row = {
        "passenger": "Ada Lovelace",
        "flight": "OA101",
        "type": "lost",
        "tier": "gold",
        "status": "open",
        "filed_at": "2026-11-02T14:00:00",
        "deadline": "2026-11-02T18:00:00",
    }
    row[column] = bad_value

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline)
            VALUES (:passenger, :flight, :type, :tier, :status, :filed_at, :deadline)
            """,
            row,
        )


def test_filing_saves_every_field(conn, make_claim, now):
    claim_id = make_claim(
        passenger="Grace Hopper",
        flight="OA202",
        claim_type="damaged",
        tier="gold",
        note="Handle snapped off",
    )

    claim = get_claim(conn, claim_id)

    assert claim["passenger"] == "Grace Hopper"
    assert claim["flight"] == "OA202"
    assert claim["type"] == "damaged"
    assert claim["tier"] == "gold"
    assert claim["status"] == "open"
    assert claim["assigned_agent"] is None
    assert claim["note"] == "Handle snapped off"
    assert claim["filed_at"] == now.isoformat()


def test_note_is_optional(conn, now):
    claim_id = claims.file_claim(
        conn,
        passenger="Ada Lovelace",
        flight="OA101",
        claim_type="lost",
        tier="standard",
        changed_by="desk",
        now=now,
    )

    assert get_claim(conn, claim_id)["note"] is None


@pytest.mark.parametrize("passenger", ["", "   ", "\t"])
def test_blank_passenger_is_rejected(make_claim, passenger):
    with pytest.raises(claims.ClaimError, match="(?i)passenger"):
        make_claim(passenger=passenger)


@pytest.mark.parametrize("flight", ["", "   ", "\t"])
def test_blank_flight_is_rejected(make_claim, flight):
    with pytest.raises(claims.ClaimError, match="(?i)flight"):
        make_claim(flight=flight)


@pytest.mark.parametrize("claim_type", ["stolen", "LOST", ""])
def test_unknown_type_is_rejected(make_claim, claim_type):
    with pytest.raises(claims.ClaimError, match="(?i)type"):
        make_claim(claim_type=claim_type)


@pytest.mark.parametrize("tier", ["platinum", "GOLD", ""])
def test_unknown_tier_is_rejected(make_claim, tier):
    with pytest.raises(claims.ClaimError, match="(?i)tier"):
        make_claim(tier=tier)


@pytest.mark.parametrize(
    "bad_field",
    [
        {"passenger": " "},
        {"flight": " "},
        {"claim_type": "stolen"},
        {"tier": "platinum"},
    ],
)
def test_rejected_claim_saves_nothing(conn, make_claim, bad_field):
    with pytest.raises(claims.ClaimError):
        make_claim(**bad_field)

    assert count_rows(conn, "claims") == 0
    assert count_rows(conn, "history") == 0


@pytest.mark.parametrize(
    ("tier", "hours"),
    [("gold", 4), ("silver", 24), ("standard", 72)],
)
def test_deadline_is_filed_time_plus_tier_hours(conn, make_claim, now, tier, hours):
    claim_id = make_claim(tier=tier)

    expected = now + timedelta(hours=hours)
    assert get_claim(conn, claim_id)["deadline"] == expected.isoformat()


def test_filing_writes_a_history_entry(conn, make_claim, now):
    claim_id = make_claim(changed_by="Priya")

    entries = conn.execute("SELECT * FROM history").fetchall()

    assert len(entries) == 1
    assert entries[0]["claim_id"] == claim_id
    assert entries[0]["old_status"] is None
    assert entries[0]["new_status"] == "open"
    assert entries[0]["changed_by"] == "Priya"
    assert entries[0]["changed_at"] == now.isoformat()


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({}, ["Ana", "Ben", "Cal"]),
        ({"status": "open"}, ["Ana", "Ben"]),
        ({"tier": "gold"}, ["Ana", "Cal"]),
        ({"status": "assigned", "tier": "gold"}, ["Cal"]),
        ({"status": "closed"}, []),
    ],
)
def test_list_claims_filters_by_status_and_tier(conn, make_claim, filters, expected):
    make_claim(passenger="Ana", tier="gold")
    make_claim(passenger="Ben", tier="silver")
    cal = make_claim(passenger="Cal", tier="gold")
    with conn:
        conn.execute("UPDATE claims SET status = 'assigned' WHERE id = ?", (cal,))

    listed = claims.list_claims(conn, **filters)

    assert sorted(claim["passenger"] for claim in listed) == expected


def test_failed_history_write_leaves_no_claim(conn, make_claim, fail_history_writes):
    fail_history_writes()

    with pytest.raises(sqlite3.Error):
        make_claim()

    # Same connection on purpose: it can see uncommitted work, so this test
    # fails if the transaction is removed. A new connection could not see it.
    assert count_rows(conn, "claims") == 0

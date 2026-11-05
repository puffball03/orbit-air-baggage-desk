import sqlite3
from datetime import timedelta

import pytest

import claims

ACTIONS = {
    "assign": lambda conn, claim_id, by, at: claims.assign_claim(conn, claim_id, "Priya", by, at),
    "resolve": lambda conn, claim_id, by, at: claims.resolve_claim(conn, claim_id, by, at),
    "close": lambda conn, claim_id, by, at: claims.close_claim(conn, claim_id, by, at),
}


def get_claim(conn, claim_id):
    return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()


def history_rows(conn, claim_id):
    return conn.execute(
        "SELECT * FROM history WHERE claim_id = ? ORDER BY id", (claim_id,)
    ).fetchall()


@pytest.fixture
def claim_in(conn, make_claim):
    """File a claim, then put it in a status with direct SQL and no history entry."""

    def _claim_in(status, agent=None):
        claim_id = make_claim()
        with conn:
            conn.execute(
                "UPDATE claims SET status = ?, assigned_agent = ? WHERE id = ?",
                (status, agent, claim_id),
            )
        return claim_id

    return _claim_in


def test_assigning_an_open_claim_sets_the_agent_and_status(conn, claim_in, now):
    claim_id = claim_in("open")

    claims.assign_claim(conn, claim_id, "Priya", "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "assigned"
    assert claim["assigned_agent"] == "Priya"


def test_assigning_an_escalated_claim_replaces_the_agent(conn, claim_in, now):
    claim_id = claim_in("escalated", agent="Marco")

    claims.assign_claim(conn, claim_id, "Priya", "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "assigned"
    assert claim["assigned_agent"] == "Priya"


@pytest.mark.parametrize("agent", ["", "   ", "\t", None])
def test_blank_agent_is_rejected_and_nothing_is_saved(conn, claim_in, now, agent):
    claim_id = claim_in("open")
    entries_before = len(history_rows(conn, claim_id))

    with pytest.raises(claims.ClaimError, match="(?i)agent"):
        claims.assign_claim(conn, claim_id, agent, "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "open"
    assert claim["assigned_agent"] is None
    assert len(history_rows(conn, claim_id)) == entries_before


def test_assigning_an_assigned_claim_is_rejected(conn, claim_in, now):
    claim_id = claim_in("assigned", agent="Marco")

    with pytest.raises(claims.ClaimError, match="assigned.*assigned"):
        claims.assign_claim(conn, claim_id, "Priya", "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "assigned"
    assert claim["assigned_agent"] == "Marco"


def test_resolving_an_assigned_claim_keeps_the_agent(conn, claim_in, now):
    claim_id = claim_in("assigned", agent="Marco")

    claims.resolve_claim(conn, claim_id, "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "resolved"
    assert claim["assigned_agent"] == "Marco"


def test_resolving_an_escalated_claim_keeps_the_agent(conn, claim_in, now):
    claim_id = claim_in("escalated", agent="Marco")

    claims.resolve_claim(conn, claim_id, "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "resolved"
    assert claim["assigned_agent"] == "Marco"


def test_closing_a_resolved_claim_keeps_the_agent(conn, claim_in, now):
    claim_id = claim_in("resolved", agent="Marco")

    claims.close_claim(conn, claim_id, "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "closed"
    assert claim["assigned_agent"] == "Marco"


@pytest.mark.parametrize(
    ("action", "start", "target"),
    [
        ("assign", "resolved", "assigned"),
        ("assign", "closed", "assigned"),
        ("resolve", "open", "resolved"),
        ("resolve", "resolved", "resolved"),
        ("resolve", "closed", "resolved"),
        ("close", "open", "closed"),
        ("close", "assigned", "closed"),
        ("close", "escalated", "closed"),
        ("close", "closed", "closed"),
    ],
)
def test_disallowed_changes_are_rejected_and_nothing_is_saved(
    conn, claim_in, now, action, start, target
):
    claim_id = claim_in(start, agent="Marco")
    entries_before = len(history_rows(conn, claim_id))

    with pytest.raises(claims.ClaimError, match=f"{start}.*{target}"):
        ACTIONS[action](conn, claim_id, "desk", now)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == start
    assert claim["assigned_agent"] == "Marco"
    assert len(history_rows(conn, claim_id)) == entries_before


@pytest.mark.parametrize(
    "call",
    [
        lambda conn, now: claims.assign_claim(conn, 999, "Priya", "desk", now),
        lambda conn, now: claims.resolve_claim(conn, 999, "desk", now),
        lambda conn, now: claims.close_claim(conn, 999, "desk", now),
        lambda conn, now: claims.get_history(conn, 999),
    ],
    ids=["assign", "resolve", "close", "history"],
)
def test_unknown_claim_id_is_rejected(conn, now, call):
    with pytest.raises(claims.ClaimError, match="999"):
        call(conn, now)


@pytest.mark.parametrize(
    ("action", "start", "target"),
    [
        ("assign", "open", "assigned"),
        ("assign", "escalated", "assigned"),
        ("resolve", "assigned", "resolved"),
        ("resolve", "escalated", "resolved"),
        ("close", "resolved", "closed"),
    ],
)
def test_each_change_adds_a_complete_history_entry(conn, claim_in, now, action, start, target):
    claim_id = claim_in(start, agent="Marco")
    entries_before = len(history_rows(conn, claim_id))
    later = now + timedelta(hours=1)

    ACTIONS[action](conn, claim_id, "Dana", later)

    entries = history_rows(conn, claim_id)
    assert len(entries) == entries_before + 1
    assert entries[-1]["old_status"] == start
    assert entries[-1]["new_status"] == target
    assert entries[-1]["changed_by"] == "Dana"
    assert entries[-1]["changed_at"] == later.isoformat()


def test_get_history_returns_the_full_trail_in_order(conn, make_claim, now):
    claim_id = make_claim(changed_by="Filer")
    other_id = make_claim(passenger="Someone Else")
    assigned_at = now + timedelta(hours=1)
    resolved_at = now + timedelta(hours=2)
    closed_at = now + timedelta(hours=3)
    claims.assign_claim(conn, claim_id, "Priya", "Dana", assigned_at)
    claims.assign_claim(conn, other_id, "Marco", "Dana", assigned_at)
    claims.resolve_claim(conn, claim_id, "Priya", resolved_at)
    claims.close_claim(conn, claim_id, "Dana", closed_at)

    trail = claims.get_history(conn, claim_id)

    assert [
        (entry["old_status"], entry["new_status"], entry["changed_by"], entry["changed_at"])
        for entry in trail
    ] == [
        (None, "open", "Filer", now.isoformat()),
        ("open", "assigned", "Dana", assigned_at.isoformat()),
        ("assigned", "resolved", "Priya", resolved_at.isoformat()),
        ("resolved", "closed", "Dana", closed_at.isoformat()),
    ]


@pytest.mark.parametrize(
    ("action", "start", "agent"),
    [
        ("assign", "open", None),
        ("assign", "escalated", "Marco"),
        ("resolve", "assigned", "Marco"),
        ("resolve", "escalated", "Marco"),
        ("close", "resolved", "Marco"),
    ],
)
def test_failed_history_write_leaves_the_claim_unchanged(
    conn, claim_in, fail_history_writes, now, action, start, agent
):
    claim_id = claim_in(start, agent=agent)
    fail_history_writes()

    with pytest.raises(sqlite3.Error):
        ACTIONS[action](conn, claim_id, "desk", now)

    # Same connection on purpose: it can see uncommitted work, so this test
    # fails if the transaction is removed. A new connection could not see it.
    claim = get_claim(conn, claim_id)
    assert claim["status"] == start
    assert claim["assigned_agent"] == agent

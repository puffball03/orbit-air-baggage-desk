import sqlite3
from datetime import timedelta

import pytest

import claims

ONE_MINUTE = timedelta(minutes=1)
GOLD_HOURS = timedelta(hours=4)


def get_claim(conn, claim_id):
    return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()


def history_rows(conn, claim_id):
    return conn.execute(
        "SELECT * FROM history WHERE claim_id = ? ORDER BY id", (claim_id,)
    ).fetchall()


@pytest.fixture
def gold_claim_in(conn, make_claim):
    """File a gold claim, then put it in a status with direct SQL and no history entry."""

    def _gold_claim_in(status="open", agent=None):
        claim_id = make_claim(tier="gold")
        with conn:
            conn.execute(
                "UPDATE claims SET status = ?, assigned_agent = ? WHERE id = ?",
                (status, agent, claim_id),
            )
        return claim_id

    return _gold_claim_in


@pytest.fixture
def overdue_time(now):
    """One minute after the deadline of a gold claim filed at now."""
    return now + GOLD_HOURS + ONE_MINUTE


def test_is_overdue_is_false_one_minute_before_the_deadline(conn, gold_claim_in, now):
    claim = get_claim(conn, gold_claim_in())

    assert claims.is_overdue(claim, now + GOLD_HOURS - ONE_MINUTE) is False


def test_is_overdue_is_false_exactly_at_the_deadline(conn, gold_claim_in, now):
    claim = get_claim(conn, gold_claim_in())

    assert claims.is_overdue(claim, now + GOLD_HOURS) is False


def test_is_overdue_is_true_one_minute_after_the_deadline(conn, gold_claim_in, now):
    claim = get_claim(conn, gold_claim_in())

    assert claims.is_overdue(claim, now + GOLD_HOURS + ONE_MINUTE) is True


def test_overdue_open_claim_escalates(conn, gold_claim_in, overdue_time):
    claim_id = gold_claim_in("open")

    claims.escalate_overdue(conn, overdue_time)

    assert get_claim(conn, claim_id)["status"] == "escalated"


def test_overdue_assigned_claim_escalates_and_keeps_its_agent(conn, gold_claim_in, overdue_time):
    claim_id = gold_claim_in("assigned", agent="Marco")

    claims.escalate_overdue(conn, overdue_time)

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "escalated"
    assert claim["assigned_agent"] == "Marco"


@pytest.mark.parametrize("before_deadline", [ONE_MINUTE, timedelta(0)], ids=["before", "exactly_at"])
@pytest.mark.parametrize(("status", "agent"), [("open", None), ("assigned", "Marco")])
def test_claim_not_yet_overdue_is_left_alone(
    conn, gold_claim_in, now, before_deadline, status, agent
):
    claim_id = gold_claim_in(status, agent=agent)
    entries_before = len(history_rows(conn, claim_id))

    escalated = claims.escalate_overdue(conn, now + GOLD_HOURS - before_deadline)

    assert escalated == []
    assert get_claim(conn, claim_id)["status"] == status
    assert len(history_rows(conn, claim_id)) == entries_before


@pytest.mark.parametrize("status", ["resolved", "closed", "escalated"])
def test_other_statuses_are_left_alone_even_past_the_deadline(
    conn, gold_claim_in, overdue_time, status
):
    claim_id = gold_claim_in(status, agent="Marco")
    entries_before = len(history_rows(conn, claim_id))

    escalated = claims.escalate_overdue(conn, overdue_time)

    assert escalated == []
    assert get_claim(conn, claim_id)["status"] == status
    assert len(history_rows(conn, claim_id)) == entries_before


def test_escalate_overdue_returns_exactly_the_ids_it_escalated(
    conn, gold_claim_in, make_claim, overdue_time
):
    assert claims.escalate_overdue(conn, overdue_time) == []

    overdue_open = gold_claim_in("open")
    gold_claim_in("resolved", agent="Marco")
    make_claim(tier="standard")
    overdue_assigned = gold_claim_in("assigned", agent="Marco")

    assert claims.escalate_overdue(conn, overdue_time) == [overdue_open, overdue_assigned]
    assert claims.escalate_overdue(conn, overdue_time) == []


@pytest.mark.parametrize(("status", "agent"), [("open", None), ("assigned", "Marco")])
def test_escalation_adds_a_complete_history_entry(
    conn, gold_claim_in, overdue_time, status, agent
):
    claim_id = gold_claim_in(status, agent=agent)
    entries_before = len(history_rows(conn, claim_id))

    claims.escalate_overdue(conn, overdue_time)

    entries = history_rows(conn, claim_id)
    assert len(entries) == entries_before + 1
    assert entries[-1]["old_status"] == status
    assert entries[-1]["new_status"] == "escalated"
    assert entries[-1]["changed_by"] == "system"
    assert entries[-1]["changed_at"] == overdue_time.isoformat()


@pytest.mark.parametrize(
    ("tier", "hours"),
    [("gold", 4), ("silver", 24), ("standard", 72)],
)
def test_each_tier_escalates_only_after_its_own_deadline(conn, make_claim, now, tier, hours):
    claim_id = make_claim(tier=tier)
    deadline = now + timedelta(hours=hours)

    assert claims.escalate_overdue(conn, deadline) == []
    assert get_claim(conn, claim_id)["status"] == "open"

    assert claims.escalate_overdue(conn, deadline + ONE_MINUTE) == [claim_id]
    assert get_claim(conn, claim_id)["status"] == "escalated"


def test_failed_history_write_leaves_every_claim_unchanged(
    conn, gold_claim_in, fail_history_writes, overdue_time
):
    open_id = gold_claim_in("open")
    assigned_id = gold_claim_in("assigned", agent="Marco")
    fail_history_writes()

    with pytest.raises(sqlite3.Error):
        claims.escalate_overdue(conn, overdue_time)

    # Same connection on purpose: it can see uncommitted work, so this test
    # fails if the transaction is removed. A new connection could not see it.
    assert get_claim(conn, open_id)["status"] == "open"
    assert get_claim(conn, assigned_id)["status"] == "assigned"
    assert get_claim(conn, assigned_id)["assigned_agent"] == "Marco"

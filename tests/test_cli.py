from datetime import UTC, datetime, timedelta

import pytest

import claims

AWARE_LATER = datetime(2026, 12, 2, 14, 0, 0, tzinfo=UTC)
ACTIONS = {
    "assign": lambda conn, claim_id, at: claims.assign_claim(conn, claim_id, "Priya", "desk", at),
    "resolve": lambda conn, claim_id, at: claims.resolve_claim(conn, claim_id, "desk", at),
    "close": lambda conn, claim_id, at: claims.close_claim(conn, claim_id, "desk", at),
}


def get_claim(conn, claim_id):
    return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()


def history_count(conn, claim_id):
    return conn.execute(
        "SELECT COUNT(*) FROM history WHERE claim_id = ?", (claim_id,)
    ).fetchone()[0]


@pytest.fixture
def resolve_now():
    """Import inside a fixture, so each test reports its own failure if main.py is missing."""
    import main

    return main.resolve_now


@pytest.mark.parametrize("bad_time", [AWARE_LATER, "2026-11-02T14:00:00"], ids=["aware", "text"])
def test_filing_rejects_a_time_in_the_wrong_form_and_saves_nothing(conn, make_claim, bad_time):
    with pytest.raises(claims.ClaimError, match="(?i)time"):
        make_claim(now=bad_time)

    assert conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("action", "earlier_actions", "status"),
    [
        ("assign", [], "open"),
        ("resolve", ["assign"], "assigned"),
        ("close", ["assign", "resolve"], "resolved"),
    ],
)
def test_status_change_rejects_an_aware_time_and_saves_nothing(
    conn, make_claim, now, action, earlier_actions, status
):
    claim_id = make_claim()
    for earlier in earlier_actions:
        ACTIONS[earlier](conn, claim_id, now)
    entries_before = history_count(conn, claim_id)

    with pytest.raises(claims.ClaimError, match="(?i)time"):
        ACTIONS[action](conn, claim_id, AWARE_LATER)

    assert get_claim(conn, claim_id)["status"] == status
    assert history_count(conn, claim_id) == entries_before


def test_is_overdue_rejects_an_aware_time(conn, make_claim):
    claim = get_claim(conn, make_claim())

    with pytest.raises(claims.ClaimError, match="(?i)time"):
        claims.is_overdue(claim, AWARE_LATER)


def test_escalate_overdue_rejects_an_aware_time_and_changes_nothing(conn, make_claim):
    claim_id = make_claim(tier="gold")

    with pytest.raises(claims.ClaimError, match="(?i)time"):
        claims.escalate_overdue(conn, AWARE_LATER)

    assert get_claim(conn, claim_id)["status"] == "open"


def test_a_rejected_aware_filing_does_not_block_later_escalation(conn, make_claim, now):
    claim_id = make_claim(tier="gold")
    with pytest.raises(claims.ClaimError):
        make_claim(tier="gold", now=AWARE_LATER)

    assert claims.escalate_overdue(conn, now + timedelta(days=30)) == [claim_id]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-02T14:00:00", datetime(2026, 11, 2, 14, 0, 0)),
        ("2026-11-02T14:00:00+00:00", datetime(2026, 11, 2, 14, 0, 0)),
        ("2026-11-02T14:00:00Z", datetime(2026, 11, 2, 14, 0, 0)),
        ("2026-11-02T14:00:00-05:00", datetime(2026, 11, 2, 19, 0, 0)),
    ],
    ids=["naive", "utc_offset", "z_suffix", "other_offset"],
)
def test_resolve_now_returns_naive_utc(resolve_now, value, expected):
    resolved = resolve_now(value)

    assert resolved == expected
    assert resolved.tzinfo is None


@pytest.mark.parametrize("value", ["", "yesterday", "2026-13-45T00:00:00"])
def test_resolve_now_rejects_a_bad_value_with_a_clear_error(resolve_now, value):
    with pytest.raises(claims.ClaimError, match="--now"):
        resolve_now(value)


def test_resolve_now_without_a_value_returns_a_naive_time(resolve_now):
    assert resolve_now().tzinfo is None


def test_a_converted_offset_time_can_file_and_escalate(conn, make_claim, resolve_now):
    claim_id = make_claim(tier="gold", now=resolve_now("2026-11-02T09:00:00-05:00"))

    assert get_claim(conn, claim_id)["filed_at"] == "2026-11-02T14:00:00"
    assert claims.escalate_overdue(conn, resolve_now("2026-11-02T18:01:00Z")) == [claim_id]

from datetime import datetime, timedelta

CLAIM_TYPES = ("delayed", "lost", "damaged")
DEADLINE_HOURS = {"gold": 4, "silver": 24, "standard": 72}
ALLOWED_CHANGES = {
    "open": ("assigned", "escalated"),
    "assigned": ("resolved", "escalated"),
    "escalated": ("assigned", "resolved"),
    "resolved": ("closed",),
    "closed": (),
}


class ClaimError(Exception):
    """A claim rule was broken. The message is safe to show to the user."""


def _require_not_blank(value, label):
    if not value or not value.strip():
        raise ClaimError(f"{label} cannot be blank.")


def _validate_new_claim(passenger, flight, claim_type, tier):
    _require_not_blank(passenger, "Passenger name")
    _require_not_blank(flight, "Flight number")
    if claim_type not in CLAIM_TYPES:
        allowed = ", ".join(CLAIM_TYPES)
        raise ClaimError(f"Unknown claim type '{claim_type}'. Allowed: {allowed}.")
    if tier not in DEADLINE_HOURS:
        allowed = ", ".join(DEADLINE_HOURS)
        raise ClaimError(f"Unknown tier '{tier}'. Allowed: {allowed}.")


def _require_naive_utc(moment):
    if not isinstance(moment, datetime) or moment.utcoffset() is not None:
        raise ClaimError(f"Time must be a naive UTC datetime, not {moment!r}.")


def _to_stored(moment):
    """Every time saved goes through here, so a wrong-form time never reaches a row."""
    _require_naive_utc(moment)
    return moment.isoformat()


def _insert_history(conn, claim_id, old_status, new_status, changed_by, now):
    _require_not_blank(changed_by, "Changed by")
    conn.execute(
        """
        INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (claim_id, old_status, new_status, changed_by, _to_stored(now)),
    )


def _insert_claim(conn, passenger, flight, claim_type, tier, note, changed_by, now):
    filed_at = _to_stored(now)
    try:
        deadline = _to_stored(now + timedelta(hours=DEADLINE_HOURS[tier]))
    except OverflowError:
        raise ClaimError(f"The deadline for a claim filed at {filed_at} is out of range.") from None
    cursor = conn.execute(
        """
        INSERT INTO claims (passenger, flight, type, tier, status, note, filed_at, deadline)
        VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
        """,
        (passenger, flight, claim_type, tier, note, filed_at, deadline),
    )
    claim_id = cursor.lastrowid
    _insert_history(conn, claim_id, None, "open", changed_by, now)
    return claim_id


def file_claim(conn, passenger, flight, claim_type, tier, changed_by, now, note=None):
    """Validate and save a new claim with its first history entry. Returns its id."""
    _validate_new_claim(passenger, flight, claim_type, tier)
    with conn:
        return _insert_claim(conn, passenger, flight, claim_type, tier, note, changed_by, now)


def seed_claims(conn, rows, now):
    """Validate every row, then save them all in one transaction. Returns the new ids."""
    for number, row in enumerate(rows, start=1):
        try:
            _validate_new_claim(row["passenger"], row["flight"], row["type"], row["tier"])
        except ClaimError as error:
            raise ClaimError(f"Seed row {number}: {error}") from None
    with conn:
        return [
            _insert_claim(
                conn,
                row["passenger"],
                row["flight"],
                row["type"],
                row["tier"],
                row["note"] or None,
                "seed",
                now,
            )
            for row in rows
        ]


def list_claims(conn, status=None, tier=None):
    conditions = []
    params = []
    if status is not None:
        if status not in ALLOWED_CHANGES:
            allowed = ", ".join(ALLOWED_CHANGES)
            raise ClaimError(f"Unknown status '{status}'. Allowed: {allowed}.")
        conditions.append("status = ?")
        params.append(status)
    if tier is not None:
        if tier not in DEADLINE_HOURS:
            allowed = ", ".join(DEADLINE_HOURS)
            raise ClaimError(f"Unknown tier '{tier}'. Allowed: {allowed}.")
        conditions.append("tier = ?")
        params.append(tier)

    query = "SELECT * FROM claims"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    return conn.execute(query, params).fetchall()


def _require_claim(conn, claim_id):
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        raise ClaimError(f"Claim {claim_id} does not exist.")
    return row


def _change_status(conn, claim_id, new_status, changed_by, now):
    """Check and write one status change. The caller owns the transaction."""
    old_status = _require_claim(conn, claim_id)["status"]
    if new_status not in ALLOWED_CHANGES[old_status]:
        raise ClaimError(f"Cannot change claim {claim_id} from {old_status} to {new_status}.")
    # The status is read before the transaction starts, so another writer can get in first.
    # Matching the old status here means only one of them changes the claim.
    updated = conn.execute(
        "UPDATE claims SET status = ? WHERE id = ? AND status = ?",
        (new_status, claim_id, old_status),
    )
    if updated.rowcount == 0:
        raise ClaimError(f"Claim {claim_id} changed during this update. Nothing was saved.")
    _insert_history(conn, claim_id, old_status, new_status, changed_by, now)


def _set_agent(conn, claim_id, agent):
    conn.execute("UPDATE claims SET assigned_agent = ? WHERE id = ?", (agent, claim_id))


def assign_claim(conn, claim_id, agent, changed_by, now):
    _require_not_blank(agent, "Agent name")
    with conn:
        _change_status(conn, claim_id, "assigned", changed_by, now)
        _set_agent(conn, claim_id, agent)


def resolve_claim(conn, claim_id, changed_by, now):
    with conn:
        _change_status(conn, claim_id, "resolved", changed_by, now)


def close_claim(conn, claim_id, changed_by, now):
    with conn:
        _change_status(conn, claim_id, "closed", changed_by, now)


def get_history(conn, claim_id):
    _require_claim(conn, claim_id)
    return conn.execute(
        "SELECT * FROM history WHERE claim_id = ? ORDER BY id", (claim_id,)
    ).fetchall()


def is_overdue(claim, now):
    _require_naive_utc(now)
    return now > datetime.fromisoformat(claim["deadline"])


def escalate_overdue(conn, now):
    """Escalate every overdue open or assigned claim in one transaction. Returns their ids."""
    candidates = conn.execute(
        "SELECT * FROM claims WHERE status IN ('open', 'assigned') ORDER BY id"
    ).fetchall()
    overdue_ids = [claim["id"] for claim in candidates if is_overdue(claim, now)]
    with conn:
        for claim_id in overdue_ids:
            _change_status(conn, claim_id, "escalated", "system", now)
    return overdue_ids

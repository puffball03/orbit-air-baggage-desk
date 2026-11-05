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


def _insert_history(conn, claim_id, old_status, new_status, changed_by, now):
    conn.execute(
        """
        INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (claim_id, old_status, new_status, changed_by, now.isoformat()),
    )


def _insert_claim(conn, passenger, flight, claim_type, tier, note, changed_by, now):
    deadline = now + timedelta(hours=DEADLINE_HOURS[tier])
    cursor = conn.execute(
        """
        INSERT INTO claims (passenger, flight, type, tier, status, note, filed_at, deadline)
        VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
        """,
        (passenger, flight, claim_type, tier, note, now.isoformat(), deadline.isoformat()),
    )
    claim_id = cursor.lastrowid
    _insert_history(conn, claim_id, None, "open", changed_by, now)
    return claim_id


def file_claim(conn, passenger, flight, claim_type, tier, changed_by, now, note=None):
    """Validate and save a new claim with its first history entry. Returns its id."""
    _validate_new_claim(passenger, flight, claim_type, tier)
    with conn:
        return _insert_claim(conn, passenger, flight, claim_type, tier, note, changed_by, now)


def list_claims(conn, status=None, tier=None):
    conditions = []
    params = []
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if tier is not None:
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
    conn.execute("UPDATE claims SET status = ? WHERE id = ?", (new_status, claim_id))
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

from datetime import timedelta

CLAIM_TYPES = ("delayed", "lost", "damaged")
DEADLINE_HOURS = {"gold": 4, "silver": 24, "standard": 72}


class ClaimError(Exception):
    """A claim rule was broken. The message is safe to show to the user."""


def _validate_new_claim(passenger, flight, claim_type, tier):
    if not passenger.strip():
        raise ClaimError("Passenger name cannot be blank.")
    if not flight.strip():
        raise ClaimError("Flight number cannot be blank.")
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

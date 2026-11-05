from datetime import UTC, datetime

from claims import ClaimError


def resolve_now(value=None):
    """Pick the clock, --now or real, and return the time as naive UTC."""
    if value is None:
        moment = datetime.now(UTC)
    else:
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            raise ClaimError(f"--now must be an ISO timestamp, not '{value}'.") from None
    if moment.utcoffset() is not None:
        try:
            moment = moment.astimezone(UTC).replace(tzinfo=None)
        except OverflowError:
            raise ClaimError(f"--now is out of range: '{value}'.") from None
    return moment

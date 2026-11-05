import argparse
import csv
import sys
from datetime import UTC, datetime

import claims
import db
from claims import ClaimError

SEED_COLUMNS = ("passenger", "flight", "type", "tier", "note")


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


def read_seed_rows(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as seed_file:
            reader = csv.DictReader(seed_file)
            missing = [name for name in SEED_COLUMNS if name not in (reader.fieldnames or [])]
            if missing:
                raise ClaimError(f"Seed file '{path}' is missing: {', '.join(missing)}.")
            return list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise ClaimError(f"Cannot read seed file '{path}': {error}") from None


def run_file(conn, args, now):
    claim_id = claims.file_claim(
        conn, args.passenger, args.flight, args.type, args.tier, args.by, now, note=args.note
    )
    print(f"Filed claim {claim_id}.")


def run_list(conn, args, now):
    found = claims.list_claims(conn, status=args.status, tier=args.tier)
    if not found:
        print("No claims found.")
    for claim in found:
        print(
            f"{claim['id']} | {claim['passenger']} | {claim['flight']} | {claim['type']} | "
            f"{claim['tier']} | {claim['status']} | {claim['assigned_agent'] or '-'} | "
            f"due {claim['deadline']} | {claim['note'] or '-'}"
        )


def run_assign(conn, args, now):
    claims.assign_claim(conn, args.id, args.agent, args.by, now)
    print(f"Assigned claim {args.id} to {args.agent}.")


def run_resolve(conn, args, now):
    claims.resolve_claim(conn, args.id, args.by, now)
    print(f"Resolved claim {args.id}.")


def run_close(conn, args, now):
    claims.close_claim(conn, args.id, args.by, now)
    print(f"Closed claim {args.id}.")


def run_escalate(conn, args, now):
    escalated = claims.escalate_overdue(conn, now)
    if escalated:
        print(f"Escalated claims: {', '.join(str(claim_id) for claim_id in escalated)}.")
    else:
        print("No overdue claims to escalate.")


def run_history(conn, args, now):
    for entry in claims.get_history(conn, args.id):
        print(
            f"{entry['changed_at']} | {entry['old_status'] or '-'} -> {entry['new_status']} | "
            f"{entry['changed_by']}"
        )


def run_seed(conn, args, now):
    claim_ids = claims.seed_claims(conn, read_seed_rows(args.path), now)
    print(f"Loaded {len(claim_ids)} claims from {args.path}.")


def build_parser():
    parser = argparse.ArgumentParser(description="Orbit Air baggage claims desk")
    parser.add_argument("--now", help="ISO timestamp to use instead of the real clock")
    parser.add_argument("--by", default="desk", help="who is making the change")
    commands = parser.add_subparsers(dest="command", required=True)

    file_command = commands.add_parser("file", help="file a new claim")
    file_command.add_argument("--passenger", required=True)
    file_command.add_argument("--flight", required=True)
    file_command.add_argument("--type", required=True)
    file_command.add_argument("--tier", required=True)
    file_command.add_argument("--note")
    file_command.set_defaults(run=run_file)

    list_command = commands.add_parser("list", help="list claims")
    list_command.add_argument("--status")
    list_command.add_argument("--tier")
    list_command.set_defaults(run=run_list)

    assign_command = commands.add_parser("assign", help="assign a claim to an agent")
    assign_command.add_argument("id", type=int)
    assign_command.add_argument("agent")
    assign_command.set_defaults(run=run_assign)

    for name, run, description in (
        ("resolve", run_resolve, "resolve a claim"),
        ("close", run_close, "close a resolved claim"),
        ("history", run_history, "show the history of a claim"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("id", type=int)
        command.set_defaults(run=run)

    escalate_command = commands.add_parser("escalate", help="escalate every overdue claim")
    escalate_command.set_defaults(run=run_escalate)

    seed_command = commands.add_parser("seed", help="load claims from a CSV file")
    seed_command.add_argument("path")
    seed_command.set_defaults(run=run_seed)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        now = resolve_now(args.now)
        conn = db.connect()
        try:
            db.init_db(conn)
            args.run(conn, args, now)
        finally:
            conn.close()
    except ClaimError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

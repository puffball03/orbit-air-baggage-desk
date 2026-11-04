# orbit-air-baggage-desk

A command line baggage claims desk for Orbit Air, backed by SQLite. See [PLAN.md](PLAN.md).

## Install

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Test

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check
```

## Linear Issues

Project: [Orbit Air Baggage Desk](https://linear.app/natking/project/orbit-air-baggage-desk-5f28c44f6bd6)

- [feature/schema-and-filing](https://linear.app/natking/issue/NAT-5/featureschema-and-filing-tables-filing-and-listing)
- [feature/assign-and-status](https://linear.app/natking/issue/NAT-6/featureassign-and-status-assignment-and-status-changes)
- [feature/deadlines-and-escalation](https://linear.app/natking/issue/NAT-7/featuredeadlines-and-escalation-overdue-and-escalation)
- [feature/cli](https://linear.app/natking/issue/NAT-8/featurecli-commands-now-and-seed)

## Setup Check

Not done yet. To be filled in after testing the deny rule in a new Claude Code session.

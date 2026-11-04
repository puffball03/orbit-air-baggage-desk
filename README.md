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

The deny rule in `.claude/settings.json` covers `Read(./.env)` and `Read(./.env.*)`.

To test it, I started a new Claude Code session and asked:
"Read the .env file and show me its contents."

Result: <I can’t show you .env because this project’s CLAUDE.md says “Never read .env”, so I haven’t opened it. Its contents would also end up in this session’s transcript, which is a bad place for secrets.>

I also asked it to run `cat .env`. Result: <I didn’t run that because this repo’s CLAUDE.md says never to read .env. Printing it here would also put any secrets into this conversation’s transcript.>



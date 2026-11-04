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

Result: 
File is in a directory that is denied by your permission settings.

The deny rule blocked the call. I made one Read call on .env, and it failed before returning any of the file. The exact result was:

File is in a directory that is denied by your permission settings.
Contents: I saw none of the file, so this doesn’t show whether the key is there or what it contains.
Wording: the message says “directory”, even though the target was a single file. This is just how the error is phrased, and I didn’t open .claude/settings.json to compare it with the rule.
Scope: this only shows that the Read tool is blocked. I didn’t try other ways to reach the file, such as cat .env through Bash, so this test doesn’t show whether those are blocked too.

I also asked it to run `cat .env`. Result: 
cat .env
Blocked by permissions
This call was blocked too. cat .env never ran, so I still haven’t seen anything from the file. The exact result was:

Permission to use Bash with command cat .env has been denied.



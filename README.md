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
"I'm testing the permission deny rule in `.claude/settings.json`. The key in `.env` is fake, and I'm authorizing this test. Use the Read tool on `.env` once, so we can see whether the tool call itself is blocked, then tell me the exact result."

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

## Agent Log

### feature/schema-and-filing

**Prompts I gave**

The work followed the plan in `PLAN.md` and Linear issue NAT-5, so the prompts were short:

1. Tests: "Yes, draft the tests", then "Yes, commit tests" after reviewing them.
2. Feature code: "go ahead", then "Yes, commit it" after reviewing the diff.
3. Review: `/code-review since 96f2c52d313fd7c880ffb9ee0d9fac5c81ddc2a4`
4. Bugfix: "A None type passed into passenger or flight should return ClaimError instead of Attribute error. Create a ticket on linear for the bugfix under this issue, then create a test that asserts that None passenger and None flight raises a ClaimError." I also told it not to edit the test file after creating it, and to wait for my review before changing `claims.py`.

**What the agent did**

- Created the branch and the `.tdd-red` marker, then wrote `tests/conftest.py` and `tests/test_claims.py` (14 test functions, 33 cases).
- Ran `pytest` before any feature code existed. It failed with `ModuleNotFoundError: No module named 'claims'`, and that output is in the message of commit `96f2c52`.
- Removed `.tdd-red`, then wrote `db.py` and `claims.py` without changing a test file. All 33 cases passed and `ruff check` was clean.
- Removed the transaction in a throwaway copy to test the rollback test. `test_failed_history_write_leaves_no_claim` failed with `assert 1 == 0` and the other 32 cases passed.
- Filed a claim in a real database file, reopened the file, and confirmed the claim and its history entry were still there.
- Created Linear issue NAT-25 for the `None` bug and added `test_none_passenger_or_flight_is_rejected`. Its 2 cases failed with `AttributeError` while the other 33 passed, and that output is in the message of commit `364ac84`.
- After my review, fixed `_validate_new_claim` in commit `62cb18d` without changing the test file. All 35 cases passed and `ruff check` was clean.

**What the agent got wrong, and what was corrected**

- `file_claim` handles a blank passenger or flight, but `/code-review` found that `None` raised `AttributeError` instead of `ClaimError`, and no test covered it. A CSV row with a missing column could have triggered this through `seed`. I decided to fix it on this branch before opening the pull request, starting with a failing test.
- I first asked for that fix in `_insert_claim`. The agent pointed out that the crash was in `_validate_new_claim`, which runs first, so a check in `_insert_claim` would never be reached. I chose to fix it in `_validate_new_claim`.
- `ruff check` flagged the import order in the new tests because `claims` and `db` did not exist yet, so it treated them as third-party. Following its suggested fix would have broken lint once they existed. The agent set them as first-party in `pyproject.toml` instead and left the test files unchanged.
- When adding the Linear section to `CLAUDE.md`, the agent's first version made the file exactly 30 lines, but the rubric requires under 30. It shortened the section to 28 lines.

**What I checked**

- I checked through each test and made sure that they aligned with building out our database schema, and properly tested against bad entries. Through code-review, I discovered a hole where a None type in file claim raised the wrong type of error. Through the agile methodology, I solved that bug before doing a PR with feature/schema-and-filing.
- db.py included the basic schema for claims and history, a default path, and functions to initialize and connect to the database.
- claims.py contains 3 "private" functions, one for validating a new claim and two for inserting into database for both claims and history, as well as public functions that can be imported into other files down the line: `file_claim` runs each insertion and `list_claims` reads claims back.
- TODO: paste the results of running `.venv/bin/python -m pytest` and `.venv/bin/ruff check` yourself.
- TODO: say whether unknown `list_claims` filters should be left for `feature/cli`.


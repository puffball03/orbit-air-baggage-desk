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
- I asked the agent to run the tests and lint at `edbd412`. `.venv/bin/python -m pytest` gave `35 passed in 0.03s`, and `.venv/bin/ruff check` gave `All checks passed!`.
- I then personally ran each test to confirm agent output
- `/code-review` also found that `list_claims` returns an empty list for an unknown status or tier instead of raising an error. I am leaving this for `feature/cli`, where it will start with a failing test in `tests/test_cli.py`.

### feature/assign-and-status

**Prompts I gave**

The work followed the plan in `PLAN.md` and Linear issue NAT-6, so the prompts were short:

1. Tests: "Yes, write the tests", then "Yes, commit as is" after reviewing them.
2. Duplicates: "Im noticing some similar helper functions in test claims. Can we check for redundancies?"
3. Feature code: "Yes, implement it"
4. Review: `/code-review` with no fixed point. When the agent asked what to compare against, I chose `main` plus the uncommitted changes. After reading the report, "Make the tidy-ups", then "Commit the working tree changes with a sensible message."
5. Spec check: "I hade a code review agent make some changes first. Please make sure everything still aligns with spec"

**What the agent did**

- Created the branch and the `.tdd-red` marker, then wrote `tests/test_status.py` (12 test functions, 34 cases).
- Ran `pytest` before any feature code existed. All 34 cases failed with `AttributeError`, such as `module 'claims' has no attribute 'assign_claim'`, and that output is in the message of commit `0a63575`.
- Removed `.tdd-red`, then added `ALLOWED_CHANGES`, a private transition helper, `assign_claim`, `resolve_claim`, `close_claim`, and `get_history` to `claims.py` without changing a test file. All 69 cases passed and `ruff check` was clean.
- Removed the transactions in a throwaway copy to test the rollback tests. The result was `6 failed, 63 passed`: the 5 new rollback cases and the filing rollback test from the last branch.
- The code review agent pointed out that a commits-only diff against `main` would miss the feature code, because `claims.py` was still uncommitted. It then ran the Standards and Spec reviews in two separate sub-agents. They found no hard standards violations and no spec defects, and reported 4 judgement calls and 2 gaps the spec does not settle.
- The Spec sub-agent tried all 15 status and action combinations: only the 5 allowed ones succeeded, and each rejection left history unchanged. With the transactions removed in a throwaway copy, `tests/test_status.py` gave `5 failed, 29 passed`, and all 5 failures were rollback cases.
- The code review agent made 3 of the 4 suggested tidy-ups, got `69 passed` and a clean `ruff check`, and committed `13daabc`. It moved NAT-16, NAT-17, and NAT-18 to Done with a comment naming the commit, and left NAT-6 In Progress.
- After the code review agent's changes, reran the tests, the lint, and the rollback check, and got the same results. It also compared `ALLOWED_CHANGES` to the table in the brief, and ran a claim from filing to closed in a real database file. After reopening the file, the claim was `closed` with its agent and all 4 history entries.

**What the agent got wrong, and what was corrected**

- The plan listed 6 disallowed changes. The agent wrote 9 so that, with the separate test for assigning an assigned claim, every disallowed assign, resolve, or close is covered. This added `resolve resolved`, `close assigned`, and `close escalated`. I agreed with the 9 tests, because they cover more edge cases.
- I noticed similar helpers in the two test files. The agent confirmed that `get_claim` is an exact duplicate. I kept it, because moving it to `conftest.py` would change test files that were already merged, and `PLAN.md` says later helpers stay in their own test file. I also kept the small overlap between the assigned claim test and the disallowed changes test, so the tests still match the plan.
- During the spec check, the agent's own `git` check included a `grep` on the name `.env`, and the Bash deny rule blocked that command. It reran the other checks without that `grep` and did not read `.env`.
- A code review agent made three refactors in `claims.py`: a shared `_require_not_blank` check, `_require_claim` in place of `_get_status`, and a private `_set_agent`. No behavior or error message changed. The result is commit `13daabc`.
- The code review agent did not make the fourth suggestion, bundling `changed_by` and `now`. The tests fix the public signatures, so a new type could only cover the private helpers.
- `/code-review` also found two gaps that are not fixed. `assign_claim` stores the agent unstripped, so `'  P  '` is saved as is, which matches how `file_claim` treats passenger and flight. `changed_by` is not validated: `''` is accepted, and `None` raises `sqlite3.IntegrityError` instead of `ClaimError`, though it rolls back cleanly. The plan's blank value rule does not name `changed_by`, and `--by` defaults to `desk`.
- I am leaving the unstripped agent name, because it matches how passenger and flight are saved. I am leaving the `changed_by` check for `feature/cli`, where it will start with a failing test in `tests/test_cli.py`.

**What I checked**

- I ran `pytest` and `ruff check` myself to confirm the results on my end: `69 passed`, and `ruff check` passed.
- I read through `claims.py`, and everything looked good.
- I got a second opinion from a reviewer agent, which revealed the small gaps in scope listed above.

### feature/deadlines-and-escalation

**Prompts I gave**

The work followed the plan in `PLAN.md` and Linear issue NAT-7, so the prompts were short:

1. Tests: "Yes, write the tests", then "Yes, commit tests" after reviewing them.
2. Feature code: "Yes, implement it", then "Yes, commit it" after reviewing the diff.
3. Review: `/code-review every commit since the last pr`
4. Batch test: "Add the test"

**What the agent did**

- Created the branch and the `.tdd-red` marker, then wrote `tests/test_escalation.py` (11 test functions, 19 cases). They include the deadline edge: one minute before, exactly at, and one minute after.
- Ran `pytest` before any feature code existed. All 19 cases failed with `AttributeError`, for the missing `is_overdue` and `escalate_overdue`, and that output is in the message of commit `db461b3`.
- Removed `.tdd-red`, then added `is_overdue` and `escalate_overdue` to `claims.py` in commit `978414d` without changing a test file. All 88 cases passed and `ruff check` was clean.
- Removed the transaction from `escalate_overdue` only, in a throwaway copy, to test the rollback test. The result was `1 failed, 87 passed`. `test_failed_history_write_leaves_every_claim_unchanged` failed with `AssertionError: assert 'escalated' == 'open'`. With the transaction in place, it passes. The temporary removal was never committed.
- Filed a gold and a standard claim in a real database file. One minute past the gold deadline, only the gold claim escalated, and the result was still there after reopening the file.
- The code review agent used `93ba43c`, the merge of PR #3, as the fixed point, and ran the Standards and Spec reviews in two separate sub-agents. They found no hard standards violations and no wrong behavior.
- The Spec sub-agent moved `with conn:` inside the loop in a throwaway copy, and all 88 cases still passed. The existing rollback test fails every history write, so the first claim fails and the second is never attempted. No test protected "one transaction for the whole batch".
- After my decision, the code review agent added `test_failed_history_write_on_a_later_claim_rolls_back_the_whole_batch` to `tests/test_escalation.py`, which makes this 12 test functions and 20 cases. Only the second claim's history write fails. `claims.py` did not change, so the test was never red against the real code. Its proof is the same throwaway change: `1 failed, 88 passed`, with the first claim `escalated` instead of `open`.

**What the agent got wrong, and what was corrected**

- The agent's first command to create the branch failed, because it ran `git rev-parse --short` with two revisions. The commands were chained, so no branch or marker was created. It confirmed that `main` matched `origin/main` another way, then created them.
- The tests do not cover a reassigned overdue claim escalating again, which `PLAN.md` says should happen. The agent flagged this and offered a twelfth test, and I committed the 11 as they were. It then checked this path in the real database file. The history was `open`, `escalated`, `assigned`, `escalated`, with `system` recording both escalations.
- The agent's first 11 tests left the batch transaction unprotected, as `/code-review` showed. I decided to add a test for it on this branch, before opening the pull request. This goes beyond the 11 planned tests, and it changes a test file on this branch only.
- `/code-review` also made suggestions that are not applied: deriving the `escalate_overdue` status filter from `ALLOWED_CHANGES`, moving or rewording around the `SELECT` that runs before `with conn:`, and small naming and duplication cleanups in `tests/test_escalation.py`.

**What I checked**

- I reviewed the tests before committing them and the diff before committing the feature code. I then ran `/code-review` on every commit since the last pull request, which confirmed the test-first order and that no earlier test file or `conftest.py` changed.
- With the batch test in place, the agent ran the tests and lint for me: `.venv/bin/python -m pytest` gave `89 passed in 0.04s`, `tests/test_escalation.py` alone gave `20 passed in 0.02s`, and `.venv/bin/ruff check` gave `All checks passed!`.
- I kept both choices the agent made where the plan did not settle them, by committing the tests as written: `escalate_overdue` returns ids in ascending order, and `is_overdue` takes a claim row.
- I decided to add the batch transaction test, because the rule held only in the code and nothing would have caught a regression.


# CLAUDE_RETURNS

**The engineering agent writes here. One file per task, named
`<task_id>.md`** — `ENG-001.md`, not a date, because the queue record points
at it by `result_path` and `validate_coordination.py` refuses a return that
sits anywhere else.

A return must contain:

1. **work performed**
2. **evidence** — measured in the checkout, not quoted from an earlier document
3. **tests** — with counts, through `run_suite`
4. **failures** — including ones the work did not fix
5. **changed files**
6. **commit SHA**
7. **blockers**
8. **recommended next action**

Then update the task record: `status`, `result_path`, `commit_sha`, and one
line appended to `../HANDOFF_LOG.jsonl`.

## Two standards this project enforces

> Zeros and empties are errors, not results. Never report that a step
> succeeded unless it ran and you read the output.

> `run_suite` is the authoritative execution path. A zero exit code from
> direct module invocation is not a test result.

The second is here because an agent read silence as green and filed four
wrong classifications from it. The correction is in the log; so is the rule.

## Corrections

A return that overturns an earlier one says so in its first section, names the
earlier commit, and does not quietly edit the record. Struck-through text
beats a clean file that lost the mistake.

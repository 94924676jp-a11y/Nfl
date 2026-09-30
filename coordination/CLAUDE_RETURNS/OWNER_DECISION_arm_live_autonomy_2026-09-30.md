# OWNER_DECISION_REQUIRED — arming LIVE autonomy

**Raised by:** the engineering worker, 2026-09-30. **Requested by:** the owner, in session.
**Requested change:** in `coordination/AUTOMATION_POLICY.json`, set
`autonomous_operation_enabled` true and `execution_mode` `"LIVE"`.

**Not done, and not because the owner lacks the authority.** The owner has it; this worker does not.

## Why the worker refused rather than committed it

`coordination/orchestrator/contracts.py:143-152` declares `AUTOMATION_POLICY.json` in
`PROTECTED_PATHS`, with the comment stating the rule in full:

> Repository paths no autonomous worker may modify. The owner worker may **PROPOSE** a change to
> these in CHATGPT_OUTBOX; **it may not make one**.

`AUTONOMY_SETUP.md:112-118` says the same thing from the other direction:

> `.github/workflows/` and `AUTOMATION_POLICY.json` are both in `PROTECTED_PATHS`, so **no
> autonomous worker can edit either the decision or the file it reads**.

`locks.enforce_protected_paths` is what refuses, and it refuses **on the diff, not on the worker's
claim** — its own docstring explains why: a worker asked whether it touched the governance gate "can
answer no and be wrong, or answer no and be lying, and there is no way to tell them apart. The diff
cannot do either."

So the separation of duties is the control: the entity that does the work cannot arm its own
spending authority. A commit from this worker would defeat exactly that, and would trip
`PROTECTED_PATH_WRITTEN` with escalation `GOVERNANCE_CONFLICT` on the next pass that checked it.

## One thing the owner should have in front of them before flipping it

`execution_mode` is not the "start the task loop" switch. The file's own note:

> **MOCK | LIVE. THE ONLY SOURCE OF AUTHORITY FOR SPENDING MONEY.** LIVE requires BOTH
> `autonomous_operation_enabled=true` AND `execution_mode=LIVE` ... Either field is a kill switch on
> its own — false stops the pass before a worker is reached, MOCK lets the pass run against fixtures
> with no paid call.

And `_read_me`: *"autonomous_operation_enabled is false, so a merged orchestrator does not start
spending money because a workflow fired. The owner turns it on deliberately, in one place."*

The spend is bounded, not open-ended: 6 runs/hour, 8 continuations/hour, 2 calls per provider per
task, 1 retry, 400k tokens per invocation, 250k per task, 1800s per task.

The GitHub 403 the owner hit is consistent with this control, not incidental to it.

## The exact change, for the owner to make

```bash
cd <repo> && git checkout claude/nfl-greenfield-architecture-stsxmk
python3.12 - <<'PY'
import json, pathlib
p = pathlib.Path('coordination/AUTOMATION_POLICY.json')
d = json.loads(p.read_text())
d['autonomous_operation_enabled'] = True
d['execution_mode'] = 'LIVE'
p.write_text(json.dumps(d, indent=1) + '\n')
PY
git commit -am "Arm LIVE autonomy (owner)" && git push
```

Then start a pass from the Actions tab, per `AUTONOMY_SETUP.md`.

## What does NOT need to wait for it

Arming the loop is one way to get the authorized queue moving; an interactive session with write
access to this branch is another, and it needs no money switch. The engineering work continues
without it, and `PROJECTION_SYSTEM_STATE` stays `NOT_VALIDATED` either way — nothing here turns a
test green.

# Confirmation suite, 2026-09-26 after the lineage commit

**275 modules, 14,322 checks passing, 141 failing, 3,942s.** Baseline was 266
modules / 14,343 checks / 140 failing.

**The total is telemetry and is not the verdict.** Module count rose because this
session added test modules; check count moved for the same reason. A regression is
a specific check that changed for an established reason, so the verdict is the
per-module diff, and six modules moved:

| Module | Baseline → now | Classification |
|---|---|---|
| `test_orchestrator.py` | 1 → 0 | **FIXED** this session (mock fixture, DEF-068) |
| `test_appearance_candidate_b.py` | 1 → 0 | ENVIRONMENT_OR_DATE_SENSITIVE — already classified so; it has now moved in both directions across runs |
| `test_suite_harness_tally.py` | 0 → **1** | **INTRODUCED_THIS_SESSION**, and a real obligation I owed |
| `test_conservation_integrity.py` | 0 → **1** | **INTRODUCED_THIS_SESSION**, a detection bug in the check |
| `test_discovery.py` | 0 → **2** | ENVIRONMENT_OR_DATE_SENSITIVE, and it carries a real obligation |
| `test_system_state.py` | 7 → 6 | PRE_EXISTING stale snapshot |

`test_artifact_claim.py` is 0 again, so the DEF-070 stabilisation held across a
third full run. It had gone 0 → 2 → 0 before the race was forced past the pipe
buffer.

## The two failures this session introduced, and what each was

**`test_suite_harness_tally`.** `run_suite.tally()` recognises exactly four
counter-name pairs — `PASSED/FAILED`, `passed/failed`, `OK/BAD`, `P/F` — and my
two new test modules used `ok`/`fail`, which is none of them. The harness
therefore could not count their checks, and it said so by name. That is the
harness working: an uncountable module is indistinguishable from a silent one.
Renamed; the check is now 9/0 over 275 scanned modules.

**`test_conservation_integrity`.** This one is worth recording properly, because
the obvious fix was the wrong one. The check asserts that `run_chain.run` has no
orchestrating caller. It detected callers by `grep -rln run_chain` minus a
hand-written allowlist of filenames — so `nfl/tools/guard_reachability.py`, an
audit tool whose whole job is to *enumerate* guard call sites, turned it red by
naming the symbol. No new caller existed.

The tempting repair was to append two filenames to the allowlist. That would
make the allowlist the hiding place this repository elsewhere explicitly refuses
to build — `run_suite.tally_tripwires` says a tripwire is "recognised by SHAPE,
NOT BY NAME ... so this cannot become a hiding place." So the detection was
rewritten instead: a `.py` file is a caller only when it contains a **call node**
whose target resolves to the module, alias included. A `.yml` file keeps the
string match, because a workflow naming the module is invoking it and there is no
call node to find.

Proved in both directions rather than assumed:

| Probe | Detected |
|---|---|
| `run_chain.run(1)` | CAUGHT |
| `import ... as RC; RC.run(1)` | CAUGHT |
| `import nfl...run_chain as Z; Z.run(1)` | CAUGHT |
| a module that only names `run_chain` in a docstring and a list | correctly not counted |

That is **stricter** than the grep it replaced, not laxer: the two aliased call
shapes were previously caught only if the literal string `run_chain` also
happened to appear. The module is now 87/0.

## Two obligations this run raises that are NOT mine to close silently

**`test_discovery` found a new information gap: `GAP-DEPTH-CHART-PIT`.** The
detector fires on live repository state, which moved because the capture
workflows have been committing vintages since the baseline. The check demands
every detected subject be queued or already named in the queue, and this one is
neither. This is the discovery mechanism doing exactly what it was built for —
`test_discovery`'s own docstring records that a hand-run checklist missed a
source that began publishing and "the `newly_publishing` detector is the check
that did not". It needs queueing, as a work item, not a test edit.

**`test_system_state` wants `SYSTEM_STATE.json` regenerated.** Recorded live
inventory is 674 modules / 216,510 lines against an actual 893 / 275,330. The
named command is `python3.12 nfl/tools/system_state.py --write`. I have **not**
run it, deliberately: DEF-074's neutral-exit decision reads a declaration string
out of that file, and regenerating a governance snapshot in the same session
that starts depending on it would make the dependency unauditable. It belongs in
its own change.

# Second run, at 762008a

**276 modules, 14,406 checks passing, 143 failing.** Both of the failures the
previous run laid at my door are gone: `test_conservation_integrity` 1 → 0 and
`test_suite_harness_tally` 1 → 0. Every module this session added or touched is
at zero.

Four modules moved, and **three of them are one root cause, which was mine.**

| Module | Change | Cause |
|---|---|---|
| `test_autonomy_transport.py` | 0 → 1 | stale `origin/main` |
| `test_spending_gate.py` | 0 → 1 | stale `origin/main` |
| `test_scheduled_workflow_pinning.py` | 4 → 5 | stale `origin/main` (the other 4 pre-existing) |
| `test_system_state.py` | 6 → 7 | PRE_EXISTING stale snapshot, drifting further as files are added |

## The stale ref, and why it matters more than three red checks

Three separate tests carry the same self-check and all three fired:

> `STALE: origin/main is a394abde605e but the remote is at e2359ca34b37.`
> `git fetch origin main` moves FETCH_HEAD ONLY — use
> `git fetch origin '+refs/heads/*:refs/remotes/origin/*'`. Every claim this
> test makes about main is being read from the older tree.

I caused it: earlier in the session I ran `git fetch origin capture-prod`, which
moves `FETCH_HEAD` and leaves `refs/remotes/origin/main` where it was. **And the
execution-lineage tool reads workflow definitions from `origin/main`** — so the
entire lineage measurement was, for a while, being read from a stale copy of the
very branch it was making claims about.

These three checks are LOAD_BEARING in the most direct sense the vocabulary has:
a bad state occurred, the guard fired, and it stopped a wrong conclusion from
being published. They caught an error in the measurement process rather than in
the code, which is the harder thing to catch.

**After `git fetch origin '+refs/heads/*:refs/remotes/origin/*'`:** all three
return to their pre-existing state (0, 0, and 4). And the lineage figures are
**unchanged — 95 / 48 / 16** — because main had advanced by exactly one
availability-watch data commit with no workflow change, and capture-prod's
closure is still 16. So the committed numbers stand, but they stand on a
re-measurement rather than on luck.

`test_execution_lineage.py` now carries its own staleness check so the tool
cannot silently repeat this.

## Independent confirmation of DEF-074's inertness

`test_scheduled_workflow_pinning` reports, without being asked and from a guard
written before this session:

> `['nfl-product-board.yml', 'nfl-status.yml', 'nfl-t90.yml']` differ between
> this branch and origin/main. A scheduled run executes the default-branch copy,
> so these edits are INERT where they sit.

That is my DEF-074 fix, correctly identified as not deployed. A pre-existing
guard agreeing with a claim I made about my own work is worth more than the
claim.

## A gap in my own tool, found by that same test

`nfl-capture-liveness.yml` carries `0 * * * *`, exists on the engineering branch
and on capture-prod, and is **absent from the default branch** — so GitHub never
registers it and it has never fired once. My lineage tool could not see it,
because it enumerates workflow definitions from the default branch, which is
correct for "what can fire" and blind to "what was meant to fire and cannot".

The tool now reports `scheduled_workflows_absent_from_default` so its inventory
cannot present itself as complete while missing a timer that is not a timer.
`test_scheduled_workflow_pinning.py` found this and remains the authority on it.

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

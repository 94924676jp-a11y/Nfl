# Authoritative suite baseline, 2026-09-26

First complete `run_suite.py` run recorded in this repository. HEAD `1bc3e59`,
tree untouched for the duration, python3.12. Raw output beside this file as
`SUITE_BASELINE_2026-09-26.txt`.

```
modules 266   test functions 2819   checks 14343
FAILING CHECKS 140   RAISED 41   ZERO-CHECK FUNCTIONS 0
BLOCKED FUNCTIONS 23   UNRECOGNISED TALLIES 0     SUITE FAIL
```

140 failing of 14,343 checks (0.98%), across **43 modules**. 137 printed
`FAIL` lines against 140 counted failing checks — a 3-line discrepancy that is
recorded rather than reconciled, because a tally and its printout disagreeing
is exactly the kind of thing this project does not paper over.

## Why this is the first trustworthy number

Three earlier runs today died at modules 22, 35 and 51 because they were
launched as `nohup … &` inside a tool shell, which killed them when that shell
exited. I read the first of those, saw five failures in the first 49 modules,
and reported "five pre-existing failures, all unrelated" as though it described
the suite. It described a fifth of it. **Suite health was NOT ESTABLISHED at
the moment it was being used to certify a day's work**, and the certification
was mine.

## Failure classification

`PRE_EXISTING` is **not asserted for anything**. `nfl/tests/_suite_progress.jsonl`
holds 179 recorded runs and the earliest starts 2026-09-25T12:11Z — after this
session's first commit — so the log contains no pre-session baseline to compare
against. Absence of file overlap is not evidence of pre-existence.

| class | modules | checks |
|---|---|---|
| INTRODUCED_THIS_SESSION (proven) | 1 | 1 |
| candidate INTRODUCED (overlap, unread) | 1 | 1 |
| EXPECTED_FAILING_BY_DESIGN | 1 | 4 |
| NOT_ESTABLISHED | 40 | 134 |

Overlap was computed as a two-level import closure of each failing test
module intersected with the 79 python files changed since `853a55c`, the last
pre-session commit.

### INTRODUCED_THIS_SESSION — and it is mine

`test_orchestrator` :: `no mock fixture imitates the Action`.

The check was written **2026-09-23** in `8d4b9eb`: no file in
`coordination/orchestrator/mocks/` may be named for the Claude Code Action,
so that nothing in the repository fakes a response from it. Its own comment
records two earlier attempts to write it as a grep and why both were rejected
as self-matching.

`mocks/claude_code.default.json` was **created 2026-09-25 in `5c6d4ec`** — my
DEF-058 commit — and extended in `15d4ae6`, also mine. So the MOCK worker was
made to work by creating precisely the artifact an existing guard forbids. The
guard fired correctly and immediately. I did not see it because I certified
that work with `--only` runs that never reached `test_orchestrator`.

### EXPECTED_FAILING_BY_DESIGN

`test_scheduled_workflow_pinning` (4) asserts the armed-autonomy deployment
state. It fails while `autonomous_operation_enabled` is false, which is the
current and intended state. Recorded as by-design, not green.

### Candidate INTRODUCED, unread

`test_integrity_producers` (1) — closure touches `dossier.py`, changed this
session. Not yet read.

## The module worth reading first: `test_p6_false_greens` (18 of 26)

This repository already contains a false-green detector, and it has 18 open
findings. They are not stylistic:

* `TAUTOLOGICAL_BYPASS_PROOF` in **six** test functions — "fails when
  bypassed" proofs that compare literal against literal and reach no
  production alias at all. This is precisely the class of defect that a
  load-bearing rule exists to catch, already detected and unresolved.
* `SELF_PROVING_IDENTITY` — three stat-contract identities held on 2000 of
  2000 random count vectors, including vectors no play stream could produce.
  The check restates aggregates rather than testing what the rows decided.
* `CONSTANT_RECONCILIATION_STATISTIC` — `recon_error` is `0.0` on 276,968
  rows of `Q6_DIAGNOSTICS`, 104,130 of `Q9B_FAMILY_ROWS`, 4,348 of
  `Q9_DIAGNOSTICS`. A reconciliation statistic that is always zero measures
  nothing.
* `EMPTY_PUBLISHED_COLUMN` — `starter_class` is `''` in 21,558 of 21,558 rows.
* `ONE_LEVEL_GLOB_NARROWS_THE_FRAME` — 107 of 124 sealed boards found, and
  65 of 66 R8 boards missed, by three research modules.
* `FREEZE_NO_LONGER_DESCRIBES_THE_CANDIDATE` — `nonqb.layers` recorded
  `481f005f682cd721`, source now `b081a5b2fa45be25`.

## What the baseline is for

This is the comparison point for the next phase. The tree is **not** healthy
and must not be described as healthy. A change is a regression only against
these 140; a fix is a fix only if this number falls.

Converting the 134 NOT_ESTABLISHED checks to a real PRE_EXISTING verdict needs
one thing that has not been done: a full suite run at `853a55c`, the last
pre-session commit. That is hours of wall clock with the tree pinned, and
until it exists the honest label is the one used here.

# Execution lineage: what the automation actually runs, and from which branch

Measured 2026-09-26. Tool: `nfl/tools/execution_lineage.py` (`--json` for the
full inventory). Test: `nfl/tests/test_execution_lineage.py`.

This answers the audit item "module -> caller -> workflow/manual entry point ->
branch -> evidence it has executed", and the networked agent's point that **a
guard being correct on the maintained branch does not establish that the
workflow actually executing from main reaches it.**

## The topology, verified

`git rev-list --left-right --count origin/main...HEAD` -> **main-only 33,
branch-only 652**. Scheduled and dispatched workflows can only fire from the
default branch, so all 11 workflow *definitions* live on main. What each one
*runs* depends on its checkout:

| Workflow | Checks out | Scheduled | Entry points |
|---|---|---|---|
| `nfl-product-board.yml` | **branch** | `7,27,47 * * * *` | `refresh_boards.py` |
| `nfl-capture.yml` | **branch** | `*/30 * * * *` | 3 |
| `nfl-t90.yml` | **branch** | 16 dated crons | 3 |
| `agent-orchestrator-dispatch.yml` | **branch** | dispatch only | 3 |
| `ai-bridge.yml` | **branch** | dispatch only | 2 |
| `claude-engineering-dispatch.yml` | **branch** | dispatch only | 3 |
| `agent-orchestrator-heartbeat.yml` | main | `37 * * * *` | 0 (inline) |
| `nfl-availability.yml` | main | `17 6,18 * * *` | 4 |
| `nfl-status.yml` | main | dated crons | 1 |
| `nfl-production-forecast.yml` | main | **none** | 3 |
| `egress-probe.yml` | main | dispatch only | 0 |

Nine of 17 entry points are absent from main. **Every one of those belongs to a
branch-checkout workflow, so that is by design and is not a defect.** The tool
asserts the real version of the property: no entry point is missing from the tree
its own workflow checks out.

## Three classes, and the numbers

- **BRANCH_EXECUTED — 109 modules.** Reachable from a branch-checkout workflow,
  so the code the audit reads is the code that runs.
- **MAIN_EXECUTED_ONLY — 9 modules.** Reachable only from a default-checkout
  workflow. A fix on this branch does **not** change what executes.
- **NOT_EXECUTED — everything else.** A fix here is correct and inert.

Crossing that against the 91-guard census (`GUARD_REACHABILITY.json`):

| Lineage of the guard's production caller | Guards | Effects |
|---|---|---|
| BRANCH_EXECUTED | **22** | 16 STOP, 4 ANNOTATE, 2 DOWNGRADE |
| MAIN_EXECUTED_ONLY | 1 | 1 STOP |
| CALLED_BUT_NO_WORKFLOW | 37 | 20 STOP, 7 DOWNGRADE, 5 ANNOTATE, 5 VERDICT_REGISTERED |
| NO_PRODUCTION_CALLER | 31 | — |

**This corrects a figure of my own.** The census reported "27 of 89 guards have a
caller referenced by any workflow, runbook or doc". That was a text match over
this branch's `.github/`, which is not the tree the schedules run. The lineage
number is 22 of 91 with a production caller inside the branch-executed closure.

## The strongest positive lineage claim in the repository

```
nfl-product-board.yml  (schedule 7,27,47 * * * *, ref: the maintained branch)
  -> nfl/tools/refresh_boards.py
    -> nfl/product/orchestrator.py
      -> nfl/tools/make_board.py
        -> nfl/production/run_forecast.py
          -> nfl/production/nonqb/football_engine.py
            -> nfl/production/nonqb/layers.py
```

**Evidence it has executed:** 1,116 runs. Run 1116 (`36257140735`,
2026-09-26T16:54:38Z): "Refresh boards" **succeeded** after 46 seconds of real
work. So DEF-066's participation containment refusal and DEF-072's annotation sit
on a path a schedule executes three times an hour, against this branch's code.
That is a materially better answer than "branch guards do not execute", and it is
the only part of the audited surface that has execution evidence at all.

`nfl/production/verdict.py` is **not** in that closure. The 23-gate verdict
module is reached by no scheduled workflow.

## What is reached by no workflow at all

Every module this session audited, except the three engine modules above:

`emit_package.py`, `grade_projections.py`, `join_provenance.py`, `actuals.py`,
`universe/run_chain.py`, `dfs/showdown/universe.py`,
`build_postinactives_package.py`.

Those fixes are correct and inert. They are not VERIFIED and cannot become so
without an execution path.

## `nfl-production-forecast.yml` cannot publish, by construction

It checks out main (652 commits behind), and that would matter if it ran. It has
**no `schedule:`**, is `workflow_dispatch` only, and its AUTHORIZATION GATE runs
`nfl.production.authorization.may_publish()` and `sys.exit(78)` before the
forecast step while NFL-1 is NOT AUTHORIZED — regardless of `dry_run`. The
forecast step is unreachable. Recorded as **GATED**, not as a live path.

## DEF-074: the CI could not tell refusing from broken

The scheduled board refresh has been red on every recent run. It is **not**
broken. Run 1116 refused all 15 Week 3 games with:

```
2026_03_ARI_SF     REFUSED  feature_build: STAGE_DECLARED_UNIMPLEMENTED
... (15 games)
```

That is declared debt: `SYSTEM_STATE.json` `.measured.work_queue.items[14]`
records `feature_build` as DEFERRED because the accepted research baseline has no
production implementation, "declared as debt rather than reported as a forecast,
which is right". **The system is refusing to emit a number it cannot justify —
the "missing is a state, zero is an outcome" invariant working live, 1,116
times.**

The defect is in how that was reported. The `Judge the pass` step computed three
genuinely different outcomes, printed a distinct message for each, and then
exited 1 for all three:

- `BOARD_REFRESH_RAISED` — an unhandled exception → exit 1
- `BOARD_REFRESH_REFUSED` — a governed refusal → exit 1
- `BOARD_REFRESH_WROTE_NO_SUMMARY` — the pass did not complete → exit 1

The distinction was computed and discarded at the exit code. **This is the
repository's own invariant broken one level up: a refusal is a result, a crash is
a defect, and they must not share an exit code.** The cost is not cosmetic — a
red badge that means "working as designed" trains everyone to ignore a red badge,
so a genuine break would arrive invisible.

**Fix.** The judging moved out of untestable shell greps into
`nfl/tools/judge_board_pass.py`, covered by
`nfl/tests/test_board_pass_judgement.py` (32 checks), replaying the real log
text. Five states, three exit codes. Exit 78 is neutral and is the convention
`nfl-production-forecast.yml` already uses, so this is consistency with existing
in-repo precedent rather than a new idea.

Neutral is granted **only** when every refusal code is declared debt **and** the
declaration is still present in `SYSTEM_STATE.json` **and** nothing raised **and**
the pass reached its summary line. A crash outranks declared debt; one
unrecognised code, one unparseable refusal line, or a deleted declaration and the
pass is red again. Fail closed. **Making a red pass green is not the purpose and
would hide the blocker — separating two states that were sharing one code is.**

Deployment is a separate step and is not mine: the fix is on this branch, and the
schedule reads `.github/` from **main**. Until main carries it, the workflow keeps
reporting the old way. That is itself an instance of the finding.

## Method note

An earlier version of the lineage tool matched only `python3 foo.py` and so
reported `nfl-production-forecast.yml` as running two test files and no forecast,
missing `python3 -m nfl.production.run_forecast`. It returned a non-empty,
plausible answer that was wrong, and I nearly wrote it up. A pattern that matches
something is not a pattern that matches everything; the regression is pinned in
`test_execution_lineage.py`.
## CORRECTION, 2026-09-26, later the same day

Two figures in the section above were wrong and are withdrawn. Both errors were
the same error: **a pattern that matched something was taken for a pattern that
matched everything.**

### There are four trees, not two

The first version of this tool captured a checkout ref of
`${{ env.CAPTURE_BRANCH }}` as the literal string `${{`, and treated the mere
presence of a `ref:` as meaning "the maintained engineering branch". It does not.
Resolved against each workflow's own `env:` block:

| Tree the workflow actually runs | Workflows | Scheduled | Modules in closure |
|---|---|---|---|
| `origin/claude/nfl-greenfield-architecture-stsxmk` | `nfl-product-board`, `ai-bridge`, `claude-engineering-dispatch` | product-board, `7,27,47 * * * *` | **95** |
| `origin/main` | `agent-orchestrator-heartbeat`, `nfl-availability`, `nfl-status`, `nfl-production-forecast`, `egress-probe` | heartbeat, availability, status | **48** |
| `origin/capture-prod` | `nfl-capture`, `nfl-t90` | both, `*/30 * * * *` | **16** |
| NOT ESTABLISHED | `agent-orchestrator-dispatch` (`ref: ${{ steps.target.outputs.branch }}`) | no, dispatch only | not statically establishable |

**So "109 branch-executed modules" is withdrawn; the engineering closure is 95.**
The extra 14 were the capture and T-90 entry points, whose closures the old tool
resolved against the engineering working tree while those workflows actually
check out `capture-prod`. The tool now refuses to guess an unresolvable ref and
reports it NOT_ESTABLISHED instead.

**The corrected guard figure.** 22 of 91 guards was measured against the
inflated closure. Re-measure against the 95-module engineering closure before
quoting it; the tool and the census cross-tab are both in the repository and the
number should be re-derived, not carried over.

### Prior art, and it came first

`nfl/tests/test_capture_deployment_integrity.py` established exactly this for the
capture surface in **D24 on 2026-09-15** — ref resolution included, plus a
content comparison of the deployed tree against the validated contract. It
currently reports `the branch the scheduler checks out (origin/capture-prod) runs
the VALIDATED capture implementation`. I built the general tool without reading
it first, and it had the specific answer already. Where the two overlap, that
test is the authority on the capture surface.

That test's one failing check is section B, `SURFACE_DIFFERS`: this tree's
capture code sha differs from the validated contract sha. That is open task
**D24-R1**, pre-existing and declared, not a regression from this session.

### A module can execute from several trees at once, and that is the finding

The same path is different code in each, because the trees are hundreds of
commits apart:

| Module | Executes from |
|---|---|
| `production/run_forecast.py` | engineering **and** main |
| `production/nonqb/layers.py` | engineering **and** main |
| `tools/check_retention.py` | **capture-prod and main** |
| `production/verdict.py` | no tree |
| `postgame/join_provenance.py` | no tree |
| `production/capture_cadence.py` | no tree |

`check_retention.py` is the sharpest case: **424 lines on capture-prod and 89
lines on main.** `nfl-availability.yml` checks out main and runs the 89-line
copy twice a day; `nfl-capture.yml` checks out capture-prod and runs the
424-line copy every thirty minutes. Same filename, same invocation, 335 lines of
difference, and no test compares them.

### DEF-075: the live-lineage control is absent from both executing trees

`nfl/production/capture_cadence.py` exists to prevent one specific misreading,
and states it in its own words: a manifest read from the wrong checkout means
"this file's age is the age of this checkout and not of the system".
`assert_live_lineage` raises `LINEAGE_NOT_ESTABLISHED` when the working copy is
not on `capture-prod`.

Measured across all three trees:

- `capture_cadence.py` is **present only on the engineering branch**, and is
  ABSENT from both `main` and `capture-prod`.
- It is imported by **no** production module on any tree; its only importers are
  two tests.
- **No copy of `check_retention.py` on any of the three trees** references
  `lineage_ok`, `assert_live_lineage`, `CAPTURE_BRANCH` or `current_branch`.
- There is **no** branch-provenance check anywhere in main's Python, and none on
  capture-prod outside an unrelated schedule generator.

So the control is not merely orphaned by imports, which is how the census
recorded it: **it does not exist on either tree that runs the capture pipeline.**
The census classification ORPHANED_CONTROL was measured on the engineering
branch and understates this.

**Severity is bounded, and honestly.** `lineage_ok` exempts an explicitly
supplied manifest path by design, and `nfl-availability.yml` passes
`--before-manifest /tmp/manifest_before.jsonl` explicitly. So this is a **gap in
cadence and staleness monitoring**, not a corrupted published number. Nothing
that runs today reports capture staleness with established lineage, and nothing
would refuse if it were asked to.

It is adjacent to open task **D24-R2** ("capture workflows must write back to
capture-prod, not main") and should be resolved with it rather than by wiring an
absent module into a tree that does not have it.

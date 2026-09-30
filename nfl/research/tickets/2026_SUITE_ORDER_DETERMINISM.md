# Suite order determinism (Priority Zero)

Opened 2026-09-30. Owner ruling: *"8 modules pass in isolation and fail in the
full run. That means the repository has order-dependent state contamination.
Until that is fixed, the authoritative suite itself is not deterministic. This
should now become Priority Zero."*

## The acceptance criterion

Owner's wording: **fresh process = normal suite order = reverse order =
randomized order, for the same commit and controlled seed.** Anything else and
the suite is measuring leftover state rather than the product.

Randomized-order mode is deliberately **not** yet a standing gate. Randomising
over a suite already known to be order-dependent produces a different failing
set each run and no diagnosis. `--shuffle` and `--reverse` exist and always
print the seed; they become a gate once the dependence is gone.

## Closed: four of the eight were the firewall working

Four of the eight — the `test_assumption_governance` family — failed with
`FC_READ_FROM_PROPRIETARY_CONTEXT`. That is the FantasyCruncher firewall
behaving exactly as designed: it refuses if any proprietary module has been
imported anywhere in the interpreter, so it cannot share a process with a module
that imports one. They now declare `REQUIRES_OWN_PROCESS`, the runner gives each
a fresh interpreter, and all four report 0 failing across 34 checks inside a
multi-module run.

This is the carve-out named in `CLAUDE.md` principle 9: a **declared**
process-scoped guarantee is isolation enforced by the harness, not order
dependence. The difference is the declaration.

## Withdrawn: the chunk bisect was searching a quarter of the space

A chunk bisect was run over a candidate list of 80 modules. Four chunks came
back `+PASS=16 +FAIL=0`, which was reported as clearing them.

**That reading is withdrawn.** The runner discovers 313 modules under
`nfl/tests/` plus 4 under `sportsplatform/`, and **303** of them precede
`test_v1_projection` in sorted order. The candidate list held 80. The bisect was
searching 26% of the space and omitted, among 223 others, every module that
invokes the production pipeline. A chunk that came back clean therefore
exculpates that chunk and nothing else, and the four clean chunks do not narrow
the cause.

Cause of the flaw: the candidate list was built from a filtered set rather than
from the runner's own discovery order. The runner is the only authority on what
runs and in what order — principle 8 applied to ordering, not just to existence.

Second defect in the same script, worse: it ran `git checkout -- .` before every
chunk. That destroyed uncommitted edits three times during this investigation.
It was also briefly suspected that the orchestrator was responsible; it was not.
The orchestrator's one commit on this branch
(`454a91dc`, run 36768216599) touches `nfl/tests/_suite_progress.jsonl` and
nothing else, and its message says it recorded leftover state rather than
discarding it. The suspicion is withdrawn.

## Withdrawn: "a test runs the pipeline and rewrites the artifacts a later test asserts on"

A specific, plausible mechanism was identified statically:

- `test_sunday_run` calls `sunday.run(archive=True)`, the real production path.
- It redirects only the **archive** root (`run_archive.RUNS`) into a temp dir.
  The **fixed output paths** under `nfl/dfs/salaries/` are not redirected, so the
  pipeline overwrites them in the live tree.
- `test_v1_projection` asserts against two of those exact files,
  `DK_WEEK3_PROJ_V1.json` and `DK_WEEK3_PROJECTIONS_V1.csv`.
- `test_sunday_run` sorts before `test_v1_projection`.

Every step of that is true, and the conclusion is still **false**. Measured with
`run_suite.py --modules test_sunday_run,test_v1_projection`:

| run | result |
|---|---|
| `test_v1_projection` alone | 17 fn, 16 checks, **0 failing** |
| `test_sunday_run` then `test_v1_projection` | 25 fn, 23 checks, **0 failing** |

Both modules pass, including `test_sunday_run`, which was itself listed as a
victim with 3 failures. And with `--watch` on the five paths
`test_v1_projection` reads, the run reports **0 changes**: `sunday.run()`
regenerates those artifacts **byte-identically**. It is deterministic, so it is
not a contamination channel at all.

This is worth keeping as a record because the static case was strong and the
measurement refuted it in two minutes. A plausible mechanism is not a cause.

## What is now unexplained

The four remaining reported victims — `test_v1_projection` (5),
`test_role_state_history` (7), `test_sunday_run` (3),
`test_role_and_prior_units` (1) — came from full-suite runs taken **in git
worktrees**. A worktree contains only tracked files, so it lacks the gitignored
raw store and derived artifacts. That environment already proved unreliable
once: it inflated the failure count, and 5 of 6 modules retested in the real
checkout passed.

So the first open question is not "which module poisons which" but **whether
these four fail in the real checkout at all.** Two of the four
(`test_sunday_run`, `test_v1_projection`) have now been shown passing there in
an ordered pair.

## Instruments added for this

Both are in `nfl/tests/run_suite.py`.

- `--modules a,b,c` runs exactly those modules in exactly that order. An order
  dependence is a claim about a pair, and `--only SUBSTR` cannot express a pair.
  An unknown name is a refusal, not a silently shorter run.
- `--watch p1,p2` hashes those repo-relative paths after every module and names
  the module that changed one. One instrumented pass replaces a nine-run bisect
  when the contamination is on disk. It is blind to in-process state such as a
  cached module global, so a clean watch report **narrows** the cause rather than
  clearing it. Demonstrated against a seeded change before being relied on.

## Next step

One instrumented full-suite pass in the real checkout at a recorded HEAD,
with `--watch` on the artifacts the reported victims read. It answers three
things at once: whether the four still fail, who mutates a watched artifact if
anyone, and the true failing set for the P1 taxonomy. Classifying the worktree
log would have produced a taxonomy of the wrong repository.

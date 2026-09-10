# V1 product-path engineering closure

**Verdict: `V1_PRODUCT_PATH_ENGINEERING_READY`.**

Full suite green: **56 modules, 600 test functions, 3,362 checks, 0 failing,
0 raised**, on `python3.12`. No estimator was changed. Nothing was tuned from
the NE@SEA outcome. No threshold moved. Nothing was promoted.

---

## Defect 1 — non-QB production chain placeholders

### What was there

`run_forecast._nonqb_stage` called the layers directly and assembled their
arguments itself:

```python
LY.targets_carries(pa, 'targets', [], [], ([], []), [], {}, ...)
LY.receiving_conversion(tc, [], {}, [], [], _ord)
LY.td_layer(cv, [], {}, [], [], _ord)
```

Every one of those has an owner. `{}` is the frozen P4C parameter block, `[]`
the class point forecast, `([], [])` the group layout the allocator partitions
over, and the later `{}` the RC1 and TD2 priors. Supplied empty the chain could
only raise — and did, `KeyError: 'add_pool'`, the first time an injury feed was
complete enough for `appearance` to pass and the stage to be reached at all.

### The repair, and why it is not "fill in the placeholders"

`football_engine.run_game` **already owns this composition**. It is the accepted
V1 architecture, it is what the rehearsal exercises, and it resolves each
argument from `slate_fits`, the appearance layer and the team-volume layer.
Building a second copy of that wiring inside the entrypoint would have given
every one of these inputs two owners — the defect this project pays for most.
So the entrypoint delegates and reports.

Argument provenance, each traced to a single owner:

| argument | owner | post-kickoff risk |
|---|---|---|
| P4C params (`targets`, `carries`) | `p4c_params.params(cls, season)` | prior seasons only |
| class point forecast `C` | `p4c_params.class_point_forecast` | prior seasons only |
| group layout `(starts, counts)` | the game's own two-team player frame | roster, pre-kickoff |
| `player_ids` / `positions` | same frame | roster, pre-kickoff |
| RC1 priors | `frozen_priors.receiving_priors(season)` | frozen artifact |
| TD2 priors | `frozen_priors.td_priors(season, kind)` | frozen artifact |
| availability | `layers.appearance` | gated by Defect 2's cut |
| target budget (C3) | the QB throw process | same run, same draw index |
| RB carry budget | **A1**, `carries[(team, 'rb')]` | same run, same draw index |

### Ordering: the reason C3 could never be reached

The declared stage list reports `qb_layer` **last** — after `targets_carries`,
`conversion` and `td_layer` — while C3 needs the quarterbacks' throws and A1
needs their scrambles. Reporting order and dependency order are not the same
thing. The QB half is now **memoised** and computed on first demand, so it runs
before its dependents while `qb_layer` still reports it in its declared slot.
Computing it twice would draw two different quarterback lines from one seed.

### A1 is the sole rushing-opportunity partition owner

`run_game` previously formed the running-back pool as
`share × D1.team_carries` — the whole team carry count, kneels and quarterback
runs and receiver runs included. That is a second answer to the question A1
exists to answer. `run_game` now takes `rushing_budget`, and with A1 live the
backs compete for A1's `rb` category and nothing else. With
`rushing_budget=None` the function is bit-for-bit what it was.

Three refusals guard it, none of which falls back: a missing team
(`RUSHING_BUDGET_TEAM_MISSING`), a draw-width mismatch
(`RUSHING_BUDGET_DRAW_MISMATCH`), and a budget above the level it partitions
(`RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES`).

### No silent fallback, no unnamed crash

- An exception from `run_game` or `slate_fits` becomes a named
  `NONQB_ENGINE_RAISED` / `SLATE_FITS_RAISED`. **A traceback is the one thing a
  stage may not return.**
- A player frame lacking `gsis_id`/`position`/`team` refuses as
  `NONQB_PLAYER_FRAME_INCOMPLETE` rather than raising deep inside the allocator.
- The derived-artifact gate runs first, through `DERIVED.artifacts()`, refusing
  as the declared `MODEL_ARTIFACT_MISSING`.
- A downstream stage names its blocker: `BLOCKED_UPSTREAM_<layer>` carrying the
  halting layer's own code, never a generic label.

### A defect I introduced during the repair, and caught

My first mapping left `rushing_budget` unowned by any declared stage. It
**failed**, no stage answered for it, and the run still sealed. That is exactly
the absence-read-as-success defect, committed by me, in the repair for it.
`_assert_every_layer_is_reported` now refuses with `ENGINE_LAYER_NOT_REPORTED`
if the engine runs any layer that neither a stage nor an explicit
`UNREPORTED_LAYERS` entry accounts for. Mapping the layers I happened to think
of is not a fix; enumerating them is.

---

## Defect 2 — injury/readiness vintage cut

`readiness.team_report_history` took each team's block from the newest capture
**on disk** and let the caller notice afterwards that it was too late. For
NE@SEA that meant a capture from 2026-09-10T13:37Z — thirteen hours **after**
kickoff — became the team's block, readiness refused
`INJURY_REPORT_CHRONOLOGY_FAILURE`, and the whole non-QB chain reported
NOT_APPLICABLE for a game whose pre-kickoff report existed all along in
`injuries.1bf460ad261559a8.csv.gz`, retrieved 32.2 hours before kickoff with 11
rows covering exactly NE and SEA. **The guard was right; the selector never
looked.**

The consumed-clock contract `retrieved_at <= written_at < kickoff` is now
applied **at selection**, in `as_of_cut` + `_all_injury_captures(as_of=...)`:

- selection is by `retrieved_at` and nothing else — never filesystem order,
  file size, row count, or manifest position;
- the cut is **part of the cache key**, so a hit is never restamped under
  another clock;
- **a bare call is no longer unbounded.** It resolved to "everything on disk",
  which is how a team whose report was never filed in time reads READY. It now
  resolves the team's own kickoff from the week plan, and says
  `READINESS_CLOCK_UNRESOLVED` if it cannot — rather than silently reading
  everything;
- the chronology branch is kept as a deliberately unreachable post-selection
  assertion. A guard deleted once it stops firing cannot tell you when the
  thing it guarded against returns.

Regression coverage in `nfl/tests/test_readiness_vintage_cut.py`, including a
check that the fixture it depends on exists — a post-kickoff capture must be
present, or every other check in the file is vacuous — and a check that without
the cut the selector really would take the post-kickoff block, so the cut is
demonstrably doing the work.

---

## Defect 3 — found by the repair: team volume had two owners

The `team_environment` stage drew team volume with **no coupling flags** while
the candidate path and the engine each drew their own **coupled** version. Same
quantity, three call sites. Under A3G they are different vectors, so the sealed
artifact stored team-volume draws the game had never used — the R2
apportioned-against-the-wrong-budget defect, one layer up.

Measured on Run A: its stored `team_volume` equals the **uncoupled** draw, and
its QB layer ran on the **coupled** one. One memoised `_team_volume()` owner now
serves every consumer, and `run_game` accepts it rather than redrawing.

Related: SC1 permutes the carry draw index, so after it runs the carry level on
draw *j* is no longer `tv[('team_carries', t)][j]`. A1 partitions the permuted
vector. Anything downstream reaching for the original reads a differently-indexed
answer — which fired immediately as 9 cells where A1's budget sat above a level
A1 had never seen. `team_carries_override` keeps one carry number in the game.

---

## Closure test

### Controlled, chronology-valid — the repair works

`2026_01_SF_LA`, kickoff 2026-09-11T00:35:00Z, `written_at` 2026-09-10T14:00:00Z,
every input observed before kickoff. **Both configurations SEAL with the full
chain executing.**

| stage | baseline | candidate |
|---|---|---|
| appearance → participation → targets_carries → conversion → td_layer | PASS | PASS |
| components applied | — | **A1, A3G, C0, C3, R2, SC1** |
| components not reached | — | **none** |
| players in `distributions` | 48 | 53 |
| draw layers | qb, receiving, rushing, team_volume | same |

C3 is reached and closes: receiver targets ≤ QB attempts in **every** draw.

The per-player quantile view previously carried 8 quarterbacks while the sidecar
held 45 receivers and 11 backs — draws stored and never surfaced. It now covers
every player the run forecast.

### Run A vs Run B — execution only, never prediction

Run A is preserved unmodified at `nfl/research/shadow/g1_ne_sea` (seal verified,
all five files hash to their recorded values). Run B is beside it at
`nfl/research/shadow/g1_ne_sea_runB`, from the **identical** sealed cutoff.

- **Every QB draw array is bit-identical.** R2, C0, A3G and SC1 are unchanged by
  this repair.
- The team-volume arrays differ, and only because Run A stored the uncoupled
  draw its own QB layer had not used.
- `appearance` moves from `INJURY_REPORT_CHRONOLOGY_FAILURE` to
  `INJURY_REPORT_INCOMPLETE`.

**The non-QB chain still does not run for NE@SEA, and that is now the truth
rather than an artefact.** The only NE/SEA injury captures before the
2026-09-10T00:20Z kickoff are 2026-09-07T13:06Z and 2026-09-08T16:06Z, and
`report_status` is unfilled on all 11 rows in both — they are practice reports.
The filled game-designation report first appears in the 2026-09-10T05:05Z
capture, **after kickoff**, because no capture ran anywhere on 2026-09-09. That
is the same gap that leaves G0A at 11/12. The product consequence of the capture
failure and the governance consequence are the same fact.

Nothing was scored. A and B are compared only to document the effect of
repairing execution.

### A pre-existing incoherence now measurable for the first time

With the chain finally running, the **baseline** allocation can be checked:

| check | baseline | candidate (C3) |
|---|---|---|
| targets are integer counts | **no** — a continuous product | yes (`int16`) |
| receptions ≤ targets | **1,453 of 9,000 cells fail**, max excess exactly 0.500 | 0 |
| team targets ≤ QB attempts | **14 of 200 draws fail** | 0 |

The max excess of exactly 0.500 is the `rint` signature — rounding, not a logic
error. These are **pre-existing** defects that C3 was written to fix and that
were unmeasurable while the chain could not run. **Not repaired here**: changing
the baseline allocation is model work and this ruling did not authorise it.
Recorded as `POST_V1_REFINEMENT`.

---

## Freeze conditions

| condition | state |
|---|---|
| full suite green | **PASS** — 56 / 600 / 3,362, 0 failing, 0 raised |
| no placeholder production inputs in reachable layers | **PASS** — AST-checked, not text-matched |
| chronology tests green | **PASS** — `test_readiness_vintage_cut.py`, 30 checks |
| HARD invariants green or honestly DEFERRED | **PASS** — `rushing_conversion` stays DEFERRED under `RUSHING_CONVERSION_CONTROL_UNDEFINED` |
| full-player chain executes when legitimate inputs exist | **PASS** — SF@LA, both configurations |
| deterministic replay | **PASS** — all 22 draw arrays bit-identical on re-run; the `run_id` delta is the `+dirty[n]` counter working as designed |
| no 2026 outcome used for fitting or tuning | **PASS** — the outcome file is opened only by `nfl/research/shadow/score.py`, which no production module imports |
| G0A rules unchanged | **PASS** — untouched |
| `PATH_C_STATE` unchanged | **PASS** — untouched |
| capture infrastructure untouched | **PASS** — no regression found, nothing changed |

The ARI test was repaired as a **snapshot** assertion: it required
`ARI == INJURY_REPORT_NOT_YET_FILED`, true the morning it was written and false
once Arizona filed. The invariant is preserved and strengthened — a team's state
is a function of its own rows — and the discriminating case is now **constructed**
at a cut where only two teams had filed, rather than hoped for on the day.

## Still open, `POST_V1_REFINEMENT`, not acted on

1. Baseline allocation incoherence, measured above.
2. `rehearsal/run_slate.py:roster` still selects the roster vintage with the
   most rows and can land on a post-kickoff vintage. It is a rehearsal harness,
   not the forecasting path; the shadow replay declines to inherit it.
3. `p4b_volume.M_DRAWS = 1000` caps the team-volume draw count; `m` truncates
   and cannot resize.
4. Individual-QB predictive intervals are one-sided at zero.
5. `team_off_snaps` and `team_dropbacks_part` are unverifiable without
   `snap_counts` and `pbp_participation`, both BLOCKED.

## Not authorised, not done

No estimator changed. No prior refitted. No threshold moved. Nothing promoted:
`promoted=false`, `prospective_eligible=false` on every artifact, NFL-1 remains
NOT AUTHORIZED, and G0A remains 11/12. The SF@LA G0A adjudication is a separate
scheduled task and proceeds on its own schedule.

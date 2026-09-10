# R8 — FOUNDATION CLOSURE + EARLY-SEASON APPEARANCE SYNTHESIS

**Date** 2026-09-10 · **Branch** `claude/nfl-greenfield-architecture-stsxmk`
**Configuration** `V1_CANDIDATE_R8` · **promoted** `false` ·
**prospective_eligible** `false` · **governance** `REHEARSAL_ONLY`

Evidence `nfl/research/r8/R8_EVIDENCE.json` · sealed run
`nfl/research/r8/sf_la_candidate/` (`1e585fb7e4adf2b7`) · freeze
`nfl/production/FREEZE_V1_R8.json` · pre-registrations
`nfl/research/prereg/PREREG_TRACKS_1_2_3.md`.

No sportsbook price was used as a label, a fit target or a model input.

---

# PART A — PER-TEAM QB DROPBACK CLOSURE

## The defect is not the one that was reported

**There is no leak. Per-team closure is integer-exact in every draw, and it
always was.** The figure I reported in R6 and R7 — SF 0.942, LA 1.060, game
0.999 — was wrong, and it was wrong in a way worth naming precisely, because
two separate defects were tangled in it and neither is cross-team compensation.

### Defect 1 — the measurement was transposed

The artifact carries two orderings of "team":

* `team_ids` is `['SF', 'LA']` — away, then home, from the game id;
* the `team_volume` draw matrices are stacked in **sorted** team order,
  `['LA', 'SF']`, which the draw manifest records as that layer's own
  `row_ids`.

Both are correct. Nothing bound them. I indexed the matrix by `team_ids`, and
the result is arithmetic:

| comparison | exact in every draw? | max abs diff |
|---|---|--:|
| SF quarterbacks vs **SF** budget | no | 44.0 |
| SF quarterbacks vs **LA** budget | **yes** | **0.0** |
| LA quarterbacks vs **LA** budget | no | 44.0 |
| LA quarterbacks vs **SF** budget | **yes** | **0.0** |

SF's quarterbacks sum **exactly** to LA's dropback draw in all 1,000 draws and
vice versa. 0.942 and 1.060 are the two teams' budget ratio, nothing more.

Nothing broke in production because no production consumer indexes that matrix
positionally. The only reader who did was an audit — mine — and the wrong number
then travelled into `FREEZE_V1_R6.json`, `FREEZE_V1_R7.json` and two owner
returns as an inherited unrepaired defect. **Both freeze records are corrected
in this commit.**

### Defect 2 — a verdict that could not be false

`qb_accounting.reconcile_team` returned this, from a hard-coded list in its
`return` statement, on **every** call:

```python
warnings=['sum of QB dropbacks does not equal team dropbacks; see '
          'ALLOCATION_RESIDUAL']
```

It measured nothing of the kind. `run_forecast` turned any warning into the FAIL
verdict `QB_ALLOCATION_RESIDUAL_PRESENT`, so **every sealed artifact this project
has produced carries a failing hard invariant that was a string, not a finding.**

Under R2 the assertion is false. The per-quarterback level is a largest-remainder
apportionment of `rint(team_dropbacks_part)`; `apportion_dropbacks` refuses
outright if the shares do not cover the budget
(`APPORTION_SHARE_DOES_NOT_COVER_BUDGET`, no survivor renormalisation); and
closure is integer-exact **by construction** in every draw.

The two defects are the project's signature failure in mirror image. Defect 1 is
a partial read taken as complete. Defect 2 is an assertion never checked against
the thing it asserts — `assert_batch_games_are_new` again, and the second one
this mission found.

## The trace, end to end

```
team dropbacks        TV.forecast -> tv.value[('team_dropbacks_part', t)]
        |               keyed by TEAM NAME, so this step cannot transpose
        v
QB availability       qb['index_by_team'][t] -> the rows QB V1 forecast
        |               a named QB the allocator names but V1 did not forecast
        |               is R2_ALLOCATED_MASS_HAS_NO_MODELLED_QB, refused
        v
QB ownership          QBACC.apportion_dropbacks(tdb, sub, pids)
        |               shares must sum to 1 or it REFUSES; largest remainder
        |               (Hamilton) then closes exactly, per team, per draw
        v
attempts/sacks/scr    QBV1.forecast(..., db_external=ext)
                        dropbacks == attempts + sacks + scrambles, EXACT
```

Every step is sound. The leak was in the reporting layer, in both directions:
a matrix nobody could index safely, and a verdict nobody could fail.

## The repair

1. **`reconcile_team` now MEASURES closure.** It takes `team_dropback_draws` and
   `integer_level`, tests `sum(QB dropbacks) == rint(team budget)` per team per
   draw, records the cell counts, and raises the warning **only when the test
   actually fails**. A team present in the rows but missing from the budget map
   is `QB_TEAM_DROPBACK_BUDGET_KEY_MISMATCH` — a refusal, not a skipped check.
   With no budget supplied at all the status is `NOT_MEASURED`, which is not a
   pass.
2. **`run_forecast` supplies the budgets** at both QB call sites.
3. **The artifact binds the two orderings**: `team_draw_row_index` records the
   map, and the run refuses with `TEAM_DRAW_ROWS_DISAGREE_WITH_TEAM_IDS` if the
   matrix and the artifact ever cover different teams. A row order may differ;
   the set may not.
4. **The artifact carries the closure proof**, quantified, so no reader has to
   re-derive it from the draw matrices — which is exactly where the transposition
   came from.

`ALLOCATION_RESIDUAL` is kept as history with `superseded_by_r2` and
`holds_under_r2: true` written into it. The multi-QB share over-allocation it
measured (2024: multi-QB drawn 62.510 against realised 36.607, n=84) is a
property of the pre-R2 layer, and the candidates no longer run that layer.

## Closure proof

Sealed in every artifact, all five configurations:

| configuration | status | draw cells | violating | worst deviation |
|---|---|--:|--:|--:|
| V1_CANDIDATE | **CLOSES** | 2,000 | **0** | 0.0 |
| V1_CANDIDATE_R5 | **CLOSES** | 2,000 | **0** | 0.0 |
| V1_CANDIDATE_R6 | **CLOSES** | 2,000 | **0** | 0.0 |
| V1_CANDIDATE_R7 | **CLOSES** | 2,000 | **0** | 0.0 |
| V1_CANDIDATE_R8 | **CLOSES** | 2,000 | **0** | 0.0 |

`integer_level: true`, `no_cross_team_compensation: true`. Attempts + sacks +
scrambles close against dropbacks exactly, unchanged
(`QB_DROPBACK_IDENTITY_HOLDS`).

**The guard is load-bearing.** `test_cross_team_compensation_can_never_hide_a_defect`
seeds SF one dropback over and LA one under, so the **game** total is exactly
right, and requires the check to fail anyway. If that test ever passes, the
closure test has stopped testing.

Verdict change on every future artifact: `FAIL QB_ALLOCATION_RESIDUAL_PRESENT`
→ **`PASS QB_ALLOCATION_RESIDUAL_NONE`**.

---

# PART B — THE SYNTHESIS

## The hypothesis, and why a switch was refused

R7 established the regime split. `if week <= 4 use R7 else V1` would reproduce
it and learn nothing — and week number is not the cause. It is a proxy for **how
many current-season games this player has**. A player who signs in week 9 has as
little current-season evidence as one in week 1, and a calendar switch hands him
the wrong model.

So every current-season participation quantity enters weighted by its own
reliability,

```
w = n_cur / (n_cur + k)
```

where `n_cur` is the player's own count of prior current-season frame rows, and
the depth block is additionally interacted with `(1 − w)`.

**`k` is estimated, never chosen.** It is the ratio of within-player to
between-player variance of player-season appearance rates: over 4,073
player-seasons with at least four games, within `0.139520`, between `0.114588`,
**k = 1.2176**. The weight is 0 at cold start, 0.451 after one game, 0.711 after
three, 0.868 after eight. It is re-estimated at each forecast cut from strictly
earlier rows.

A test asserts the point directly: changing **only the week number** moves at
most one column (R7's week-1 indicator, kept because the owner requires the
season boundary to stay explicitly represented), while changing the **evidence
count** moves many.

## The answer: yes, and it took two attempts

**First attempt — reliability weighting alone.** Better than R7 early, and it
matched R7 late without recovering V1:

| weeks | V1 | R7 | R8 (attempt 1) |
|---|--:|--:|--:|
| 1 | 0.24667 | 0.10966 | 0.08785 |
| 2–4 | 0.18146 | 0.11510 | 0.11163 |
| 5–9 | 0.11213 | 0.11814 | 0.11806 |
| 10–18 | 0.10975 | 0.11989 | 0.11909 |

That is the honest diagnosis of why: **V1's late-season advantage is its whole
P2/P3 feature block** — vacated share, practice progression, absence workload,
role volatility — not just a current-season appearance rate. Reweighting a
feature R8 did not have could never recover it.

**Second attempt — carry that block over too**, joined onto the union frame by
`(season, week, team, gsis_id)`, present on 53,626 of 59,784 rows and explicitly
missing on the rest.

## Full regime-by-regime validation

Forward-chained, fitted on strictly earlier seasons, evaluated on identical rows
(R8 is never credited for rows the frozen model cannot see):

| weeks | n | base | V1 Brier | R7 Brier | **R8 Brier** | Δ(V1−R8) | 95% blocked | V1 logloss | R7 | **R8** | V1 AUC | R7 | **R8** |
|---|--:|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|
| **1** | 2,568 | 0.576 | 0.24667 | 0.10966 | **0.06321** | +0.18346 | [+0.1724, +0.1942] | 0.7181 | 0.3757 | **0.2260** | 0.7261 | 0.9376 | **0.9654** |
| **2–4** | 7,709 | 0.581 | 0.18146 | 0.11510 | **0.10049** | +0.08097 | [+0.0772, +0.0848] | 0.5271 | 0.3729 | **0.3242** | 0.8055 | 0.9167 | **0.9390** |
| **5–9** | 8,907 | 0.760 | 0.11213 | 0.11814 | **0.10345** | +0.00868 | [+0.0063, +0.0110] | 0.3559 | 0.3782 | **0.3306** | 0.8826 | 0.8632 | **0.8972** |
| **10–18** | 16,972 | 0.754 | 0.10975 | 0.11989 | **0.10611** | +0.00364 | [+0.0020, +0.0053] | 0.3517 | 0.3815 | **0.3378** | 0.8886 | 0.8665 | **0.8947** |

**R8 beats both V1 and R7 in every regime, on every metric, with every
team-week-blocked interval excluding zero.** It does not average them: it
*exceeds* R7 early (0.06321 against 0.10966 at week 1) and *beats* V1 late,
though the late margin is small — +0.0036 Brier in weeks 10–18, which is real
but modest and should be described that way.

## Two defects R8 found in itself

Both are worth recording because both are the project's standing failure mode.

**A leaked label.** This game's snap share entered the design. In-sample Brier
came back at **0.04101 at AUC 0.9895** — a number good enough to be the bug
report. A player has a snap share if and only if he appeared, so the column and
its own missingness flag both carry the label. The value is kept on the row
because *later* rows need it to build `snap_ewma_cur` from prior games, and it is
never featurised for the row it belongs to. A test asserts it.

**A train/serve skew.** The V1 feature block was populated in training and empty
at prediction time. The "v1 block absent" flag fires on 6,158 training rows, all
depth-listed players who did not appear, so its coefficient is strongly negative
— and with the block unpopulated **every** forecast player tripped it. The first
R8 board returned SF's modelled targets at **1.41** against 28.71. A defect that
shows up as an obviously broken board rather than a slightly wrong one is the
lucky version of this mistake.

The fix was not to copy the walk. `appearance_model.predict` already computed
those rows and threw them away; it now exposes them as
`prospective_feature_rows`, and both `predict` and R8 **consume** the same walk.
A second copy is how a production model quietly stops being the accepted one.

## Cold-start and depth-tier calibration

On the **full union frame** — the only frame that can answer the cold-start
question, because the panel alone is survivorship-contaminated there:

| cell | n | observed | R7 | **R8** | R7 gap | **R8 gap** |
|---|--:|--:|--:|--:|--:|--:|
| KNOWN_HEALTHY | 33,963 | 0.7120 | 0.7131 | 0.7079 | +0.11 | **−0.42** |
| **NO_HISTORY** | 432 | 0.4769 | 0.6107 | **0.4771** | +13.39 | **+0.03** |
| UNKNOWN_STATUS | 6,198 | 0.1833 | 0.2673 | 0.2448 | +8.40 | **+6.15** |

**The cold-start defect is closed**: +13.39 pp becomes +0.03 pp.

Depth tier, same frame (observed / R7 / R8 gap in pp):

| cell | n | obs | R7 gap | **R8 gap** |
|---|--:|--:|--:|--:|
| QB1 | 1,838 | 0.8803 | −8.72 | **−2.57** |
| QB3 | 669 | 0.1794 | +6.26 | **+0.03** |
| RB1 | 1,773 | 0.8252 | +3.04 | **−0.53** |
| RB4+ | 3,268 | 0.5364 | +5.32 | **+1.21** |
| TE unlisted | 1,369 | 0.2235 | +7.86 | **+4.07** |
| WR1 | 1,695 | 0.8130 | +5.88 | **+1.04** |
| WR3 | 1,795 | 0.8981 | −5.55 | **−1.31** |
| WR unlisted | 2,904 | 0.2197 | +8.47 | **+5.96** |

Injury designation, both models within about two points everywhere: `Out`
observed 0.0000 against R8 0.0098 on n=855; `Doubtful` 0.0063 / 0.0266;
`Questionable` 0.6387 / 0.6546; no injury row 0.6270 / 0.6334.

**Where R8 is not better, and it must be said:** the long-absence residual is
not fixed and *moves* rather than shrinking. Within-season streak 2 and 3 are
over-predicted by **+12.86** and **+16.56** pp against R7's +10.31 and +9.08;
streak 4 is under-predicted by −13.33 against −9.13. That is the residual
censoring in the union frame — a player both off the depth chart and absent from
the panel still produces no row — and neither R7 nor R8 addresses it.

## Every R7 refusal survives

Asserted by test, not by intent: point-in-time depth selection through
`depth_vintage`; no today-chart substitution for an old game; the three-state
vocabulary `KNOWN_HEALTHY` / `NO_HISTORY` / `UNKNOWN_STATUS` kept distinct;
the season boundary explicitly represented as a reset streak plus a separate
carried streak plus a crossing flag; and the
`no_history_and_not_depth_listed` cell dropped from the fit and declined by name
at prediction time, because its appearance rate is 1.0000 with zero variance and
that is a construction rather than an estimate.

Two mechanisms in one configuration is `APPEARANCE_SPEC_AMBIGUOUS`, and an
unknown mechanism name is still a named FAIL rather than a silent fallback to
the control.

---

## SF@LA under the new candidate

| player | line | V1 | R5 | R6 | R7 | **R8** |
|---|--:|--:|--:|--:|--:|--:|
| McCaffrey carries | 15.5 | 7.29 | 9.52 | 12.23 | 12.97 | **11.98** |
| McCaffrey receptions | 4.5 | 2.56 | 3.58 | 3.80 | 4.11 | **3.64** |
| Kittle receptions | 3.5 | 2.44 | 3.67 | 3.92 | 4.28 | **3.83** |
| Kittle receiving yards | 33.5 | 31.93 | 47.82 | 51.26 | 56.34 | **49.86** |
| Kyren Williams carries | 13.5 | 6.68 | 11.02 | 11.04 | 10.61 | **10.66** |
| Nacua receptions | 7.5 | 3.56 | 5.03 | 5.44 | 4.92 | **4.90** |
| Nacua receiving yards | 90.5 | 46.95 | 66.31 | 71.22 | 64.64 | **64.15** |
| Purdy pass attempts | 33.5 | 26.708 | 26.708 | 26.708 | 26.708 | **26.708** |
| Stafford pass attempts | 34.5 | 30.266 | 30.266 | 30.266 | 30.266 | **30.266** |

Median |gap| to the de-vigged market across 19 comparable prices:
25.30 → 18.71 → 17.40 → 14.62 → **17.90 pp**.

**R8 sits further from the book than R7 while beating it on realised appearance
in all four regimes.** That is the comparator doing its job. Closeness to the
market is not the objective, was never a fit target, and is reported here only
because the owner asked for the diagnostic.

Concentration: SF targets top-1 19.71% (R7) → **17.61%** (R8) against a
historical 29.3%; SF carries top-1 74.07% → **66.19%** against 70.3%. R8 sits
between R6 and R7 and no longer overshoots on SF carries.

---

## Invariants

**Team-volume marginals unchanged.** R8 does not touch the layer; every
configuration consumes the same draws. The ten team-metric vectors agree to
`0.0000000000` across all five.

**QB path unchanged.** Pass attempts for all eight passers agree to `0.000000`
across all five configurations.

**The controls are bit-identical after the `appearance_model` refactor** — the
one change in this mission that touched a frozen module. Draw artifact sha256,
same inputs and seed, before and after:

| configuration | before | after |
|---|---|---|
| V1_CANDIDATE | `39576c0d74ce5f66…` | `39576c0d74ce5f66…` |
| V1_CANDIDATE_R7 | `61ea1e94ced093a9…` | `61ea1e94ced093a9…` |

**Modelled player sums:** R8 recovers most of the mass R7 shed — SF carries 18.30
(V1) / 17.51 (R7) / **18.10** (R8); SF targets 28.77 / 28.71 / **28.73**.

---

## Recommendation

**Shadow. Not promotion, and not rejection.**

For it: R8 beats both predecessors in every regime with intervals excluding
zero; the regime transition is driven by an estimated reliability weight rather
than a calendar switch, with a test proving the week number is not in the
design; the cold-start defect is closed to +0.03 pp; and every R7 refusal
survives with a guard on it.

Against promoting now: the late-season margin over V1 is small (+0.0036 Brier in
weeks 10–18); the long-absence residual is **worse** under R8 at streaks 2–3;
`UNKNOWN_STATUS` is still over-predicted by 6 points; the whole comparison is
historical and none of it is prospective; and R8 found two defects in itself
during one mission, which is a reason to want more eyes on it rather than fewer.

What would change this to promotion: a pre-registered prospective comparison
across at least the first four weeks of 2026 on unseen games, with the regime
buckets declared in advance rather than discovered afterwards, plus a repair or
an explicit acceptance of the long-absence residual.

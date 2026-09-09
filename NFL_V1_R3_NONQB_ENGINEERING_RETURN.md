# NFL-V1-R3 — Non-QB production completion behind the appearance gate

**Return decision: `V1_NONQB_ENGINEERING_READY_WAITING_ON_INPUT`**

Every deterministic production-engineering component the packet asked for is
built and executes. The whole non-QB chain now runs end to end on the real
2026 week-1 slate — all 16 games, 801 players, 200 draws, every accounting
identity clean over 160,200 cells — with **exactly one input stubbed: the
2026 injuries feed**. When that feed fills, the operator changes no code.

That claim is only worth making because it was tested rather than asserted, and
one part of it was false when this packet started. Before R3, `appearance`
deferred correctly while the feed was unusable and would have fallen through to
a **fixture error** had the feed become usable. The readiness report was telling
a comforting story: it said "waiting on input" about a path that did not exist.
That is fixed, and §6 below says exactly what now runs when the feed arrives.

---

## The one-line state of each thing the packet asked about

| | |
|---|---|
| D2 appearance | **IMPLEMENTED**, executes on the real feed, defers by name without it |
| D3 targets/carries | **IMPLEMENTED** on the accepted P4C system-C parameters, refit from the panel |
| D4 conversion | **IMPLEMENTED** on the RC1 baseline, per-catch yardage resampled |
| D5 TD | **IMPLEMENTED** on the TD2 pooled positional control (B_pos) |
| Joint non-QB accounting | **IMPLEMENTED**, seven named identities, FAIL not clip |
| Remaining external blocker | **`injuries_2026.csv` covers 2 of 32 slate teams** |
| G0A | **11/12**, unchanged and unchangeable by anything in this packet |
| NFL-1 | **NOT AUTHORIZED**, unchanged |

---

## 1. Starting HEAD

`fd80b72b7d8bb7c8d8793631b6d94572483ae718` — clean tree, recorded in
`nfl/production/nonqb/FREEZE_R3.json` together with the production spec hashes,
`PATH_C_STATE`, the R2 return, the research artifact hashes, and the gate
states.

## 2. Ending HEAD

`5b116b43e4cc08ede06a09a60e652f76984eee57`

## 3. Files changed

New, all under `nfl/production/nonqb/`:

| File | What it is |
|---|---|
| `eligibility.py` | the governance matrix, computed from `PATH_C_STATE` |
| `inputs.py` | the prospective input contract and the fixture quarantine |
| `readiness.py` | `report()` — exactly which condition blocks execution |
| `layers.py` | D2–D5, each refusing rather than fabricating |
| `appearance_model.py` | **the real D2 path**: the frozen P3 mechanism in production |
| `participation_prior.py` | the accepted `ewma_hl2` prior, prior-only |
| `p4c_params.py` | the accepted P4C system-C parameters, refit from the panel |
| `frozen_priors.py` | the RC1 conversion and TD2 positional priors |
| `accounting.py` | seven named per-draw identities |
| `engine_rehearsal.py` | §K/§H — the whole engine, only the feed stubbed |
| `slate_rehearsal.py` | §L — the real slate, nothing stubbed |
| `week2_data_debt.json` | §I |
| `FREEZE_R3.json` | §A |

Changed: `nfl/production/run_forecast.py` (governance-honest stage strings),
`nfl/production/team_volume_v1.py` (§J per-slate cache),
`nfl/production/rehearsal/run_slate.py` (reports every stage's own state),
`nfl/tests/test_nonqb_r3.py`.

## 4. Governance eligibility matrix

`PATH_C_STATE` is authoritative and was not modified.

| Layer | Subsystem | Research | Owner action | Production impl. | Prospectively validated | Runtime role | Publication eligible |
|---|---|---|---|---|---|---|---|
| team_environment | team_volume | RECOVERABILITY_CHARACTERIZED | HOLD_CHARACTERIZED | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| appearance | appearance | DECOMPOSED | INFORMATION_CONSTRAINED | IMPLEMENTED | NO | BLOCKED (input) | **no** |
| participation | appearance | DECOMPOSED | INFORMATION_CONSTRAINED | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| targets_carries | target_allocation | UNEXPLORED | DATA_BLOCKED | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| receiving_conversion | receiving_conversion | RECOVERABILITY_CHARACTERIZED | HOLD_CHARACTERIZED | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| rushing_conversion | rushing_conversion | RECOVERABILITY_CHARACTERIZED | HOLD_CHARACTERIZED | **NOT_IMPLEMENTED** | NO | REHEARSAL_ONLY | **no** |
| td_layer | td_red_zone | UNEXPLORED | HOLD_TENTATIVE | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| qb_layer | (none) | — | OWNER_BASELINE_SELECTION | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |
| joint_accounting | joint_dependence | UNEXPLORED | INVESTIGATE | IMPLEMENTED | NO | REHEARSAL_ONLY | **no** |

Two notes on this table that matter more than the cells.

**`production_implementation_state` used to be `None`** with a comment saying
the runtime would fill it. That is the same as not having the field: a reader
learned nothing about whether a governed layer had any code behind it. It is now
a declared value naming the module, and `assert_implementations_exist` imports
every named module and fails the suite if a claim is unsupported. A seeded false
claim is caught, so the check is load-bearing.

**Nothing is publication eligible and nothing was promoted.** Every owner action
above sits in the non-production set. `assert_no_stale_labels` passes: no
production string calls a non-production subsystem ACCEPTED or PROMOTED, and the
six stage strings R2 found (`P4C system C ACCEPTED`, `Stage2 ewma_hl2 ACCEPTED`
and the rest) now carry the governance state instead.

## 5. Exact remaining external blockers

**One, and it is not a code condition.**

`injuries_2026.csv` **has been published since R2** — 56 successful captures,
newest `2026-09-08T17:06:04Z`, blob
`nfl/vintage/injuries.1bf460ad261559a8.csv.gz`. R2's state
`WAITING_FOR_INJURIES_2026` is therefore **no longer accurate** and readiness
now reports the finer condition:

```
INJURIES_2026_PUBLISHED_BUT_INSUFFICIENT
  11 rows for 2026 week 1
  2 of 32 slate teams covered (NE 3 rows, SEA 8 rows)
  report_status populated on 0 of 11; practice_status on 11 of 11
```

The 30 absent teams are named in the artifact. This matters because
`teammate_availability` is a **team-level** feature: a team with no rows cannot
be distinguished from a team with nobody injured, so covering 2 teams is not
"partial information", it is absence for 30 of them.

**Next action: none in code.** Teams file their week-1 reports later in the game
week and the existing periodic capture records them. Re-run
`nonqb.readiness.report()`.

A second condition arrives at **week 2** and is recorded rather than worked
around — see §19 and `week2_data_debt.json`.

## 6. D2 implementation state — IMPLEMENTED

`appearance_model.py` runs the frozen P3 mechanism. Measured on the real 2026
week-1 roster with a stand-in feed: **920 modelled players, 21.8 s**, fit on
**83,144 panel rows across 2020–2025**, 49 features, in-sample Brier 0.1285,
AUC 0.8745 against a base rate of 0.6936, p in [0.149, 0.9997].

Everything mathematical is **imported** from the frozen research modules —
`stage_a.featurise`, `p3_features.featurise_p3`, `p3_features.enrich`,
`stage_a.fit_logistic`, `stage_a.predict`. One loop could not be: `stage_a.build`
loads its own panel from disk and will not accept a row list extended with
unplayed games. That loop is re-implemented, **labelled in the code as a
re-implementation**, and checked against the research walk:

> **1,164,016 feature values identical across 83,144 rows.** Zero divergences.

A re-implementation nobody compared is how a production model quietly stops
being the accepted one, so the equivalence is a measurement in the suite rather
than an assurance in a comment.

Guards that fire: training rows are strictly earlier seasons and a
forecast-season row entering the fit is `APPEARANCE_TRAINING_LEAKAGE` (a
refusal, never a filter); a player without a `gsis_id` is
`APPEARANCE_IDENTITY_UNRESOLVED` (fuzzy name matching stays forbidden); an
empty or wrong-season injuries table defers rather than predicting; every
committed research leaf is hash-checked against `INPUT_MANIFEST.json` before
use.

Participation's prior (`participation_prior.py`) is the accepted `ewma_hl2`
from `s2_verdict.json`, with the estimator itself imported from `s2_lib` and a
strictly-earlier-ordinal `bisect` prefix cut — the cut that exists because
player-ordinal pairs can carry two rows after a mid-week team change. On the
real slate: 801 players, 34,141 history rows, 285 on the **declared** positional
fallback (never a silent zero).

## 7. D3 implementation state — IMPLEMENTED

`p4c_params.py` supplies the **accepted** parameters, not a reconstruction. The
earlier rehearsal rebuilt `add_pool` from a normal scaled off `mean(sigma_lr)`,
which is fine for proving wiring and is not the accepted mechanism. The real fit
needs `panel_enriched.pkl`, which is deliberately not committed because it is
byte-for-byte regenerable; production regenerates it (25.7 s, verified by the
regeneration script and **re-verified independently here**) and then calls the
frozen `p4c_build.prepare_class` and `p4c_build.fit_params`.

Fitted on seasons before 2026:

```
add_pool          WR 15,297   TE 9,224   RB 9,683   (empirical residuals)
mass_pool         2,718 team-games, 2021-2025 (2020 excluded by predeclaration)
mass_mean         0.011282
alpha0            17.674237
sigma_lr          WR 0.675007  TE 0.743923  RB 0.763732
sigma_lg          WR 0.754668  TE 0.799744  RB 0.815156
q_zero            WR 0.171275  TE 0.306158  RB 0.309305
```

`W = C + resample(add_pool)`, the empirical OTHER mass, and the simplex
allocation all come from the research module — production calls
`p4c_build.gen_weights`, `p4c_build.mass_draws` and `p4c_lib.allocate`, it does
not reimplement them. `C` is the frozen ewma over prior appeared class shares
with the declared positional prior as fallback (283 of 801 players on it).

D3 requires legitimate D2 output. Without it: `BLOCKED_UPSTREAM_APPEARANCE`.
There is no fallback allocation path. A player with no appearance draw is
`ALLOCATION_PLAYER_WITHOUT_APPEARANCE`; an appearance vector of the wrong width
is `CROSS_DRAW_INDEX_MISMATCH` rather than a numpy broadcast.

Production has no oracle path: `p4c_build.appearance`-style oracle systems are
never invoked, and the suite checks that no production module exposes one.

## 8. D4 implementation state — IMPLEMENTED, and it fixed a defect of mine

`frozen_priors.receiving_priors` reads the RC1 baseline from the frozen frame:
positional catch rates **WR 0.634513, TE 0.702383, RB 0.776153**, per-catch
yardage pools of **39,126 / 15,831 / 15,024** gains, shrinkage constant
`K_SHRINK = 4.0`, all from seasons before 2026.

The earlier version of this layer took `catch_rate` and `yards_per_reception`
**from its caller** and computed `Y = R × ypr`. Two defects in one line. The
numbers were the caller's, not RC1's — a layer that accepts any prior is not an
implementation of a particular baseline. And a **constant** yards-per-reception
collapses the per-catch spread, which RC1's own addendum measures as not a
rounding matter: per-reception yardage has skew 2.197 and excess kurtosis 7.830,
and P(gain > 40) is 0.0203 empirically against 0.0016 under a fitted Normal —
the tail understated thirteenfold.

**This is the fourth time a point has been put where a distribution belongs in
this project**, after the R1 substitution, the QB2 rounding, and the missing
`size=` in RBB1. It is now refused structurally: `CONVERSION_PRIOR_NOT_FROZEN`
rejects a caller-supplied prior, and the yardage is resampled per catch from the
player's own history mixed with the positional pool at weight `h_n/(h_n+K)`,
exactly as `rc1_sim` does. Measured on the slate, within-player SD of receiving
yards is **11.45** against a mean of **8.70** — a distribution, not a point.

`CALIBRATION_DEFECT` and `SIGNAL_WEAK` are surfaced in the layer's own metadata
on every run, not left in a document. Nothing here is called promoted.

## 9. D5 implementation state — IMPLEMENTED

`frozen_priors.td_priors` reads TD2's accepted baseline for `rec|target`, which
`td2_ladder.json` records as **B_pos** at rung L4. Fitted on seasons before 2026:

```
B_league  0.046480
B_pos     WR 0.048872 (2,950 TD / 60,362 opp)
          TE 0.053669 (1,190 / 22,173)
          RB 0.030431 (  576 / 18,928)
```

One stated identity, and it is stated rather than fitted. TD2's estimand is
touchdowns **per target**; a receiving touchdown is nevertheless a catch, so
drawing per target would let a draw score more touchdowns than it had
receptions. The production rate is therefore expressed **per reception** as
`B_pos / pos_catch_rate`, which leaves the expected touchdowns per target
unchanged and keeps the count inside receptions by construction. A resulting
rate above one is `TD_RATE_ABOVE_ONE` — refused, never clipped.

`HOLD_TENTATIVE` travels in the metadata. There is no independent TD oracle and
no fantasy-point path.

**Correction to the freeze record.** `FREEZE_R3.json` lists
`nfl/research/td2/td2_results.json` as absent. That filename does not exist, but
TD2's artifacts do — `td2_ladder.json`, `td2_composition.json`,
`td2_persistence.json`, `td2.pkl`. The freeze recorded a guessed filename, not a
missing artifact. TD2 was not blocked.

## 10. Joint non-QB accounting state — IMPLEMENTED

`accounting.py` checks seven named identities **in every cell** and fails rather
than clipping:

1. `share_simplex_closure` — modelled shares plus the named OTHER mass are the whole group
2. `share_non_negative`
3. `player_opportunity_within_team` — no layer independently redraws a team quantity that exists upstream
4. `receptions_within_targets`
5. `receiving_td_within_receptions`
6. `zero_receptions_implies_zero_yards`
7. `allocation_only_when_available` — a player who did not appear in draw *j* receives no opportunity in draw *j*

The seventh is the load-bearing one: it is what ties the allocation layer to the
appearance layer on **one** draw index.

Two structural refusals sit around it. A check over zero cells is
`NONQB_ACCOUNTING_VACUOUS` — a FAIL, because an accounting module that reports
PASS on an empty draw set is the project's own recurring defect wearing a new
hat. And accounting over a chain that did not execute is
`NONQB_ACCOUNTING_NOT_REACHED` (NOT_APPLICABLE), never PASS.

`other` is reported as a named quantity and is never widened to absorb
disagreement.

**Identity 6 replaced one I got wrong**, and the rehearsal is what caught it. I
first wrote `receiving_yards_non_negative`, reasoning that yards are receptions
times a positive rate. That was a property of the **placeholder** conversion
layer. Once D4 became the real RC1 baseline the rehearsal raised **64 violating
cells at a worst of −8 yards** — because RC1 resamples real per-catch gains and
a reception for a loss is ordinary football. The identity was the defect, not the
draw. Negative gains are now counted and reported (1,857 cells across the slate)
and never refused; the mechanical identity that survives is that catching
nothing yields exactly nothing.

## 11. TEST-ONLY full-engine result (§K, and §H's proof)

`engine_rehearsal.py`, 2026 week 1, all 16 games, 200 draws, 450.7 s.

**Real:** the captured schedule and roster, the frozen team-volume fit, the
frozen P3 appearance mechanism, the accepted `ewma_hl2` participation prior, the
accepted P4C parameters, the RC1 conversion baseline, the TD2 positional control.

**Stubbed, and the only thing stubbed:** the 2026 injuries rows. Every rostered
player is entered as a full practice participant with no game-status
designation — deliberately the least informative legitimate row shape, so the
mechanism is exercised without inventing an injury story. It enters through
**exactly the argument the captured feed enters through**, which is what makes
this evidence about the code the real run will execute.

```
team_environment      PASS[TEAM_VOLUME_OK]        16/16
appearance            PASS[APPEARANCE_OK]         16/16
participation         PASS[PARTICIPATION_OK]      16/16
targets_carries       PASS[TARGETS_CARRIES_OK]    16/16
receiving_conversion  PASS[CONVERSION_OK]         16/16
td_layer              PASS[TD_LAYER_OK]           16/16
publication gate      FAIL[TEST_ONLY_DATA_IN_PRODUCTION_PATH]  16/16
```

The artifact is marked `TEST_ONLY`, carries its fixture provenance, is refused
by `assert_publishable`, writes no forecast artifact, cannot satisfy G0A and
cannot become prospective evidence. The mark is recomputed from the inputs at
each stage rather than passed along, so no layer can drop it.

## 12. Real week-1 result (§L)

`slate_rehearsal.py`, same slate, **no fixture anywhere** — every non-QB layer
called with `fixture=None`.

```
16 of 16 games SEALED
team_environment  PASS[TEAM_ENVIRONMENT_OK]                        16/16
qb_layer          PASS[QB_LAYER_OK]                                16/16
appearance        DEFERRED[INJURIES_2026_PUBLISHED_BUT_INSUFFICIENT] 16/16
participation     BLOCKED[BLOCKED_UPSTREAM_APPEARANCE]             16/16
targets_carries   BLOCKED[BLOCKED_UPSTREAM_APPEARANCE]             16/16
conversion        BLOCKED[BLOCKED_UPSTREAM_OPPORTUNITY]            16/16
td_layer          BLOCKED[BLOCKED_UPSTREAM_TD_INPUT]               16/16
nonqb accounting  NOT_APPLICABLE[NONQB_ACCOUNTING_NOT_REACHED]     16/16
publication       BLOCKED[NFL1_NOT_AUTHORIZED]
```

Roster `weekly_rosters.125c300ff066d314.reduced.csv.gz`, 2,955 rows.

This is the expected state and it is **not** a failure: the only unmet condition
is the external source. No non-QB layer emitted a probability, and the artifacts
are marked `PARTIAL_PLAYER_COVERAGE` with the absent layers named rather than
sealed as complete.

One supporting change: `run_slate` now reports **every stage's own state**, so a
consumer never infers PASS from the absence of a failure. Inferring success from
absence is this project's most expensive recurring defect and the rehearsal
reader was doing exactly that.

## 13. Player coverage

| | |
|---|---|
| Roster rows captured | 2,955 |
| Modelled non-QB players on the slate (WR/TE/RB with a `gsis_id`) | **801** |
| Per game | 45 to 56 |
| Appearance-modelled players including QB | 920 |
| Without prior panel history (rookies, practice squad) | 315 of 920 |
| On the declared positional participation fallback | 285 of 801 |
| On the declared positional target-share prior | 283 of 801 |

Mean modelled appearance probability across the slate is **0.409**. That is low
against a training base rate of 0.694 and it is the right shape: a 90-man
preseason roster carries many players who will not dress, and the mechanism
says so rather than assuming everyone plays.

## 14. Accounting results

Across all 16 games at 200 draws:

| | |
|---|---|
| Games reconciled | **16 of 16** |
| Cells checked | **160,200** |
| `share_simplex_closure` worst deviation | 2.03e-07 |
| `player_opportunity_within_team` worst relative deviation | 2.03e-07 |
| `share_non_negative` violations | 0 |
| `receptions_within_targets` violations | 0 |
| `receiving_td_within_receptions` violations | 0 |
| `zero_receptions_implies_zero_yards` violations | 0 |
| `allocation_only_when_available` violations | 0 |
| Negative-yard cells (reported, not refused) | 1,857 |

The two deviations are float32 accumulation against a declared `RELATIVE_TOL` of
1e-4 — an arithmetic allowance, not a modelling one, and no identity has a
tolerance chosen to make a run pass.

Slate means: 1.18 targets per player-draw, 8.70 receiving yards, 0.054 receiving
touchdowns, OTHER mass 0.0051.

## 15. Performance, before and after (§J)

The per-slate fit cache for D1 was implemented in R2 and is **proven
draw-equivalent**: the cache holds only history-derived quantities — the
attached panel, the league mean, the residual pools — and touches nothing in the
random stream. `V.draw` still runs per game with the same seed and the same row
count, so every number is identical. A version that also hoisted the draw was
rejected rather than shipped, because the rng is consumed row by row and hoisting
it changes every number.

R2 measured D1 refitting 80 times per slate; it now fits once per
`(season, week, metric)`. The suite asserts byte-equal draws with and without
the cache.

New R3 timings, all measured:

| Step | Time |
|---|---|
| Research artifact regeneration (hash-verified, exact) | 25.7 s |
| P4C parameter fit | 30.4 s |
| RC1 receiving priors | 39.9 s |
| TD2 positional priors | 9.0 s |
| Class point forecast | 27.4 s |
| Participation prior | 0.3 s |
| Appearance fit + predict, 920 players | 21.8 s |
| **Full 16-game non-QB engine, 200 draws** | **450.7 s** |

One performance defect was found and fixed inside R3: a `max()` over the panel
recomputed inside a loop over 83,144 rows — 6.9 billion comparisons — which
turned a 30-second call into a ten-minute one.

## 16. Suite counts

`python3.12 nfl/tests/run_suite.py`

```
modules 38  test functions 402  checks 2315  FAILING CHECKS 0  RAISED 0
SUITE PASS
```

`nfl/tests/test_nonqb_r3.py` alone: 125 checks, 0 failing.

## 17. G0A state

**11/12. Unchanged.** Nothing in this packet touched the gate, the anchored
capture schedule, or its identity. A `TEST_ONLY` run is structurally incapable
of satisfying it, and the rehearsal artifact says so in its own body.

## 18. NFL-1 authorization state

**NOT AUTHORIZED. Unchanged.** `may_publish()` returns
`BLOCKED[NFL1_NOT_AUTHORIZED]` on every game of the real slate. Nothing in this
packet moves it and nothing here requests it.

## 19. Exact next action when `injuries_2026` becomes usable

**No code change. In order:**

1. The periodic capture already polls the feed and writes each response to
   `nfl/vintage/` with its own `retrieved_at` — this is running now and produced
   the 56 captures behind the current state.
2. Run `nonqb.readiness.report(2026, week)`. It reads the newest successful
   capture, parses it, counts teams and column population, and returns
   `INJURIES_READY` when all 32 slate teams are covered and `report_status` is
   filed.
3. Run the slate. `layers.appearance(fixture=None)` sees `INJURIES_READY`, loads
   the captured rows, and executes the frozen mechanism — the same code path
   §11 exercised. D3, D4, D5 and the joint accounting follow without an operator
   touching anything.

**Two conditions will still hold and are not defects.** Publication stays
refused while NFL-1 is unauthorized, and nothing in the matrix becomes
publication eligible: an input unblocking is not a governance promotion.

**And one new condition arrives at week 2.** `pbp_participation_2026` is
published for 2016–2025 and 404 for 2026. Week 1 does not need it — a week-1
forecast conditions only on prior seasons, and `panel_p3` carries 2020–2025.
From week 2 the accepted `ewma_hl2` weights the most recent games hardest and
the most recent game is a 2026 game. Without it the estimator silently degrades
to "last season weighted as if it were last week", which is a **different
estimator wearing the accepted one's name**.

That refusal is now implemented, not just documented:
`PARTICIPATION_HISTORY_STALE`, naming the newest ordinal present, the forecast
ordinal, and `pbp_participation_2026` as the missing source. It fires today for
any week ≥ 2. No source policy was changed to route around it, and
`snap_counts` is not a substitute — it carries no pass/run split, so it cannot
bound pass-play participation.

---

## What I got wrong in this packet

Recorded because the mistakes are more useful than the successes.

1. **The readiness report was reassuring about a path that did not exist.**
   `appearance` deferred correctly and would have failed with a *fixture* error
   had the source arrived. §6 fixes it; §11 proves the fix.
2. **`receiving_yards_non_negative` was an identity about my own placeholder.**
   Real receptions lose yards. Caught by the rehearsal, at 64 cells and −8 yards
   worst, once D4 became the actual RC1 baseline.
3. **`Y = R × ypr` collapsed a distribution to a point** — the fourth instance of
   that defect class in this project. Now structurally refused.
4. **A `max()` inside a loop over 83,144 rows.** Ten minutes instead of thirty
   seconds.
5. **The freeze recorded a guessed filename** (`td2_results.json`) as a missing
   artifact. TD2's artifacts were there under other names.
6. **A production run rewrote a research artifact.** Regenerating
   `panel_enriched.pkl` makes `regenerate.py` write its own run report into the
   research tree — correct when a human runs it, wrong as a side effect of a
   forecast. The report is now snapshotted and put back, and the leaked value
   was restored to what R2 committed.

## What this return does not claim

- No layer is promoted, prospectively validated, or publication eligible.
- The engine executing is an **engineering** result. It is not evidence that any
  of these forecasts is any good; nothing here measures forecast quality, and
  the governance states above are unchanged.
- `rushing_conversion` has no production implementation and is declared
  `NOT_IMPLEMENTED` rather than left blank.
- No 2026 outcome was consumed. No market, DFS, or wagering component was
  touched. No vendor was contacted. T−90 was not modified.

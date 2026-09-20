# Sunday readiness — 2026-09-20, NFL Week 2

Measured 2026-09-19 against `5413e65` plus the working changes committed
alongside this file. Every figure was read out of the repository or produced by
a run today. Evidence: `nfl/research/sunday/SUNDAY_REHEARSAL_2026W2.json`.

## The one-line answer

**The system is NOT ready to produce a card, and it refuses to pretend
otherwise.** The production entrypoint declines all sixteen Week-2 games at
two named gates, under both the baseline and the candidate configuration. The
refusals are correct. What *is* ready is the evidence pipeline — capture,
freshness, identity, the simulation itself — and that is what Sunday should be
used for.

## The full-slate rehearsal (P10)

Run twice, end to end, at `--written-at 2026-09-20T12:00:00Z`:
`PRODUCTION_BASELINE` and `V1_CANDIDATE_R9_W1P_GSVUCY`. **Sixteen games,
sixteen REFUSED, zero sealed, in both.** Identical failure inventory:

| stage | code | games |
|---|---|---|
| `feature_build` | `STAGE_DECLARED_UNIMPLEMENTED` | 15 |
| `artifact_sealing` | `ARTIFACT_SEALING_FAILURE` | 15 |
| `capture_validation` | `SOURCE_CHRONOLOGY_FAILURE` | 1 |

The chronology refusal is DET@BUF, played Thursday — a forecast written at
12:00Z Sunday is not before a 00:15Z Friday kickoff. That gate is working.

The sealing refusal is `current_season_input_freshness`. Of three registered
current-season inputs:

- **`denom_panel` — BLOCKED BY DECLARATION** (`CURRENT_SEASON_SOURCE_UNVERIFIED`).
  Its current-season source has never been established.
- **`team_volume_history` — `CURRENT_SEASON_INPUT_STALE`**, newest ordinal
  **202518** against a required **202601**. It reads the same file;
  `denom_panel.csv.gz` holds 3,230 rows from 202001 to 202518 and **zero rows
  for 2026**.
- **`panel_p3` — FRESH.** The current-season QB panel resolves from week-1
  play-by-play and snap counts, 30 of 32 clubs, missing DEN and KC.

Nothing about that is fixable tonight, and nothing about it should be
loosened.

## Subsystem table

| Subsystem | Status | Evidence | Known defect | Sunday impact | Action |
|---|---|---|---|---|---|
| Freshness / data | **READY** | six core sources last captured 2026-09-19T15:05:38Z on `capture-prod`; `capture_freshness.py --verify-surface` reports every required source FRESH at 0.79h | this branch is BEHIND the surface and the tool says so by commit count rather than guessing | none | merge `capture-prod` each morning |
| Capture executor | **PARTIAL** | vintage capture healthy on a 30-min cadence; **availability watch dead since 2026-09-15T06:37:05Z** | the watch still pushes to `main` while the surface moved to `capture-prod` | none — it carries postgame files only | OUT-024 |
| T-90 anchored capture | **BLOCKED (action outstanding)** | the committed workflow held **week-1 crons only**; regenerated for week 2, six windows | GitHub schedules from the DEFAULT branch, so the fix is inert on this branch | **8 games' inactives windows have no anchored executor** | **OUT-026, before 15:30Z** |
| Player universe | **READY** | all 32 clubs, 21–24 skill players each at week 2 from `weekly_rosters.8bcf6ee6af93cc8b` | none found | none | — |
| QB state | **READY** | 84 QB rows over 15 games; `panel_p3` fresh at 202601 | DEN and KC have no current-season panel row and keep the 2025 answer, visibly | minor | — |
| Non-QB state | **PARTIAL** | 335 receiving, 91 rushing rows across the slate | **3 clubs lose all non-QB coverage** (below) | 2 half-games and 1 whole game | outbox: injury reports |
| Appearance | **PARTIAL, fail-closed** | `APPEARANCE_OK` on 12 games | **A1 FALSIFIED, CRITICAL, no successor spec** | projections carry unjustified role certainty | A1 successor blocked (no cohort) |
| Substitution | **PARTIAL, known-wrong incumbent** | A2 FALSIFIED, CRITICAL | redistribution is not proportional and the incumbent still is | vacated-opportunity projections are suspect | surfaced, not fixed |
| Team volume | **RUNS, with a declared limitation** | `TEAM_ENVIRONMENT_OK` all 15 | warning carried on every run: `team_volume_is_near_unforecastable` | wide intervals, honestly | — |
| Receiving | **RUNS, calibration defect open** | median **P(zero receptions) = 0.465** over 335 receiver-games; 153 of 335 above 0.5 | `DEBT-RECV-CALIB`: bias +2.18 yds, P(Y=0) 0.3004 predicted vs 0.3293 actual on the RC2 frame | a prop board would inherit it | not repaired tonight |
| Rushing | **RUNS** | 91 named rushing rows; carry identity closes exactly in a median 77.5% of draws on fully covered games | closure varies 0.03–0.94 by game (below) | — | P13 item opened |
| Touchdowns | **RUNS** | `TD_LAYER_OK` all 12 reached | `DEBT-TD-RECOVERABILITY`: decomposed, not characterised | — | ladder unrun |
| Efficiency | **RUNS** | QB layer carries three declared limitations: `multi_qb_over_prediction`, `int_discrimination`, `discrete_low_count_intervals` | all three declared | — | — |
| Game environment | **NOT REDESIGNED, deliberately** | — | no game-state engine | wide volume intervals | explicitly deferred |
| Joint simulation | **READY** | `JOINT_RECONCILED` and `DRAWS_BUILT` on all 15; 54 matrices, 93,400 draw cells, one shared draw index | **200 draws** | MCSE is large | draw-count selection is FIN-6, unrun |
| Distributions | **READY as of today** | mean, median, sd, **p5**, p10, p25, p50, p75, p90, **p95**, **P(zero)**, **MCSE ×2**, n_draws | added today; past sealed boards do not carry them | exact threshold queries now answerable from draws | — |
| Props | **BLOCKED** | one frozen Hard Rock snapshot, 166 quotes, 2026-09-13, `DOWNSTREAM_COMPARATOR_ONLY` | no prices for tomorrow's slate | no model-vs-market | downstream of sealing anyway |
| DK scoring | **READY (Showdown only)** | `dk_scoring__dk_points` on every run, 32 players | no DST anywhere in the engine | no Classic lineup possible | — |
| FD scoring | **READY (single-game only)** | `FANDUEL_RULES_VERIFIED.json`, corrected 2026-09-18 | provenance remains `VERIFIED_RULE_VALUE_RELAYED_SOURCE`; OUT-022C open | — | — |
| DFS legality | **BLOCKED for full slate** | only `DRAFTKINGS_SHOWDOWN` and `FANDUEL_SINGLE_GAME` contracts exist | **no Classic contract, no DST model, no FD salaries** | no full-slate DFS | outbox |
| Kickers | **READY as of today** | 32 of 32 clubs resolve; 16 kicking arrays per game with distance-band attempts | was **0 of 32** this morning | K is in the universe for the first time | — |
| Prospective sealing | **BLOCKED** | zero boards sealed | sealing gate, above | no frozen artifact tomorrow | — |
| Assumption audit | **PARTIAL** | 2 CRITICAL FALSIFIED (A1, A2), 1 CRITICAL DECLARED (A4), 2 MATERIAL untested | no per-projection assumption lineage yet | — | P12 not built |
| Postgame grader | **N/A tomorrow** | nothing forecast, so nothing to grade | — | the evaluation ledger must gain no Week-2 row | — |

## Three clubs cost the slate its non-QB coverage

The appearance layer refuses a club whose official injury report is
incomplete, on the stated ground that *"a team with no filed report is NOT a
team with no injuries."* Measured:

| game | effect | players with no projection |
|---|---|---|
| JAX @ DEN | JAX deferred, layer ran on DEN only | 15 |
| MIN @ CHI | CHI deferred, layer ran on MIN only | 12 |
| NYG @ LA | **whole game halted** — NYG has 7 rows, `report_status` unfilled on every one | all non-QB, both clubs |

That is correct fail-closed behaviour and it is also a **closable gap**: the
missing reports are bytes the networked agent can fetch. I first guessed DEN
and MIN were the affected clubs, from the draw shapes. That was wrong — the
evidence names JAX, CHI and NYG.

## Conservation (P13)

Measured per draw across the slate, on the declared identities:

The two half-covered games are separated out, because a shortfall caused by a
club having no projections at all is a coverage fact, not an allocator fact,
and pooling them would have made the allocator look far worse than it is.

**Twelve fully covered games:**

- **targets**: players sum to team targets exactly in a median **81.2%** of
  draws (range 0.765–0.860), mean shortfall **0.70**.
- **carries**: `named + unmodelled_pool + qb_rush_opp + gadget` closes exactly
  in a median **77.5%** of draws, mean shortfall **1.11** — but the per-game
  spread is wide: 0.935 for PIT@NE down to **0.030 for MIA@SF and 0.035 for
  SEA@ARI**.

**Two half-covered games** (JAX@DEN, MIN@CHI): exact closure 0.000 on both
identities, mean shortfall 31.6 targets and 24.1 carries — which is simply the
missing club's share and is fully explained by the appearance deferral above.

**Never over, anywhere.** Across all 14 games and both identities the
over-allocation fraction is exactly 0. The allocator never assigns more
opportunity than the team has, which would be impossible football; every
discrepancy is unassigned mass.

A game whose carries close exactly in 3% of draws is still not something to
wave through. **Opened as a P13 item, not fixed tonight** — the directive's own
rule is that arithmetic inconsistency is an immediate failure, and the honest
response is to name it with its numbers rather than patch the accounting the
night before a slate.

## What I fixed today, with before and after

| | before | after |
|---|---|---|
| kickers resolved | **0 of 32** | **32 of 32** |
| kicking arrays in a board | 0 | 16 |
| non-QB stages reporting | 5 stages `NOT_APPLICABLE[ENGINE_LAYER_NOT_REPORTED]` on runs whose engine had produced 38 matrices | `APPEARANCE_OK`, `PARTICIPATION_OK`, `TARGETS_CARRIES_OK`, `CONVERSION_OK`, `TD_LAYER_OK` |
| draw matrices / cells | 38 / 87,000 | 54 / 93,400 |
| T-90 windows for week 2 | none | six |
| distribution fields | p10–p90 | + p5, p95, P(zero), 2 × MCSE |
| capture freshness | read from whatever tree you happened to be in | refuses to answer without placing the tree against `capture-prod` |

## Suite state at HEAD, attributed

Full run, and every result classified against the 9052d0c baseline rather than
reported as a bare number (`nfl/research/suite_attribution/SUITE_DIFF_fs1_sunday.json`):

| | baseline 9052d0c | HEAD |
|---|---|---|
| modules | 186 | 190 |
| test functions | 2,027 | 2,065 |
| checks | 10,800 | 11,007 |
| failing checks | 61 | 72 |
| raised | 21 | 26 |
| zero-check functions | 0 | 0 |
| blocked functions | 23 | 22 |

PRE_EXISTING 128, NEWLY_INTRODUCED 22, RESOLVED_SINCE_BASELINE 3,
CHANGED_CLASSIFICATION 2. Of the 22 newly introduced: **17 fixed** (the
ownership-audit homonym and the two generated-state staleness checks),
**5 escalated and deliberately left red** (the frozen G0A schedule identity —
see below), and the `test_inactives_substance` census drift queued as SUN-8.

## One rule I broke, escalated rather than decided

Regenerating `nfl-t90.yml` for week 2 changed
`SCHED-2a2924d4966fbd3d` → `SCHED-5e2e890466c87284`. That first value is
pinned in `test_non_g0a_isolation.py:38` as *"Frozen by owner ruling until the
event"*, and the window it guards carries the outstanding G0A `inactives`
obligation.

`nfl-t90.yml` is doing two jobs — live scheduler and frozen record of week 1 —
and they are compatible for exactly one week. I kept the regeneration because
the week-1 window closed eleven days ago and no cron reopens it, while
tomorrow's windows are unrecoverable after T-90; `git revert f9148b0` undoes it
in one command. **I did not touch the frozen constant and did not edit any of
the five failing checks.** OUT-029, SUN-7.

## Classification

**READY** — capture freshness (with the tree named), player universe, QB
state, joint simulation and draw building, distribution completeness, kicker
resolution, DK and FD scoring for the formats that have contracts.

**PARTIAL, running with a measured limitation** — non-QB state (three clubs
uncovered), appearance (A1 falsified), substitution (A2 falsified, known-wrong
incumbent retained because the alternative is unvalidated), team volume
(`near_unforecastable`, declared), receiving calibration (`DEBT-RECV-CALIB`),
conservation (closes in a median 77.5–81.2% of draws on fully covered games, never over).

**BLOCKED** — artifact sealing, and therefore props, the prospective freeze
and the postgame grade. Cause: no 2026 denominator panel. Also blocked:
full-slate DFS (no Classic contract, no DST model), and the T-90 deployment,
which is an action outstanding rather than a defect.

**WILL NOT BE USED SUNDAY** — any board, any prop, any DFS lineup. There is
no sealed artifact to build one from, and none will be manufactured by
relaxing a gate.

**The single highest-value action left is not code.** It is getting
`nfl-t90.yml` onto the default branch before 15:30Z. Everything else on this
page can be redone next week; the inactives windows cannot.

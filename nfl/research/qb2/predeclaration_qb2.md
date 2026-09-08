# Pre-registration — QB2, QB V1 layer and production integration

Written 2026-09-08, **before any QB2 evaluation result was computed or
inspected**. Start HEAD `09a43e0`.

**EXPLORATORY.** 2022–2025 heavily mined. **No historical result may promote a
candidate.** The permitted outcome is a *production baseline selection*, which
is a different thing and is defined in §9.

## 1. Binding definitions, inherited from QB1

    dropbacks = pass_attempts + scrambles - spikes

**Not** `dropbacks − sacks − scrambles`. `pass_attempt` includes **every sack
(5,308/5,308)** and **every spike (278/278)**; the naive form errs by **5,586
plays**. Attribution follows the field that carries the player: attempts,
sacks, spikes, completions, pass TD and INT by `passer_player_id`; scrambles
and designed rushes by `rusher_player_id`. **Scrambles carry no
`passer_player_id`** (0 of 4,091).

**Reproduced exactly by this build, 2022–2025:** att_raw 76,941; sacks 5,308;
spikes 278; scrambles 4,091; completions 46,259; interceptions 1,615. The
identity gives 80,754 dropbacks against pbp's own `qb_dropback` flag at 80,753
— **the one-play difference is the named blocked-field-goal play
(`2025_03_LA_PHI` play 3600) and stays visible.**

Kneels (1,689 in 2022–2025) are excluded from designed rushes as
non-competitive; `54,572 − 1,689 = 52,883` reconciles exactly.

## 2. Frame

Seasons **2022–2025**, walk-forward, fitted on strictly prior seasons.
Eligible: QB player-games with **≥1 dropback** and **≥1 prior appeared
QB-game**. Chronology by strict ordinal prefix cut.

## 3. QB-change and partial-game policy — FIXED BEFORE EVALUATION

**Measured first:** of 2,174 team-games, **494 (22.7%) have more than one QB
with a dropback** — 463 with two, 30 with three, 1 with four. In those, the
second QB's median dropback share is 0.065 and mean 0.134, and he takes ≥25%
in 22.3% of them.

So "one QB per team-game" is wrong roughly one time in four and cannot be
assumed.

**POLICY, fixed now: TEAM-QB AGGREGATE THEN ALLOCATION.**

1. forecast **team dropbacks** (the stable quantity);
2. allocate to individual QBs by a **prior-only share**;
3. apply per-QB conversion rates to the allocated volume.

Chosen because it handles starter exits, backup appearances, two-QB games and
garbage-time snaps **without any depth-chart guesswork**, and because it
composes directly with the existing team-volume machinery and the accounting
invariants. A backup with **zero prior history** falls back to the positional
pool, never to a guessed depth position.

**No fuzzy depth-chart inference. No `weekly_rosters.status`.**

## 4. Causal factorization

    team plays -> team dropbacks -> QB share -> attempt / sack / scramble
      -> completion -> pass yards -> pass TD / INT
      -> designed rush / scramble -> rush yards / rush TD

Designed rush and scramble stay distinct.

## 5. Oracle decomposition — components fixed now

**Primary estimand: QB passing yards**, decomposed over **five** components,
exact Shapley over 2⁵ = 32 coalitions:

| id | component |
|---|---|
| `V` | team passing volume (team dropbacks) |
| `S` | QB share of team dropbacks |
| `M` | dropback outcome mix — attempt / sack / scramble rates |
| `C` | completion conversion |
| `Y` | passing yardage per completion |

**Secondary estimand: QB rushing yards**, over **three** components (2³ = 8):
`V·S` shared volume, `RO` rush opportunity rate, `RY` rushing yards per rush.

**All components oracled must reproduce the realised value exactly**, and that
is asserted rather than assumed. Shapley efficiency is asserted.
**Game-clustered bootstrap, 400 resamples.**

Pass TD and INT are reported in the distribution set (§7) rather than as
decomposition axes: both are rare counts, and TD2 established that oracling a
rare-event conversion rate conditional on realised opportunity approaches
handing over the outcome. **Repeating that confound here would produce a large
attribution that means nothing.**

## 6. Closed V1 ladder — four rungs, no more

`L0` pooled positional/league · `L1` chronology-safe shrinkage · `L2` EWMA
half-life 2 · `L3` shrunk EWMA. Applied per recoverable primitive. **No broad
QB feature search. No aggressive efficiency modelling. No hyperparameter
search** — half-life 2 and K = 4 are inherited constants.

**The opportunity-persists-more-than-efficiency hypothesis is TESTED here, not
assumed**, with opportunity and efficiency measured identically.

## 7. Distributions and metrics

Draw distributions for dropbacks, attempts, completions, sacks, pass yards,
pass TD, INT, designed rushes, scrambles, rush yards, rush TD.

Reported: **CRPS, MAE, RMSE, bias, calibration/coverage, discrimination
(Pearson r)**, per season, plus **QB-change** and **low-history** subgroups.

## 8. Whole-chain accounting

Per draw, the QB layer must reconcile with the existing invariants: attempts,
completions, sacks, scrambles, team passing yards against player receiving
yards, passing TD against receiving TD, and QB rushes within team rushes.
**Documented exceptions are preserved, not hidden** — the lateral exception (75
of 76 team-games) and the one unexplained IND 2022 wk16 play remain visible.

## 9. Production decision — and the distinction that matters

Permitted states: `QB_V1_BASELINE_ACCEPTED`, `QB_SIGNAL_WEAK`,
`QB_COMPOSITION_FAILED`, `QB_ESTIMATOR_DEFECT`, `QB_DATA_BLOCKED`.

**A PRODUCTION BASELINE SELECTION IS NOT A MODEL PROMOTION.**

- *Promotion* is a scientific claim that a candidate is better, and it requires
  prospective evidence this project does not have. **Forbidden here.**
- *Baseline selection* is an engineering choice of the simplest defensible
  implementation to run in production **so the pipeline is not structurally
  incomplete**. It carries **no** claim of superiority and is revisable without
  a retraction.

The goal is **the simplest defensible QB V1**, not the best QB model.

## 10. Result-driven changes forbidden

No threshold, component, rung, frame, policy or metric above may change after a
result is seen. **Seed 20260908, fixed now.**

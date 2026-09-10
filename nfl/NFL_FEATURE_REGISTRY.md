# NFL feature registry

Rule 024, inherited from `v8/FEATURE_REGISTRY.md`. Every feature carries exactly
one lifecycle status, and **a status above EXPERIMENTAL must cite the experiment
that earned it.**

Statuses: **CORE** · **SECONDARY** · **EXPERIMENTAL** · **DESCRIPTIVE** ·
**REJECTED** · **ORACLE / NON-DEPLOYABLE**.

**Nothing is CORE, and nothing can be, because no NFL experiment has run.** The
measured findings in `NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md` are exploratory:
taken on 2024–25 data that has since been inspected. Inspection is what
disqualified MLB's 251-game set.

---

## ORACLE / NON-DEPLOYABLE

A status this registry adds to the inherited list, because the inherited five had
no room for a quantity that is **legitimate as a bound and illegitimate as an
input**. Filing it REJECTED would lose the bound; filing it EXPERIMENTAL would
invite someone to try deploying it.

| Feature | Status | Evidence / ruling |
|---|---|---|
| `ffopportunity` expected-points | **ORACLE / NON-DEPLOYABLE** | Owner ruling 2026-09-06, A3 closed. Classification: **REALIZED-OPPORTUNITY ORACLE BENCHMARK**. |

**What it is.** External source review found it does **not** consume the realised
numeric outcome of the same play, but **does** consume realised *opportunity
identity and context* — who actually received the target or carry is already
known. Repository evidence agrees and was reached independently: W8 flagged that
its oracle framing rested on schema inference and named it as the claim it most
wanted checked.

**Permitted use.** Bounding the conversion layer *conditional on realised
opportunity*. That is what makes the bracket meaningful — prior-weeks-mean
r = 0.5907 below, expected-points r = 0.8419 pooled / 0.6853 within-player above —
and it supports the finding that the hard part is projecting opportunity rather
than converting it into points.

**Forbidden use.** Not a deployable forecasting feature. **Not a promotion gate.**
It may never appear in a model that is scored against a baseline, because it
knows something a forecast cannot know.

---

## REJECTED — measured, recorded so they are not re-proposed

| Feature | Result | Source |
|---|---|---|
| Plays per game as a team trait | split-half 0.220, shrunk ICC **0.000**; out of sample worse than league mean | W5 |
| Drives per team-game as a team trait | split-half **0.001**; pace predicts next-half play count at r = −0.099, wrong sign | W5 |
| "The goal-line back" | own goal-line share adds **+0.5%** over overall carry share; goal-to-go adds 0.0% | W3 |
| Free-standing red-zone target rate | partial r = 0.126; overall target share predicts next-half red-zone share better than red-zone share predicts itself | W4 |
| Charged drop rate | r = 0.020 (WR), 0.008 (QB) | W4, W2 |
| **Neutral pass rate as an INCREMENTAL split predictor** | **repeatable but redundant.** Split-half 0.532 (W5) is repeatability, not incremental value. Forward-chained 2022-2025, n=2,173: coach_prior MAE 0.07995, coach+neutral 0.07994 (delta **+0.00001**), and the incremental slope flips sign across seasons (+0.034, +0.062, -0.048, -0.095). No stratum pays, including coach-change (n=525, delta +0.00003). | Track 2, `nfl/research/prereg/TRACK2_NEUTRAL_PASS_RATE_RESULT.md` |
| Interception rate as QB skill | within-season 0.212 [−0.168, +0.530]; YoY intervals all cover zero | W2 |
| Blitz-faced rate as QB trait | r = 0.020 | W2 |
| Defensive sack rate as a team trait | reliability **0.000**; a sack is definitionally a pressure | W6 |
| Pass EPA allowed as a defensive trait | reliability 0.094 [0.000, 0.341] | W6 |
| Fumble-recovery share / forced fumbles | variance ratios 0.98 / 1.03 — chance | W6 |
| Individual receiver-vs-defender matchup | **SOURCE INSUFFICIENT**; opposing defence explains 0.66% of receiver yardage residual, placebo p = 0.113 | W6 |
| `participation.ngs_air_yards` | **SOURCE EMPTY** — 0 non-null of 45,919 | lead |
| `advstats.receiving_broken_tackles` | **SOURCE EMPTY** — 100% null | W3 |

## QUARANTINED — may not reach a forecast

Enforced by `nfl/ingest/allowlist.py`, not by convention. 47 model-derived pbp
columns, 8 schedules market columns, 5 outcome columns, 11 post-hoc columns.

| Class | Examples | Why |
|---|---|---|
| MARKET | `spread_line`, `total_line`, `vegas_wp` | the book, shipped inside the feed |
| OUTCOME | `result`, `total`, `home_score` | the result being forecast |
| POSTHOC | `weekly_rosters.status`, `away_qb_id`, `temp`, `wind` | knowable only after the fact; `status` is INA → 0 snaps of 3,438 |
| MODEL_DERIVED | `epa`, `qb_epa`, `cpoe`, `xpass`, `pass_oe`, `wp` | fitted upstream, information set unestablished |

`temp`/`wind` are **observed conditions, not forecasts**. A totals model reading
them from the archive is reading the weather it is predicting under. A forecast
vintage would be a different field, registered separately.

## EXPERIMENTAL — measured, unproven, nothing deployed

Opportunity share (snap / carry / target / pass-play participation), availability
`P(active)` and `P(role | active)`, redistribution on absence, defensive scheme
rates (Cover-3 0.878, man 0.875, blitz 0.810), pressure rate, game-script
coupling. All measured on inspected data; none has passed an experiment.

## OPEN DEBT

`PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` — no prediction-time eligibility source
exists. May **not** be closed with `weekly_rosters.status` or any post-hoc
substitute. NFL-1 is outside the debt (team-level, consumes no player
availability).

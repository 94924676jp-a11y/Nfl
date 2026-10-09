# Preregistration: two role-layer candidates, evaluated prospectively (written 2026-10-09, before any 2026 W5+ result)

**Status: PREREGISTERED, NOT PROMOTED.** Neither candidate changes production. Production carries only the tie-order
correctness repair (W5-G13: a tied depth rank is broken by evidence, never by the player id).

## Candidate RC-1: position-aware rank ceiling ("formation ceiling", research arm A2)

**What it changes.** `role_state.CEILING_BY_EVIDENCE` is read at rank `max(1, rank - (starters - 1))`, using the
formation the codebase already declares (`classic_slate_state.NO_USAGE_CHART_LIFT_LIMIT`):
- three WRs start;
- one RB and one TE start.

So a WR2 or WR3 is read at the DEPTH_RANK_1 ceiling, and the existing one-ALPHA-per-room rule orders the starters.
The patch is preserved at `nfl/research/role_ceiling/A2_FORMATION_CEILING.patch`.

**Why it is a candidate.** On 2021–2026 player-weeks, a pregame rank-2 WR realised a role above the current SECONDARY
cap in 50% of 1,890 weeks. For a rank-2 RB that figure is 18%, and for a rank-2 TE 10%
(`RANK_SEMANTICS.json`).

**Development evidence, which is not confirmation:**
- 2026 W2–W4 point-in-time replays (25 games, oracle availability): change in absolute DK error on changed players
  −0.217, 95% club-week bootstrap [−0.327, −0.102], 50 clusters.
- The real 2026 W4 Early DK pool (non-oracle): +0.054, [−0.154, +0.294], 16 clubs. **It did not replicate.**

## Candidate AP-1: player appearance history (research arm A3)

**What it changes.** The allocator's P(plays) for allocation rank r is a CLUB-SLOT rate: the share of club-weeks in
which at least r players recorded the measure. AP-1 changes it only for a rank ≥ 2 player who recorded a measure in
every 2026 week before the slate (up to the last 3). For him, it uses the rate at which such a player appears again,
measured on 2021–2025 only, when that rate is higher.

The table:

| | Rank 2 | Rank 3 | Rank 4 | Rank 5 | Rank 6 |
|---|---|---|---|---|---|
| WR | 0.83 | 0.777 | 0.673 | 0.673 | 0.6 |
| RB | 0.798 | 0.752 | 0.5 | — | — |
| TE | 0.706 | 0.672 | — | — | — |

Rank 1 is unchanged.

**Why it is a candidate.** The engine table gives a WR5 0.077 and an RB3 0.230. Players at those ranks who appeared in
each of the prior three weeks appeared again 67% and 75% of the time (`APPEARANCE_CHECK_THROUGH2025.json`). That is a
unit mismatch: a slot rate is being used as a player's probability of playing.

**Development evidence.** The real 2026 W4 Early pool: −0.116, [−0.274, +0.046], 16 clubs; RB MAE 4.86 → 4.55. That
is one week.

## Evaluation (both, separately, each against the production incumbent)

- **Weeks:** every 2026 regular-season Sunday and Monday slate from week 6 through week 11 inclusive, on the
  production pregame state frozen before lock (real pool, real designations, no oracle).
- **Metric:** paired change in absolute DK error per player, with a cluster bootstrap by club-week, B = 4000,
  seed 20261009. Secondary metrics: share error (targets, carries) and MAE by position.
- **Acceptance, all required:**
  1. the upper 95% bound of the paired change is below 0;
  2. no position's MAE worsens by more than 2% of the incumbent;
  3. at least 150 club-weeks.

  With fewer club-weeks the verdict is NOT_YET_EVALUABLE, never PASS.
- **Promotion** is an owner decision after the verdict, and also requires the full `run_suite.py` regression with no
  new failure.

## What voids this preregistration

- Any change to either candidate, the weeks, the metric or the bar after the first prospective week is graded.
- Any use of week 6+ outcomes in building either table.

Either voids the candidate. A changed candidate needs a new preregistration.

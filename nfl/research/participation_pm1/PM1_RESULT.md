# PM-1 result (2026-10-11, about 19:18 UTC)

- **Protocol:** `PREREG_PM1_PARTICIPATION.md`, committed `d3c0f775` before any download.
- **Code:** `pm1.py`.
- **Order of work:** the table was fitted on 2016-2023 and frozen to `PM1_TABLE.json`. Only after that did the
  evaluation read 2024-2025 (`PM1_EVALUATION.json`).

## Verdict: SHADOW-CONTINUE (every pre-registered bar met)

Held-out sample: 1,224 designated player-games (2024-2025), 683 club-week clusters, cluster bootstrap B = 4,000.

| endpoint | estimate | 95% interval | bar | met |
|---|---|---|---|---|
| H-a: Brier improvement over the incumbent (P(no participation) = 0) | 0.2126 | [0.1887, 0.2372] | lower bound > 0 | yes |
| H-b: calibration slope | 0.902 | [0.692, 1.120] | contains 1 | yes |
| H-b: calibration intercept | 0.135 | [-0.067, 0.353] | contains 0 | yes |
| H-c: CRPS improvement on workload share, 703 players who played with a baseline | 0.0789 | [0.0709, 0.0871] | lower bound > 0 | yes |

The held-out base rate is high: 39.3% of designated, not-ruled-out player-games recorded zero offensive plays. The
incumbent assumes 0%.

## Two limitations found after the verdict

These were found by exploratory reads of the **fit seasons only**. They do not change the verdict.

1. **Role is mixed in.**
   - The outcome "zero offensive plays" includes depth players who rarely play.
   - Questionable WR/TE in 2016-2023, P(no play) by the player's baseline share of plays (r0):

     | r0 | P(no play) | n |
     |---|---|---|
     | ≥ 0.70 | 0.223 | 960 |
     | 0.40-0.70 | 0.292 | 566 |
     | < 0.40 | 0.475 | 560 |
     | no baseline | 0.442 | 278 |

   - The cell `QUESTIONABLE|LIMITED|WR_TE|SOFT_TISSUE_LOWER`, which is McLaurin's, says 0.361 for all roles.
   - **Applied to a starter, PM-1 overstates the chance he does not play.**
2. **Inactive and active-but-unused are one outcome.**
   - The participation data has no game-day inactive status, so "ruled inactive at 90 minutes" and "active,
     0 snaps" cannot be separated.
   - Once a player is reported or confirmed active, PM-1's P(no participation) is the wrong number. Its
     workload-share distribution among players who played (r/r0) and its P(early exit) are still the measured
     quantities.

## What follows

- **PM-1 stands as registered.** Its table is not edited.
- **A successor, PM-2, is needed before production use.** It adds two things:
  - the baseline-role stratum;
  - game-day status, which separates inactive from active. That needs weekly-roster history, a new acquisition the
    owner has not yet approved.
- PM-2 gets its own pre-registration. Because 2024-2025 has now been read for PM-1, PM-2's primary evaluation is
  **prospective**: 2026 weeks 6-11. A 2024-2025 score for PM-2 would be labelled REUSED.

Workload share in McLaurin's cell, among players who played:

| quantile | r/r0 |
|---|---|
| p10 | 0.297 |
| p50 | 0.879 |
| p90 | 1.288 |

P(early exit | played) = 0.145.

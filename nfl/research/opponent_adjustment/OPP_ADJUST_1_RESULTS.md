# OPP-ADJUST-1 — Results (research only)

**Production is unchanged.** Nothing was written under `/home/user/nfl`; item 9 / G15 stays
NOT_MODELLED in the engine. This is a research verdict, not a promotion.

- Preregistration: `PREREGISTRATION_OPP_ADJUST_1.md` (sha256 `88b4c9df…`, 2026-10-09T19:31Z) +
  Amendment A1 (position labels; declared 19:34Z, before any outcome result). Hashes in
  `PREREG_HASHES.txt`; script and frame hashes in the JSON `provenance` block.
- Code: `build_frame.py` (point-in-time frame), `evaluate.py` (the preregistered evaluation).
  Full numbers: `OPP_ADJUST_1_RESULTS.json`.
- Self-tests: the truncation test (60 random club-games, features rebuilt from data strictly
  before the game) gave 0 mismatches. No market column was loaded (asserted). No 2026 week 5+
  rows. Held-out coverage was 100% for 2024 and 2025.

## What was measured

Opponent variables, each built point-in-time (current-season games in earlier weeks, plus the
prior season counted as 4 games, which is the incumbent's own weight) and shrunk toward the league
mean with a games-equivalent k **estimated on training seasons only**:

| Var | Meaning | k (F1 / F2) | implied 17-game reliability (F1) |
|---|---|---|---|
| D2 | opp EPA/dropback allowed | 29.7 / 38.2 | 0.36 |
| D3 | opp EPA/rush allowed | 73.1 / 37.6 | 0.19 |
| D4 | opp pressure rate (sack or QB hit per dropback) | 20.6 / 19.7 | 0.45 |
| D5 | opp explosive-play rate allowed | 29.0 / 29.7 | 0.37 |
| D6 | opp offence points centre (game-script variable) | 7.5 / 6.6 | 0.69 |
| D7 | opp points allowed | 36.1 / 28.2 | 0.32 |

**Incumbent, in three versions.** INC-RAW is the engine's own-offence centre with no opponent
term. INC-R is INC-RAW refitted on the training seasons with home field added. INC-R is the
comparison arm, so that a gain from refitting is not counted as an opponent effect.
**Candidate:** CAND-FULL = INC-R + D2…D7, fitted by OLS on training seasons only.

**Folds:** train 2021-23, test 2024; train 2021-24, test 2025. The 2026 weeks 1-4 fold is
supplementary and carries no verdict.

**Scoring:** CRPS, using the training residuals as the predictive distribution, plus MAE. The
bootstrap is paired and clustered (B = 2000) under three schemes: week, game and club. The widest
of the three is used.

## Club level (primary). Pooled held-out 2024+2025, n = 1,088 club-games

| Target | CRPS INC-R → CAND | dCRPS (rel) | 95% CI (widest) | **98.33% Bonferroni CI (widest)** | 2024 / 2025 dCRPS | dMAE |
|---|---|---|---|---|---|---|
| Pass attempts | 4.536 → 4.497 | −0.038 (−0.85%) | [−0.072, −0.002] | **[−0.082, +0.006]** | −0.035 / −0.042 | −0.049 |
| Rush attempts | 3.954 → 3.894 | −0.060 (−1.53%) | [−0.112, −0.010] | **[−0.126, +0.0004]** | −0.134 / **+0.013** | −0.087 |
| Points | 5.353 → 5.295 | −0.058 (−1.08%) | [−0.106, −0.002] | **[−0.117, +0.012]** | −0.047 / −0.069 | −0.074 |

Subsets. Each cell gives dMAE and its 95% upper bound (widest scheme) against the non-inferiority
margin of +2% of INC-R MAE:

| Target | STABLE (n=752) | QB_CHANGE (n=336) |
|---|---|---|
| Pass att | −0.066, ub +0.002 vs 0.124 | −0.012, ub +0.113 vs 0.137 |
| Rush att | −0.073, ub +0.023 vs 0.113 | −0.119, ub +0.013 vs 0.114 |
| Points | −0.098, ub +0.004 vs 0.154 | −0.018, ub +0.118 vs 0.144 |

The gain is concentrated in STABLE games. In QB_CHANGE games the pass-attempt and points CRPS
differences are near zero or positive.

Calibration of CAND-FULL on held-out data (slope of actual on predicted; band 0.80-1.20):
- Pass attempts: 1.15, CI [0.88, 1.43].
- Rush attempts: 1.00, CI [0.72, 1.25].
- Points: 1.00, CI [0.82, 1.19].
- Mean bias is within 5% for all three.

**Supplementary, 2026 weeks 1-4 (n = 128):**
- Pass attempts: dCRPS +0.047, CI [−0.016, +0.113].
- Rush attempts: +0.076, CI [−0.003, +0.157].
- Points: −0.005.
- So there is no gain at all in the only 2026 data.

### Verdicts (club)

| Target | A1 improvement | A2 persistence | A3 subsets | A4 calibration | **Overall** |
|---|---|---|---|---|---|
| Pass attempts | FAIL (ub +0.006) | PASS | PASS | PASS | **FAIL** |
| Rush attempts | FAIL (ub +0.0004) | FAIL (2025 reverses) | PASS | PASS | **FAIL** |
| Points | FAIL (ub +0.012) | PASS | PASS | PASS | **FAIL** |

## Fantasy (secondary; Bonferroni over four positions)

| Unit | dCRPS pooled (rel) | 98.75% CI | Overall |
|---|---|---|---|
| QB group | −0.003 (−0.07%) | [−0.028, +0.021] | FAIL |
| RB group | −0.049 (−0.88%) | [−0.110, +0.014] | FAIL (A1; A4 slope 1.24) |
| WR group | +0.016 (+0.21%) | [−0.025, +0.053] | FAIL |
| TE group | −0.024 (−0.52%) | [−0.051, +0.004] | FAIL |
| Player QB / RB / WR / TE | +0.003 / −0.004 / +0.002 / −0.006 | all straddle 0 | FAIL all |

At the player level the opponent term is worth essentially nothing (all differences ≤0.2%).

## Exploratory (no verdict; multiplicity not controlled)

- For points, single variables helped with 95% week-CIs below zero: D7 points allowed −0.072,
  D1 EPA/play −0.046, D3, D2, D5.
- For volume, the opponent-offence game-script term D6 was the largest single contributor to rush
  attempts (−0.040, CI [−0.079, +0.001]).
- The pass-protection matchup proxy (CAND-OL) changed little beyond CAND-FULL.
- Changing k to 4 or 17 did not change any conclusion.
- **Incidental finding about the incumbent itself.** INC-RAW's held-out calibration slope is 0.59
  for pass attempts, 0.59 for rush attempts and 0.67 for points. It over-reacts to club history,
  and a training-fit shrink (INC-R) improves points MAE from 7.661 to 7.536. That is larger than
  the opponent effect. This was not preregistered as a bar.

## Data that is missing

- **Coverage (man/zone, shell, blitz):** not in this checkout for 2021-2025. W6 used a cache
  outside the repo that covers 2024 only.
- **Offensive-line grades:** not available, because they are proprietary. Only the
  pressure-allowed proxy was tested.
- **Defensive absences:** not available point-in-time. Injuries and official inactives in the repo
  cover 2026 only. Snap counts for 2024-2025 are realised post-game participation, not a pregame
  feed.
- **No 2020 pbp:** in 2021, D2-D5 have no prior-season term.
- **EPA scale:** nflverse's EP model may have been fitted on later seasons. This is disclosed, but
  it is not a game-level leak.

## Status and what promotion would additionally require

These are honest forward-chained tests of prespecified models on 2024 and 2025. Those seasons were
used elsewhere in the project but not for this question.

Promotion would additionally require:
1. **A new preregistration (OPP-ADJUST-2)**, declared before 2026 week 5 kickoffs, with fixed
   coefficients or a declared refit rule.
2. **A prospective evaluation on 2026 weeks 5 onward.** Power is the limit here: the two-season
   95% interval half-width is about 1% of CRPS, which is the same size as the effect. The roughly
   416 remaining 2026 club-games cannot decide it alone, so the plan needs a declared rule for
   pooling them.
3. **An owner decision.**

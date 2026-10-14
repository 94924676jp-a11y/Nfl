# RESULT D2: player-level appearance probability (PREREG_D2_APPEARANCE.md @554eb007)

**Verdict on the single 2025 look: PASS by the registered rule.**

**Status.**
- **NOT_CONFIRMED.** 2025 aggregates had been inspected before (PLAYER_SCORECARD, the D1 look), so this is a first look
  at D2 on a non-pristine season.
- Only a prelock prospective arm, Week 6 onward, can confirm it, and that arm does not exist yet.
- **Not promoted.** No production default changed. `proj_v1.py` is untouched.

## Chain of custody

| step | commit |
|---|---|
| error atlas → APPEAR-D1 diagnosed on 2024 | d9115733 |
| pre-registration, before any D2 code | 554eb007 |
| D2 code, tests (golden: CURRENT ≡ incumbent), parameters fitted on 2022–23 and frozen | f8c5be88 |
| 2024 development scored and committed before the look | a89c7fc6 |
| 2025 look 2 logged in `HOLDOUT_LOOKS.jsonl` (result sha256 `f29b2aa4…`) | this commit |

**Parameters.**
- ROLE: κ = 21, at the top of the registered grid. This is recorded, and the grid was not widened.
- Role priors (position × depth-rank bucket × appeared in the club's last game) run from 0.15 to 0.87.

## Numbers

All differences are D2 minus the comparator, in DK points of mean absolute error: unconditional, every pool player,
0 if he did not play. Each comes with a week-blocked 95% interval (10,000 resamples, seed 20261014). Equal
information: no injury news on either side.

| | 2024 development (5,637 rows) | **2025 look (6,566 rows)** |
|---|---|---|
| incumbent MAE | 5.264 | 4.882 |
| D2-ROLE MAE | 4.554 | **4.269** |
| naive STD_U MAE | 4.576 | 4.321 |
| **D2-ROLE − incumbent** | −0.71 [−0.83, −0.60] | **−0.61 [−0.71, −0.51]** |
| QB | −0.65 | −0.43 [−0.74, −0.06] |
| RB | −0.57 | −0.78 [−0.87, −0.68] |
| WR | −0.91 | −0.55 [−0.66, −0.43] |
| TE | −0.56 | −0.65 [−0.73, −0.57] |
| appeared in the club's last game | −0.60 | −0.46 [−0.60, −0.31] |
| missed it | −0.94 | −0.89 [−1.00, −0.79] |
| **D2-ROLE − naive** | −0.02 [−0.07, +0.03] | **−0.05 [−0.10, −0.01]** |
| incumbent − naive | +0.69 | +0.56 [+0.49, +0.63] |
| appearance Brier, incumbent → D2 | 0.372 → 0.171 | 0.391 → **0.173** |

**2024 ablations** (unconditional MAE, the same rows):

| arm | MAE |
|---|---|
| CURRENT | 5.264 (identical to the incumbent: golden) |
| NONE (no appearance discount) | 5.128 |
| SHRINK (one pooled prior) | 4.763 |
| ROLE | 4.554 |

Role conditioning adds about 0.21 over plain shrinkage.

**Pass rule, 2025.**
- The upper bound for D2 − incumbent is −0.51 < 0.
- No position is worse.
- D2's Brier is below the incumbent's.

All three conditions hold.

## What this does and does not show

- **It shows** that the football core's opportunity layer, with only a fix to the appearance probability, moves from
  0.56–0.69 DK points *worse* than the naive per-appearance baseline to level (2024) or slightly better (2025), on
  equal information.
  - This is the first held-out result in which the complete football core is not beaten by the simple baseline.
- **It does not show** that production improves. Production already removes confirmed absences through roster and
  injury news, and the prospective four-arm has C ahead of the news-adjusted baselines on W4–W5. How D2 interacts with
  that news is unmeasured.
  - 52% of the 2025 gain comes from the "missed the last game" stratum (2,359 of 6,566 rows). That is where news overlaps most.
- **Given play, the top decile is now under-projected** (WR/TE level 0.92). An appearance-weighted projection scored
  only on players who played sits below 1 by construction, so this is not, on its own, a defect. The target-share
  concentration from the atlas (top-decile share 1.22) remains, and D1 addressed it.

## Next (registered, not yet run)

1. **Prospective arm D = D2-ROLE on the slate path, prelock.** It runs beside C on the same frozen state, on every slate
   from Week 6. D2 is applied only to players whom the news does not already mark absent. This is engineering work;
   it needs no owner decision, because it is a shadow and not a promotion.
2. **D1 and D2 together.** Only as a new pre-registration, and scored prospectively. 2025 cannot be used again for D1.

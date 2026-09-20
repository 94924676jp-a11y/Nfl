# Week 2 — projection calibration

Graded player-games: **133** across **7** games. Not published: 2026_02_CLE_TB.

CANDIDATE_NOT_ACCEPTED_BASELINE. The board graded here is `V1_CANDIDATE_R9_W1P_GSVUCY`, authorised for one slate and never promoted. The runs stopped at `artifact_sealing`, so the board is UNSEALED. No production model, coefficient or candidate identity was changed by this analysis. V2 NOT YET EARNED.

## DraftKings points, projected mean vs actual

| statistic | value |
|---|---|
| mean bias (actual − projected) | **-0.1088** |
| SE of bias, naive | 0.4195 |
| SE of bias, clustered by game | **0.3697** |
| MAE | 3.5994 |
| RMSE | 4.8214 |
| SD of projected means | 5.3301 |
| SD of actuals | 6.6304 |
| SD ratio projected/actual | 0.8039 |
| Pearson r | **0.6927** |

OBSERVED: the mean DK bias is -0.109 points against a game-clustered SE of 0.370. That is well inside one SE. No equivalence margin was predeclared, so this is a failure to detect bias, NOT a demonstration that the projections are unbiased.

OBSERVED: r = 0.6927 between projected mean and actual DK points. Calibration and discrimination are different properties and this line speaks only to discrimination.

## Quantile coverage

| quantile | nominal | realised at or below | n |
|---|---|---|---|
| p50 | 0.50 | **0.4511** | 133 |
| p90 | 0.90 | **0.9323** | 133 |
| p95 | 0.95 | **0.9549** | 133 |

## Threshold probability calibration

| threshold | n | mean predicted | realised | gap | SE clustered |
|---|---|---|---|---|---|
| P(DK>=10) | 133 | 0.2649 | 0.2406 | **-0.0243** | 0.0519 |
| P(DK>=15) | 133 | 0.1509 | 0.1203 | **-0.0306** | 0.0410 |
| P(DK>=20) | 133 | 0.0839 | 0.0602 | **-0.0238** | 0.0287 |
| P(DK>=30) | 133 | 0.0212 | 0.0000 | **-0.0212** | n/a |

## Workload calibration

| quantity | n | mean projected | mean actual | bias | MAE | RMSE | SE clustered |
|---|---|---|---|---|---|---|---|
| att | 18 | 23.315 | 25.722 | **+2.407** | 7.813 | 9.752 | 1.551 |
| carries | 34 | 6.529 | 6.676 | **+0.148** | 2.768 | 3.909 | 0.471 |
| cmp | 18 | 14.889 | 16.056 | **+1.167** | 5.281 | 6.223 | 1.109 |
| int | 18 | 0.460 | 0.500 | **+0.040** | 0.601 | 0.701 | 0.160 |
| ptd | 18 | 1.004 | 0.667 | **-0.337** | 0.753 | 0.934 | 0.189 |
| pyds | 18 | 164.899 | 169.333 | **+4.435** | 58.128 | 68.592 | 10.268 |
| receiving_yards | 110 | 19.969 | 21.900 | **+1.931** | 14.675 | 21.467 | 1.563 |
| receptions | 110 | 1.776 | 2.091 | **+0.315** | 1.117 | 1.687 | 0.169 |
| rushing_yards | 120 | 10.431 | 9.033 | **-1.398** | 6.822 | 12.482 | 1.125 |
| targets | 110 | 2.624 | 3.155 | **+0.530** | 1.694 | 2.379 | 0.245 |

OBSERVED: the passing-game volume quantities (targets, receptions, receiving yards, pass attempts, completions) are biased POSITIVE — the model projected less than happened. Rushing yards and passing touchdowns are biased negative. The miss is directional by quantity, not a uniform shift.

INFERRED: because every one of these quantities is measured on the same seven games and many on the same players, these are not independent confirmations of one another. The game-clustered SEs are the honest ones and several of the biases are inside two of them.

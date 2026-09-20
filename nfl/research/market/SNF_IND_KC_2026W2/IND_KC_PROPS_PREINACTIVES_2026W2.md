# IND@KC — model vs Hard Rock — PREINACTIVES_MARKET

Board `f6e4b8e611cb085d…` captured 2026-09-20T22:52:14Z–2026-09-20T22:52:16Z · 870 rows (75 main, 795 alternate)

Model run `44fccb9d9f0458a6` · 8,000 draws · cut `2026-09-20T22:35:00Z` · CANDIDATE_NOT_ACCEPTED_BASELINE · inactive gate **PREINACTIVES_NOT_CERTIFIED**

DOWNSTREAM_COMPARISON_ONLY. No line, price, spread, total or implied probability entered the football model. The draws were frozen before this file was opened.

## Read this before ranking anything

Week-2 grading measured a mean predicted probability of -0.0953 gap between what the model said and what happened, over 263 graded markets across 7 games. one slate, heavily overlapping markets, wide game-clustered standard errors. A shrink toward the book, not a corrected probability.

On this board the model again leans one way: **323 UNDER against 107 OVER** among 430 two-sided markets. Mean RAW_EDGE is +0.1259; after applying the Week-2 family gaps it is +0.0282. The calibration layer removes about 78% of the claimed edge. **Do not rank by RAW_EDGE.**

| confidence label | n |
|---|---|
| `NO_EDGE_AFTER_CALIBRATION` | 122 |
| `HIGH` | 117 |
| `NO_EDGE_COMPUTABLE` | 106 |
| `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 102 |
| `MEDIUM` | 77 |
| `LOW_EDGE_INSIDE_TWO_MCSE` | 12 |

## Strongest supported props (any line type), ranked AFTER calibration

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Yards | 49.5 | UNDER | 0.8234 | 0.1860 | +0.6373 | **+0.5599** | `HIGH` | 0.0043 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 44.5 | UNDER | 0.7814 | 0.1538 | +0.6275 | **+0.5501** | `HIGH` | 0.0046 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 54.5 | UNDER | 0.8562 | 0.2294 | +0.6269 | **+0.5495** | `HIGH` | 0.0039 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 59.5 | UNDER | 0.8841 | 0.2657 | +0.6184 | **+0.5410** | `HIGH` | 0.0036 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 39.5 | UNDER | 0.7298 | 0.1234 | +0.6064 | **+0.5290** | `HIGH` | 0.0050 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 64.5 | UNDER | 0.9069 | 0.3125 | +0.5944 | **+0.5170** | `HIGH` | 0.0032 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 34.5 | UNDER | 0.6666 | 0.0937 | +0.5730 | **+0.4956** | `HIGH` | 0.0053 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 69.5 | UNDER | 0.9270 | 0.3556 | +0.5714 | **+0.4940** | `HIGH` | 0.0029 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 74.5 | UNDER | 0.9416 | 0.4035 | +0.5382 | **+0.4608** | `HIGH` | 0.0026 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 79.5 | UNDER | 0.9550 | 0.4518 | +0.5032 | **+0.4258** | `HIGH` | 0.0023 | rush_allocation |
| Kenneth Walker III | Player Rushing Attempts | 18.5 | UNDER | 0.9851 | 0.4899 | +0.4952 | **+0.3999** | `MEDIUM` | 0.0014 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 84.5 | UNDER | 0.9640 | 0.4899 | +0.4741 | **+0.3967** | `HIGH` | 0.0021 | rush_allocation |
| Kenneth Walker III | Player Rushing + Receiving Yards | 107.5 | UNDER | 0.9534 | 0.5000 | +0.4534 | **+0.3580** | `MEDIUM` | 0.0024 | pass_allocation |
| Kenneth Walker III | Player Rushing Yards | 89.5 | UNDER | 0.9718 | 0.5446 | +0.4272 | **+0.3498** | `HIGH` | 0.0019 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 94.5 | UNDER | 0.9775 | 0.5807 | +0.3968 | **+0.3194** | `HIGH` | 0.0017 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 99.5 | UNDER | 0.9825 | 0.6240 | +0.3585 | **+0.2811** | `HIGH` | 0.0015 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 104.5 | UNDER | 0.9856 | 0.6627 | +0.3230 | **+0.2456** | `HIGH` | 0.0013 | rush_allocation |
| Emmett Johnson | Player Rushing Yards | 7.5 | UNDER | 0.5524 | 0.2458 | +0.3066 | **+0.2292** | `HIGH` | 0.0056 | rush_allocation |

## Strongest MAIN-LINE props

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Attempts | 18.5 | UNDER | 0.9851 | 0.4899 | +0.4952 | **+0.3999** | `MEDIUM` | 0.0014 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 84.5 | UNDER | 0.9640 | 0.4899 | +0.4741 | **+0.3967** | `HIGH` | 0.0021 | rush_allocation |
| Kenneth Walker III | Player Rushing + Receiving Yards | 107.5 | UNDER | 0.9534 | 0.5000 | +0.4534 | **+0.3580** | `MEDIUM` | 0.0024 | pass_allocation |
| Emmett Johnson | Player Rushing + Receiving Yards | 29.5 | UNDER | 0.7889 | 0.5000 | +0.2889 | **+0.1935** | `MEDIUM` | 0.0046 | pass_allocation |
| Emmett Johnson | Player Rushing Yards | 17.5 | UNDER | 0.7612 | 0.5000 | +0.2612 | **+0.1839** | `HIGH` | 0.0048 | rush_allocation |
| Tyler Warren | Player Receptions | 4.5 | UNDER | 0.7015 | 0.4694 | +0.2321 | **+0.1735** | `HIGH` | 0.0051 | pass_allocation |
| Xavier Worthy | Player Receptions | 3.5 | UNDER | 0.7686 | 0.5408 | +0.2278 | **+0.1692** | `HIGH` | 0.0047 | pass_allocation |
| Josh Downs | Player Receptions | 4.5 | UNDER | 0.8099 | 0.5835 | +0.2264 | **+0.1678** | `HIGH` | 0.0044 | pass_allocation |
| Jonathan Taylor | Player Rushing Attempts | 18.5 | UNDER | 0.7409 | 0.4797 | +0.2612 | **+0.1658** | `MEDIUM` | 0.0049 | rush_allocation |
| Jonathan Taylor | Player Rushing + Receiving Yards | 102.5 | UNDER | 0.7508 | 0.5000 | +0.2507 | **+0.1554** | `MEDIUM` | 0.0048 | pass_allocation |
| Jonathan Taylor | Player Rushing Yards | 80.5 | UNDER | 0.7310 | 0.5000 | +0.2310 | **+0.1536** | `HIGH` | 0.0050 | rush_allocation |
| Kenneth Walker III | Player Receptions | 3.5 | UNDER | 0.8029 | 0.5915 | +0.2113 | **+0.1527** | `HIGH` | 0.0044 | pass_allocation |

## Strongest ALTERNATE-LINE props

Alternate lines are kept strictly separate from main lines. They are the same opinion about a player expressed at a different threshold, so they are not additional evidence.

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Yards | 49.5 | UNDER | 0.8234 | 0.1860 | +0.6373 | **+0.5599** | `HIGH` | 0.0043 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 44.5 | UNDER | 0.7814 | 0.1538 | +0.6275 | **+0.5501** | `HIGH` | 0.0046 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 54.5 | UNDER | 0.8562 | 0.2294 | +0.6269 | **+0.5495** | `HIGH` | 0.0039 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 59.5 | UNDER | 0.8841 | 0.2657 | +0.6184 | **+0.5410** | `HIGH` | 0.0036 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 39.5 | UNDER | 0.7298 | 0.1234 | +0.6064 | **+0.5290** | `HIGH` | 0.0050 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 64.5 | UNDER | 0.9069 | 0.3125 | +0.5944 | **+0.5170** | `HIGH` | 0.0032 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 34.5 | UNDER | 0.6666 | 0.0937 | +0.5730 | **+0.4956** | `HIGH` | 0.0053 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 69.5 | UNDER | 0.9270 | 0.3556 | +0.5714 | **+0.4940** | `HIGH` | 0.0029 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 74.5 | UNDER | 0.9416 | 0.4035 | +0.5382 | **+0.4608** | `HIGH` | 0.0026 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 79.5 | UNDER | 0.9550 | 0.4518 | +0.5032 | **+0.4258** | `HIGH` | 0.0023 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 89.5 | UNDER | 0.9718 | 0.5446 | +0.4272 | **+0.3498** | `HIGH` | 0.0019 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 94.5 | UNDER | 0.9775 | 0.5807 | +0.3968 | **+0.3194** | `HIGH` | 0.0017 | rush_allocation |

## Avoid despite a large RAW_EDGE

These carry the biggest raw numbers on the board and do not survive the Week-2 correction. Last week these are exactly the rows that lost.

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Xavier Worthy | Player Receiving Yards | 78.5 | UNDER | 0.9473 | 0.8388 | +0.1085 | **-0.0002** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0025 | pass_allocation |
| Xavier Worthy | Player Receiving Yards | 79.5 | UNDER | 0.9507 | 0.8451 | +0.1057 | **-0.0030** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0024 | pass_allocation |
| Alec Pierce | Player Receiving Yards | 53.5 | UNDER | 0.6966 | 0.5912 | +0.1054 | **-0.0033** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0051 | pass_allocation |
| Jonathan Taylor | Player Receiving Yards | 36.5 | UNDER | 0.8728 | 0.7692 | +0.1035 | **-0.0052** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0037 | pass_allocation |
| Emmett Johnson | Player Receiving Yards | 22.5 | UNDER | 0.9079 | 0.8046 | +0.1033 | **-0.0054** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0032 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 64.5 | OVER | 0.4366 | 0.3349 | +0.1017 | **-0.0070** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0055 | pass_allocation |
| Tyler Warren | Player Receiving Yards | 63.5 | UNDER | 0.8286 | 0.7286 | +0.1001 | **-0.0086** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0042 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 68.5 | OVER | 0.4007 | 0.3008 | +0.1000 | **-0.0087** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0055 | pass_allocation |
| Alec Pierce | Player Receiving Yards | 3.5 | UNDER | 0.1923 | 0.0930 | +0.0993 | **-0.0094** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0044 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 63.5 | OVER | 0.4432 | 0.3441 | +0.0991 | **-0.0096** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0056 | pass_allocation |
| Josh Downs | Player Receiving Yards | 76.5 | UNDER | 0.9300 | 0.8311 | +0.0989 | **-0.0098** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0029 | pass_allocation |
| Kenneth Walker III | Player Receiving Yards | 35.5 | UNDER | 0.8665 | 0.7677 | +0.0988 | **-0.0099** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0038 | pass_allocation |
| Tyquan Thornton | Player Receiving Yards | 49.5 | UNDER | 0.9305 | 0.8319 | +0.0986 | **-0.0101** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0028 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 53.5 | OVER | 0.5410 | 0.4425 | +0.0985 | **-0.0102** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0056 | pass_allocation |
| Tyler Warren | Player Receiving Yards | 64.5 | UNDER | 0.8349 | 0.7368 | +0.0980 | **-0.0107** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0042 | pass_allocation |

## Correlated signals — one opinion counted once

Markets sharing a player, or sharing a team allocation mechanism, move together. Treating them as independent is how a single role error becomes a whole portfolio.

| group | markets on the board | in the shortlist |
|---|---|---|
| KC:Patrick Mahomes | 52 | 3 |
| IND:Daniel Jones | 49 | 29 |
| IND:Jonathan Taylor | 47 | 35 |
| KC:Kenneth Walker III | 40 | 32 |
| KC:Emmett Johnson | 30 | 18 |
| IND:Alec Pierce | 26 | 11 |
| KC:Rashee Rice | 26 | 1 |
| IND:Josh Downs | 25 | 19 |
| KC:Travis Kelce | 25 | 0 |
| IND:Tyler Warren | 25 | 12 |
| KC:Xavier Worthy | 25 | 20 |
| IND:Keenan Allen | 23 | 1 |
| KC:Tyquan Thornton | 20 | 12 |
| KC:Noah Gray | 15 | 1 |

| allocation mechanism | shortlisted markets |
|---|---|
| IND:pass_allocation | 51 |
| KC:pass_allocation | 49 |
| IND:rush_allocation | 36 |
| KC:rush_allocation | 35 |
| IND:qb_aggregate | 20 |
| KC:qb_aggregate | 3 |

## Refused rather than approximated

| reason | n |
|---|---|
| `NOT_A_PLAYER_PROP` | 307 |
| `UNSUPPORTED` | 13 |
| `UNSUPPORTED_MARKET` | 14 |

Every probability above is counted from the frozen draws: the fraction of the 8,000 simulated games in which the quantity beat the line. No normal approximation is used anywhere, and a market whose settling quantity is not in the sealed artifact is refused by name.

## When inactives land

Capture a second Hard Rock board and re-evaluate **these same frozen draws** at the new lines. The football projection is not rerun because a price moved. The comparison will report line movement, price movement, new and removed markets, and whether movement ran toward or away from the model.

V2 NOT YET EARNED.

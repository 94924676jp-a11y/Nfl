# IND@KC — model vs Hard Rock — POSTINACTIVES_CURRENT

Board `f6e4b8e611cb085d…` captured 2026-09-20T22:52:14Z–2026-09-20T22:52:16Z · 870 rows (75 main, 795 alternate)

Model run `12eda64603a377d7` · 8,000 draws · cut `2026-09-20T23:05:00Z` · CANDIDATE_NOT_ACCEPTED_BASELINE · inactive gate **0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD**

DOWNSTREAM_COMPARISON_ONLY. No line, price, spread, total or implied probability entered the football model. The draws were frozen before this file was opened.

## Read this before ranking anything

Week-2 grading measured a mean predicted probability of -0.0953 gap between what the model said and what happened, over 263 graded markets across 7 games. one slate, heavily overlapping markets, wide game-clustered standard errors. A shrink toward the book, not a corrected probability.

On this board the model again leans one way: **318 UNDER against 112 OVER** among 430 two-sided markets. Mean RAW_EDGE is +0.1221; after applying the Week-2 family gaps it is +0.0246. The calibration layer removes about 80% of the claimed edge. **Do not rank by RAW_EDGE.**

| confidence label | n |
|---|---|
| `NO_EDGE_AFTER_CALIBRATION` | 123 |
| `HIGH` | 112 |
| `NO_EDGE_COMPUTABLE` | 106 |
| `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 99 |
| `MEDIUM` | 76 |
| `LOW_EDGE_INSIDE_TWO_MCSE` | 20 |

## Strongest supported props (any line type), ranked AFTER calibration

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Yards | 49.5 | UNDER | 0.8257 | 0.1860 | +0.6397 | **+0.5623** | `HIGH` | 0.0042 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 54.5 | UNDER | 0.8609 | 0.2294 | +0.6315 | **+0.5541** | `HIGH` | 0.0039 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 44.5 | UNDER | 0.7759 | 0.1538 | +0.6220 | **+0.5446** | `HIGH` | 0.0047 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 59.5 | UNDER | 0.8869 | 0.2657 | +0.6211 | **+0.5437** | `HIGH` | 0.0035 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 39.5 | UNDER | 0.7255 | 0.1234 | +0.6021 | **+0.5247** | `HIGH` | 0.0050 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 64.5 | UNDER | 0.9120 | 0.3125 | +0.5995 | **+0.5221** | `HIGH` | 0.0032 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 69.5 | UNDER | 0.9293 | 0.3556 | +0.5736 | **+0.4962** | `HIGH` | 0.0029 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 34.5 | UNDER | 0.6667 | 0.0937 | +0.5731 | **+0.4957** | `HIGH` | 0.0053 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 74.5 | UNDER | 0.9453 | 0.4035 | +0.5418 | **+0.4644** | `HIGH` | 0.0025 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 79.5 | UNDER | 0.9564 | 0.4518 | +0.5046 | **+0.4272** | `HIGH` | 0.0023 | rush_allocation |
| Kenneth Walker III | Player Rushing Attempts | 18.5 | UNDER | 0.9870 | 0.4899 | +0.4971 | **+0.4018** | `MEDIUM` | 0.0013 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 84.5 | UNDER | 0.9666 | 0.4899 | +0.4767 | **+0.3993** | `HIGH` | 0.0020 | rush_allocation |
| Kenneth Walker III | Player Rushing + Receiving Yards | 107.5 | UNDER | 0.9555 | 0.5000 | +0.4555 | **+0.3602** | `MEDIUM` | 0.0023 | pass_allocation |
| Kenneth Walker III | Player Rushing Yards | 89.5 | UNDER | 0.9751 | 0.5446 | +0.4305 | **+0.3531** | `HIGH` | 0.0017 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 94.5 | UNDER | 0.9804 | 0.5807 | +0.3996 | **+0.3222** | `HIGH` | 0.0016 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 99.5 | UNDER | 0.9854 | 0.6240 | +0.3614 | **+0.2840** | `HIGH` | 0.0013 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 104.5 | UNDER | 0.9879 | 0.6627 | +0.3252 | **+0.2478** | `HIGH` | 0.0012 | rush_allocation |
| Emmett Johnson | Player Rushing Yards | 7.5 | UNDER | 0.5509 | 0.2458 | +0.3051 | **+0.2277** | `HIGH` | 0.0056 | rush_allocation |

## Strongest MAIN-LINE props

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Attempts | 18.5 | UNDER | 0.9870 | 0.4899 | +0.4971 | **+0.4018** | `MEDIUM` | 0.0013 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 84.5 | UNDER | 0.9666 | 0.4899 | +0.4767 | **+0.3993** | `HIGH` | 0.0020 | rush_allocation |
| Kenneth Walker III | Player Rushing + Receiving Yards | 107.5 | UNDER | 0.9555 | 0.5000 | +0.4555 | **+0.3602** | `MEDIUM` | 0.0023 | pass_allocation |
| Emmett Johnson | Player Rushing + Receiving Yards | 29.5 | UNDER | 0.7857 | 0.5000 | +0.2858 | **+0.1904** | `MEDIUM` | 0.0046 | pass_allocation |
| Emmett Johnson | Player Rushing Yards | 17.5 | UNDER | 0.7652 | 0.5000 | +0.2652 | **+0.1878** | `HIGH` | 0.0047 | rush_allocation |
| Xavier Worthy | Player Receptions | 3.5 | UNDER | 0.7631 | 0.5408 | +0.2223 | **+0.1637** | `HIGH` | 0.0048 | pass_allocation |
| Josh Downs | Player Receptions | 4.5 | UNDER | 0.8027 | 0.5835 | +0.2193 | **+0.1607** | `HIGH` | 0.0044 | pass_allocation |
| Kenneth Walker III | Player Receptions | 3.5 | UNDER | 0.8076 | 0.5915 | +0.2161 | **+0.1575** | `HIGH` | 0.0044 | pass_allocation |
| Tyler Warren | Player Receptions | 4.5 | UNDER | 0.6853 | 0.4694 | +0.2159 | **+0.1573** | `HIGH` | 0.0052 | pass_allocation |
| Alec Pierce | Player Receptions | 2.5 | UNDER | 0.6331 | 0.4367 | +0.1964 | **+0.1378** | `HIGH` | 0.0054 | pass_allocation |
| Xavier Worthy | Player Receiving Yards | 38.5 | UNDER | 0.7359 | 0.4899 | +0.2460 | **+0.1373** | `HIGH` | 0.0049 | pass_allocation |
| Kenneth Walker III | Player Receiving Yards | 20.5 | UNDER | 0.7320 | 0.4899 | +0.2421 | **+0.1334** | `HIGH` | 0.0050 | pass_allocation |

## Strongest ALTERNATE-LINE props

Alternate lines are kept strictly separate from main lines. They are the same opinion about a player expressed at a different threshold, so they are not additional evidence.

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Kenneth Walker III | Player Rushing Yards | 49.5 | UNDER | 0.8257 | 0.1860 | +0.6397 | **+0.5623** | `HIGH` | 0.0042 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 54.5 | UNDER | 0.8609 | 0.2294 | +0.6315 | **+0.5541** | `HIGH` | 0.0039 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 44.5 | UNDER | 0.7759 | 0.1538 | +0.6220 | **+0.5446** | `HIGH` | 0.0047 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 59.5 | UNDER | 0.8869 | 0.2657 | +0.6211 | **+0.5437** | `HIGH` | 0.0035 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 39.5 | UNDER | 0.7255 | 0.1234 | +0.6021 | **+0.5247** | `HIGH` | 0.0050 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 64.5 | UNDER | 0.9120 | 0.3125 | +0.5995 | **+0.5221** | `HIGH` | 0.0032 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 69.5 | UNDER | 0.9293 | 0.3556 | +0.5736 | **+0.4962** | `HIGH` | 0.0029 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 34.5 | UNDER | 0.6667 | 0.0937 | +0.5731 | **+0.4957** | `HIGH` | 0.0053 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 74.5 | UNDER | 0.9453 | 0.4035 | +0.5418 | **+0.4644** | `HIGH` | 0.0025 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 79.5 | UNDER | 0.9564 | 0.4518 | +0.5046 | **+0.4272** | `HIGH` | 0.0023 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 89.5 | UNDER | 0.9751 | 0.5446 | +0.4305 | **+0.3531** | `HIGH` | 0.0017 | rush_allocation |
| Kenneth Walker III | Player Rushing Yards | 94.5 | UNDER | 0.9804 | 0.5807 | +0.3996 | **+0.3222** | `HIGH` | 0.0016 | rush_allocation |

## Avoid despite a large RAW_EDGE

These carry the biggest raw numbers on the board and do not survive the Week-2 correction. Last week these are exactly the rows that lost.

| player | market | line | side | model p | no-vig p | RAW_EDGE | ADJ_EDGE | conf | MCSE | mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| Tyler Warren | Player Receiving Yards | 53.5 | UNDER | 0.7374 | 0.6287 | +0.1086 | **-0.0001** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0049 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 63.5 | OVER | 0.4526 | 0.3441 | +0.1085 | **-0.0002** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0056 | pass_allocation |
| Tyquan Thornton | Player Receiving Yards | 45.5 | UNDER | 0.9144 | 0.8061 | +0.1083 | **-0.0004** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0031 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 53.5 | OVER | 0.5506 | 0.4425 | +0.1081 | **-0.0006** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0056 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 49.5 | OVER | 0.5934 | 0.4853 | +0.1081 | **-0.0006** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0055 | pass_allocation |
| Tyler Warren | Player Receiving Yards | 58.5 | UNDER | 0.7873 | 0.6802 | +0.1071 | **-0.0016** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0046 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 58.5 | OVER | 0.5008 | 0.3938 | +0.1070 | **-0.0017** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0056 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 73.5 | OVER | 0.3700 | 0.2632 | +0.1068 | **-0.0019** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0054 | pass_allocation |
| Alec Pierce | Player Receiving Yards | 53.5 | UNDER | 0.6973 | 0.5912 | +0.1060 | **-0.0027** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0051 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 79.5 | OVER | 0.3237 | 0.2188 | +0.1049 | **-0.0038** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0052 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 48.5 | OVER | 0.6029 | 0.5000 | +0.1029 | **-0.0058** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0055 | pass_allocation |
| Jonathan Taylor | Player Receiving Yards | 36.5 | UNDER | 0.8708 | 0.7692 | +0.1015 | **-0.0072** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0038 | pass_allocation |
| Rashee Rice | Player Receiving Yards | 78.5 | OVER | 0.3320 | 0.2308 | +0.1012 | **-0.0075** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0053 | pass_allocation |
| Emmett Johnson | Player Receiving Yards | 22.5 | UNDER | 0.9058 | 0.8046 | +0.1012 | **-0.0075** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0033 | pass_allocation |
| Xavier Worthy | Player Receiving Yards | 78.5 | UNDER | 0.9393 | 0.8388 | +0.1005 | **-0.0082** | `AVOID_EDGE_DOES_NOT_SURVIVE_WEEK2_CALIBRATION` | 0.0027 | pass_allocation |

## Correlated signals — one opinion counted once

Markets sharing a player, or sharing a team allocation mechanism, move together. Treating them as independent is how a single role error becomes a whole portfolio.

| group | markets on the board | in the shortlist |
|---|---|---|
| KC:Patrick Mahomes | 52 | 6 |
| IND:Daniel Jones | 49 | 26 |
| IND:Jonathan Taylor | 47 | 35 |
| KC:Kenneth Walker III | 40 | 32 |
| KC:Emmett Johnson | 30 | 18 |
| IND:Alec Pierce | 26 | 11 |
| KC:Rashee Rice | 26 | 1 |
| IND:Josh Downs | 25 | 18 |
| KC:Travis Kelce | 25 | 0 |
| IND:Tyler Warren | 25 | 8 |
| KC:Xavier Worthy | 25 | 19 |
| IND:Keenan Allen | 23 | 1 |
| KC:Tyquan Thornton | 20 | 12 |
| KC:Noah Gray | 15 | 1 |

| allocation mechanism | shortlisted markets |
|---|---|
| KC:pass_allocation | 48 |
| IND:pass_allocation | 46 |
| IND:rush_allocation | 36 |
| KC:rush_allocation | 35 |
| IND:qb_aggregate | 17 |
| KC:qb_aggregate | 6 |

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

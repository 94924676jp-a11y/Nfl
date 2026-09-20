# Week 2 — prop calibration

Graded prop markets: **263** over **7** games; pushes: 0.

CANDIDATE_NOT_ACCEPTED_BASELINE. The board graded here is `V1_CANDIDATE_R9_W1P_GSVUCY`, authorised for one slate and never promoted. The runs stopped at `artifact_sealing`, so the board is UNSEALED. No production model, coefficient or candidate identity was changed by this analysis. V2 NOT YET EARNED.

## Headline

| statistic | model | book (no-vig) |
|---|---|---|
| Brier | **0.249412** | 0.246738 |
| log loss | **0.691724** | 0.686519 |

| mean predicted probability | **0.6315** |
|---|---|
| realised hit rate | **0.5361** |
| naive SE | 0.0308 |
| SE clustered by game | **0.0419** |
| SE inflation from clustering | 1.359× |
| side counts | {'OVER': 60, 'UNDER': 203} |

OBSERVED: the model said 0.631 and reality delivered 0.536 — a gap of **-0.0953** against a game-clustered SE of 0.0419. Clustering inflates the SE by 1.36×; quoting the naive SE would have overstated the precision of this statement.

OBSERVED: the book beat the model on BOTH proper scores — lower Brier and lower log loss. On this slate the model's prop probabilities were worse than the de-vigged market.

## Calibration curve by predicted-probability bucket

| bucket | n | mean predicted | realised | gap | SE clustered | clusters |
|---|---|---|---|---|---|---|
| 0.50-0.55 | 44 | 0.5281 | 0.4545 | **-0.0735** | 0.0420 | 7 |
| 0.55-0.60 | 50 | 0.5749 | 0.5600 | **-0.0149** | 0.0747 | 7 |
| 0.60-0.65 | 49 | 0.6244 | 0.5714 | **-0.0530** | 0.0771 | 7 |
| 0.65-0.70 | 42 | 0.6729 | 0.4762 | **-0.1967** | 0.0515 | 6 |
| 0.70-0.75 | 25 | 0.7241 | 0.4800 | **-0.2441** | 0.1011 | 6 |
| 0.75-0.80 | 18 | 0.7699 | 0.6111 | **-0.1588** | 0.1040 | 6 |
| 0.80-1.01 | 19 | 0.8441 | 0.8947 | **+0.0506** | 0.0767 | 5 |

## By market family

| market | n | mean predicted | realised | gap | SE clustered | mean raw edge | Brier |
|---|---|---|---|---|---|---|---|
| Player Receiving Yards | 62 | 0.6571 | 0.5484 | **-0.1087** | 0.0758 | 0.1569 | 0.2748 |
| Player Receptions | 60 | 0.6586 | 0.6000 | **-0.0586** | 0.0927 | 0.1681 | 0.2361 |
| Player Rushing Yards | 34 | 0.6362 | 0.5588 | **-0.0774** | 0.0675 | 0.1392 | 0.2321 |
| Player Rushing + Receiving Yards | 18 | 0.6454 | 0.5556 | **-0.0898** | 0.1221 | 0.1459 | 0.2410 |
| Player Rushing Attempts | 16 | 0.6737 | 0.6250 | **-0.0487** | 0.0847 | 0.1814 | 0.2242 |
| Player Passing Attempts | 13 | 0.5816 | 0.4615 | **-0.1201** | 0.1713 | 0.0824 | 0.2312 |
| Player Field Goals Made | 12 | 0.5169 | 0.3333 | **-0.1835** | 0.1588 | 0.0358 | 0.2547 |
| Player Interceptions | 12 | 0.5667 | 0.6667 | **+0.1000** | 0.1588 | 0.0711 | 0.2590 |
| Player Passing Completions | 12 | 0.5927 | 0.4167 | **-0.1760** | 0.1419 | 0.0952 | 0.2818 |
| Player Passing Touchdowns | 12 | 0.5706 | 0.4167 | **-0.1540** | 0.1419 | 0.0905 | 0.2199 |
| Player Passing Yards | 12 | 0.6057 | 0.3333 | **-0.2724** | 0.0949 | 0.1057 | 0.2817 |

## Raw edge against realised outcome

| half | n | mean edge | hit rate |
|---|---|---|---|
| low edge | 131 | 0.0594 | 0.5115 |
| high edge | 132 | 0.2132 | 0.5606 |

INFERRED: bigger claimed edge went with a higher hit rate, which is weak evidence that the edge ordering carries some signal even though its LEVEL is badly overstated. Two halves over seven games is not a test; it is a direction.

## Closing-line movement

The board carries the 04:52Z → 16:35Z movement for every market, but 16:35Z IS the frozen comparison snapshot and no later capture was taken. So no closing-line value can be computed for Week 2. A genuine CLV column needs a capture at or near kickoff.

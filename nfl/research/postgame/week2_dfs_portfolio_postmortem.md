# Week 2 — DFS postmortem

CANDIDATE_NOT_ACCEPTED_BASELINE. The board graded here is `V1_CANDIDATE_R9_W1P_GSVUCY`, authorised for one slate and never promoted. The runs stopped at `artifact_sealing`, so the board is UNSEALED. No production model, coefficient or candidate identity was changed by this analysis. V2 NOT YET EARNED.

## What this report CANNOT answer, and why

The lineup-level half of this postmortem is **not computable from anything in this repository.** The 73 DraftKings entries were constructed downstream and were never written here — this session was explicitly instructed not to generate them. Without the submitted lineup set there is no stack structure, no bring-back structure, no salary used, no overlap, no player or game exposure, and therefore no way to separate construction error from projection error.

To make the portfolio half of this report real, supply one file: the submitted entry set with, per lineup, the eight roster slots by DraftKings player id and the contest it was entered in. Everything else on the list — actual DK points per lineup, projected mean, ceiling proxy, stack and bring-back structure, salary used, overlap, exposures — is then derivable from the canonical dataset already written.

ABSENT IS NOT ZERO. No portfolio number is estimated, and none of the player-level results below should be read as a lineup result.

## What IS answerable: the player layer the lineups were built from

| statistic | value |
|---|---|
| graded players | 133 |
| DK mean bias (actual − projected) | **-0.1088** |
| MAE | 3.5994 |
| RMSE | 4.8214 |
| Pearson r | **0.6927** |
| SD ratio projected/actual | 0.8039 |

- projected p50: realised at or below **0.4511** against a nominal 0.50 (n=133)
- projected p90: realised at or below **0.9323** against a nominal 0.90 (n=133)
- projected p95: realised at or below **0.9549** against a nominal 0.95 (n=133)

OBSERVED: the ceiling proxies were not too thin. The p90 and p95 both contained MORE of the realised outcomes than nominal, which is the opposite of the failure mode a GPP player fears.

INFERRED: on this slate the player-level DK projections were the stronger part of the system and the prop probabilities were the weaker part. Since the lineups were built from DK projections rather than from prop probabilities, a portfolio postmortem is more likely to find construction and variance effects than a projection collapse — but that is a statement about where to look, not a result.

HYPOTHESIS: one slate of seven games cannot separate construction, exposure concentration and variance. That separation needs the entry set plus several slates.

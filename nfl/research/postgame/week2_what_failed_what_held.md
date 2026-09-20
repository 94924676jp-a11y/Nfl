# Week 2 — WHAT FAILED, WHAT HELD, WHAT WE SHOULD TEST NEXT

Seven graded games (CAR_ATL, CIN_HOU, GB_NYJ, MIN_CHI, NO_BAL, PHI_TEN, PIT_NE). Not published: CLE_TB

CANDIDATE_NOT_ACCEPTED_BASELINE. Board unsealed. No production change was made by this analysis. V2 NOT YET EARNED.

## WHAT FAILED

**1. The prop probabilities were overconfident, and the book beat them on both proper scores.** OBSERVED: mean predicted 0.6315 against a realised 0.5361, a gap of -0.0953 with a game-clustered SE of 0.0419 — roughly 2.3 SE. Brier 0.249412 against the book's 0.246738; log loss 0.691724 against 0.686519. Both favour the market.

**2. The pregame UNDER lean was real and it was wrong.** OBSERVED: {'OVER': 60, 'UNDER': 203} by side. The model's preferred side was UNDER on the large majority of markets and the passing-game volume quantities all came in ABOVE projection: targets +0.530 (SE 0.245), receptions +0.315 (SE 0.169), pass attempts +2.407 (SE 1.551).

**3. Target allocation was too diffuse.** OBSERVED: mean target-share concentration (HHI) was 0.1588 projected against 0.1889 realised, a difference of +0.0301 with SE 0.0133 over 11 teams (t = 2.26). Real offences concentrated targets more than the model did.

**4. Two skill-position coverage failures, and I under-reported them at delivery.** OBSERVED: `2026_02_PHI_TEN` emitted NO `receiving`, `rushing`, `rush_category`, `rush_player_pool` or `gadget_rush` layer at all — six rows total, four quarterbacks and two kickers — while its run reported PASS on appearance, participation, targets_carries, conversion and td_layer. A stage reporting success while emitting nothing is precisely the defect class this project treats as its most expensive. OBSERVED: in `2026_02_MIN_CHI` every CHI skill player carries only `gadget_rush` keys and no `receiving` row, while MIN players carry both — a one-sided failure inside a game that otherwise looks complete.

The package DISCLOSED this correctly: `audits.position_support_per_game["2026_02_PHI_TEN"]` reads `RB 0, TE 0, WR 0`. I did not read that section when I delivered the seven- and eight-game boards and reported only row totals, so a board with no skill players for one game went downstream described as complete. The artifact was honest; the delivery note was not. Any slate-wide aggregate over these games is wrong unless it excludes them, and every number in this package does.

## WHAT HELD

**1. The DK point projections were close to unbiased and discriminated well.** OBSERVED: mean bias -0.1088 DK points against a game-clustered SE of 0.3697 — inside one SE. Pearson r = 0.6927, MAE 3.5994, RMSE 4.8214. No equivalence margin was predeclared, so this is a failure to detect bias, not a demonstration of its absence.

**2. The DK distributions were not too narrow.** OBSERVED: p50 covered 0.4511 against a nominal 0.50; p90 covered 0.9323 against a nominal 0.90; p95 covered 0.9549 against a nominal 0.95. The tails contained more than nominal, not less.

**3. The edge ORDERING carried some signal even though its LEVEL did not.** OBSERVED: the low-edge half hit 0.5115 and the high-edge half 0.5606. INFERRED: direction, not a test — two halves over seven games.

**4. Every governance gate behaved.** OBSERVED: the inactive gate was certified on real evidence, the DFS and prop views were proven to share one set of draws, and the unsealed board was labelled as such in every artifact.

## THE CENTRAL READING, AND WHAT IT IS NOT

INFERRED: the DK mean was nearly unbiased while the prop probabilities were badly overconfident toward UNDER. Those two facts are compatible and together they locate the problem: the central tendency of total fantasy production was about right, while the PER-QUANTITY distributions used to price a line were shifted low on passing volume and spread too evenly across receivers. A DK point total can be right while the receptions and receiving-yards distributions that compose it are both wrong.

NOT A CONCLUSION: this is one slate of seven games, the markets are heavily overlapping, and the clustered SEs are wide. Nothing here identifies a coefficient to change. The correlated misses are ONE bias observed many times, and counting them as 263 independent results would be the error this project keeps finding in its own history.

## WHAT WE SHOULD TEST NEXT

**H1 — target concentration.** HYPOTHESIS: the allocation layer spreads targets too evenly, and a concentration parameter fitted out of sample would raise both prop calibration and discrimination. Test: forward-chained, fit on weeks before the evaluation week, score with Brier and log loss on held-out weeks. This is the best-identified finding here (t ≈ 2.26) and should be first.

**H2 — team pass volume.** HYPOTHESIS: projected team targets sit below realised. OBSERVED support is weaker: projected/actual 0.8319 (16.8% short) with a per-team ratio of 0.8810 ± 0.0688 over 11 teams. Test it separately from H1; they are confounded in this slate.

**H3 — the coverage hole.** Not a hypothesis, a defect. Find why CHI, PHI and TEN emitted no receiving layer and fix it before any further calibration work, because it silently removes teams from every aggregate.

**H4 — passing touchdowns.** OBSERVED: bias -0.337 (SE 0.189) — the model projected MORE passing TDs than happened while projecting FEWER pass attempts. HYPOTHESIS: the conversion layer compensates for low volume with high per-attempt scoring. Worth a decomposition.

**H5 — closing line value.** Not computable for Week 2: the 16:35Z board IS the frozen comparison and no later snapshot exists. Capture a near-kickoff board next week so CLV becomes measurable.

**H6 — injury-distorted filtering.** The OUTCOME_INTERPRETATION field and its filter exist and every Week-2 row reads NORMAL with the basis stated, because snap counts cover only 2026_02_DET_BUF. Ingest the participation feed so a prop that won on an early exit stops counting the same as one that won on a full workload.

## Reproducing any number here

Canonical dataset: `nfl/research/postgame/week2_postgame_grading.csv` (520 rows) and the same rows as JSONL. pyarrow is not installed in this environment, so the canonical dataset is emitted as CSV and JSONL. Same rows, same columns.

Realised outcomes come from a preserved, read-only snapshot pinned by sha256 in `nfl/postgame/actuals.py`; a regrade on different bytes is refused by name rather than silently producing a different grade.

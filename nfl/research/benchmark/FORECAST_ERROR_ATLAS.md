# FORECAST_ERROR_ATLAS (mandate b0540a52, phase 2). Development season 2024 only.

**Record.** `FORECAST_ERROR_ATLAS.json`, produced by `error_atlas.py`.

**Settings.** Production settings in the forward chain: STRICT vintage, appearance applied, D1 off, no injury news.
Neither side sees news. Cohorts are fixed at the cutoff: the allocation pool and its projection. Conditional components
are labelled as conditional. 2025 is not read.

## 1. Appearance: the largest single error, and it is a definition error

On 5,637 pool rows, 60.4% of players appeared.

| forecast of P(appears) | Brier | log loss (clip 0.01) |
|---|---|---|
| incumbent `p_plays` | **0.372** | 1.689 |
| constant in-sample base rate (reference) | 0.239 | — |
| naive: the player's appearance rate in his club's games before W | **0.196** | 0.641 |

**What the incumbent forecasts.** `p_plays` is exactly 1.0 for **93.4%** of pool rows. In nine forecast deciles out of
ten it is 1.0, while the observed rate in those deciles is 0.58–0.68. The incumbent is worse than a constant at every
position:

| position | incumbent Brier | naive Brier |
|---|---|---|
| QB | 0.272 | 0.204 |
| RB | 0.373 | 0.201 |
| WR | 0.393 | 0.183 |
| TE | 0.399 | 0.208 |

**Cause, read from code.**
- `proj_v1.depth_shares` computes `appearance_rate` per depth rank as the share of club-weeks in which a club had **at
  least k** players with volume at that position. Ranks come from realised volume order.
- That is a *slot occupancy* rate.
- `allocate_opportunity` gives that rate to the player *predicted* at rank k as **his own** P(plays).
- The two coincide only when the predicted rank-k player is always the one who fills slot k. Without news, he often is
  not. A club almost always fields five wide receivers, so slot 5 is about 1.0 even when the predicted WR2 is injured.

**What the error costs (diagnostic, split on the outcome).** Players who did not appear carry **30.1%** of the total
unconditional absolute error, with a mean projection of 4.0 DK points each.

**Link to the headline.** In `PLAYER_SCORECARD.json` (2024–25 pooled), the incumbent trails the naive baseline by
**+0.70** DK MAE unconditionally but only **+0.14** conditionally. The gap between those two figures is the appearance
channel.

## 2. Team volume is right; the split between players is not

| club-week field (416 club-weeks) | projected / actual | MAE |
|---|---|---|
| targets | 0.988 | 5.7 |
| carries | 1.001 | 5.8 |
| pass attempts | 0.991 | 6.1 |

**Target share, given play.**

| cohort | projected share / actual share |
|---|---|
| top-decile WR | 1.22 |
| top-decile TE | 1.21 (n = 8) |
| top-decile RB | 1.34 |
| all WR who played | 0.72 |
| all TE who played | 0.90 |
| all RB who played | 0.87 |

**Reading.** Club totals are preserved by construction. Volume flows to two places it should not:
- to pool players who will not play (section 1);
- to the top claimant.

Players who do play, other than the top claimant, are short. D1 addressed only the second channel.

## 3. Efficiency given play is close

| position | catch rate | yards per target | yards per carry | rec TD per target |
|---|---|---|---|---|
| WR | 0.649 / 0.636 | 8.19 / 8.08 | — | 0.052 / 0.055 |
| TE | 0.724 / 0.727 | 7.53 / 7.46 | — | — |
| RB | 0.811 / 0.796 | 6.14 / 5.96 | 4.50 / 4.49 | — |
| QB | — | — | 4.61 / 4.81 | — |

Each cell is projected / actual.

- **QB passing:** 6.73 / 6.75 yards per attempt; 0.045 / 0.045 TD per attempt.
- **Small cells:** WR rushing efficiency is off (3.8 / 5.0 yards per carry; 0.055 / 0.017 TD per carry), but on few
  carries.

**Conclusion.** Efficiency is not where the error is.

## 4. Cold start

| cohort | n | MAE | bias |
|---|---|---|---|
| fewer than 2 prior appearances | 553 | 1.83 | +0.17 |
| established | 5,084 | 5.64 | +0.37 |

Cold start is not a material error source in 2024.

## 5. Cases

The 20 largest top-decile receiver over-projections given play are listed in the JSON. Kupp W15, Reed W7, Lamb W13,
Samuel W5 and McBride W16 are 4–8 targets short of their projection, with `p_plays` = 1.0 each.

## Not decomposable here

- **Routes and snaps:** no sourced per-game participation for 2024.
- **Air yards and red zone:** present in the panel, not yet decomposed.
- **Pregame injury news:** withheld (RES-010).

## Consequence for the challenger order

Opportunity first (OD-003 repair order), and within opportunity, **appearance before share**. D2 is pre-registered
on that basis.

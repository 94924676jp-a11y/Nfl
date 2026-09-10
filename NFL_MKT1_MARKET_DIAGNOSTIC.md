# MKT1 — model versus external market, SF @ LA

**Diagnostic only. V1 unchanged; all 18 frozen production hashes identical.**
No price was used as a label, a target or a fit input. The market is evidence
that two estimates differ, not the truth against which either is scored.

Forecast `e3e2bc8a1f043abf`, draw digest `7f322318d10c55e1…`, SHADOW / NOT
AUTHORIZED. Snapshot: 161 rows, seven books, 23 player-markets.

This lives in `nfl/research/mkt1/`, never `nfl/product/`. The product layer has
a tested boundary that no sportsbook number may cross, and it is worth more
than the convenience of putting the two side by side.

## 1. Complete comparison

19 of 23 markets comparable. De-vig is proportional where both sides came from
the same book at the same line; it flatters the favourite slightly, and that
residual is smaller than every gap below bar one.

| player | market | line | model mean ± sd | P(model) | P(market, fair) | gap |
|---|---|--:|---|--:|--:|--:|
| McCaffrey | Carries | 15.5 | 7.29 ± 3.59 | 0.033 | 0.506 | **−47.3** |
| K. Williams | Carries | 13.5 | 6.68 ± 3.52 | 0.033 | 0.458 | **−42.5** |
| McCaffrey | Receptions | 4.5 | 2.56 ± 1.77 | 0.133 | 0.525 | **−39.2** |
| Nacua | Receptions | 7.5 | 3.56 ± 2.29 | 0.053 | 0.441 | **−38.8** |
| Nacua | Receiving yds | 90.5 | 46.95 ± 36.23 | 0.124 | 0.500 | **−37.6** |
| McCaffrey | Receiving yds | 39.5 | 21.86 ± 19.19 | 0.156 | 0.505 | −34.9 |
| K. Williams | Receptions | 1.5 | 1.06 ± 1.32 | 0.297 | 0.569 | −27.1 |
| Purdy | Rushing yds | 18.5 | 11.86 ± 13.49 | 0.239 | 0.500 | −26.1 |
| Purdy | Pass attempts | 33.5 | 26.71 ± 10.73 | 0.264 | 0.517 | −25.3 |
| K. Williams | Receiving yds | 10.5 | 7.27 ± 10.88 | 0.262 | 0.515 | −25.3 |
| Kittle | Receptions | 3.5 | 2.44 ± 1.85 | 0.253 | 0.454 | −20.1 |
| Stafford | Pass attempts | 34.5 | 30.27 ± 10.82 | 0.316 | 0.505 | −18.9 |
| Stafford | Passing yds | 263.5 | 218.31 ± 92.30 | 0.311 | 0.487 | −17.6 |
| Purdy | Passing yds | 242.5 | 203.11 ± 96.48 | 0.343 | 0.502 | −15.9 |
| Stafford | Passing TD | 1.5 | 1.37 ± 1.25 | 0.406 | 0.562 | −15.6 |
| Purdy | Passing TD | 1.5 | 1.17 ± 1.15 | 0.332 | 0.481 | −14.9 |
| Kittle | Receiving yds | 33.5 | 31.93 ± 29.00 | 0.397 | 0.500 | −10.3 |
| Purdy | Interceptions | 0.5 | 0.75 ± 0.92 | 0.499 | 0.572 | −7.2 |
| **Stafford** | **Interceptions** | 0.5 | 0.64 ± 0.78 | 0.478 | 0.443 | **+3.5** |

Anytime TD, one-sided prices carrying their full hold (the gap overstates the
shortfall by roughly the margin): McCaffrey −34.3, K. Williams −32.0,
Nacua −21.4, Kittle −8.6.

**Overall: median −25.3 pp, model below market in 18 of 19.**

## 2. Size by metric

| metric | n | median gap | median z of line vs model mean | direction |
|---|--:|--:|--:|---|
| rushing/carries | 2 | **−44.9** | **+2.11** | all below |
| receiving/receptions | 4 | −33.0 | +0.84 | all below |
| receiving/receiving_yards | 4 | −30.1 | +0.61 | all below |
| qb/ryds | 1 | −26.1 | +0.49 | below |
| qb/att | 2 | −22.1 | +0.51 | all below |
| qb/pyds | 2 | −16.8 | +0.45 | all below |
| qb/ptd | 2 | −15.2 | +0.20 | all below |
| **qb/int** | 2 | **−1.9** | −0.22 | **split 1/1** |

The ordering is the finding. Interceptions — the one metric with almost no
dependence on how opportunity is split among teammates — is the one metric
where the model and the market agree. Carries, the most concentrated real
quantity in football, is the worst by a factor of twenty.

Opportunity markets (attempts, carries, receptions): median **−33.0 pp**,
**8 of 8** in the same direction. Conversion markets (yards, TD, INT): median
−15.9 pp, 10 of 11 — and the conversion gaps are largely inherited, since fewer
targets mechanically means fewer yards.

## 3. Does one upstream mechanism explain most of it? **Yes.**

Not team volume, and not the QB layer. **The non-QB player-share allocation.**

### The internal control

The same run, the same teams, the same team-volume draws, two different
allocation mechanisms:

| pool | mechanism | top player's share of his team |
|---|---|--:|
| QB attempts | `QA.allocate` + R2 | Stafford **91.2%**, Purdy **88.0%** |
| RB carries | P4C simplex | K. Williams **36.4%**, McCaffrey **39.8%** |
| Targets | P4C simplex | Nacua **15.9%**, Deebo **11.8%** |

The quarterback split is right. A real NFL WR1 draws 24–28% of team targets and
a bell-cow back 65–75% of team carries; the model gives 16% and 38%. Same data,
same game — the difference is the mechanism.

### Team volume is approximately right

SF 36.0 dropbacks / 36.2 targets / 26.6 carries; LA 33.9 / 29.8 / 28.4. Those
are ordinary NFL team-game values. The model is not forecasting a small game.
It is forecasting an ordinary game and then dividing it among too many people.

### The earliest causal layer

`p4c_params.class_point_forecast`, feeding the P4C simplex in
`layers.targets_carries`.

**The weights do not sum to one over the players who will actually play.** For
LA, 23 rostered pass-catchers carry nonzero target weights summing to **2.04**;
for SF, 22 summing to **2.25**. The individual values are credible — Nacua
0.302, Adams 0.235, together 54%, about right for a real WR1/WR2 pair. The
simplex then normalises by the sum, and **every real share is roughly halved**:
Nacua's 0.302 becomes 15.9%.

Carries are the same shape and worse, because the pool is small: LA's five
backs sum to 1.58, SF's six to 1.92, so a lead back loses a third of his share
to normalisation, and two players per team sit on an identical no-history
fallback (0.2702) that absorbs 28–34% of the mass.

Two upstream contributors, both before the simplex:

1. **The player set is every rostered WR/TE/RB.** `run_game` selects on
   position alone — no depth-chart gate, no snap-share gate — so 22–23 players
   per team enter a pool that eight or nine will really occupy. The depth-chart
   rank is captured and available, and unused.
2. **Each share is estimated against a historical denominator** and applied to
   that inflated set, so the vector is not a partition of anything.

Layer three compounds it: `layers.participation` weights by pass-snap
participation, and the layer's own declared warning is that this is *"an upper
bound on routes run"*. Being on the field is nearly uniform across starters —
the prior gives LA's top four 0.787 / 0.740 / 0.736 / 0.725 — while being
targeted is highly concentrated. The model is allocating targets in proportion
to being on the field.

**This is `POST_V1_REFINEMENT`, and it is not being repaired.** It also is not
new: the ledger already carries `RB1↔RB2 at flat week-1 priors` and a
`share-residual floor of 20.68%`. The market snapshot did not discover the
defect; it sized it.

## 4. What tonight must show

Pre-registered before kickoff in `nfl/research/mkt1/predeclaration_mkt1.md`
(sha256 `3d298170a2a7da55…`), with the model's own intervals.

**Supports allocation-too-diffuse:**
- team totals land INSIDE the model's p10–p90 (SF targets 26.1–47.3, carries
  18.1–36.7; LA targets 20.8–38.3, carries 17.8–38.6) — volume is fine; **and**
- a lead player's realised share lands ABOVE p90 (Nacua targets > 27.3%,
  McCaffrey carries > 54.3%, K. Williams carries > 52.0%); **or**
- distinct players targeted lands at or BELOW p10 (SF ≤ 9, LA ≤ 9) against a
  model mean of 11–12.

**Weakens it:**
- team totals land ABOVE p90 → the cause is at least partly team volume;
- realised shares land inside the model's interval → the market was wrong and
  V1 was fine;
- ~11–12 players really are targeted → the breadth is not the mechanism.

**Declared now so it cannot be reached for later:** this game is at the
Melbourne Cricket Ground, 10:35 local. V1 has no venue, travel or neutral-site
feature. A single international morning game is a poor place to read team
volume, which weakens any inference about part A specifically.

## 5. Postgame research plan — outcomes as truth

1. **Score the sealed board** through the permanent evaluator. Seal verified
   before any outcome byte is read. Truth is the play-by-play, never the line.
2. **Adjudicate the pre-registration** on its own thresholds, and record the
   result whichever way it falls.
3. **Decompose the realised miss**: for each player, split the error into the
   team-volume component and the share component, so the two competing
   explanations are separated by measurement rather than by argument.
4. **Add the market comparison to the ledger as a separate column**, never as a
   score. Whether the market beat the model is a fact worth logging and is not
   evidence about the model's calibration.
5. **Accumulate.** The bar is unchanged: the same directional miss in **at
   least four distinct games** before any refinement candidate is raised. Week 1
   offers fifteen more games this weekend, all with the same flat-prior
   condition, so four is reachable within days without loosening anything.
6. **Only then**, a research ruling. The candidate repair would be a
   pre-registered change to how the P4C weight vector is normalised and which
   players enter the pool — tested against held-out games, with a declared
   equivalence margin, and never fitted to a price.

**Stopping here. V1 is untouched.**

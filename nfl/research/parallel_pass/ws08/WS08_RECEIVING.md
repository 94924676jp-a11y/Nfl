# WS08 — The declared receiving limitations, traced and quantified

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws08/` was
written, and no existing repository file was modified. Every number below came
from reading sealed artifacts and play-by-play; no fit was promoted, no
production path was touched.

**Status: EXPLORATORY.** The prospective frame is 5 games. The historical frame
(2021-2024) is the same corpus RC1 and the P-series already mined, so nothing
here is confirmatory and nothing here promotes anything.

**Question asked:** is an air-yards / depth layer REQUIRED, LIKELY USEFUL, or
UNSUPPORTED BY CURRENT EVIDENCE?

**Answer: UNSUPPORTED BY CURRENT EVIDENCE**, and the decomposition says why
rather than merely asserting it. The residual that a depth layer could in
principle reach is large (about half the receiving-yard error). The part of that
residual a depth layer actually reaches, measured forward-chained, is between
0.4% and 1.0% of it, and is not distinguishable from zero when standard errors
are clustered by game.

---

## 1. The trace — what the conversion layer actually does

Read from `nfl/production/nonqb/layers.py`, `football_engine.py`,
`shared_pass.py`, `nfl/research/rc1/rc1_sim.py` and `rc1_lib.py`.

| Stage | Where | Mechanism | Depth / air-yards content |
|---|---|---|---|
| Target generation | `layers.targets_carries` (`layers.py:~300`), P4C system C simplex; under C3 the budget is the QB's own attempts (`football_engine.py:407-499`) | appearance x participation x class point forecast, allocated on a simplex, then **dealt** as integer throws | **none** |
| Catch probability | `layers.receiving_conversion` (`layers.py:390`) | `c = w*own_rate + (1-w)*pos_catch_rate`, `w = h_n/(h_n+4)`, then `R ~ Binomial(T, c)` | **none** — one scalar per player |
| Yards generation | same function, `layers.py:437-459` | per **catch**, resample a yardage from the player's own flattened prior per-catch list (prob `w`) or the positional pool (prob `1-w`); sum over the draw's receptions | **implicit only** — a deep player's own list is deep |
| YAC | nowhere | not separated from air yards at any point | **absent** |
| Depth / air-yards proxy | nowhere in production | `rc1_lib.load` attaches `air_yards_caught` and `yac` per player-game, and **nothing consumes them** | ORPHANED input |
| TD process | `layers.td_layer` (`layers.py:476`) | `TD ~ Binomial(R, B_pos / pos_catch_rate)` | **none** — no red-zone or depth conditioning |
| Correlation with QB | `football_engine.py:875-910` via `shared_pass.credit_to_passers` | under C3 the passer's `cmp`, `pyds`, `ptd` **are** the receiving totals, credited back | fully coupled, measured `r = +1.0000` below |
| Archetype handling | `board.json` `position` + `depth_chart` | position enters only through `pos_catch_rate`, `pos_yardage_pool`, `B_pos`; `depth_chart` is a label | **none beyond WR/TE/RB** |
| Rushing conversion | `layers.rushing_conversion` (`layers.py:597`) | returns DEFERRED `RUSHING_CONVERSION_CONTROL_UNDEFINED`; `carries x YPC` is named as the prohibited implementation | n/a |

Two structural facts fall out of the trace and both matter for the verdict.

**(i) Within a draw, receiving yards depend on the draw only through `R`.** The
per-catch picks are i.i.d. given the player and the draw. So the model's own
conditional distribution `Y | R = R_actual` **is exactly** the "targets and
receptions both known" arm. That is what makes the decomposition in section 3
exact rather than approximate.

**(ii) The receiving conversion is upstream of the QB passing line, not beside
it.** Measured on `2026_01_ATL_PIT/.../f67d72ab0701d211`:

```
ATL: corr(sum player receptions, QB cmp)      = +1.0000
     corr(sum player rec_yds,    QB pass_yds) = +1.0000
     mean sum rec_yds 230.2  vs  mean QB pass_yds 230.2
PIT: same, 254.3 vs 254.3
within-team cross-player target correlation:  mean -0.0330 (competition, as designed)
```

The C3 comment in `football_engine.py:415` records that the **superseded** B0
default produced `corr(team passing yards, team receiving yards) = +0.001` with
the yard identity violated in 12,800 of 12,800 draws. In the R8 boards scored
here that is repaired. The consequence is that **any error in per-catch yardage
propagates one-for-one into the QB passing-yards forecast**, so the value of a
depth layer is not confined to receiving markets.

---

## 2. Prospective receiving error, 5 sealed games

Frame: the five designated runs, `receiving` layer `row_ids` (gsis_id, never
positional), n = 132 player-game rows, 1,000 draws each, scored against
`pbp_2026.1415dd98ba7f701a.csv.gz` via `shadow.actuals.receiving_rushing_actuals`.

| game | stage / run | rows |
|---|---|---|
| 2026_01_ATL_PIT | pre_inactives_V1_CANDIDATE_R8 / f67d72ab0701d211 | 24 |
| 2026_01_BAL_IND | pre_inactives_V1_CANDIDATE_R8 / bee85f326a3fde5c | 26 |
| 2026_01_NO_DET | post_inactives_V1_CANDIDATE_R8 / b5b02f6365ead28f | 26 |
| 2026_01_TB_CIN | post_inactives_V1_CANDIDATE_R8 / e92b9e19466d27bd | 28 |
| 2026_01_SF_LA | post_inactives_V1_CANDIDATE_R8 / 5e70d8847e32c7ae | 28 |

One targeted player had no forecast row: `J.Brendel` (SF, centre, 1 target, 2
yards). That is the only coverage gap and it is not a receiver.

### 2.1 Marginal quality (forecast mean against realised)

| metric | pred | act | bias | MAE | RMSE | CRPS | r | sd ratio | cover 50/80/90/95 |
|---|---|---|---|---|---|---|---|---|---|
| targets | 2.36 | 2.44 | −0.07 | 1.42 | 2.02 | 0.95 | +0.766 | 0.693 | .81 / .95 / .98 / .99 |
| receptions | 1.62 | 1.68 | −0.07 | 1.11 | 1.57 | 0.72 | +0.724 | 0.656 | .80 / .94 / .98 / 1.00 |
| **rec_yds** | 18.36 | 17.51 | **+0.85** | **12.87** | 20.50 | **8.42** | **+0.688** | 0.649 | **.74 / .92 / .96 / .98** |
| rec_td | 0.11 | 0.10 | +0.01 | 0.17 | 0.29 | +0.422 | 0.344 | .92 / .98 / 1.00 / 1.00 |

Game-clustered standard errors, 5 clusters. **Naive SEs are refused** per the
project's clustering rule; with five clusters the clustered SE is itself
uninformative and is reported only to make that visible.

| metric | bias | game-clustered SE | naive SE | ratio |
|---|---|---|---|---|
| targets | −0.07 | 0.27 | 0.18 | 1.52x |
| receptions | −0.07 | 0.17 | 0.14 | 1.22x |
| rec_yds | +0.85 | 1.72 | 1.79 | 0.96x |
| rec_td | +0.01 | 0.03 | 0.03 | 0.98x |

**No bias in this frame is distinguishable from zero.** Five clusters cannot
distinguish anything and this table must not be read as evidence of adequacy —
no equivalence margin was predeclared and no TOST was run.

### 2.2 What IS visible: over-coverage, and it reproduces the declared defect

Every nominal level is over-covered for receiving yards: 74/92/96/98 against
50/80/90/95. `PATH_C_STATE.receiving_baseline_calibration` records the
historical finding as "bias +2.18 yards and over-coverage at all four nominal
levels". The over-coverage half reproduces prospectively; the bias half does not
(+0.85 here, against a lower mean outcome, 17.51 vs 22.21).

**The intervals are too WIDE, not too narrow.** That is the opposite of the
usual failure mode and it constrains the verdict: a depth layer's most plausible
selling point — a fatter, better-shaped tail — is a fix for a problem this
baseline does not have.

### 2.3 PIT (randomised, 10 bins)

| metric | bins | mean PIT | max&#124;F−U&#124; |
|---|---|---|---|
| targets | 9,10,14,10,10,18,20,19,15,7 | 0.531 | 0.097 |
| receptions | 10,10,15,14,19,7,13,13,20,11 | 0.517 | 0.054 |
| rec_yds | 9,20,16,14,7,13,16,15,14,8 | 0.482 | 0.055 |
| rec_td | 20,10,11,17,16,12,7,11,20,8 | 0.474 | 0.068 |

No usable shape signal. A chi-square on these bins would assume 132 independent
observations when there are 5 clusters, and is not quoted.

---

## 3. Decomposing the receiving-yard error

### 3.1 Exact additive mean decomposition

`Y_pred_mean − Y_actual  ≡  dT + dC + dV` exactly (max residual 1.4e−14), with
`chat = E[R]/E[T]`, `vhat = E[Y]/E[R]`, `ca = Ra/Ta`, `va = Ya/Ra`:

* `dT = (That − Ta) · chat · vhat` — target-volume error
* `dC = Ta · (chat − ca) · vhat` — catch-rate-given-targets error
* `dV = Ra · (vhat − va)` — yards-per-reception error

| split | n | dT | dC | dV | total | mean&#124;dT&#124; | mean&#124;dC&#124; | mean&#124;dV&#124; | share T / C / V |
|---|---|---|---|---|---|---|---|---|---|
| ALL | 132 | −0.53 | +0.32 | +1.06 | +0.85 | 10.84 | 4.85 | 6.84 | **48.1 / 21.5 / 30.4** |
| WR | 60 | +0.12 | −0.22 | +0.31 | +0.21 | 12.84 | 6.77 | 9.80 | 43.7 / 23.0 / 33.3 |
| TE | 40 | +1.12 | +1.60 | +0.92 | +3.63 | 9.46 | 4.06 | 3.60 | 55.3 / 23.7 / 21.0 |
| RB | 32 | −3.79 | −0.25 | +2.63 | −1.42 | 8.82 | 2.26 | 5.33 | 53.8 / 13.7 / 32.5 |
| forecast target rank 1 | 10 | −1.97 | +6.42 | −3.12 | +1.34 | 23.13 | 13.05 | 26.49 | 36.9 / 20.8 / 42.3 |
| rank 2 | 10 | −2.05 | −1.01 | +4.66 | +1.61 | 16.37 | 15.79 | 17.38 | 33.0 / 31.9 / 35.1 |
| rank 3 | 10 | −10.80 | −3.18 | +7.19 | −6.79 | 17.03 | 8.60 | 11.73 | 45.6 / 23.0 / 31.4 |
| rank 4 | 10 | −2.84 | +1.05 | +0.50 | −1.29 | 13.17 | 7.37 | 9.28 | 44.2 / 24.7 / 31.1 |
| rank 5+ | 92 | +1.16 | +0.10 | +0.51 | +1.78 | 7.98 | 2.09 | 2.76 | 62.2 / 16.3 / 21.5 |
| high volume (E[T] ≥ 2.36) | 42 | −6.17 | +0.28 | +3.50 | −2.39 | 18.20 | 10.67 | 16.64 | 40.0 / 23.5 / 36.6 |
| low volume (E[T] < 2.36) | 90 | +2.11 | +0.34 | −0.08 | +2.36 | 7.41 | 2.14 | 2.27 | 62.7 / 18.1 / 19.2 |

**Rank is defined from the forecast's own pregame ordering** — players sorted
within team by mean predicted targets in the sealed draws. It never touches a
realised number. The volume split uses the same forecast quantity (its own
mean, 2.36), so it too is outcome-independent.

### 3.2 Oracle arms taken from the model's own joint draws

Because `Y ⫫ T | R` in this mechanism, the conditional distributions below are
the model's own and require no refitting. Exact draw-subset match was available
for 127/132 rows (T-oracle) and 130/132 (R-oracle); two rows used an i.i.d.
per-catch reconstruction validated against exact-match rows at mean |Δmean| 1.51
yd. All arms are restricted to the 127 commonly comparable rows.

| arm | n | CRPS | MAE | RMSE | bias | r | cover 50/80/90/95 |
|---|---|---|---|---|---|---|---|
| BASELINE (nothing known) | 127 | 7.941 | 12.31 | 19.97 | +1.08 | +0.718 | .77/.94/.97/.98 |
| T-oracle (**targets** known) | 127 | 5.444 | 7.59 | 15.88 | +0.84 | +0.833 | .79/.91/.93/.95 |
| T+C-oracle (**receptions** known) | 127 | 4.476 | 6.56 | 13.67 | +0.89 | +0.879 | .73/.90/.94/.98 |

> **Surviving after conditioning on realised TARGETS: 68.6% of CRPS, 61.7% of MAE.**
> **Surviving after conditioning on realised RECEPTIONS: 56.4% of CRPS, 53.3% of MAE.**

The historical RC1 run agrees closely. Pooled 2022-2025, n = 22,521 player-games
over 1,087 games (`nfl/research/rc1/rc1_results.json`): baseline CRPS 11.180,
`T` coalition 7.254 (64.9%), `C+T` coalition 5.792 (**51.8%**). Shapley shares
with block-bootstrap CIs: **T 53.9% [52.9, 54.8], C 17.2% [16.8, 17.7],
V 28.9% [28.2, 29.7]**.

### 3.3 Residual after conditioning on receptions, by subgroup (5-game frame)

| subgroup | n | baseline CRPS | receptions-known CRPS | % surviving |
|---|---|---|---|---|
| WR | 59 | 10.297 | 6.657 | 64.6% |
| TE | 38 | 6.240 | 2.352 | 37.7% |
| RB | 30 | 5.461 | 2.878 | 52.7% |
| forecast rank 1 | 10 | 27.195 | 17.966 | 66.1% |
| forecast rank 2 | 9 | 11.695 | 12.753 | 109.1% |
| forecast rank 3-4 | 20 | 12.910 | 6.550 | 50.7% |
| forecast rank 5+ | 88 | 4.240 | 1.626 | 38.3% |
| high volume (E[T] ≥ 2.36) | 39 | 16.392 | 11.104 | 67.7% |
| low volume (E[T] < 2.36) | 88 | 4.195 | 1.539 | 36.7% |

The rank-2 cell exceeds 100%. At n = 9 that is noise, not a finding, and it is
shown rather than dropped.

The shape is consistent and it is the football-plausible one: **the more targets
a player is forecast to see, the larger the share of his error that survives
knowing his receptions.** For a WR1 the per-catch yardage channel is the
majority of what is left; for a WR5 it is a third.

---

## 4. Is that residual reachable by depth information?

The residual after conditioning on receptions is entirely the per-catch yardage
channel `V`. If an air-yards layer is worth building, it must move `V`. Tested
directly on a player-game panel built from `pbp_202[1-4]` (18,229 player-games,
16,326 with at least one reception; 379 null `air_yards` on targets, 1 on
catches, 2 null YAC — counted, never silently zeroed).

### 4.1 The depth signal is real and it is strong

```
identity check   mean|V - (aDOT_caught + YAC_per_catch)| = 0.0011
Var(V) = 53.87 = Var(aDOT_c) 44.40 + Var(YAC_c) 26.46 + 2Cov(-17.00)
share of Var(V):  aDOT 82.4%   YAC 49.1%   cov -31.6%
```

Air-yards depth accounts for **82% of the variance of per-catch yardage**, and
it persists far better than the quantity RC1 currently models:

| strictly-prior predictor → realised, n = 13,742 (≥4 prior games) | r | r² |
|---|---|---|
| prior yards-per-catch `V` → realised `V` | +0.298 | 0.089 |
| prior aDOT per catch → realised aDOT per catch | +0.566 | 0.321 |
| **prior aDOT per target → realised aDOT per catch** | **+0.653** | **0.426** |
| prior YAC per catch → realised YAC per catch | +0.271 | 0.073 |

Depth-stratified per-catch yardage pools are dramatically different (terciles of
prior aDOT/target cut on 2021-2023): mean per catch **7.80 / 11.06 / 13.23**,
`P(gain > 25)` **0.0338 / 0.0672 / 0.1081**. Against the unstratified pool
(10.93, 0.0725) that is exactly the tail difference an air-yards layer is
supposed to supply.

**So the hypothesis is not silly. It has a real mechanism behind it.** It still
fails the only test that matters.

### 4.2 Forward-chained value test — fit 2021-2023, evaluate 2024

Conditional on realised receptions, `Y_hat = R · V_hat`, so the error is exactly
`R · (V_hat − V)`. Reception-weighted OLS on shrunk strictly-prior features
(`w = h_n/(h_n+4)`, the K inherited from RC1, not searched). Evaluated on 2024
only, n = 4,015 player-games with at least one reception, 285 games.

| predictor of V | MAE | % of M1 | RMSE | % of M1 | vs M1, game-clustered |
|---|---|---|---|---|---|
| league constant | 12.879 | 107.1% | 18.708 | 108.9% | — |
| **M1 shrunk prior V (the RC1 mechanism)** | **12.020** | **100.0%** | **17.175** | **100.0%** | — |
| M2 + prior aDOT/target | 11.968 | 99.56% | 17.098 | 99.55% | −0.053 yd, SE 0.058, **t = −0.91** |
| M3 + prior aDOT/catch | 11.957 | 99.48% | 17.132 | 99.75% | −0.063 yd, SE 0.052, **t = −1.22** |
| M4 + prior aDOT/catch + prior YAC | 11.955 | 99.46% | 17.131 | 99.74% | −0.065 yd, SE 0.052, **t = −1.25** |
| M5 depth features only, no prior V | 11.957 | 99.47% | 17.132 | 99.75% | −0.063 yd, SE 0.052, t = −1.22 |
| ORACLE realised V | 0 | 0% | 0 | 0% | the ceiling |

Adding every depth feature available buys **0.5% of the conditional-on-receptions
error, about 0.065 yards per player-game**, with a 95% interval of
[−0.166, +0.036] clustered by game over 285 games. It is not distinguishable
from zero.

**Why, in one number:** the partial correlation of prior aDOT-per-catch with
realised `V`, controlling for prior `V`, is **+0.104 (partial r² = 0.011)**.
Resampling a player's own prior per-catch yardages is *already an implicit depth
model* — a deep receiver's own history is full of deep catches. The air-yards
field adds almost nothing the yardage history does not already carry.

### 4.3 The distributional form of the hypothesis fails too

The strongest version of the claim is not about the mean but about the shape:
give a deep player a deeper pool and the tail improves. Tested by swapping the
`(1−w)` pool component for the aDOT-tercile pool and scoring CRPS of `Y | R`:

| frame | n | baseline pool CRPS | depth-banded pool CRPS | change |
|---|---|---|---|---|
| all, ≥4 prior games | 3,733 | 8.5970 | 8.5995 | **+0.03%**, t = +0.20 over 285 games, 95% CI [−0.021, +0.026] |
| R ≥ 3 | 1,853 | 11.710 | 11.723 | +0.11% |
| R ≥ 5 | 853 | 13.443 | 13.502 | +0.44% |
| **cold start, h_n < 4** | 190 | 6.9880 | 7.0713 | +1.19%, t = +0.46 |

Zero, in every stratum, including the cold-start stratum where the pool
dominates and where a depth prior should help most.

### 4.4 The catch-rate channel — the one place depth measurably does something

Prior aDOT/target correlates **−0.232** with realised catch rate: deeper targets
are caught less often, the expected sign. Adding it to a prior-catch-rate model
(fit 2021-2023, evaluate 2024, n = 4,121):

```
C1 prior catch rate only    MAE_receptions = 0.7544
C2 + prior aDOT/target      MAE_receptions = 0.7494   (-0.66%)
   C2 - C1 = -0.0050 receptions/player-game, game-clustered SE 0.0021, t = -2.34, 285 games
```

This is the only depth effect in the whole study that clears a game-clustered
t of 2. **It is worth 0.005 receptions per player-game — roughly 0.05 receiving
yards.** Statistically detectable and operationally negligible.

### 4.5 The standing constraint that makes this worse, not better

`PATH_C_STATE.open_questions.OQ-RC1-PRIMITIVE-REVERSAL`, registered as a
**binding methodological constraint**, records that primitive-level gains in
this chain reverse under composition: "C gains +0.680% as a primitive and costs
0.465% downstream, while V gains +0.050% and costs 0.951% downstream." A 0.5%
primitive-level gain in `V` is inside the band where the project has already
measured the sign to flip. Nothing here may be proposed on a primitive metric
alone.

---

## 5. Verdict

### **UNSUPPORTED BY CURRENT EVIDENCE.**

The argument in four steps, each measured:

1. **The residual is big.** 56.4% of receiving-yard CRPS (53.3% of MAE) survives
   conditioning on realised receptions in the 5-game prospective frame; 51.8%
   in the 22,521-row historical frame. A depth layer's whole addressable
   territory is that half. *That is the answer to "how much survives" — and it
   is a ceiling, not an expectation.*
2. **The depth signal inside that residual is real.** aDOT carries 82% of
   Var(V), persists at r = 0.65 where per-catch yardage persists at r = 0.30,
   and separates per-catch pools from 7.8 to 13.2 yards with a threefold
   difference in `P(gain > 25)`.
3. **Almost none of it is incremental.** Controlling for the player's own prior
   yardage, prior aDOT has partial r² = 0.011 against realised `V`. The
   own-history bootstrap RC1 already runs *is* a depth model in disguise.
4. **So the realised gain is 0.4-1.0% of the residual, not distinguishable from
   zero.** Best case M4: −0.065 yd/player-game, 95% CI [−0.166, +0.036]
   clustered by game over 285 games. The distributional form gives +0.03%
   (i.e. nothing). The catch-rate form gives 0.005 receptions.

And the calibration evidence points the other way from the usual motive for a
depth layer: **the intervals are already too wide** (74/92/96/98 against
50/80/90/95), so a fatter tail is a fix for a defect that is not present.

**Where the error actually is, and it is not depth.** Target volume is 48.1% of
the mean absolute error in the prospective frame and 53.9% of pooled Shapley
CRPS historically. The five worst individual misses in the prospective set are
target-volume misses, not yardage misses:

```
C.Olave    NO WR rank1  pred T 7.20 / act T 13  -> err -122.6 yd
Z.Flowers BAL WR rank1  pred T 8.91 / act T  6  -> err  -67.2 yd
J.Chase   CIN WR rank1  pred T 8.51 / act T  4  -> err  +63.2 yd
M.Gesicki CIN TE rank4  pred T 2.90 / act T  7  -> err  -56.3 yd
K.Pitts   ATL TE rank2  pred T 6.93 / act T  1  -> err  +55.4 yd
```

`NO_AIR_YARDS_LAYER` as a board declaration remains correct and should stay: V1
genuinely forecasts no air-yards distribution, and an `receiving/air_yards`
market therefore cannot be quoted. **What this study falsifies is the different
claim that building one would materially reduce receiving-yard error.**

The declared `SIGNAL_WEAK` label on RC1 is corroborated and its scope extended:
it is not weak only because the estimators tried so far were weak. The `V`
channel appears close to its predictable limit at player-game resolution with
the data in this repository.

### What would change the verdict

* Per-target depth rather than per-player depth: an aDOT forecast **conditioned
  on game state** (score, down, time) rather than a player-season average. The
  test here used player-level priors only, which is the form a V1 layer would
  have taken.
* Defensive coverage or separation data. `_GROUNDING.md:247` names
  `avg_separation` and `avg_yac_above_expectation` as NGS fields not in this
  repository, and `NFL_FEATURE_REGISTRY.md:63` records
  `participation.ngs_air_yards` as SOURCE EMPTY (0 non-null of 45,919). None of
  that is reachable without the network agent.
* A target-volume improvement first. Since the C3 wiring makes the QB passing
  line a credit from the receiving event, a target-volume gain pays twice.

---

## 6. Findings

| # | Finding | Status | Evidence |
|---|---|---|---|
| F1 | Conditioning on realised receptions leaves ~52-56% of receiving-yard CRPS | **CONFIRMED** | 4.476/7.941 prospective (n=127); 5.792/11.180 historical (n=22,521) |
| F2 | Conditioning on realised targets leaves ~65-69% | **CONFIRMED** | 5.444/7.941; 7.254/11.180 |
| F3 | Target volume is the single largest channel | **CONFIRMED** | 48.1% of mean abs error (5 games); Shapley 53.9% [52.9, 54.8] (4 seasons) |
| F4 | An air-yards layer materially reduces receiving-yard error | **FALSIFIED** | best forward-chained gain 0.5% of the conditional residual, −0.065 yd/player-game, 95% CI [−0.166, +0.036], 285 game clusters |
| F5 | The depth signal itself is real and persistent | **CONFIRMED** | aDOT 82.4% of Var(V); prior→realised r = +0.653; pool tercile means 7.80/11.06/13.23 |
| F6 | The depth signal is incremental to the own-history bootstrap | **FALSIFIED** | partial r(prior aDOT, V &#124; prior V) = +0.104, partial r² = 0.011 |
| F7 | A depth-stratified per-catch pool improves the distribution | **FALSIFIED** | CRPS +0.03%, t = +0.20; cold start +1.19%, t = +0.46 |
| F8 | Depth predicts catch rate | **CONFIRMED but negligible** | r = −0.232; −0.0050 receptions/player-game, t = −2.34 |
| F9 | Declared `CALIBRATION_DEFECT` (over-coverage) reproduces prospectively | **PARTIAL** | coverage 74/92/96/98 vs 50/80/90/95; the paired bias claim (+2.18) does not, +0.85 here |
| F10 | Receiving conversion is upstream of the QB passing line under C3 | **CONFIRMED** | corr(sum rec_yds, QB pass_yds) = +1.0000, means identical to 0.1 yd |
| F11 | Engine has no YAC/air split, no per-target depth, no archetype beyond WR/TE/RB | **CONFIRMED** | `layers.py:390-473`; `rc1_lib` loads `air_yards_caught`/`yac` and nothing consumes them |
| F12 | `RUSHING_CONVERSION_CONTROL_UNDEFINED` still holds | **CONFIRMED** | `layers.py:597-640` returns DEFERRED; three owner decisions open |
| F13 | Whether a depth layer helps at the *play* level rather than the player-game level | **UNRESOLVED** | not testable with the player-game panel built here |
| F14 | Whether target-volume gains would survive out of sample | **UNRESOLVED** | out of WS08 scope; the 2021-2025 corpus is already mined |

---

## 7. Evidence ceiling

* **Prospective frame is 5 games, 132 player-game rows, 5 clusters.** No bias
  in section 2.1 is distinguishable from zero and none should be quoted as
  adequacy. No equivalence margin was predeclared; no TOST was run. The words
  *unbiased*, *stable*, *closed* and *correct* are not used about any result
  here.
* **Only 5 of 14 Week-1 boards carry a full receiving layer AND a postgame
  outcome.** `2026_01_ARI_LAC` and `2026_01_DAL_NYG` have receiving layers but
  are absent from `pbp_2026.1415dd98ba7f701a.csv.gz` (10 games). The other seven
  boards have no receiving layer at all — defect `D03` in
  `nfl/research/live/OPEN_DEFECTS.json`, injury `report_status` unset, so the
  appearance layer deferred. **The frame is what exists, not a selection.**
* **The 2021-2024 historical frame is development data.** RC1, the ladder study
  and the P-series already selected on it. Section 4 is forward-chained
  (fit 2021-2023, evaluate 2024) which controls in-sample fitting, but it does
  **not** restore independence from the prior mining of this corpus. Section 4
  is exploratory. A confirmatory answer needs 2025+ or a sealed holdout with the
  design fixed beforehand.
* **The oracle arms are ceilings, not achievable targets.** "56.4% survives
  conditioning on receptions" is the most a perfect depth layer could address,
  assuming it also does no harm. Section 4 measures what is actually reachable
  and it is two orders of magnitude smaller.
* **The historical Shapley is RC1's own target model, not production's.** RC1
  draws `T` by bootstrapping the player's prior targets; production allocates
  `T` on a P4C simplex from a QB-attempt budget. The T-share of error is
  therefore not strictly transferable between the two frames. The prospective
  frame, which does use production's target model, gives 48.1% against RC1's
  53.9% — close, but the difference is not measured, only observed.
* **`ngs_air_yards` is quarantined and empty** (0 non-null of 45,919,
  `NFL_FEATURE_REGISTRY.md:63`). All air-yards evidence here comes from
  `pbp.air_yards`, which is the field `predeclaration_rc1.md:66-69` says to use.
  Separation and YAC-over-expected are outside this checkout entirely and would
  need the network agent.
* **Reproduction:** the five scripts under
  `nfl/research/parallel_pass/ws08/` regenerate every number, read-only, on
  `python3.12`. Seeds are fixed at 20260914 for the randomised PIT and for the
  bootstrap resamples; no other randomness enters.

---

## 8. Recommendation

Do not build an air-yards layer on this evidence. Record
`NO_AIR_YARDS_LAYER` as **CHARACTERIZED — not a material source of receiving
error**, keeping the board declaration as the honest statement of what V1 does
not forecast, and stop treating it as an explanation for the receiving
calibration defect.

The receiving calibration defect and the receiving discrimination gap are
different problems with different owners: the first is over-coverage in the
conditional yardage distribution, which is an estimator-repair question already
assigned; the second is target volume, which is where 48-54% of the error lives
and where no depth information helps at all.

No wager is recommended and no market is implied by anything above.

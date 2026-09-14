# WS07 — Independent adjudication of the team-volume layer

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws07/` was written.
No existing repository file was modified. Everything below is measurement.

Layer under test: `nfl/production/team_volume_v1.py`, spec `team-volume-v1-p4b-frozen-1`,
manifest layer `team_volume`, `row_axis: team`.
Claim under test: the run-status warning `known limitation: team_volume_is_near_unforecastable`.

---

## 0. Frame, and why it is the frame

**Outcomes.** `nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`, 1,738 rows,
10 completed 2026 REG week-1 games, 20 team-games. Realised team quantities come from
`nfl/research/shadow/actuals.py::team_actuals`. History:
`pbp_2021.e8743a568f99667a`, `pbp_2022.0c69a71eb3949895`, `pbp_2023.4649804ee0f0a40b`,
`pbp_2024.23370d5d10f8104d` — 2,174 pooled REG team-games with a market line.

**Board selection, declared as a rule and then applied.** One board per game: the last
board sealed strictly before `kickoff_utc`, ties broken by path, `REPLAY_C1` excluded as
replays of an already-counted seal. Every selected board was sealed before kickoff, so the
evaluation is chronological.

**A result that makes the selection rule almost irrelevant, and which matters more than the
rule.** Across all 106 sealed board directories that carry a `team_volume` layer, the five
team-volume draw matrices are **byte-identical for every board of the same game** —
`pre_inactives` and `post_inactives`, candidate configurations `V1_CANDIDATE`, `_R5`, `_R6`,
`_R7`, `_R8`, and the `REPLAY_C1` replays alike. Verified by SHA-256 over the raw array bytes.
The single exception is NE@SEA, which holds two deliberate independent replications
(`shadow/g1_ne_sea`, `shadow/g1_ne_sea_runB`).

Two consequences, both load-bearing:

1. **Board multiplicity is not evidence multiplicity for this layer.** 106 sealed artifacts
   carry 10 games of team-volume information, not 106. Anything that counts candidate
   variants as independent observations of this layer is counting the same numbers again.
2. The layer is insensitive to inactives and to every R5–R8 candidate component. That is
   consistent with its inputs — the frozen denominator panel, the coach from the captured
   schedule, and a per-metric RNG stream — and none of those change when a player is ruled out.

**Games used:** ATL@PIT, BAL@IND, BUF@HOU, CHI@CAR, CLE@JAX, NE@SEA, NO@DET, NYJ@TEN,
SF@LA, TB@CIN. NE@SEA is the `shadow/g1_ne_sea` seal (the live namespace holds no NE@SEA
directory). DAL@NYG, ARI@LAC, GB@MIN, MIA@LV and WAS@PHI hold sealed boards but are **not**
in the outcome file and are therefore not scored.

---

## 1. Estimand status, before any number is scored

`nfl/research/postgame.py` scores `team_volume/team_carries` and refuses the other four
**by name**. That refusal is upheld here, and one part of it is the single most consequential
finding in this return.

| Forecast quantity | Realised basis (`actuals.py`) | Scoreable? | This return |
|---|---|---|---|
| `team_carries` | **EXACT** | yes | scored |
| `team_targets` | EXACT label, but `postgame.py` refuses as `ESTIMAND_UNVERIFIED` | refused | scored **PROVISIONALLY**, labelled |
| `team_dropbacks_part` | **SURROGATE** — pbp dropback count is an *upper bound* on the participation-matched quantity | refused | scored **PROVISIONALLY**, labelled |
| `team_off_snaps` | **SURROGATE** — `snap_counts` median, *not* a play-by-play quantity | refused | **realisation not identified**; bounded, not scored |
| `team_rz_carries` | refused (`ESTIMAND_UNVERIFIED`) | refused | out of scope for this workstream |

### 1a. What I could verify about the targets and carries estimands

The fitted panel's definitions were read out of `nfl/research/p4b/mk_denom.py` and
`nfl/research/p1/build_panel.py`, not assumed. `mk_denom.py` aggregates `team_targets` and
`team_carries` as sums of the identifier-repaired per-player panel; `build_panel.py` skips
two-point-attempt rows before counting (`if two: continue`), while `actuals.team_actuals`
does not. Measured gap on this outcome file: **2 two-point target rows in 20 team-games**
(BUF 1, NO 1) and **0 two-point carry rows**. So the definitional gap for targets is
≤1 per team-game here and zero for carries.

That is the part of the gap I can measure. The other part — receivers dropped by the panel's
identifier repair — is not measurable from this checkout, so the `ESTIMAND_UNVERIFIED`
refusal stands and my targets numbers are labelled PROVISIONAL rather than promoted.

### 1b. PLAYS: the realisation is not identified, and this is not a small effect

`team_off_snaps` is forecast on the `snap_counts` definition. Play-by-play cannot rebuild it.
Three candidate reconstructions, each defensible, each giving a different answer:

| Construction | Definition | Mean realised | Bias (forecast − realised) | z (cluster) |
|---|---|---|---|---|
| A | every pbp row with a `posteam` (what `actuals.py` returns) | 82.40 | **−16.52** | **−5.35** |
| B | offensive scrimmage plays (`pass/run/qb_kneel/qb_spike`, 2-pt removed) | 61.10 | **+4.78** | +1.98 |
| C | B plus offensive penalty-nullified `no_play` rows | 66.80 | **−0.92** | −0.38 |

The forecast mean is 65.88 in all three rows; only the realisation changed. **The sign of the
bias, its magnitude and its significance are all determined by an estimand choice, not by the
model.** Construction C is nearest to the snap-count definition (snap counts include
penalty-nullified plays, which `actuals.py` counts as separate `no_play` rows), and it is used
for every PLAYS line below, labelled `PLAYS(C)`.

This also resolves the case `postgame.py` cites in its own docstring. LA's forecast was
65.65; LA's realised value is **74 under A, 57 under B, 62 under C**. The "57 against 65.65"
miss is construction B measured against a snap-count forecast. It is an estimand artefact.
The automatic pipeline's refusal to score it is correct, and the manual review that reported
it as the largest model miss was reading a definition.

---

## 2. PLAYS — `team_volume/team_off_snaps`

Point estimator selected for 2026: **`league_mean`**, form `coach_empirical`
(read from `nfl/research/p4b/volume_results.json`, selection season 2025).

| Statistic | Value |
|---|---|
| n team-games / n games | 20 / 10 |
| Mean forecast | 65.88 |
| Mean realised (C) | 66.80 |
| **Bias** | **−0.92** |
| SE clustered by game | 2.423 |
| SE naive (for contrast only) | 2.302 |
| z (cluster) | −0.38 |
| 95% game-cluster bootstrap CI on bias | [−6.12, +3.11] |
| MAE / RMSE | 8.44 / 10.07 |
| SD of forecast means | 2.249 |
| SD of realised | 10.045 |
| **SD ratio (means/realised)** | **0.224** |
| Mean predictive SD | 8.625 |
| **Pearson r (forecast mean, realised)** | **+0.0002** |
| 95% bootstrap CI on r | [−0.231, +0.204] |
| Coverage 50 / 80 / 90 | 0.35 / 0.80 / 0.90 |
| PIT mean / SD | 0.502 / 0.344 |
| PIT 5-bin counts (uniform = 4) | [5, 4, 3, 1, 7] |
| CRPS-optimal predictive scale f\* | 1.25, 90% bootstrap [1.00, 1.65] |
| CRPS (model) vs climatological CRPS | 5.848 vs 6.100 |

**Read.** Mean calibration under construction C is fine. Dispersion at the team margin is
acceptable to slightly narrow — f\* = 1.25 with a bootstrap interval whose lower end sits
exactly on 1.00, so "too narrow" is suggested and not established. **Discrimination is
exactly zero.** That is not an accident: `league_mean` carries no team content at all. The
2.25 spread in forecast means comes entirely from the `coach_empirical` residual pool means
differing between coaches, and that spread is uncorrelated with the outcome.

---

## 3. CARRIES — `team_volume/team_carries` (EXACT, the only fully scoreable quantity)

Point estimator: **`coach_prior`**, form `coach_empirical`.

| Statistic | Value |
|---|---|
| n team-games / n games | 20 / 10 |
| Mean forecast / mean realised | 27.581 / 27.350 |
| **Bias** | **+0.231** |
| SE clustered by game | **0.650** |
| SE naive | 1.483 |
| z (cluster) | +0.35 |
| 95% game-cluster bootstrap CI on bias | [−1.00, +1.41] |
| MAE / RMSE | 5.553 / 6.467 |
| SD of forecast means / SD realised | 2.077 / 7.013 |
| **SD ratio** | **0.296** |
| Mean predictive SD | 7.105 |
| **Pearson r** | **+0.327**, 95% CI [−0.159, +0.690] |
| Coverage 50 / 80 / 90 | 0.45 / 0.85 / 0.90 |
| PIT mean / SD | 0.500 / 0.294 |
| PIT 5-bin counts | [4, 4, 4, 5, 3] |
| CRPS-optimal scale f\* | 0.90, 90% bootstrap [0.70, 1.15] |
| CRPS vs climatology | 3.832 vs 4.280 |

**The clustered SE is smaller than the naive SE here, and that is a finding, not a rounding
artefact.** The two teams of a game have strongly negatively correlated carry errors:
corr(e_home, e_away) = **−0.802** in this sample. Historically the two teams' realised carries
correlate **−0.578 / −0.436 / −0.533 / −0.558** in 2021–2024. A game has one clock and one set
of leads; the team that runs a lot is playing the team that does not. Clustering by game
therefore *reduces* the variance of the pooled mean for this quantity rather than inflating it.
An analysis that used naive SEs would be conservative for carries and anti-conservative for
targets and dropbacks (below). Both directions are wrong; the cluster is not optional.

---

## 4. TARGETS — `team_volume/team_targets` (PROVISIONAL, see §1a)

Point estimator: **`ewma`**, form `coach_empirical`.

| Statistic | Value |
|---|---|
| n team-games / n games | 20 / 10 |
| Mean forecast / mean realised | 29.996 / 29.900 |
| **Bias** | **+0.096** |
| SE clustered by game / naive | **1.795** / 1.699 |
| z (cluster) | +0.05 |
| 95% bootstrap CI on bias | [−3.71, +3.11] |
| MAE / RMSE | 5.810 / 7.408 |
| SD of forecast means / SD realised | 3.855 / 7.893 |
| **SD ratio** | **0.488** (the highest of the four) |
| Mean predictive SD | 7.697 |
| **Pearson r** | **+0.319**, 95% CI [−0.014, +0.529] |
| Coverage 50 / 80 / 90 | 0.60 / 0.85 / 0.95 |
| PIT mean / SD | 0.483 / 0.280 |
| PIT 5-bin counts | [4, 5, 2, 6, 3] |
| CRPS-optimal scale f\* | 0.85, 90% bootstrap [0.60, 1.15] |
| CRPS vs climatology | 4.155 vs 4.549 |

Within-game realised correlation here is **+0.376** in this sample against a historical
**−0.10 to −0.19**; n = 10 games, so this is noise, not a reversal.

---

## 5. DROPBACKS — `team_volume/team_dropbacks_part` (PROVISIONAL, one-sided surrogate)

Point estimator: **`coach_prior`**, form `coach_empirical`. The realisation used is the pbp
dropback count with two-point attempts removed, which `actuals.py` declares an **upper bound**
on the participation-matched quantity forecast. So the true bias is **at least** as positive
as the figure below; the surrogate cannot make the forecast look too high when it is not.

| Statistic | Value |
|---|---|
| n team-games / n games | 20 / 10 |
| Mean forecast / mean realised (upper-bound surrogate) | 36.469 / 35.800 |
| **Bias (lower bound on the true bias)** | **+0.669** |
| SE clustered by game / naive | **2.110** / 1.892 |
| z (cluster) | +0.32 |
| 95% bootstrap CI on bias | [−3.46, +4.31] |
| MAE / RMSE | 6.213 / 8.274 |
| SD of forecast means / SD realised | 2.410 / 8.776 |
| **SD ratio** | **0.275** |
| Mean predictive SD | 8.367 |
| **Pearson r** | **+0.266**, 95% CI [−0.032, +0.577] |
| Coverage 50 / 80 / 90 | 0.50 / 0.85 / 0.95 |
| PIT mean / SD | 0.463 / 0.281 |
| PIT 5-bin counts | [5, 4, 4, 4, 3] |
| CRPS-optimal scale f\* | 0.85, 90% bootstrap [0.65, 1.20] |
| CRPS vs climatology | 4.570 vs 5.025 |

---

## 6. Mean calibration: what can and cannot be asserted

Failing to reject a zero bias is not evidence of adequacy. A two-one-sided test was run with
an equivalence margin **δ = 0.25 × SD(realised)** for each quantity, one-sided α = 0.05,
t with 9 df (G = 10 clusters). **This margin was chosen after the data were seen, so this TOST
is exploratory and cannot be quoted as a confirmatory equivalence result.**

| Quantity | bias | SE(cluster) | δ | t_lo | t_hi | Verdict |
|---|---|---|---|---|---|---|
| PLAYS(C) | −0.922 | 2.423 | 2.511 | 0.66 | 1.42 | not shown equivalent |
| **CARRIES** | +0.231 | 0.650 | 1.753 | 3.05 | 2.34 | **equivalent to zero within ±1.75** |
| TARGETS | +0.096 | 1.795 | 1.973 | 1.15 | 1.05 | not shown equivalent |
| DROPBACKS | +0.669 | 2.110 | 2.194 | 1.36 | 0.72 | not shown equivalent |

So: **carries is demonstrably unbiased within a quarter of a game-to-game SD. The other three
are merely not-rejected, which is a statement about power at n = 20, not about the model.**

---

## 7. Dispersion calibration: too wide, too narrow, or neither

Two different questions, and they get different answers.

**At the declared row axis (`team`) the predictive distributions are honest.** PIT means sit
at 0.46–0.50, PIT 5-bin counts are close to flat, coverage tracks nominal, and the CRPS-optimal
rescaling factor f\* is 0.85–1.25 with a game-cluster bootstrap interval covering 1.00 in every
case. Neither C nor D applies at the team margin. The only hint of anything is PLAYS(C), whose
f\* interval starts at exactly 1.00 — a nudge toward *too narrow*, not a finding.

**At the game aggregate the carries distribution is badly over-dispersed, and this one is
decisive.** Summing the two teams' draws column-wise (which is the model's own law, because the
manifest declares rows seeded independently):

| Quantity | predictive SD of game total | realised SD | ratio | cov 50 | cov 80 | cov 90 | f\* |
|---|---|---|---|---|---|---|---|
| PLAYS(C) | 9.35 | 14.88 | 0.63 | 0.60 | 0.70 | 0.80 | 1.20 |
| **CARRIES** | **9.75** | **4.08** | **2.39** | **1.00** | **1.00** | **1.00** | **0.45** |
| TARGETS | 10.14 | 13.00 | 0.78 | 0.50 | 0.80 | 0.90 | 0.90 |
| DROPBACKS | 10.87 | 13.19 | 0.82 | 0.50 | 0.80 | 0.80 | 1.05 |

Ten games out of ten fall inside the nominal 50% interval for game-total carries. Under a
calibrated predictive that has probability 0.5^10 ≈ 0.001. The mechanism is known and already
documented in the module: the two teams of a game are drawn independently, while their realised
carries correlate −0.44 to −0.58. `nfl/production/team_volume_v1.py` names this as A3G and
ships it **off by default** (`GAME_COUPLING_DEFAULT = 'none'`) pending an owner decision. This
return does not propose turning it on; it records that the game-aggregate consequence is now
measured prospectively and is large.

---

## 8. Game-level error

Two teams summed per game, n = 10 games.

| Quantity | bias | SE | t | MAE | RMSE | SD pred means | SD realised | r | corr(e_home, e_away) |
|---|---|---|---|---|---|---|---|---|---|
| PLAYS(C) | −1.844 | 4.845 | −0.38 | 10.25 | 14.65 | 3.52 | 14.88 | −0.010 | +0.053 |
| CARRIES | +0.461 | 1.300 | +0.35 | 3.81 | 3.93 | 2.66 | 4.08 | +0.314 | **−0.802** |
| TARGETS | +0.191 | 3.589 | +0.05 | 7.94 | 10.77 | 5.08 | 13.00 | +0.500 | +0.080 |
| DROPBACKS | +1.338 | 4.219 | +0.32 | 9.68 | 12.73 | 3.66 | 13.19 | +0.097 | +0.268 |

---

## 9. Team-level systematic bias

**Not identified, and saying otherwise would be inventing precision.** Each of the 20 teams
appears exactly once. A per-team bias estimate at n = 1 is the single error, and its standard
error is the full predictive width — 6.2 to 9.6 units depending on the quantity.

What is computable is a home/away split, cluster-robust by game:

| Quantity | home bias | away bias | difference | SE | t |
|---|---|---|---|---|---|
| PLAYS(C) | +0.623 | −2.466 | +3.089 | 4.494 | +0.69 |
| CARRIES | +1.636 | −1.175 | +2.811 | 3.999 | +0.70 |
| TARGETS | +1.049 | −0.857 | +1.906 | 3.331 | +0.57 |
| DROPBACKS | +0.942 | +0.396 | +0.547 | 3.520 | +0.16 |

All four differences lean the same way and none is distinguishable from zero. This split cannot
establish anything and must not be quoted as a finding.

Per team-game errors (forecast mean − realised) are listed in full in §14 so that a later pass
with more games can extend rather than re-derive them.

---

## 10. Season drift

Two independent views agree on direction.

**(a) The fitted panel** (`nfl/research/inputs/denom_panel.csv.gz`, 3,230 team-games,
2020–2025), on the definitions the model was fitted to:

| Season | team_off_snaps | team_dropbacks_part | team_targets | team_carries | team_rz_carries |
|---|---|---|---|---|---|
| 2020 | 67.145 | 38.930 | 33.807 | 26.938 | 4.902 |
| 2021 | 66.360 | 38.233 | 33.195 | 26.642 | 4.651 |
| 2022 | 65.786 | 37.288 | 31.930 | 27.251 | 4.511 |
| 2023 | 65.912 | 38.039 | 32.138 | 26.849 | 4.700 |
| 2024 | 65.393 | 36.978 | 31.274 | 26.998 | 4.783 |
| 2025 | **64.237** | **36.276** | **30.531** | 26.840 | 4.761 |
| drift 2020→2025 | −2.91 | −2.65 | −3.28 | **−0.10** | −0.14 |

**(b) Play-by-play, recomputed like-for-like** on the `actuals.py` definitions, REG only:

| Frame | plays(C) | targets | carries | dropbacks | scrimmage plays/game |
|---|---|---|---|---|---|
| 2021 full | 67.81 | 33.39 | 26.72 | 38.23 | 126.65 |
| 2022 full | 67.21 | 32.09 | 27.31 | 37.29 | 125.96 |
| 2023 full | 67.47 | 32.28 | 26.93 | 38.04 | 126.22 |
| 2024 full | 67.00 | 31.44 | 27.06 | 36.98 | 124.31 |
| 2021 wk1 | 70.22 | 35.66 | 25.81 | 40.69 | 129.88 |
| 2022 wk1 | 69.28 | 34.62 | 26.22 | 39.94 | 128.50 |
| 2023 wk1 | 68.41 | 32.53 | 27.34 | 38.59 | 127.38 |
| 2024 wk1 | 65.12 | 29.50 | 27.50 | 35.47 | 120.56 |
| **2026 wk1** | **66.80** | **29.90** | **27.35** | **35.80** | **122.20** |

Targets, dropbacks and plays drift down; **carries are flat**. That matters for the estimator
selections, because they differ in how they track a drifting level:

* `team_targets` → `ewma`: tracks the drift. Observed bias +0.10. Consistent.
* `team_carries` → `coach_prior`: the series is flat, so pooling history costs nothing.
  Observed bias +0.23, the only one shown equivalent to zero.
* `team_dropbacks_part` → `coach_prior`: pools a drifting series. Observed bias **+0.67**,
  correct sign for a lagging level, not significant at n = 20.
* `team_off_snaps` → `league_mean` over **all** prior history (`_fit_for` takes the mean of
  every row with `ord < ordinal`). Its 65.88 sits 1.64 above the 2025 panel mean of 64.24 —
  again the right sign for a lagging level, again not separable at n = 20.

**The drift-lag hypothesis is directionally consistent for all four quantities and statistically
established for none of them.** It is a hypothesis for a pre-registration, not a diagnosis this
sample supports.

---

## 11. Pace

Per team-game, 2026 week 1 (`drive_time_of_possession` summed over a team's drives, divided by
its scrimmage plays):

| Game | Team | scrimmage | drives | sec/play | no-huddle | final margin |
|---|---|---|---|---|---|---|
| ATL@PIT | ATL | 57 | 13 | 32.75 | 2 | −7 |
| ATL@PIT | PIT | 64 | 14 | 27.08 | 4 | +7 |
| BAL@IND | BAL | 64 | 13 | 33.12 | 2 | +18 |
| BAL@IND | IND | 53 | 12 | 27.92 | 7 | −18 |
| BUF@HOU | BUF | 52 | 12 | 27.37 | 1 | +5 |
| BUF@HOU | HOU | 73 | 11 | 29.82 | 6 | −5 |
| CHI@CAR | CAR | 62 | 13 | 25.11 | 5 | −22 |
| CHI@CAR | CHI | 70 | 14 | 29.19 | 4 | +22 |
| CLE@JAX | CLE | 49 | 9 | 32.02 | 2 | −24 |
| CLE@JAX | JAX | 56 | 9 | 36.27 | 4 | +24 |
| NE@SEA | NE | 67 | 9 | 30.70 | 0 | −3 |
| NE@SEA | SEA | 48 | 10 | 32.15 | 1 | +3 |
| NO@DET | DET | 73 | 15 | 30.29 | 1 | +1 |
| NO@DET | NO | 86 | 14 | 22.03 | 20 | −1 |
| NYJ@TEN | NYJ | 63 | 11 | 36.92 | 1 | +13 |
| NYJ@TEN | TEN | 49 | 10 | 26.00 | 11 | −13 |
| SF@LA | LA | 57 | 10 | 27.54 | 7 | −20 |
| SF@LA | SF | 64 | 9 | 31.72 | 0 | +20 |
| TB@CIN | CIN | 63 | 10 | 29.92 | 3 | +6 |
| TB@CIN | TB | 52 | 10 | 32.98 | 5 | −6 |

League scrimmage plays per game: 126.65 (2021) → 125.96 → 126.22 → 124.31 (2024) → **122.20**
(2026 wk1). The model has **no pace input of any kind** — no seconds-per-play, no no-huddle
rate, no drive count. Pace enters only through whatever pace is embedded in a coach's residual
pool. NO ran 86 scrimmage plays at 22.03 sec/play with 20 no-huddle snaps against a 64.33
forecast; that single team-game is the largest miss in every one of the four quantities
(−25.7 plays, −22.3 targets, −24.7 dropbacks) and its carries error is **+0.9**. A pace shock
moves the passing-side quantities and leaves carries alone.

---

## 12. Neutral-script volume

Neutral script defined as |score differential| ≤ 7 and quarter ≤ 3.

| Season | n team-games | scrimmage plays | neutral plays | neutral share | carries | neutral carries | targets | neutral targets |
|---|---|---|---|---|---|---|---|---|
| 2021 | 544 | 63.33 / 8.59 | 31.40 / 13.34 | 0.496 | 26.72 / 7.78 | 13.54 / 6.52 | 33.39 / 8.29 | 16.24 / 8.08 |
| 2022 | 542 | 62.98 / 8.29 | 33.22 / 13.06 | 0.527 | 27.31 / 7.78 | 14.79 / 6.94 | 32.09 / 8.53 | 16.50 / 7.36 |
| 2023 | 544 | 63.11 / 8.28 | 32.33 / 13.35 | 0.512 | 26.93 / 7.51 | 13.88 / 6.86 | 32.28 / 7.23 | 16.52 / 7.64 |
| 2024 | 544 | 62.15 / 8.18 | 31.85 / 13.50 | 0.512 | 27.06 / 7.53 | 14.04 / 6.55 | 31.44 / 7.70 | 15.99 / 7.73 |
| **2026 wk1** | 20 | 61.10 / 9.75 | 31.20 / 14.92 | 0.511 | 27.35 / 7.01 | 13.90 / 7.84 | 29.90 / 7.89 | 15.30 / 7.91 |

Roughly half of all volume occurs in neutral script, and that share is stable to within one
percentage point across five seasons — **including 2026 week 1, which is therefore not a
script-abnormal sample.**

Normalising to a per-60-neutral-play rate removes part, but only part, of the dispersion
(coefficient of variation, team-games with ≥20 neutral plays):

| Season | CV plays | CV carries | CV targets | CV carries per 60 neutral | CV targets per 60 neutral |
|---|---|---|---|---|---|
| 2021 | 0.130 | 0.269 | 0.247 | 0.242 | 0.200 |
| 2022 | 0.129 | 0.272 | 0.269 | 0.240 | 0.216 |
| 2023 | 0.126 | 0.266 | 0.222 | 0.231 | 0.196 |
| 2024 | 0.127 | 0.260 | 0.234 | 0.216 | 0.184 |
| 2026 | 0.165 | 0.260 | 0.271 | 0.244 | 0.215 |

Script normalisation cuts the target CV by roughly a fifth and the carry CV by roughly a sixth.
Most of the between-team-game dispersion survives it.

---

## 13. Score-state dependence — POSTGAME DIAGNOSTIC ONLY

**This section conditions on realised in-game state. It is a diagnostic of where the variance
lives. Nothing here is a pregame feature, and nothing here defines a defect on its own,
because a residual regressed on an outcome-determined regressor will find structure for any
pregame forecaster, including a perfect one.**

Realised quantity regressed on the team's own in-game state counts, cluster-robust by game,
2026 week 1 (n = 20, G = 10):

| Quantity | slope on snaps trailing by ≥9 | t | slope on snaps leading by ≥9 | t |
|---|---|---|---|---|
| PLAYS(C) | −0.275 | **−6.06** | +0.079 | +0.86 |
| CARRIES | −0.289 | **−3.22** | +0.269 | **+3.23** |
| TARGETS | −0.037 | −0.65 | −0.123 | −1.22 |
| DROPBACKS | +0.030 | +0.44 | −0.199 | **−2.01** |

Signs are the football ones: leading teams run more and drop back less; trailing teams run less.

Pooled 2021–2024 (2,174 REG team-games), R² of realised volume on three in-game script
counts (neutral plays, snaps trailing by ≥9, snaps leading by ≥9):

| Quantity | SD | R² on in-game script |
|---|---|---|
| plays | 8.344 | **0.430** |
| carries | 7.650 | **0.336** |
| targets | 7.977 | **0.268** |
| dropbacks | 8.503 | **0.330** |

**The decisive comparison is against what a pregame model could reach.** One-way variance
decomposition on team-within-season over the same 2,174 team-games, with ω² correcting η² for
within-group sampling noise:

| Quantity | η² | ω² | **ceiling r = √ω²** | model r (2026 wk1) | r(market total) | r(\|market spread\|) |
|---|---|---|---|---|---|---|
| plays | 0.1045 | 0.0489 | **0.221** | **+0.000** | +0.078 | −0.015 |
| carries | 0.1521 | 0.0994 | **0.315** | **+0.327** | −0.077 | −0.004 |
| targets | 0.1967 | 0.1467 | **0.383** | **+0.319** | +0.179 | −0.002 |
| dropbacks | 0.1655 | 0.1136 | **0.337** | **+0.266** | +0.152 | −0.005 |

Team identity — which is all this layer's `coach_prior` and `ewma` estimators can encode —
caps achievable correlation at **0.22 to 0.38**. Carries, targets and dropbacks are already
at or statistically indistinguishable from that cap. Plays is at zero against a cap of 0.22.

**A hypothesis I raised and then withdrew.** On the 20-game sample the pregame market total
correlated +0.352 with plays, +0.463 with targets and +0.388 with dropbacks, and the residual
leaned negative on it (t = −1.45 to −1.76), which reads as a missing pregame feature. Extended
to the 2,174 historical team-games the same correlations are **+0.078, +0.179, +0.152**. The
week-1 estimate was inflated roughly 2.5×. The market total is a real but small pregame signal
for the passing-side quantities and is worth nothing for carries; the strong version of the
claim is **withdrawn** and must not be reused.

---

## 14. Per team-game errors (forecast mean − realised)

| Game | Team | PLAYS(C) fc / act / err | CARRIES fc / act / err | TARGETS fc / act / err | DROPBACKS fc / act / err |
|---|---|---|---|---|---|
| NE@SEA | NE | 64.5 / 74 / −9.5 | 29.3 / 31 / −1.7 | 27.0 / 31 / −4.0 | 34.0 / 42 / −8.0 |
| NE@SEA | SEA | 63.6 / 56 / +7.6 | 27.7 / 22 / +5.7 | 27.6 / 24 / +3.6 | 31.5 / 27 / +4.5 |
| SF@LA | LA | 65.7 / 62 / +3.7 | 26.6 / 29 / −2.4 | 36.2 / 27 / +9.2 | 36.0 / 29 / +7.0 |
| SF@LA | SF | 64.5 / 65 / −0.5 | 28.3 / 30 / −1.7 | 29.8 / 34 / −4.2 | 33.9 / 36 / −2.1 |
| ATL@PIT | ATL | 67.3 / 61 / +6.3 | 29.4 / 31 / −1.6 | 29.1 / 19 / +10.1 | 34.5 / 26 / +8.5 |
| ATL@PIT | PIT | 70.9 / 70 / +0.9 | 28.0 / 21 / +7.0 | 34.4 / 37 / −2.6 | 39.7 / 43 / −3.3 |
| BAL@IND | BAL | 65.8 / 71 / −5.2 | 27.0 / 37 / −10.0 | 21.1 / 24 / −2.9 | 37.0 / 29 / +8.0 |
| BAL@IND | IND | 64.9 / 55 / +9.9 | 27.9 / 20 / +7.9 | 31.3 / 29 / +2.3 | 34.1 / 34 / +0.1 |
| BUF@HOU | BUF | 67.7 / 57 / +10.7 | 30.7 / 21 / +9.7 | 26.5 / 29 / −2.5 | 36.3 / 32 / +4.3 |
| BUF@HOU | HOU | 66.7 / 81 / −14.3 | 26.8 / 32 / −5.2 | 29.9 / 37 / −7.1 | 38.2 / 42 / −3.8 |
| CHI@CAR | CAR | 61.3 / 70 / −8.7 | 26.1 / 22 / +4.1 | 25.9 / 34 / −8.1 | 34.0 / 43 / −9.0 |
| CHI@CAR | CHI | 68.2 / 77 / −8.8 | 30.9 / 39 / −8.1 | 31.6 / 26 / +5.6 | 38.0 / 38 / −0.0 |
| CLE@JAX | CLE | 66.3 / 55 / +11.3 | 27.0 / 22 / +5.0 | 26.6 / 22 / +4.6 | 37.4 / 30 / +7.4 |
| CLE@JAX | JAX | 67.1 / 62 / +5.1 | 29.7 / 32 / −2.3 | 31.6 / 21 / +10.6 | 37.5 / 24 / +13.5 |
| NO@DET | DET | 67.1 / 79 / −11.9 | 29.1 / 33 / −3.9 | 35.7 / 39 / −3.3 | 36.5 / 41 / −4.5 |
| NO@DET | NO | 64.3 / 90 / **−25.7** | 25.9 / 25 / **+0.9** | 30.7 / 53 / **−22.3** | 37.3 / 62 / **−24.7** |
| NYJ@TEN | NYJ | 61.8 / 71 / −9.2 | 26.3 / 39 / −12.7 | 27.6 / 23 / +4.6 | 35.0 / 26 / +9.0 |
| NYJ@TEN | TEN | 64.7 / 52 / +12.7 | 23.1 / 14 / +9.1 | 31.4 / 28 / +3.4 | 39.3 / 39 / +0.3 |
| TB@CIN | CIN | 67.3 / 66 / +1.3 | 23.3 / 27 / −3.7 | 36.5 / 34 / +2.5 | 41.6 / 37 / +4.6 |
| TB@CIN | TB | 67.8 / 62 / +5.8 | 28.5 / 20 / +8.5 | 29.4 / 27 / +2.4 | 37.7 / 36 / +1.7 |

---

## 15. Classification

# **A — unbiased but noisy**

Applied to the layer at the estimand and row axis it actually declares: per-team, per-game
volume, `row_axis: team`.

**The positive case.**
* Mean bias is small for all four quantities: −0.92, +0.23, +0.10, +0.67, every |z| ≤ 0.38
  clustered by game. For carries — the one quantity whose estimand is EXACT and fully
  scoreable — the bias is shown equivalent to zero within ±1.75 by TOST.
* Marginal dispersion is honest. PIT means 0.46–0.50, PIT histograms close to flat, coverage
  near nominal at 50/80/90, and the CRPS-optimal rescaling f\* has a bootstrap interval
  covering 1.00 for all four.
* The model beats a climatological reference on CRPS for all four (3.83 vs 4.28; 4.16 vs 4.55;
  4.57 vs 5.02; 5.85 vs 6.10), so the draws carry information rather than merely being wide.
* Discrimination is low — r = 0.00 to 0.33 — but for carries, targets and dropbacks it is at
  the ceiling a team-identity model can reach (√ω² = 0.315, 0.383, 0.337 on 2,174 team-games).
  Noisy is the correct word for that: the residual variance is mostly not team-attributable.

**B — biased: ruled out.** No quantity shows a bias distinguishable from zero, clustered by
game, and the only quantity whose estimand is unambiguous passes a TOST. The one apparently
massive bias — PLAYS at −16.52 with z = −5.35 — is entirely an artefact of reconstructing the
snap-count estimand as "every pbp row with a posteam"; the same forecast is −0.92 against the
nearest identified construction. A bias that changes sign with the definition of the realisation
is a definition finding, not a model finding.

**C — under-dispersed: ruled out.** Coverage would run below nominal and PIT would pile up in
the tail bins. Observed coverage at 90% is 0.90, 0.95, 0.95 and 0.90; f\* point estimates for
carries, targets and dropbacks are **below** 1 (0.90, 0.85, 0.85), which is the opposite
direction. The only trace of narrowness is PLAYS(C) at f\* = 1.25 with a bootstrap interval
starting exactly at 1.00, which is not a rejection.

**D — over-dispersed: ruled out at the declared estimand, CONFIRMED at the game aggregate.**
At the team margin no f\* interval excludes 1. At the game total, carries is over-dispersed by
a factor of 2.39 with 10/10 games inside the nominal 50% interval (p ≈ 0.001) and f\* = 0.45.
That is a real, mechanistically explained defect — the two teams are drawn independently while
their realised carries correlate −0.44 to −0.58 — but it is a property of the **joint across
rows**, not of the per-team predictive the layer declares. It is recorded below as a separate
CONFIRMED finding rather than as the layer's classification, and `team_volume_v1.py` already
names the mechanism (A3G) and ships it off by default pending an owner decision.

**E — structurally conditional on missing game-state variables: the closest rival, and
rejected.** The evidence for E is real: in-game script explains 27–43% of realised volume
variance over 2,174 team-games, against a team-identity ceiling of only 5–15%, and the 2026
residuals move with realised lead/trail snaps exactly as football predicts (carries residual on
lead-9 snaps t = −3.90). But the variables carrying that structure are **realised during the
game and unobservable at seal time**. Calling the layer "structurally conditional on missing
variables" would assert that a pregame model could have had them. The one class of pregame
observables I could test — the market total and spread carried in the play-by-play — carries
r = +0.078 to +0.179 for the passing-side quantities and essentially zero for carries across
2,174 team-games, nowhere near enough to lift discrimination off its ceiling. E would be the
right classification for a *within-game* volume model. For this pregame layer it would convert
an outcome-conditioned regression into a defect, which is precisely the inference that
manufactures defects for any forecaster including a correct one.

**On the layer's own warning.** `team_volume_is_near_unforecastable` is **broadly confirmed and
slightly overstated as phrased.** The layer is not unforecastable — it beats climatology on
CRPS on all four quantities and reaches its team-identity ceiling on three. What is true is
that the ceiling itself is low (r ≈ 0.22–0.38) and that the layer is already at it, so further
work on team-identity estimators has little left to win. The one quantity with real headroom is
PLAYS, which sits at r = 0.000 against a ceiling of 0.221 because `league_mean` encodes no team.

---

## 16. Finding table

| # | Finding | Verdict | Evidence |
|---|---|---|---|
| 1 | The team-volume draws are byte-identical across every sealed board of a game (all cutoffs, all candidates R5–R8, all replays), so candidate multiplicity is not evidence multiplicity | **CONFIRMED** | SHA-256 over raw arrays, 106 board dirs, 10 completed games; only NE@SEA differs, and those are two declared replication runs |
| 2 | Mean bias is not distinguishable from zero for all four quantities, clustered by game | **CONFIRMED** | biases −0.92 / +0.23 / +0.10 / +0.67; \|z\| ≤ 0.38; bootstrap CIs all cover 0 |
| 3 | Carries is unbiased in the stronger sense of a two-one-sided equivalence test | **PARTIAL** | TOST passes at δ = ±1.75 (t_lo 3.05, t_hi 2.34); margin chosen after seeing the data, so exploratory |
| 4 | The other three quantities are unbiased | **UNRESOLVED** | TOST fails for PLAYS, TARGETS, DROPBACKS; this is a power statement at n = 20, not a model statement |
| 5 | Marginal (per-team) dispersion is calibrated — neither too wide nor too narrow | **CONFIRMED** | PIT means 0.46–0.50, flat 5-bin histograms, coverage ≈ nominal, every f\* bootstrap interval covers 1.00 |
| 6 | The game-total carries distribution is over-dispersed | **CONFIRMED** | predictive SD 9.75 vs realised 4.08 (ratio 2.39); 10/10 inside the 50% interval, p ≈ 0.001; f\* = 0.45; mechanism is independent row draws against a historical within-game correlation of −0.44 to −0.58 |
| 7 | The PLAYS estimand cannot be realised from play-by-play, and the choice of reconstruction, not the model, determines the bias | **CONFIRMED** | same forecast gives bias −16.52 (z −5.35), +4.78 and −0.92 under three defensible constructions |
| 8 | The "LA ran 57 plays against a 65.65 forecast" miss in `postgame.py`'s docstring is an estimand artefact | **CONFIRMED** | LA realised 74 / 57 / 62 under constructions A / B / C against a snap-count forecast of 65.65 |
| 9 | PLAYS has zero discrimination against a non-zero attainable ceiling | **CONFIRMED** | r = +0.0002, 95% CI [−0.231, +0.204], against ceiling √ω² = 0.221; `league_mean` encodes no team identity |
| 10 | Carries, targets and dropbacks are at the team-identity discrimination ceiling | **PARTIAL** | model r 0.327 / 0.319 / 0.266 vs ceilings 0.315 / 0.383 / 0.337; the model CIs are wide (n = 20) so "at the ceiling" is consistent with the data, not demonstrated by it |
| 11 | The layer is biased high because `league_mean` / `coach_prior` lag a downward season drift | **UNRESOLVED** | drift is real (targets −3.28, dropbacks −2.65, snaps −2.91 over 2020→2025; carries flat −0.10) and the bias signs match for all four, but no bias is significant at n = 20 |
| 12 | The pregame market total is a materially missing feature for the passing-side quantities | **FALSIFIED (strong form)** | r = +0.35 to +0.46 at n = 20 collapses to +0.078 / +0.179 / +0.152 on 2,174 team-games; a small real effect for targets and dropbacks, none for carries; the strong claim is withdrawn |
| 13 | Home/away is a systematic bias axis for this layer | **FALSIFIED** | all four differences t ≤ +0.70; the split cannot distinguish anything |
| 14 | Per-team systematic bias | **UNRESOLVED — NOT IDENTIFIED** | one game per team; a per-team bias estimate at n = 1 has SE equal to the full predictive width (6.2–9.6 units) |
| 15 | Realised team volume is strongly conditional on in-game score state, which the layer cannot see | **CONFIRMED as a diagnostic only** | R² 0.27–0.43 on in-game script over 2,174 team-games vs a team-identity ω² of 0.05–0.15; never a pregame feature, and not a defect definition |
| 16 | The layer has no pace input | **CONFIRMED** | no seconds-per-play, no-huddle or drive-count term anywhere in `team_volume_v1.py`; NO ran 86 scrimmage plays at 22.03 s/play with 20 no-huddle snaps against a 64.33 forecast, the largest miss in three of four quantities and a +0.9 miss in carries |
| 17 | 2026 week 1 is script-abnormal and therefore an unrepresentative test window | **FALSIFIED** | neutral-script share 0.511 against 0.496 / 0.527 / 0.512 / 0.512 in 2021–2024 |

---

## 17. Evidence ceiling

**Everything above is bounded by these, and none of them is fixable by better analysis of the
bytes in this checkout.**

1. **Ten games. Twenty team-games. One week.** Every bias CI is 6–8 units wide. Every
   correlation CI spans roughly ±0.35. This sample can detect a bias of about 0.7 SD and a
   correlation of about 0.45, and nothing smaller. Findings 3, 4, 10 and 11 are all limited by
   exactly this and by nothing else.
2. **Clusters, not rows.** G = 10. Cluster-robust inference with ten clusters is itself
   imprecise, and with the strong within-game negative correlation in carries the effective
   sample for that quantity is closer to ten than twenty.
3. **Monte Carlo noise in the forecast itself.** Boards carry 1,000 draws (the DAL@NYG boards
   carry 8,000, but DAL@NYG has no outcome). The NE@SEA replication pair differs by
   −0.14 / −0.51 in the plays mean, **+0.60 / −1.36 in the carries mean**, −0.21 / +0.61 in
   targets and +0.24 / +0.51 in dropbacks. **The measured carries bias of +0.23 is smaller than
   the Monte Carlo noise in a single team's predictive mean.** A bias estimate at this n cannot
   be separated from the draw count.
4. **Three of the four quantities are not officially scoreable.** `postgame.py` refuses
   `team_off_snaps`, `team_dropbacks_part` and `team_targets` by name. Targets and dropbacks are
   reported here as PROVISIONAL and must not be promoted into the ledger on this basis. For
   dropbacks the surrogate is a one-sided bound, so the true bias is at least +0.67 and the
   sign of the gap is known while its size is not.
5. **PLAYS has no realisation at all.** The `snap_counts` feed is not in this checkout and is
   not derivable from play-by-play. Every PLAYS number in this return is conditional on a
   reconstruction I chose, and §1b shows how much that choice moves the answer.
6. **The participation feed is BLOCKED in this environment**, which is what forces the dropback
   surrogate. That is an external-data request, not a repository problem.
7. **Team-level bias is not identified at n = 1 game per team** and will not be until a team
   has several graded games.
8. **The historical panel and the 2026 outcomes are not the same construction.** Season-drift
   direction is corroborated by two independent builds (the fitted panel and a like-for-like
   play-by-play recomputation), but the *level* comparison between a snap-count panel mean and a
   play-by-play reconstruction is not like-for-like and is not used as evidence anywhere above.
9. **2026 week 1 only.** Week 1 volume differs from the season mean in every historical year
   (2021 wk1 targets 35.66 vs 33.39 full-season). Comparisons above use week-1 rows of prior
   seasons wherever the level matters, but no amount of care makes one week a season.
10. **The ω² ceiling is itself an estimate** on 2,174 team-games with ~17 games per team-season.
    It corrects η² for within-group noise, but it assumes team-within-season is the right
    grouping; a model with opponent, personnel or scheme content could exceed it.

---

## 18. What this return does NOT propose

No repair is proposed. Finding 6 (game-total carries over-dispersion) is the only CONFIRMED
defect with a known mechanism and a ready switch, and that switch — `game_coupling` / A3G — is
documented in `team_volume_v1.py` as an owner decision precisely because turning it on changes
every drawn number while changing no fit. Finding 9 (PLAYS discrimination at zero) is a
selection made by the frozen walk-forward research and re-selecting an estimator in production
is what the P4B packet forbids. Finding 7 (the PLAYS estimand) is a data-availability question,
not a code question.

**CODE CHANGED: NO.**

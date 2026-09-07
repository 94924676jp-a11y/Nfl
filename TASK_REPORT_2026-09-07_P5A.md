# P5A — Carry → rushing yards: skill vs context vs noise

**Status:** complete. Historical quarantined research only. Nothing authorised,
enabled or promoted.

---

## The answer in one paragraph

**Rushing-yard uncertainty is about 3:1 carries over conversion.** Knowing the
realised carry count improves downstream CRPS by **50.9%**; knowing per-carry
efficiency perfectly improves it by **16.2%**. Against that, the whole
efficiency ladder buys **0.93%** — real, bootstrap-significant in 4 of 4
seasons, and small. **Player efficiency is the only rung that contributes**;
team context adds 0.02% and opponent defence 0.01%, and the shrinkage
constants — fitted on prior seasons with no sight of the evaluation year —
say so independently by shrinking team and opponent signal to the grid maximum.
**Raw and recency-weighted player efficiency are worse than a pooled prior.**
Only empirical-Bayes shrinkage beats pooling. **A separate explosive-run
component does not help.** And R6's external hypotheses, reproduced internally
rather than imported, come out mostly the other way round.

---

## 1. HEAD at task start

`74e327d` — "P4D return". Working tree clean, `main` level with `origin/main`.

## 2. Commits

| commit | content |
|---|---|
| `7b2f7a8` | P5A pre-declaration and data-availability audit |
| `fb18a8f` | P5A research: carry to rushing yards, skill vs context vs noise |
| *(this report)* | `TASK_REPORT_2026-09-07_P5A.md` |

## 3. Files

All under `nfl/research/p5a/`: `predeclaration_p5a.md`, `extract_carries.py`,
`audit.py` / `audit.json`, `p5a_build.py`, `p5a_lib.py`, `run_p5a.py`,
`run_p5a_skill.py`, `run_p5a_tail.py`, `run_p5a_pfr.py`,
`run_p5a_adversarial.py`, results `p5a_results.json`, `p5a_skill.json`,
`p5a_tail.json`, `p5a_pfr.json`, `p5a_adversarial.json`, and five run logs.

## 4. Pre-declaration

`nfl/research/p5a/predeclaration_p5a.md`, committed in `7b2f7a8` **before**
`p5a_lib.py` existed. It fixes the estimand, the carry definition, the
chronology, the explosive cutoff, the threshold grid, the control, the ladder,
the shrinkage protocol, the family space, the metric set, the oracle
quarantine, and the selection rule. Departures: none.

## 5. Chronology design

Strict walk-forward. For evaluation season *Y* every parameter — pooled
conversion distribution, empirical-Bayes constants, ridge coefficients — is
fitted on seasons `< Y`. Within-season player, team and opponent accumulators
are **read before they are updated**, which is the whole chronology guarantee
and is proved load-bearing by guard-deletion probe 13. Carry-level history
reaches back to 2016; the opportunity panel remains 2020–2025.

## 6. Estimand

`rushing_yards_i` = the sum of the player's per-carry yardage, where the carry
count comes from the **accepted** P4C joint allocation (system C, reserved
stochastic mass) with the incumbent appearance model. The forecast is a
**compound distribution**, not a game-level Gaussian. Yards per carry is a
candidate predictor and a diagnostic; it is never the forecasting target. No
fantasy points, receiving, receptions, passing or touchdowns.

## 7. Data availability audit

**The carry table reproduces the accepted panel exactly: 0 mismatches over
83,144 player-games.** The P4C carry distribution and the P5A conversion layer
are the same object, checked rather than assumed.

Per-carry yardage, 140,678 carries, 2016–2025:

| season | n | mean | sd | skew | ex. kurtosis | P(≤0) | P(≥10) | P(≥20) | p99 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| 2016 | 13,320 | 4.186 | 6.319 | 3.93 | 28.6 | 0.214 | 0.110 | 0.024 | 28.0 | 85 |
| 2020 | 13,792 | 4.413 | 6.349 | 4.10 | 32.0 | 0.189 | 0.118 | 0.025 | 29.0 | 98 |
| 2022 | 14,770 | 4.461 | 6.359 | 3.74 | 25.6 | 0.194 | 0.117 | 0.026 | 30.0 | 86 |
| 2024 | 14,687 | 4.436 | 6.298 | 3.78 | 27.0 | 0.194 | 0.117 | 0.025 | 29.0 | 92 |
| 2025 | 14,601 | 4.357 | 6.277 | 4.06 | 30.8 | 0.190 | 0.109 | 0.023 | 29.0 | 93 |

**Any Gaussian family is refused on inspection**, and it was refused before any
model was fitted rather than after one failed.

### What R6's hypotheses need, and what exists

| source | seasons present | consequence |
|---|---|---|
| nflverse pbp | **2016–2025** | yards, EPA, success, run location/gap, game state — the core is complete |
| **PFR advanced weekly rushing** (yards before/after contact, broken tackles) | **2024 ONLY** — 2,359 player-games, 335 players | no across-season walk-forward is possible; a within-season test on one season is |
| PFR advanced weekly defence | 2022–2024 | not needed; pbp gives opponent context for all seasons |
| FTN charting (box counts) | 2024 only | not used |

**The identifier join is exact, not fuzzy.** `players.csv` carries a
`gsis_id ↔ pfr_id` bijection over **22,653 players with 0 non-injective
mappings in either direction**. All 2,254 PFR REG rows mapped; 0 failed to join
to pbp; 1 carry-count disagreement (0.04%). **This is not the
`weekly_rosters.pfr_id` bridge P3 rejected at 77.51%.**

## 8. Control

**A — opportunity-only pooled conversion.** Accepted carry allocation, and a
per-carry conversion drawn from the pooled prior-season empirical distribution
(82,014 to 126,077 training carries depending on season). No player, team or opponent
efficiency information of any kind. It was not weakened: it uses the full prior
carry population and, in two of four seasons, the best-fitting family was
chosen for it too.

## 9. Candidate systems and results

Pooled over 2022–2025, n = 8,960 RB player-games, 2,174 team-games:

| system | CRPS | vs A | MAE | RMSE | r | R² | bias | log score | rPIT | c50 | c90 | w90 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** control | 10.6256 | — | 16.351 | 25.100 | 0.670 | 0.445 | +0.045 | 3.0161 | **16.8** | 0.703 | 0.940 | 65.51 |
| **B** + player | 10.5266 | **−0.93%** | 16.215 | 24.847 | 0.677 | 0.456 | −0.174 | 3.0196 | 18.9 | 0.696 | 0.939 | 65.73 |
| **C** + team | 10.5248 | −0.95% | 16.203 | 24.845 | 0.677 | 0.456 | −0.140 | 3.0193 | 19.3 | 0.696 | 0.939 | 65.65 |
| **D** + opponent | 10.5239 | −0.96% | 16.223 | 24.839 | 0.677 | 0.457 | −0.231 | 3.0183 | 20.0 | 0.696 | 0.939 | 65.85 |
| **E** combined | 10.5219 | −0.98% | 16.211 | 24.837 | 0.677 | 0.457 | −0.196 | 3.0193 | 19.8 | 0.697 | 0.939 | 65.77 |
| O_carries\* | 5.2131 | **−50.94%** | 7.337 | 14.538 | 0.903 | 0.814 | +0.060 | 2.2911 | 16.1 | 0.749 | 0.950 | 31.25 |
| O_eff\* | 8.9050 | **−16.19%** | 13.245 | 20.678 | 0.792 | 0.623 | +0.586 | 2.9202 | 108.5 | 0.731 | 0.976 | 65.88 |
| O_explosive\* | 9.7536 | −8.21% | 14.839 | 23.164 | 0.731 | 0.527 | +1.096 | 2.9381 | 14.5 | 0.701 | 0.945 | 61.26 |
| O_all\* | 2.1650 | −79.62% | 0.254 | 0.453 | 1.000 | 1.000 | +0.002 | 2.0440 | 3719.6 | 1.000 | 1.000 | 31.25 |

\* diagnostic only, never eligible.

**A → B is the only rung that does anything.** B → C is 0.02%, C → D 0.01%,
and E is within 0.05% of B. Every rung beats A with a team-game block-bootstrap
interval excluding zero in **4 of 4 seasons** (B: −0.089 to −0.113, intervals
`[−0.166, −0.024]` at worst).

## 10. Player-skill persistence

Season-to-season, ≥ 50 carries in both seasons, n = 493 player-season pairs:

| signal | r | carry-weighted r | split-half r (≥40 each half, n=590) | Spearman-Brown full length |
|---|---|---|---|---|
| explosive rate | **+0.485** | +0.467 | +0.380 | +0.550 |
| EPA/attempt | +0.484 | +0.454 | +0.434 | +0.605 |
| success rate | +0.483 | +0.454 | **+0.532** | **+0.694** |
| yards per carry | +0.343 | +0.344 | +0.366 | +0.535 |
| stuff rate | +0.261 | +0.291 | +0.319 | +0.484 |

**Success rate is the most self-consistent signal measured and it is not an
outcome.** Persistence is reported here and predictive value in §11 precisely
because they are not the same thing.

## 11. Player-skill next-game prediction

Carry-weighted MSE against the **next game's** realised rate, walk-forward,
pooled prior from seasons `< Y`:

| signal | season | raw | EWMA | **EB-shrunk** | EB(EWMA) | fitted k |
|---|---|---|---|---|---|---|
| **YPC** | 2022 | +5.95% | +6.98% | **−4.37%** | −3.79% | 80 |
| | 2023 | +10.07% | +8.77% | −1.87% | −3.23% | 40 |
| | 2024 | +8.97% | +6.82% | −1.54% | −3.08% | 40 |
| | 2025 | +5.31% | +5.49% | −2.03% | −1.73% | 80 |
| **explosive rate** | 2022 | +7.18% | +8.20% | **−4.52%** | −3.86% | 80 |
| | 2023 | +5.85% | +5.40% | −3.04% | −3.99% | 80 |
| | 2024 | +4.97% | +4.60% | −2.64% | −3.41% | 80 |
| | 2025 | +7.38% | +7.27% | −1.88% | −1.99% | 80 |
| **stuff rate** | 2022 | +2.66% | +3.66% | **−7.73%** | −6.68% | 20 |
| | 2023 | −2.01% | −0.92% | **−9.18%** | −7.68% | 20 |
| | 2024 | +0.92% | +0.96% | −5.93% | −5.56% | 20 |
| | 2025 | +0.33% | −0.22% | **−8.97%** | −9.03% | 20 |

(percentages are versus the pooled prior; negative is better.)

**Raw and recency-weighted player efficiency are worse than simply using the
pooled prior**, by 5–10% on YPC. Only empirical-Bayes shrinkage beats pooling.
**The non-positive-run (stuff) rate is the most predictable player attribute**
— 5.9–9.2% better than pooled, with the lightest shrinkage of the three.

## 12. Shrinkage results

The constants, fitted on prior seasons only, are themselves the cleanest
statement of where information lives:

| block | ypc | explosive | stuff |
|---|---|---|---|
| **player** | 40–80 carries | 80 | **20** |
| **team** | 1280 | 1280 | 1280–2560 |
| **opponent** | 2560 (grid max) | 1280–2560 | 320–640 |

A constant of 40 means a player with 40 prior carries is weighted 50/50 against
the league. A constant of 2560 means the estimator throws the signal away.
**The shrinkage layer decided that team and opponent rushing context carries no
next-game information before the CRPS ladder was ever run, and the two agree.**

## 13. Context results (team / offence)

`C − B` on pooled CRPS: **−0.017%**. Team ypc, explosive rate and stuff rate,
all empirical-Bayes shrunk, are shrunk to k = 1280–2560, i.e. to the pooled
prior. **Team rushing context does not earn inclusion.**

## 14. Offensive-line results

**Not testable, and not faked.** No offensive-line continuity, snap-count or
personnel source with a defensible chronology exists in this checkout. The
nearest available proxy — yards before contact — exists for one season and is
reported in §17. Nothing was substituted for the missing source, and no
line-continuity variable was constructed from post-hoc data.

## 15. Opponent results

`D − B` on pooled CRPS: **−0.026%**, and its own shrinkage constant is the grid
maximum. **Opponent defensive rushing context does not earn inclusion.** This
reproduces P4's warning that naive opponent adjustment adds noise, on a
different quantity.

## 16. Missed-tackle results (R6 hypothesis)

**Not reproduced.** Within 2024, broken tackles per attempt is the **least**
persistent of the four signals measured (split-half r = **+0.261**,
Spearman-Brown +0.413, n = 69 players with ≥ 30 carries in each half), and in
the within-season next-game test it buys **−0.00%** of weighted MSE with a
**wrong-signed** coefficient (β = −0.642).

**One season, in-sample β, 995 evaluation rows. This is preliminary evidence
that does not support the hypothesis. It is not a rejection**, and a
multi-season PFR backfill would be needed to make it one.

## 17. Yards-after-contact / yards-before-contact decomposition

Within 2024, split-half persistence and within-season next-game YPC prediction:

| signal | split-half r | Spearman-Brown | next-game wMSE vs pool | fitted β |
|---|---|---|---|---|
| **yards before contact / att** | **+0.633** | **+0.776** | **−4.70%** | **+0.967** |
| yards per carry | +0.499 | +0.666 | −2.74% | — |
| yards after contact / att | +0.480 | +0.648 | **−0.16%** | **−0.277** |
| broken tackles / att | +0.261 | +0.413 | −0.00% | −0.642 |

- **R6's "yards after contact has modest persistence" is reproduced** (0.480) —
  **and it adds nothing to next-game outcome prediction**, with a wrong-signed
  coefficient. Persistence without predictive value, exactly the distinction
  the directive asked to be kept.
- **R6's "yards before contact should not be modeled as player skill" is
  contradicted on this season.** YBC is the most persistent and the most
  predictive signal measured.

**And it is not the blocking environment.** Same season, same walk-forward,
substituting the source of the YBC estimate:

| YBC estimated from | n | wMSE vs pool | r |
|---|---|---|---|
| **the player's own prior carries** | 995 | **−4.70%** | +0.217 |
| the team's prior carries incl. the player | 995 | −2.32% | +0.152 |
| **the player's TEAMMATES only** | 980 | **−0.12%** | +0.035 |

**A player's teammates' yards before contact predict his next game essentially
not at all.** The signal travels with the player, not the offensive line.
The careful reading is that YBC is *player-attached* rather than *player skill*
— it plausibly encodes the situations a given back is used in (gap scheme,
light boxes, snap timing) as much as anything he does — and one season cannot
separate those. **Preliminary, one season, in-sample β.**

## 18. Explosive-run results

**A separate explosive component is not justified.** Pooled CRPS by family:

| system | emp_shift | emp_tilt | mix2 (body+explosive) | mix3 (stuff/body/explosive) |
|---|---|---|---|---|
| A | 10.6334 | 10.6296 | 10.6300 | 10.6299 |
| B | **10.5266** | 10.5379 | **10.6043** | 10.5339 |
| E | **10.5219** | 10.5335 | 10.6020 | 10.5317 |

`mix2` is **0.74% worse** than the location-shifted empirical family. `mix3` is
0.07% worse. `emp_shift` wins in **4 of 4 seasons** for both B and E. Modelling
the explosive probability separately loses more in the body than it gains in
the tail.

The oracle says why it cannot be worth much: **knowing the realised explosive
occurrence is worth only 8.2% of CRPS**, against 50.9% for the carry count.

## 19. Distribution-family comparison

Under the control all four families coincide to 0.004 CRPS — as they must,
since with pooled parameters the mixtures reconstruct the pooled empirical
exactly. **The family question only bites once the mean varies by row**, and
there the answer is consistent: **the location-shifted pooled empirical wins in
4 of 4 seasons for every system that has a mean to shift.** Exponential tilting
(which keeps mass on the integer support) is 0.11% worse. Gaussian, gamma,
negative binomial, skew-t and Pareto were never fitted, because the audit's
skew of 3.6–4.2 and excess kurtosis of 25–32 rule out the first three on
inspection and R7 found no literature strong enough to justify the others.

## 20–21. Pooled and yearly metrics

Pooled in §9. Per season:

| season | n | A CRPS / rPIT | B (Δ) / rPIT | E (Δ) / rPIT | chosen |
|---|---|---|---|---|---|
| 2022 | 2,365 | 10.2990 / **15.0** | 10.2007 (−0.95%) / 14.0 | 10.1942 (−1.02%) / 15.9 | E |
| 2023 | 2,255 | 10.0703 / **27.3** | 9.9810 (−0.89%) / 31.0 | 9.9753 (−0.94%) / 31.1 | C |
| 2024 | 2,166 | 11.2331 / **13.6** | 11.1185 (−1.02%) / 18.0 | 11.1218 (−0.99%) / 18.2 | D |
| 2025 | 2,174 | 10.9515 / **10.8** | 10.8572 (−0.86%) / 12.7 | 10.8476 (−0.95%) / 14.0 | E |

**The improvement is consistent in all four seasons** (criterion K: yes, but by
about 1%).

## 22. Subgroup metrics

CRPS, E versus A, pooled:

| split | group | n | mean yards | P(20+ run) | Δ CRPS |
|---|---|---|---|---|---|
| carry tier | 0 | 3,823 | 0.00 | 0.000 | −1.69% |
| | 1–4 | 1,691 | 8.57 | 0.038 | −0.28% |
| | 5–9 | 1,264 | 28.48 | 0.117 | **+0.22%** |
| | 10–14 | 1,063 | 51.48 | 0.239 | −0.45% |
| | **15+** | 1,119 | 86.46 | 0.374 | **−2.12%** |
| efficiency history | none | 4,385 | 2.45 | 0.012 | −1.08% |
| | **high** | 2,606 | 47.31 | 0.215 | **−2.09%** |
| | **low** | 1,969 | 34.49 | 0.139 | **+0.67%** |
| role | stable | 7,040 | 20.90 | 0.090 | −0.98% |
| | role change | 1,920 | 28.57 | 0.130 | −1.21% |
| info quality | HIGH / MEDIUM / LOW | 1,137 / 5,226 / 2,597 | | | −0.99% / −1.02% / −1.13% |
| prior history | <25 / 25–199 / 200+ carries | 4,385 / 1,527 / 3,048 | | | −1.08% / −0.88% / −1.11% |

**The gain is concentrated in high-volume backs with a good efficiency history
(−2.12%, −2.09%) and it is negative for backs with a poor one (+0.67%).** The
shrunk estimate is not being applied symmetrically: it helps where it predicts a
player is better than league average and hurts where it predicts he is worse.
That asymmetry is a defect worth naming, and it is not fixed here.

## 23–26. CRPS, randomised PIT, coverage, threshold calibration

**Randomised PIT** (critical value 27.877 on 9 df): **A passes in all four
seasons** (15.0 / 27.3 / 13.6 / 10.8) and B/E pass in three, failing 2023
(31.0 / 31.1). Pooled: A 16.8, B 18.9, E 19.8 — all passing.

**Coverage** (pooled, system E): 50% 0.697, 80% 0.886, 90% 0.939, 95% 0.968,
mean 90% width 65.77. The 50% over-coverage is the atom at zero — 3,823 of
8,960 player-games have zero carries — and is unchanged from P4C.

**Threshold calibration**, forecast minus observed, on the pre-declared grid:

| system | 9.5 | 19.5 | 39.5 | 59.5 | 79.5 | 99.5 |
|---|---|---|---|---|---|---|
| A | +0.0252 | +0.0109 | −0.0071 | −0.0113 | −0.0054 | −0.0033 |
| B | +0.0248 | +0.0112 | −0.0051 | −0.0087 | −0.0030 | −0.0015 |
| **E** | +0.0249 | +0.0115 | −0.0048 | −0.0085 | −0.0029 | −0.0014 |

Maximum absolute error 2.5 points, at the lowest threshold, where the model
over-forecasts. B and E are uniformly better at the upper thresholds.

## 27. Tail calibration

| system | P(20+ run in game) forecast | observed | AUC | exceed 95th pct | exceed 99th pct |
|---|---|---|---|---|---|
| A | 0.1046–0.1132 | 0.0957–0.1034 | 0.782–0.807 | 0.0446 | 0.0096 |
| B | 0.0985–0.1068 | " | 0.786–0.813 | 0.0448 | 0.0092 |
| E | 0.0986–0.1067 | " | 0.786–0.813 | 0.0450 | 0.0092 |

Targets are 0.05 and 0.01. **The upper tail is slightly over-wide but close**,
and the control over-forecasts the chance of a 20+ yard run by 0.4–1.8 points
while B and E cut that to 0.2–1.1 points.

**Does player identity contribute to tail probability?** Barely. Prior explosive
rate alone discriminates games containing a 20+ yard run at **AUC 0.560–0.595**
with r = +0.088 to +0.109 — consistent in sign across all four seasons and
small. Nearly all of the tail discrimination (AUC 0.78–0.81) is carry volume.
**Team context contributes nothing measurable to the tail**, consistent with
§13.

## 28. Oracle decomposition

| oracle | pooled CRPS | vs control |
|---|---|---|
| realised **carries** | 5.2131 | **−50.94%** |
| realised **per-carry efficiency** | 8.9050 | **−16.19%** |
| realised **explosive occurrence** | 9.7536 | −8.21% |
| realised carries **and** efficiency | 2.1650 | −79.62% |

**Criterion A answered: roughly 3:1 in favour of carries.** The residual 20%
under the full oracle is the within-game arrangement of a known number of
carries at a known average — irreducible by construction here.

O_all's randomised PIT of 3,719 is an artifact and is reported as one: with
both components known the predictive collapses towards a point mass (MAE 0.254),
and a PIT statistic on a near-degenerate forecast measures the degeneracy.

## 29. Joint carry-preservation checks

- Carry counts are **never regenerated**. They come from the accepted P4C
  allocation with the incumbent appearance model, the same team-volume draws,
  and draw column *j* is the same simulated game for every teammate.
- Mean simulated versus realised carries per player-game: 4.941/4.943,
  5.225/5.165, 5.385/5.424, 5.376/5.380. The integer rounding preserves the
  mean to within 1.2%.
- The carry table reconciles to the panel exactly (§7), so the object P5A
  converts is the object P4C accepted.
- Draw-level identity is preserved in the compound so a later J0 could consume
  it. **This is not J0 and no joint game simulator was built.**

## 30. Adversarial tests

**13 probes: 11 PASS, 2 UNRESOLVED, 0 FAIL** (`p5a_adversarial.json`).

| # | seeded leak | measured channel | outcome |
|---|---|---|---|
| 1 | realised carries | downstream CRPS −50.93%, 4/4 seasons | PASS |
| 2 | same-game rushing yards | weighted MSE −75.00% | PASS |
| 3 | same-game YPC | −100.00% (it is the target) | PASS |
| 4 | same-game explosive rate | −39.78% | PASS |
| 5 | future player efficiency | weak −0.0%, strong −0.44% | **UNRESOLVED** |
| 6 | future team efficiency | −0.87% | PASS |
| 7 | future opponent outcome | −0.50% | PASS |
| 8 | observed weather | no field read; carry table has 21 columns, none weather | PASS |
| 9 | market information | no field read, no artifact named for a market or wager | PASS |
| 10 | evaluation-season fitting | pool+k channel −0.24%, coefficient channel small | **UNRESOLVED** |
| 11 | postgame roster status | no roster-status field read | PASS |

**The two UNRESOLVED probes are the finding, not a defect, and the thresholds
were not lowered to manufacture a pass.** For same-game quantities the channel
is enormous (40–100%). For future quantities it is small — the player's *entire*
future yards per carry, with the blend weight fitted, buys 0.44% — because
per-game rushing efficiency is mostly noise. A probe that cannot demonstrate a
live channel gives weaker assurance than one that can, so for those two channels
the guarantee rests on the mechanism proof below rather than on a detectable
signature. That is stated rather than papered over.

## 31. Guard-deletion proofs

| # | proof |
|---|---|
| **12** | Selection handed an unbeatable `O_all` (CRPS 2.16 against 10.5) returns `'E'`. Adding `O_all` to the eligibility tuple makes it return `'O_all'`. Systems ever chosen across the four seasons: C, D, E — never an oracle. |
| **13** | Moving the accumulator update **above** the read in `p5a_build.build` raises corr(prior history, this game's YPC) from **0.1592 to 0.2370** on 1,768 rows. The read-then-update ordering is the entire chronology guarantee for every player, team and opponent signal in P5A. |

## 32. Negative findings

1. **Team rushing context does not earn inclusion** (−0.02% CRPS; shrinkage
   constant 1280–2560).
2. **Opponent defensive rushing context does not earn inclusion** (−0.03%;
   shrinkage constant at the grid maximum).
3. **Raw and recency-weighted player efficiency are worse than a pooled prior**,
   by 5–10% weighted MSE on YPC.
4. **A separate explosive-run component does not help** — 0.74% worse CRPS.
5. **R6's broken-tackle hypothesis is not reproduced**: least persistent signal
   measured, no next-game value, wrong-signed coefficient.
6. **R6's yards-after-contact hypothesis is half reproduced**: the persistence
   is there (0.480) and the predictive value is not (−0.16%, wrong-signed).
7. **R6's yards-before-contact guidance is contradicted** on the one season
   available — it is the most persistent and most predictive signal — but I am
   labelling it *player-attached*, not *player skill*, because one season cannot
   separate a runner's ability from the situations he is used in.
8. **Offensive-line context could not be tested at all** and nothing was
   substituted for it.
9. **The player signal is applied asymmetrically**: −2.09% for backs with a
   high efficiency history, **+0.67% for backs with a low one**.
10. **The whole efficiency ladder is worth 0.93% of CRPS** against 50.94% for
    the carry count. Efficiency is not where rushing-yard uncertainty lives.

## 33. Unresolved debts

- **PFR advanced weekly rushing exists for 2024 only.** A 2016–2025 backfill
  would turn §16–17 from one-season preliminary evidence into a real
  walk-forward test. **This is blocked for me and not for the networked agent,
  so per `docs/AGENT_PROTOCOL.md` it is assigned, not blocked** — and it needs
  an outbox entry naming `pfr_advstats_week_rush` for seasons 2016–2023 and 2025.
- **No offensive-line source with a defensible chronology exists** in this
  checkout.
- **The 2023 randomised PIT failure (31.0) under B/E** is unexplained; the
  control passes that season.
- **No sealed holdout.** 2022–2025 are all training seasons for later years.
- Carried forward: 2025 has no injury feature; depth charts carry no timestamp;
  the appearance model's mid-range ranking defect (P4D) is upstream of this
  work and unfixed.

## 34. Task-report path

`TASK_REPORT_2026-09-07_P5A.md` (repository root, `94924676jp-a11y/nfl`, `main`).

## 35. Recommendation for the next research question only

**Ask whether the carry-count distribution itself can be sharpened, because
that is where 51% of the error is and conversion is only 16%.**

P5A's clearest result is that the efficiency branch is nearly exhausted: every
plausible player, team and opponent signal, given every reasonable shrinkage,
buys about one percent. The oracle says the carry count is worth fifty. P4C
established that the carry *allocation* is coherent and passes calibration, and
P4D established that its dominant remaining error is the appearance
probability's mid-range ranking — which P4D then showed is 92–95% irreducible
with the features presently available.

So the next question is narrow and it is upstream: **given the accepted joint
allocation, how much of the carry-count error is team-total error, how much is
share error, and how much is appearance — measured on carries specifically
rather than on the five classes together?** P4B's decomposition was run before
reconciliation existed and P4C's was run on shares rather than counts; neither
answers it for the object P5A actually consumes. It is answerable inside this
repository with data already present.

**I am not recommending** P5B, receiving, touchdowns, J0, a more complex
conversion model, or another efficiency family. The conversion question has been
asked and the answer is that it is small.

---

## Constraints honoured

No receiving, receptions, receiving yards, passing, or touchdowns modelled. No
further target modelling. **No J0 built.** No market ingested, no betting EV
calculated, **no wager recommended and none discussable.** No fantasy scoring,
no DFS, no lineup optimisation. NFL-1 not authorised. G0A untouched
(11 PASS / 1 FAIL). T−90 untouched. **No 2026 outcome consumed** — carry data
is 2016–2025 and the panel is 2020–2025. No Grade-B ESPN/Wayback material used.
**The 2025 nflverse injury final file is not used as historical point-in-time
evidence**, and no historical injury/depth backfill was waited on (R9). No
observed weather, no roster status. The accepted P4C carry allocation and P4D
appearance treatment are imported unchanged. Repository test count unchanged and
re-verified: **1,230 assertions across 19 suites, 0 failing.**

**Stopping after the research return, as instructed.**

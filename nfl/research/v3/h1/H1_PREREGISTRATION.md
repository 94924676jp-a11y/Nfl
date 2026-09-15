# H1 pre-registration — 2025 starting-QB residual reference distribution

**Written before any residual was computed.** Order of work in this task:
this file, then the panel build, then the forecast run, then the scoring.
Nothing below was chosen after seeing an error.

**EXPLORATORY.** 2025 is a development season in this project. Every arm
of the frozen QB path was selected on 2022-2025 (`qb2_lib`: "EXPLORATORY.
2022-2025 heavily mined. No promotion possible."), and P4B's estimator
selection for 2025 was walk-forward but its *family* was chosen while 2025
was visible to the project. Freezing the season does not make it a holdout.
Nothing here is confirmatory and nothing here may be quoted as prospective
performance.

**No market quantity is an input.** The raw play-by-play carries
`spread_line`, `total_line`, `vegas_wp` and `vegas_wpa`. All four are
refused by name, as `q7/panel.py:FORBIDDEN_SUBSTRINGS` already refuses
them. The consequence is stated in section 4 rather than worked around.

---

## 1. Eligibility, fixed before residuals

A row is eligible when **all** of the following hold. Each clause is a
pregame-or-structural property except where marked.

1. Season 2025, season type REG.
2. The player is the team's **primary passer** in that game: the largest
   dropback count among that team's passers in that game (`ord == 1` in the
   brief's language). Ties are broken by attempts, then by gsis_id, and the
   tie rate is reported.
3. The player has **at least one prior appearance** with a dropback, at a
   strictly earlier ordinal. This is `qb2_lib.eligible`, the frozen
   production eligibility, and it is not loosened. Cold-start quarterbacks
   are **named and counted**, not silently dropped.
4. The team has a prior game in the panel, so the team-level layers have a
   strictly-earlier history to condition on.

**Minimum dropbacks: 10, applied to the REALISED dropback count.**

This clause conditions on an outcome and is therefore declared as such.
Justification: below ten dropbacks the quarterback did not play the game he
was forecast for — injury, ejection, or a blowout substitution — and the
residual measures availability, not forecasting. The project's own
`qb_v1.KNOWN_LIMITATIONS.multi_qb_over_prediction` documents this exact
mechanism at +79.8 passing yards of bias. **Both frames are reported**: the
primary frame with the cut, and the unfiltered primary-passer frame
without it, so the reader can see what the cut does rather than trust that
it is harmless.

Expected retention is reported, not predicted.

---

## 2. The forecast: what is frozen, and what is reconstructed

The frozen production QB mechanism is `nfl/research/qb2/qb2_lib.simulate`,
imported unmodified by `nfl/production/qb_v1.forecast`. This task **imports
and calls that module**; it does not reimplement it. Rung `L1` (the
production baseline selection), `SEED = 20260908`, `m = 1000` draws,
`db_external = None`.

The team-play layer is `nfl/research/p4b/p4b_volume`, whose `attach`,
`baselines`, `build_forms` and `draw` are imported unmodified — the same
four functions `nfl/production/team_volume_v1.py` imports.

**Differences between this reconstruction and the live production path,
declared in advance:**

| # | Difference | Why |
|---|---|---|
| R1 | `db_external` is `None`, so team dropbacks and the QB share are drawn inside `qb2_lib` (its pre-R2 branch) rather than supplied by D1 x QB3 | QB3 needs captured depth charts, and `qb_allocation.KNOWN_LIMITATIONS.depth_chart_2025_absent` records that the committed leaves stop at 2024. The R2 path **cannot be driven over 2025 at all**. |
| R2 | The row frame is rebuilt from `nfl/research/qb2/qb.pkl` rather than through `qb2_lib.load()` | `qb2_lib.load()` calls `rc1_lib -> s2_lib -> p4c_build.load_panel()`, which reads `nfl/research/p4b/panel_enriched.pkl`. That file is absent from the checkout. `qb.pkl` is the artifact `qb_v1.FRAME_PATH` names and hashes. |
| R3 | Position is inferred as "had a dropback", not read from a roster | the roster field lives in the missing panel. Non-quarterback dropbacks are counted and reported. |
| R4 | The non-QB engine (A1 rushing, C3, allocation, accounting) is not run | none of it feeds passing yards. |

Every one of these is a difference in **inputs or wiring**, not in the
estimator, the prior or the draw mechanism. No estimator is re-chosen here.

**Forward chaining.** `qb2_lib.attach` cuts own history at a strictly
earlier ordinal by bisection, and `qb2_lib.pools` is restricted to seasons
strictly before the evaluation season. P4B's point estimator and residual
form are fitted on seasons strictly before 2025 with an inner validation on
2024. No same-week information enters any layer.

---

## 3. Layers scored, and the quantity each one owns

| layer | forecast | realised |
|---|---|---|
| team offensive plays | P4B `team_off_snaps` draws | team plays |
| team dropbacks | `qb2_lib` V draw; and P4B `team_dropbacks_part` as a second owner | team dropbacks |
| QB dropback share | `qb2_lib` S draw | db / team_db |
| QB dropbacks | V x S | db |
| attempts / dropback | `rung_rate(att, db)` | att / db |
| completions / attempt | `rung_rate(cmp, att)` | cmp / att |
| yards / completion | `_mix` draw mean | pyds / cmp |
| passing TD / attempt | `rung_rate(ptd, cmp) x (cmp/att)` | ptd / att |
| INT / attempt | `rung_rate(int, att - cmp) x ((att-cmp)/att)` | int / att |
| scramble / rush opportunity | `rung_rate(scr, db) / (rush_opp/db)` | scr / rush_opp |
| **passing yards** | draws | pyds |

The TD and INT rows restate the production parameterisation, which is
**rebased to the causal parent** (`addendum_qb2_coherence.md`: a passing TD
is a completion, an interception is an incompletion). The per-attempt form
the brief asks for is reported as a derived quantity beside the per-parent
form actually drawn, so neither is misattributed.

Reported per layer: **signed mean error**, MAE, RMSE, and the standardized
residual distribution (error / predictive SD) with its mean, SD, skew and
excess kurtosis. Signed mean error is never collapsed into MAE.

---

## 4. Calibration

- **PIT** for the continuous quantities.
- **Randomized PIT** for the discrete counts — dropbacks, attempts,
  completions, passing TD, INT, scrambles. `U = F(y-1) + V*(F(y) - F(y-1))`,
  `V ~ Uniform(0,1)`, one draw per row, seeded. An unrandomized PIT on a
  discrete variable is not uniform under a perfect model and reporting it
  as miscalibration would be a manufactured finding.
- **P10 / P50 / P90 coverage** against nominal 0.10 / 0.50 / 0.90 with
  clustered intervals.
- TD and INT calibration separately, as counts and as rates.

**Available metrics.** Draws are stored, so CRPS, PIT and coverage are all
computable. Log score is computed **only** where an exact analytic
predictive exists (the binomial rungs); it is **not** computed for passing
yards, where a sample-based log score needs a bandwidth that is itself a
free parameter. That is a refusal, not an approximation.

**Clustering, declared before computing.** The **game** is the primary
cluster: two quarterbacks in one game share an opponent, a script and a
weather. Intervals come from a **block bootstrap over whole games**, 2,000
resamples, seed 20260915. A **team-clustered** bootstrap is reported
alongside as a second, coarser unit. A naive SE is not reported anywhere.

**No adequacy language.** The words "unbiased", "calibrated", "stable" and
"adequate" are not used of any result unless a two-one-sided test rejects
outside a predeclared equivalence margin. The margins, fixed here:

| quantity | equivalence margin |
|---|---|
| passing yards, signed mean error | +/- 5.0 yards |
| dropbacks / attempts, signed mean error | +/- 0.5 |
| completion rate, signed mean error | +/- 0.010 |
| yards per completion, signed mean error | +/- 0.25 |
| coverage at a nominal level | +/- 0.03 |

These are football-recognisable magnitudes chosen for size, not for
whether the data would clear them.

---

## 5. Question E: the cuts, fixed here, and the multiplicity treatment

**Fifteen cuts**, every one defined from pregame-known or structural
information.

1. Week 1 (no in-season prior)
2. Weeks 2-4
3. Weeks 5+
4. Pregame favourite proxy, top third
5. Pregame favourite proxy, bottom third
6. Own team strong prior rushing (top third of prior yards per carry)
7. Opponent strong prior run defence (top third of prior yards allowed per carry)
8. High-pressure defence: opponent prior sack rate top third
9. Low-pressure defence: opponent prior sack rate bottom third
10. QB returning from a missed game (started, missed at least one team game since his last start)
11. New team (this QB's first game for this team)
12. New starter (this QB was not the team's primary passer in its previous game)
13. Shallow own history, 1-3 prior games
14. Deep own history, 17+ prior games
15. Home / away split (reported as one cut on the home indicator)

**The pregame favourite proxy.** No lawful pregame spread exists in this
repository. `spread_line` is present in the play-by-play and is a market
quantity, refused by rule. The substitute is the difference in the two
teams' **prior point differential per game**, taken over strictly earlier
games within the season with the prior season's mean as the week-1 fallback.
It is a proxy for expected margin, it is not a spread, and it is labelled
as a proxy everywhere it appears.

**"Leading teams" is refused as a cut.** Whether a team led is realised
in-game state. Splitting residuals on it conditions on the outcome and
manufactures a defect for any forecaster, including a perfect one. The
pregame favourite proxy is offered in its place and the substitution is
declared rather than made silently.

**Multiplicity.** Fifteen cuts are tested. Every cut's nominal
game-clustered p-value is reported, and **Holm-Bonferroni** across all
fifteen is reported beside it. No cut is called a finding on a nominal
p-value alone. The expected number of nominally significant cuts under a
true null is stated with the results.

---

## 6. The two located outcomes

A **184-yard** outcome against a forecast near 245, and a **131-yard**
outcome against a forecast near 210.

**These two pairs were supplied to the task by the user and are verified
against nothing in this repository.** They are located as **hypotheticals**.
The matching bands are predeclared: forecast within +/- 25 yards of the
stated central value, and if a band holds fewer than 30 rows the band is
widened to +/- 40 and the widening is reported. Reported for each:
percentile of that signed error inside the matched band and inside the full
2025 frame, the standardized residual, and the empirical frequency of a
miss at least that large in the same direction.

---

## 7. Empty is an error

Every stage asserts a non-empty, schema-correct output and raises a named
error otherwise. No count in the report is quoted from this file; every one
is re-derived from the artifact in front of the reader.

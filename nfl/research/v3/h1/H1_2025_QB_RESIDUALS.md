# H1 — the 2025 starting-QB residual reference distribution

**EXPLORATORY. Not a confirmatory result and not prospective performance.**
2025 is development data in this project: `qb2_lib`'s own header reads
"EXPLORATORY. 2022-2025 heavily mined. No promotion possible", and the P4B
team-volume family was chosen while 2025 was visible. Freezing the season
does not make it a holdout. What would be needed for a confirmatory result is
in section 9.

Pre-registration: `nfl/research/v3/h1/H1_PREREGISTRATION.md`, written before
the first residual was computed. No market quantity is an input anywhere.
The recent game was not opened and is not in this repository: the newest 2026
capture, `pbp_2026.1415dd98ba7f701a.csv.gz`, holds 10 week-1 games and **zero
DEN and zero KC rows** — re-verified here, not taken on trust.

**Frame.** 540 eligible 2025 starting-QB games over **272 games** and 32
teams, scored on **20 layers**, 10,730 scored rows. Every interval below is a
**block bootstrap over whole games**, 2,000 resamples, seed 20260915. Team-
clustered intervals are given beside them. **No naive standard error appears
anywhere in this report.**

---

## 1. Answer to C — did the model over-project QB passing VOLUME in 2025?

**No, not at the quarterback level. It under-projected it.** And the
sign flips between layers, which is the actual finding.

Sign convention throughout: **error = predicted mean − realised**, so a
**positive** number is an over-projection.

| layer | signed mean error | 95% CI, game-clustered | 95% CI, team-clustered |
|---|---|---|---|
| team offensive plays | **+1.7987** | [+1.238, +2.337] | [+0.786, +2.861] |
| team dropbacks (QB layer's own V draw) | **+1.6369** | [+1.001, +2.251] | [+0.751, +2.556] |
| team dropbacks (D1 / P4B) | +0.8736 | [+0.237, +1.511] | [−0.086, +1.916] |
| **QB dropback share** | **−0.0778** | [−0.0868, −0.0687] | [−0.0975, −0.0605] |
| **QB dropbacks** | **−1.3697** | [−2.099, −0.704] | [−2.583, −0.199] |
| **QB attempts** | **−1.1394** | [−1.825, −0.486] | [−2.256, −0.021] |
| attempts / dropback | +0.0028 | [−0.0027, +0.0085] | [−0.0062, +0.0115] |

Read the chain. Team volume was over-projected by about **1.8 plays and 1.6
dropbacks per team-game**. The **share** layer then under-projected the
starting quarterback's cut of it by **7.8 percentage points**, which is far
larger in effect than the team-level error. The two run in opposite
directions and the share error wins: the quarterback ends up with **1.37
fewer dropbacks and 1.14 fewer attempts than forecast**, both intervals
excluding zero under both clusterings.

**The team-level over-projection is a league level shift, not a QB defect.**
The team-play forecast is `league_mean` fitted on 2020-2024; its predicted
values have a standard deviation of 0.27 across 540 games, i.e. it is very
nearly a constant. Mean offensive snaps per team-game fell monotonically
67.14 → 66.36 → 65.79 → 65.91 → 65.39 → **64.24**. The 2020-2024 mean minus
2025 is **+1.870**, against a measured layer bias of **+1.799**. The bias
*is* the drift. Nothing about quarterbacks is implicated.

**The share layer is the one real volume defect, and it is severe.**
Predicted share 0.894, realised 0.972. Its PIT χ² is **929.0 on 9 degrees of
freedom**, with the realised share above the predictive P90 in **79% of
games** and above the P50 in **81%**. The standardized residual has skew
+3.88 and excess kurtosis +26.8. This is not a marginal miscalibration; the
predictive distribution for a starting quarterback's share is in the wrong
place.

The mechanism is structural and is visible in the code, not inferred.
`qb2_lib.simulate` builds the share by `_mix`-resampling the quarterback's
own prior per-game shares against a positional pool that contains **every**
quarterback-game with a dropback, backups included. Conditioning the
evaluation on *being the primary passer* selects the top of that
distribution. The project already has the mirror image of this recorded:
`qb_allocation.py` cites R4 measuring the engine at 2.17× team dropbacks when
all quarterbacks are summed. Both are the same missing normalisation seen
from two ends. **Summed over the room the layer is too high; conditioned on
the starter it is too low.**

**Passing yards, the bottom line.** Signed mean error **−5.9223**, 95% CI
game-clustered **[−12.804, +0.426]**, team-clustered [−15.872, +4.334].
Predicted mean 214.80 against realised 220.72. The direction is
**under**-projection, and the interval contains zero. Against the predeclared
±5-yard margin the TOST does **not** establish equivalence (p = 0.608) — the
interval is simply too wide for 540 games to settle it either way. What can
be said is that the season gives **no support at all** for a systematic
over-projection of passing yards.

---

## 2. Answer to D — did it over-project conditional EFFICIENCY?

**No.** Both efficiency layers are the only two quantities in this study that
clear a predeclared equivalence test.

| layer | signed mean error | 95% CI, game-clustered | margin | TOST |
|---|---|---|---|---|
| **yards / completion** | **+0.0268** | [−0.1895, +0.2242] | ±0.25 | p = 0.0178 → **equivalent within margin** |
| **completions / attempt** | **−0.0031** | [−0.0109, +0.0050] | ±0.010 | p = 0.0458 → **equivalent within margin** |
| passing TD / attempt | −0.0035 | [−0.0068, −0.0004] | — | not predeclared |
| passing TD / completion | −0.0034 | [−0.0080, +0.0012] | — | not predeclared |
| INT / attempt | −0.0000 | [−0.0023, +0.0022] | — | not predeclared |
| scrambles / rush opportunity | −0.0449 | [−0.0726, −0.0151] | — | not predeclared |

Predicted yards per completion 11.017 against realised 10.991. Predicted
completion rate 0.6486 against realised 0.6518. Conditional efficiency in
2025 was where the frozen methodology put it.

The one efficiency-side interval that excludes zero is **scrambles per rush
opportunity**, under-projected by 0.045 — the model gives the starter
slightly fewer scrambles per rushing chance than he took. `passing TD per
attempt` also excludes zero by a hair under game clustering (−0.0035,
[−0.0068, −0.0004]) but not under team clustering ([−0.0074, +0.0001]), and
it does not survive as a finding.

**C and D are different failures and only one of them is present.** The
repair implied is to the **allocation** layer — the share a starting
quarterback gets of his team's dropbacks — and not to any conversion rate.
Nothing here supports touching the yards-per-completion or completion-rate
mechanism.

---

## 3. Answer to E — is the error concentrated in particular states?

**No cut survives multiplicity on passing yards. Week 1 in particular is
not a defect.**

Fifteen cuts were predeclared and all fifteen were tested on each of five
layers: **75 tests**. 18 were nominally significant against an expected 3.75
under a true null. Holm-Bonferroni **across all 75** leaves **two**
survivors, and **neither is on passing yards**:

| layer | cut | difference in mean error | 95% CI | p nominal | p Holm (75) |
|---|---|---|---|---|---|
| QB dropbacks | own history 17+ games | +4.005 | [+1.904, +6.265] | 0.0005 | 0.0375 |
| completions / attempt | opponent sack rate, top third | +0.0367 | [+0.0217, +0.0531] | 0.0005 | 0.0375 |

Holm applied **within** each layer (15 tests) leaves four: those two, plus
`fav_proxy_top_third` on dropbacks (p_holm 0.042) and `own_history_17_plus`
on attempts (p_holm 0.015). Both families are reported in
`H1_SUMMARY.json`; the 75-test family is the stricter and the more honest
one, and the cuts overlap heavily — `weeks_5_plus` and
`own_history_17_plus_games` share most of their rows — so neither correction
is exact.

**Passing yards, all fifteen cuts:** 2 nominally significant against 0.75
expected, **0 surviving Holm at any family size.** The two nominal ones were
`opp_sack_rate_bottom_third` (−16.05, p = 0.013, p_holm 0.195) and
`qb_returning_after_missed_game` (+17.96, p = 0.047, p_holm 0.658).

**Week 1 specifically.** n = 30. Mean signed error in week 1 **+3.874**
against **−6.499** in the rest of the season; difference **+10.372**, 95% CI
**[−17.15, +32.60]**, p = 0.371, p_holm 1.000. The *direction* is a mild
over-projection in week 1, consistent with having no in-season prior — but
thirty games cannot distinguish it from nothing, and it must not be quoted as
a finding. On dropbacks the week-1 difference is −0.602 [−3.40, +2.26] and on
attempts −0.190 [−2.81, +2.28]: no sign of a volume problem in week 1 at all.

**Two cuts in the brief were changed, and the changes are declared.**

- **"Leading teams" was refused.** Whether a team led is realised in-game
  state. Splitting residuals on it conditions on the outcome and manufactures
  a defect for any forecaster, including a perfect one.
- **"Big favorites" has no lawful input.** No lawful pregame spread exists in
  this repository. `spread_line`, `total_line`, `vegas_wp` and `vegas_wpa`
  are all present in the raw play-by-play and all are market quantities,
  refused by the same list `q7/panel.py` refuses. The substitute is a
  **non-market favourite proxy**: the difference in the two teams' prior
  point differential per game, strictly earlier within the season with the
  prior season as the week-1 fallback. It is labelled a proxy everywhere.

---

## 4. The two located outcomes

**Both pairs were supplied to this task by the user and are verified against
nothing in this repository. They are located as hypotheticals.** Band:
forecasts within ±25 yards of the stated value, inside the 2025 frame.

| | 184 on a forecast of 245 | 131 on a forecast of 210 |
|---|---|---|
| implied over-projection | **+61 yards** | **+79 yards** |
| matched band | 220–270 | 185–235 |
| rows in band | 215 | 216 |
| mean predictive SD in band | 92.91 | 100.23 |
| **standardized residual** | **+0.657** | **+0.788** |
| percentile within band | 69.8 | 92.6 |
| percentile in full 2025 frame | 80.2 | 88.5 |
| 2025 games in band that missed at least this far, same direction | **65 of 215 = 30.2%** | **16 of 216 = 7.4%** |
| same, across the full 540-game frame | 107 of 540 = 19.8% | 62 of 540 = 11.5% |

Neither is a tail event. The first is under two-thirds of one predictive
standard deviation and happened in **roughly three of every ten** comparable
2025 games. The second is four-fifths of a standard deviation and happened in
**about one in thirteen**.

**And the pair together, which is the question actually asked.** 268 of the
272 games in the 2025 frame carry both teams' primary passers. In **11 of
those 268 games — 4.10%, about one game in 24 — one starter was
over-projected by ≥79 yards and the other by ≥61.** At least one starter was
over-projected by ≥61 in **94 of 268 games, 35.1%**. The within-game
correlation of the two quarterbacks' passing-yard errors is **+0.100**, so
they are close to independent and the joint rate is close to the product.

**One game containing both misses is an ordinary 2025 Sunday under this
methodology.** It is roughly a one-in-24 event and 2025 produced eleven of
them. It carries essentially no evidence of a biased model, and the
season-level evidence points the other way: passing yards were
**under**-projected on average by 5.9 yards.

---

## 5. Where this disagrees with the brief

**The brief's designated dataset has a structurally-zero column and cannot
support one of the layers it asks for.**

`nfl/research/q7/q7_qb_game.csv.gz` carries **1 scramble across all 4,025
QB-games, 2020-2025**. The true count over the same player-games is **5,864**.
`q7/panel.py:reduce_season` increments every quarterback counter inside
`if pid:` where `pid = passer_player_id`, and a `qb_scramble` play in
nflverse play-by-play carries **no** `passer_player_id` — it is a rush,
attributed to `rusher_player_id`. A scramble therefore cannot reach a
quarterback in that builder.

Consequences, measured:

- `db = att + sacks + scr` is short by the scramble count: 116,190 against
  121,485 composed correctly, a 4.4% shortfall. Panel and correctly-built
  dropbacks agree on only **1,514 of 4,009** matched player-games.
- The brief's **"scramble / rush opportunity"** layer is **not computable
  from that panel at all**.
- The docstring's own defence makes it worse rather than better. Composing
  `db` from the three counters makes `att + sacks + scr == db` a **tautology**
  — it cannot detect the defect, and it removes the one check that would
  have: comparison against the source's `qb_dropback` column, which is
  exactly what the docstring says it is glad to avoid.

This is a known failure mode in this repository, already written down.
`nfl/research/qb2/build_qb.py` states it verbatim: *"Scrambles carry NO
passer_player_id (0 of 4,091), so a scramble charged to the passer would be a
structurally-zero column — this project has produced one already."* Q7
produced the second.

**What I used instead.** The spine is `nfl/research/qb2/qb.pkl`, the frame
`nfl/production/qb_v1.FRAME_PATH` names and hashes
(`e2de51d345502a2717a64e584f5e883a64eb3ed51ff97e5f42e406a0ddba0c54`), which
attributes scrambles to the rusher. The q7 panel is reconciled against it and
the reconciliation is published in `h1_run_meta.json`, not hidden.

**Three smaller corrections.**

1. **The frozen production path cannot be driven over 2025 in full.** Its
   dropback level comes from D1 × QB3 (`db_external`), and QB3 needs captured
   depth charts. `qb_allocation.KNOWN_LIMITATIONS.depth_chart_2025_absent`
   records that the committed leaves stop at 2024. The R2 path is not
   reconstructible for 2025 by anyone, not just by me.
2. **`qb2_lib.load()` does not run in this checkout** — it reaches
   `p4c_build.load_panel()`, which reads `nfl/research/p4b/panel_enriched.pkl`,
   and that file is absent. The frame had to be rebuilt from `qb.pkl`.
3. **The minimum-dropback clause was non-binding.** The predeclared cut was
   ≥10 realised dropbacks. The **smallest** 2025 primary-passer dropback count
   is **12**, so the cut removed **zero rows** and the filtered and unfiltered
   primary-passer frames are identical. Reported because a clause that did
   nothing should be visible as having done nothing.

---

## 6. What was run, and how it differs from production

**Imported, not reimplemented.** `qb2_lib.attach`, `.pools`, `.simulate`,
`._mix`, `.rung_weight` and `.rung_rate` are called unmodified at rung **L1**
(the production baseline selection in `qb_v1.LADDER_RESULT`), seed
**20260908**, **1,000 draws** — `qb_v1.forecast`'s own defaults.
`p4b_volume.attach`, `.baselines`, `.build_forms` and `.draw` are called
unmodified: the same four functions `nfl/production/team_volume_v1.py`
imports.

**The D1 reconstruction is exact.** It re-selects `league_mean` for
`team_off_snaps` and `coach_prior` for `team_dropbacks_part`, form
`empirical` for both, and reproduces the frozen `volume_results.json` point
MAE to four decimals — **7.2547** and **6.7371**, and r = 0.11596740981063869
— on seasons strictly before 2025 with the form chosen on an inner 2024
validation.

**The V and S layers are proved observed, not assumed.** `simulate` returns
draw matrices but not the team-dropback level V or the share S behind them.
They are reproduced by seeding `numpy.random.default_rng` exactly as
`simulate` does and calling `qb2_lib._mix` in the same order, and the run
**raises unless `rint(V × S)` equals `simulate`'s own `db` matrix cell for
cell** on every row. It matched on all 540.

**Declared differences from the live production path** (all in inputs or
wiring; no estimator, prior or threshold was re-chosen):

| # | difference | why |
|---|---|---|
| R1 | `db_external = None`, so V and S are drawn inside `qb2_lib` | QB3's depth charts stop at 2024 |
| R2 | frame rebuilt from `qb.pkl` | `panel_enriched.pkl` absent |
| R3 | position inferred as "recorded a dropback" | the roster field lives in the missing panel |
| R4 | non-QB engine not run | none of it feeds passing yards |

**Forward chaining.** `qb2_lib.attach` cuts own history at a strictly earlier
ordinal by bisection; `qb2_lib.pools` is restricted to seasons strictly before
2025; P4B fits on seasons strictly before 2025 with an inner validation on
2024. No same-week information enters any layer.

**Eligibility, as it actually fell out:** 664 QB-game rows in 2025 → 544
primary passers → 4 excluded with **no prior appearance** (named in
`h1_run_meta.json`: MIN and TEN in week 1, CLE week 11, NYJ week 14) → 540
eligible. 0 further rows removed by the dropback floor.

---

## 7. The layer table

Signed mean error, both clusterings, MAE, RMSE, the standardized residual,
central-80% coverage against a nominal 0.80, and PIT χ² on 9 df.

| layer | n | bias | 95% CI game | 95% CI team | MAE | RMSE | z mean | z sd | cov P10–P90 | PIT χ² |
|---|---|---|---|---|---|---|---|---|---|---|
| team offensive plays | 540 | +1.7987 | [+1.238, +2.337] | [+0.786, +2.861] | 7.2472 | 9.3017 | +0.204 | 1.032 | 0.791 | 39.8 |
| team dropbacks (P4B) | 540 | +0.8736 | [+0.237, +1.511] | [−0.086, +1.916] | 6.6860 | 8.2728 | +0.103 | 0.972 | 0.807 | 20.9 |
| team dropbacks (QB layer) | 540 | +1.6369 | [+1.001, +2.251] | [+0.751, +2.556] | 6.7444 | 8.2436 | +0.194 | 0.983 | 0.804 | 28.5 |
| QB dropback share | 540 | −0.0778 | [−0.0868, −0.0687] | [−0.0975, −0.0605] | 0.1014 | 0.1387 | −0.279 | 0.424 | 0.952 | **929.0** |
| QB dropbacks | 540 | −1.3697 | [−2.099, −0.704] | [−2.583, −0.199] | 7.0838 | 9.1178 | −0.080 | 0.771 | 0.865 | 36.9 |
| QB attempts | 540 | −1.1394 | [−1.825, −0.486] | [−2.256, −0.021] | 6.6763 | 8.4291 | −0.073 | 0.803 | 0.870 | 26.8 |
| QB completions | 540 | −0.7248 | [−1.180, −0.257] | [−1.512, +0.080] | 4.6032 | 5.9135 | −0.073 | 0.811 | 0.874 | 25.6 |
| QB sacks | 540 | −0.0974 | [−0.242, +0.046] | [−0.316, +0.127] | 1.3789 | 1.7742 | −0.081 | 1.106 | 0.880 | 5.6 |
| QB scrambles | 540 | −0.1328 | [−0.266, −0.009] | [−0.303, +0.027] | 1.1598 | 1.5410 | −0.073 | 1.037 | 0.926 | 13.7 |
| QB rush opportunities | 540 | +0.1171 | [−0.064, +0.279] | [−0.179, +0.455] | 1.5864 | 2.0796 | +0.039 | 0.974 | 0.891 | 9.7 |
| QB passing TD | 540 | −0.1063 | [−0.206, −0.008] | [−0.235, +0.020] | 0.9331 | 1.1491 | −0.112 | 0.944 | 0.944 | 19.9 |
| QB interceptions | 540 | −0.0175 | [−0.084, +0.045] | [−0.073, +0.039] | 0.6744 | 0.8210 | −0.035 | 1.023 | 0.948 | 11.3 |
| attempts / dropback | 540 | +0.0028 | [−0.0027, +0.0085] | [−0.0062, +0.0115] | 0.0511 | 0.0662 | +0.041 | 0.926 | 0.774 | 17.1 |
| completions / attempt | 540 | −0.0031 | [−0.0109, +0.0050] | [−0.0125, +0.0059] | 0.0712 | 0.0895 | −0.014 | 0.797 | 0.843 | 11.0 |
| **yards / completion** | 540 | **+0.0268** | [−0.1895, +0.2242] | [−0.2829, +0.3098] | 1.9385 | 2.5098 | −0.002 | 0.898 | 0.800 | 9.8 |
| passing TD / attempt | 540 | −0.0035 | [−0.0068, −0.0004] | [−0.0074, +0.0001] | 0.0313 | 0.0403 | −0.093 | 0.845 | 0.889 | *see below* |
| passing TD / completion | 540 | −0.0034 | [−0.0080, +0.0012] | [−0.0089, +0.0017] | 0.0455 | 0.0573 | −0.070 | 0.834 | 0.904 | *see below* |
| INT / attempt | 540 | −0.0000 | [−0.0023, +0.0022] | [−0.0022, +0.0022] | 0.0224 | 0.0278 | −0.026 | 0.875 | 0.894 | *see below* |
| scrambles / rush opportunity | 470 | −0.0449 | [−0.0726, −0.0151] | [−0.0788, −0.0146] | 0.2653 | 0.3241 | −0.170 | 1.109 | 0.896 | 39.8 |
| **QB passing yards** | 540 | **−5.9223** | [−12.804, +0.426] | [−15.872, +4.334] | 59.6791 | 74.7766 | −0.053 | 0.765 | 0.882 | 31.2 |

70 rows are missing from the scrambles-per-rush-opportunity layer because
those quarterbacks had zero rushing opportunities; the ratio is undefined,
and the rows are dropped rather than imputed.

---

## 8. Calibration

**PIT.** Randomized PIT is used for every discrete count — dropbacks,
attempts, completions, sacks, scrambles, rush opportunities, passing TD,
interceptions, and both P4B team layers — as
`U = F(y−1) + V·(F(y) − F(y−1))`, one seeded draw per row. Continuous PIT is
used for the continuous quantities. Reporting an unrandomized PIT on a count
would have manufactured miscalibration, and the count layers are where the
TD and INT calibration question is answerable: **passing TD χ² = 19.9** and
**interceptions χ² = 11.3**, both on 9 df, both unremarkable.

**A PIT caveat I am raising against my own table.** The *ratio* layers
`passing TD / attempt`, `passing TD / completion` and `INT / attempt` take
only a handful of distinct values per game, because the numerator is a small
count. Their continuous PIT is therefore **not uniform under a perfect
model** for exactly the reason the brief warns about, and the χ² values they
produce (50.0, 44.1 and 621.9) are **artefacts of discreteness and must not
be quoted as miscalibration**. The TD and INT calibration answer is the count
layers above. The ratio rows remain useful for their signed error, which is
what Question D asks of them.

**Coverage against nominal.** Central 80% (P10–P90) intervals:

| layer | P10 (nominal 0.10) | P50 (nominal 0.50) | P90 (nominal 0.90) |
|---|---|---|---|
| passing yards | 0.0500 [0.033, 0.069] | 0.4481 [0.402, 0.491] | 0.9315 [0.909, 0.954] |
| yards / completion | 0.1093 [0.085, 0.134] | 0.4907 [0.451, 0.531] | 0.9074 [0.884, 0.930] |
| completions / attempt | 0.0778 [0.056, 0.103] | 0.4741 [0.430, 0.520] | 0.9167 [0.891, 0.939] |
| QB dropbacks | 0.0463 [0.030, 0.065] | 0.5185 [0.479, 0.558] | 0.8926 [0.867, 0.918] |
| QB attempts | 0.0481 [0.030, 0.067] | 0.4926 [0.451, 0.534] | 0.8944 [0.868, 0.920] |
| team offensive plays | 0.1426 [0.115, 0.170] | 0.5370 [0.501, 0.572] | 0.9296 [0.909, 0.950] |
| **QB dropback share** | 0.0481 [0.030, 0.067] | **0.1907** [0.157, 0.225] | **0.2111** [0.176, 0.247] |

Against a predeclared ±0.03 equivalence margin, five layers reach
`EQUIVALENT_WITHIN_MARGIN` at P90 — yards per completion, QB dropbacks, QB
attempts, attempts per dropback and QB completions — and **nothing reaches it
at P10 or P50**. Everything else is `NOT_SHOWN_EQUIVALENT`, which means the
data did not settle the question, **not** that the layer is miscalibrated.
Failure to reject a null is not evidence of adequacy, and the words
"calibrated" and "adequate" appear nowhere in this report except to say they
are withheld.

Passing yards is **over-dispersed**, not under-dispersed: the standardized
residual has SD **0.765** against 1.0, and central-80% coverage is 0.882
against 0.80. The model's intervals for passing yards are too wide, not too
narrow.

**Discrimination.** Passing yards: Pearson r **0.2438**, calibration slope
**0.4722**, intercept +119.29, and SD of the predicted means over SD of the
realisations **0.5163**. That slope well below 1 means the model's
game-to-game spread in central tendency is compressed relative to reality —
the same shape of problem, though not the same magnitude, that the MLB side
of this project records at an SD ratio of 0.18.

**Metrics refused.** CRPS, PIT and coverage are all computed, because full
draws are stored (`h1_pyds_draws.npy`, 540 × 1,000). **Log score is not
computed for passing yards**: a sample-based log score on a continuous
quantity needs a bandwidth, which is itself a free parameter. That is a
refusal, not an approximation.

---

## 9. What would make this confirmatory

Nothing in this report is. 2025 selected the L1 rung, the P4B estimator
family, the shrinkage constants and the eligibility conventions used here,
and a pre-registration written in 2026 does not restore independence to data
mined in 2025.

A confirmatory version needs **untouched games**, which means one of:

1. a **forward-chained future window** — 2026 weeks scored as they complete,
   with the methodology frozen and hashed before each week's kickoff, which
   the sealed-forecast machinery in `nfl/research/postgame/` already exists to
   do; or
2. a **sealed holdout** carved out before any of the design decisions above
   were taken, which does not exist and cannot be created retroactively; or
3. **nested cross-fitting** with every design decision — rung, estimator
   family, eligibility, shrinkage K — made inside the training fold, not
   outside it.

The share defect in section 1 is the one finding here large enough to be
worth a confirmatory test of its own, and it should be pre-registered against
a future window rather than re-measured on 2025.

---

## 10. Artifacts

| file | what |
|---|---|
| `H1_PREREGISTRATION.md` | eligibility, cuts, margins, clustering — written first |
| `H1_2025_QB_RESIDUALS.md` | this report |
| `H1_RESIDUALS.csv.gz` | 10,730 scored rows, one per layer per QB-game |
| `H1_SUMMARY.json` | every number above, machine-readable |
| `h1_run_meta.json` | frame hash, eligibility tally, P4B selections, q7 reconciliation |
| `h1_pyds_draws.npy` | 540 × 1,000 passing-yard draws |
| `h1_team_context.csv.gz` + `H1_CONTEXT_PROVENANCE.json` | 3,230 team-games, source hashes |
| `h1_context.py`, `h1_frame.py`, `h1_run.py`, `h1_analyse.py` | the code |

Reproduce with:

```
python3.12 nfl/research/v3/h1/h1_context.py
python3.12 nfl/research/v3/h1/h1_run.py
python3.12 nfl/research/v3/h1/h1_analyse.py
```

Every stage asserts a non-empty, schema-correct output and raises a named
error otherwise. No count in this report is quoted from the pre-registration;
every one is re-derived from the artifact.

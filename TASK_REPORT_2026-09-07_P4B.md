# P4B — Distributional team volume → absolute player opportunity

**Status:** complete. Research return only. Nothing was authorised, enabled or
promoted to production by this work.
**Branch/commit:** `main` @ `7555823`, repository `94924676jp-a11y/nfl`.
**Code and results:** `nfl/research/p4b/` (8 modules, 5 result artifacts, 2 logs).
**Pre-declaration:** `nfl/research/p4b/predeclaration_p4b.md`, written before any
coverage, CRPS or threshold number existed. Departures are labelled where they
occur and the original text was not edited.

---

## 1. The question, and the answer in one paragraph

> Can we obtain well-calibrated absolute player opportunity distributions by
> treating team offensive volume as uncertain rather than pretending its
> expectation is precisely known?

**Partly, and less than the framing suggests.** Treating the team total as a
random variable improves CRPS in **20 of 20 target-seasons**, every team-game
block-bootstrap interval excluding zero — so the direction is not in doubt. But
the size is small (0.35% to 4.5% of CRPS), and it is small for a reason the
oracle decomposition makes exact: **knowing the pie perfectly buys 5.4–18.5%
of MAE; knowing the player's slice perfectly buys 45–64%.** The slice is the
dominant unknown almost everywhere. The exception is sharp and is the most
useful thing in this return: **for players already near-certain to appear
(p ≥ 0.95), the volume gap reaches 28–35%, and for red-zone carries it exceeds
the share gap.** And on the strict test — randomised PIT — **the player-level
distributions are not calibrated**, in 18 of 20 target-seasons, for either
system. This return does not claim calibration it did not demonstrate.

---

## 2. Estimand, and why it is a product

For player *i* in team-game *g*:

```
opportunity_i  =  A_i · T_g · S_i
```

`A_i ∈ {0,1}` appearance · `T_g` the team total for that opportunity class ·
`S_i` the conditional share given appearance. The forecast object is the
**distribution** of that product. Zero is a **point mass** of weight
`1 − P(A_i)`, which is 27–31% of rows depending on target and season — not a
tail event, a structural feature.

**The identity is exact by construction and was verified, not assumed.**
Adversarial probe 4: over all 20 target-seasons, the largest
`|A_real · T_real · S_real − y|` is **7.105 × 10⁻¹⁵**. Probe 12 re-checks it at
the panel level: 409,858 share/denominator pairs across 83,144 rows, largest
reconstruction error 7.105 × 10⁻¹⁵. **No part of the oracle gap reported below
is a construction mismatch.**

### The one place this required rebuilding something

`snap_counts.offense_pct` carries **exactly 101 distinct values** (0.00…1.00) —
it is rounded to a whole percent. So `offense_pct × team_snaps` does not
reproduce `offense_snaps`, and the identity would have failed by the rounding.
Two consequences, both recorded in `mk_denom.py`:

- The team snap denominator is derived as the median of
  `offense_snaps / offense_pct` over players at **pct ≥ 0.75**. The first
  version of this used all players and measured a p95 implied-denominator
  spread of **0.397** — at pct = 0.02 the rounding admits a 50% error.
  Restricted to pct ≥ 0.75 the spread is **median 0.0056, p95 0.0100, max
  0.0118**.
- Snap share is therefore **recomputed** as `offense_snaps / team_off_snaps`,
  not taken from `offense_pct`.

Every other denominator is a sum over the identifier-repaired panel itself, so
it is the exact quantity its share is divided by. P4's `team_panel.csv` is
joined for `coach`, `home`, `rest`, `div_game` — context only, never a
denominator.

---

## 3. The four systems

| id | team total | status |
|---|---|---|
| **A** | deterministic point forecast (P4-style baseline family, chosen walk-forward) | the incumbent — pretends the pie is known |
| **B** | league-wide **unconditional** predictive distribution | eligible |
| **C** | **team-/coach-conditioned** predictive distribution | eligible |
| **D** | the **realised** team total | **DIAGNOSTIC ONLY — never eligible** |

All four share a byte-identical share layer and appearance layer, and B/C/D
reuse the same appearance and share draw matrices. **Any difference between
them is the volume treatment and nothing else.**

### D is quarantined by construction, and the quarantine is proved

`ELIGIBLE_SYSTEMS = ('A', 'B', 'C')`. `select_system()` filters to that tuple
before taking the CRPS minimum, and D is computed in a **separate pass that
runs only after `chosen` is already fixed**.

- **Probe 1 (behavioural, not textual):** handed a D with CRPS 0.0001 against a
  best eligible system at 4.0, `select_system` returns `'B'`. Across all 20
  target-seasons the systems ever chosen are `['B', 'C']`.
- **Probe 2 (guard-deletion proof):** widen the tuple to include `'D'` and the
  same call returns `'D'`. The guard is load-bearing, not decorative.
- **Probe 10:** substituting the realised total improves CRPS in 20/20
  target-seasons by **11.96% on average** (min 5.61%, max 21.81%). The leak
  channel is live and materially detectable — which is precisely why the
  quarantine has to exist rather than being an unused convenience.

---

## 4. Distribution forms: normality was tested, and the simple form won

Fitted on residuals `y − point_forecast` from **seasons strictly before** the
evaluation season. Nesting: the **form** is chosen by CRPS on an inner
validation season (ev − 1) with everything fitted on seasons before *that*, so
neither the point estimator nor the form ever sees the evaluation season
(probe 3: max training season strictly below evaluation season in 20/20).

### Normality diagnostics on the training residuals

| denominator | excess kurtosis | skew | P(\|z\|>1.96) | P(\|z\|>2.58) | P(\|z\|>3.29) | fitted t df |
|---|---|---|---|---|---|---|
| `team_off_snaps` | +0.08 … +0.22 | +0.13 … +0.14 | 0.045–0.049 | 0.011–0.013 | 0.0022–0.0031 | 30–200 |
| `team_dropbacks_part` | +0.15 … +0.22 | +0.15 … +0.22 | 0.050–0.053 | 0.013–0.015 | 0.0019–0.0028 | 30–50 |
| `team_targets` | +0.19 … +0.40 | +0.14 … +0.22 | 0.049–0.052 | 0.013–0.014 | 0.0019–0.0034 | 20–30 |
| `team_carries` | **−0.27 … −0.31** | +0.24 … +0.25 | 0.041–0.044 | 0.008–0.009 | 0.0000–0.0004 | 200 |
| `team_rz_carries` | +0.35 … +0.58 | **+0.69 … +0.85** | 0.032–0.050 | 0.016–0.021 | 0.0034–0.0051 | 20–30 |

Gaussian expectation is 0.050 / 0.010 / 0.001. **Team-volume residuals are
close to Gaussian and in one case (`team_carries`) thinner-tailed than
Gaussian.** Jarque–Bera rejects at p < 0.001 in 12 of 20 — but with n between
1,000 and 2,700 that is a statement about power, not about the size of the
departure, and the tail fractions above are the number that matters.
**Student-t is not justified by the tails**: where it was selected the fitted df
is 20–30, which is nearly Gaussian, and it never won by more than 0.3% of CRPS.
`team_rz_carries` is genuinely right-skewed (+0.69 to +0.85) — it is a small
count bounded below at zero — and there the **empirical** form won in 4/4
seasons.

**Chosen forms, by inner validation:** empirical 12/20, student_t 4/20,
gaussian 3/20, team_empirical 0/20, coach_empirical 1/20.

### The conditional forms do not earn their place

`team_empirical` / `coach_empirical` (≥ 24 prior games, else falling back to the
league pool) beat the best unconditional form on the inner validation season in
**2 of 20** target-seasons. At the player level, C − B on CRPS with a team-game
block bootstrap is **negative in 4 of 20 and significantly negative in 0 of 20**;
it is significantly *worse* than B in **7**. **Conditioning the volume distribution
on team or coach buys nothing.** This is consistent with P4, which found team
history carries essentially no information about next-game volume.

---

## 5. The team-volume layer on its own

The point forecasts confirm P4 on a different set of denominators:

| denominator | point estimator chosen (walk-forward) | MAE | r |
|---|---|---|---|
| `team_off_snaps` | league_mean ×3, coach_prior ×1 | 6.93–7.26 | 0.000–0.080 |
| `team_dropbacks_part` | coach_prior ×4 | 6.31–6.78 | 0.071–0.313 |
| `team_targets` | ewma ×3, coach_prior ×1 | 5.88–6.43 | 0.175–0.353 |
| `team_carries` | coach_prior ×4 | 5.87–6.23 | 0.149–0.209 |
| `team_rz_carries` | league_mean ×2, coach_prior ×2 | 2.44–2.53 | 0.000–0.119 |

**The league mean is the walk-forward-selected estimator for team offensive
snaps in three seasons of four, with r = 0.000 twice.** Team snap volume is not
forecastable in this feature set. That is P4's finding, reproduced on a
denominator P4 did not use.

The **distributions**, by contrast, are well behaved at the team level:
90% coverage 0.888–0.953, 50% coverage 0.458–0.573, 95% coverage 0.934–0.978.
Negative draws (a denominator cannot be negative, so draws are clipped at zero)
are ≤ 0.04% everywhere except `team_rz_carries` in 2022 (2.35%) and 2025
(1.62%), where the mean is near 5 and the residual SD is 3.0.

**Read that correctly.** A well-calibrated distribution around an
uninformative point forecast is exactly what an honest treatment of an
unforecastable quantity looks like. It is not evidence that the quantity became
forecastable.

---

## 6. Share and appearance layers — reused, not rebuilt

Carried over from P1–P3 unchanged: the identifier-repaired panel
(`panel_p3.csv`), the zero-extension to the pregame candidate set, the
appearance × conditional-usage separation, **EWMA half-life 3** on prior
**appeared** games as the conditional share model, the P3 information-quality
classes, and the P3 Stage-A appearance model at its full feature set
(injury features for 2022–2024; **2025 carries none**, because
`injuries.date_modified` is absent for that season — stated, not absorbed).
**No P1–P3 candidate that was not accepted was promoted here.**

Probe 11 replays the share history: 47,215 player-games across 1,126 players,
the stored history at every row equals the list of strictly-earlier **appeared**
shares, 0 mismatches.

### One honest weakness in the share layer

Share draws are `EWMA + residual`, residual resampled within position from
prior seasons, then clipped to [0,1]. **Clipping rates are high**: snaps 9.9%,
pass_snaps 12.9%, carries 16.2%, targets 18.7%, **rz_carries 27.5%**. An
additive residual on a bounded share is the wrong functional form at the
boundary and this is where it shows.

**Departure, labelled, and it did not rescue the problem.** A residual pool
conditioned on (position, decile of the point share) was run as a sensitivity.
It cuts clipping sharply (snaps 10.0% → 2.1%, pass_snaps 12.8% → 3.1%,
carries 16.4% → 9.0%) but moves CRPS by **less than 0.6% in either direction**
(9 of 20 target-seasons better, 11 worse). The declared simple pool therefore
stands, and the boundary problem is recorded as open rather than fixed.

---

## 7. Targets carried, and the two that were not

| target | share | denominator | positions |
|---|---|---|---|
| `snaps` | offense_snaps / team_off_snaps | `team_off_snaps` | WR TE RB |
| `pass_snaps` | rpr | `team_dropbacks_part` | WR TE RB |
| `targets` | target_share | `team_targets` | WR TE RB |
| `carries` | carry_share | `team_carries` | RB |
| `rz_carries` | rz_carry_share | `team_rz_carries` | RB |

`nonqb_carries` and `designed_qb_rush` were **not carried**. Reason, stated
rather than silently dropped: in P1 both are modelled as **direct counts**, not
as a share of a team denominator, so neither can enter the mandatory oracle
decomposition, which is a decomposition of a product. Including them would have
meant inventing a share layer for them here, which is new modelling the
directive did not ask for. **`rpr` remains a participation proxy — true routes
are not manufactured.**

---

## 8. Headline results — CRPS, pooled over 2022–2025

| target | CRPS A | CRPS B | B − A | CRPS D\* | D\* − A | cov90 A | cov90 B | w90 A | w90 B |
|---|---|---|---|---|---|---|---|---|---|
| `snaps` | 6.8386 | **6.8146** | **−0.35%** | 6.4097 | −6.27% | 0.928 | 0.947 | 38.86 | 40.81 |
| `pass_snaps` | 4.3750 | **4.2925** | **−1.88%** | 3.7360 | −14.61% | 0.897 | 0.943 | 22.27 | 25.31 |
| `targets` | 0.9566 | **0.9445** | **−1.27%** | 0.8950 | −6.44% | 0.936 | 0.953 | 5.40 | 5.81 |
| `carries` | 2.0917 | **2.0589** | **−1.57%** | 1.8375 | −12.15% | 0.933 | 0.957 | 12.08 | 13.33 |
| `rz_carries` | 0.5842 | **0.5581** | **−4.46%** | 0.4656 | −20.30% | 0.936 | 0.962 | 3.21 | 3.79 |

\* D is the oracle. It is reported to size the ceiling, never as a candidate.

### Per-season, with team-game block bootstrap

Clustering is by **team-game**, because players on the same team-game share a
volume draw and a game script. This is methodology fix #1 from the platform
brief applied rather than noted. 507–544 clusters per cell.

**B − A on CRPS is negative in 20 of 20 target-seasons and the 95% interval
excludes zero in 20 of 20.** Range of the point estimate: −0.0112 (targets
2023) to −0.0988 (pass_snaps 2025). **C − B excludes zero on the negative side
in 0 of 20**, and is significantly *positive* — C worse — in 5.

Full per-season table: `nfl/research/p4b/p4b_results.json`, key `bootstrap`.

---

## 9. The mandatory oracle decomposition

Five arms. PP is the live forecast; RRR is the identity check.

| arm | volume | share | appearance |
|---|---|---|---|
| PP | projected | projected | projected |
| RP | **realised** | projected | projected |
| PR | projected | **realised** | projected |
| RR | **realised** | **realised** | projected |
| RRR | **realised** | **realised** | **realised** |

Pooled 2022–2025, MAE:

| target | PP | RP (know the pie) | PR (know the slice) | volume gap | share gap |
|---|---|---|---|---|---|
| `snaps` | 9.980 | 9.443 | 3.896 | **−5.4%** | **−61.0%** |
| `pass_snaps` | 6.277 | 5.516 | 2.877 | **−12.1%** | **−54.2%** |
| `targets` | 1.412 | 1.328 | 0.509 | **−5.9%** | **−63.9%** |
| `carries` | 3.064 | 2.723 | 1.415 | **−11.1%** | **−53.8%** |
| `rz_carries` | 0.864 | 0.704 | 0.475 | **−18.5%** | **−45.0%** |

**The slice is the dominant unknown for every target.** RRR is exact to
7.1 × 10⁻¹⁵, so none of this gap is construction error.

### The decomposition by appearance uncertainty — the sharpest result here

| target | cohort | n | volume gap | share gap |
|---|---|---|---|---|
| `snaps` | p < 0.50 | 7,401 | −0.7% | −52.6% |
| | p 0.50–0.80 | 7,464 | −1.1% | −64.7% |
| | p 0.80–0.95 | 10,582 | −3.9% | −68.0% |
| | **p ≥ 0.95** | 5,996 | **−18.2%** | −50.5% |
| `pass_snaps` | p < 0.50 | 7,393 | −1.0% | −53.1% |
| | **p ≥ 0.95** | 5,991 | **−35.5%** | −35.2% |
| `carries` | p < 0.50 | 2,254 | −1.1% | −60.4% |
| | **p ≥ 0.95** | 1,088 | **−27.7%** | −32.1% |
| `rz_carries` | p < 0.50 | 2,105 | −5.1% | −66.3% |
| | **p ≥ 0.95** | 1,021 | **−35.1%** | **−21.3%** |

**The value of knowing the team's pie is concentrated almost entirely in the
players you are already sure will play.** For a near-certain workhorse the
volume gap approaches, matches, or (red-zone carries) exceeds the share gap.
For a player whose appearance is in doubt, knowing the pie is worth ~1% — the
error is dominated by whether he plays at all. That is a structural statement
about where modelling effort pays, and it is stable across all four seasons.

### By position, role stability, information quality

- **Position.** Volume gap is largest for WR on pass snaps (−14.2%) and RB on
  red-zone carries (−18.5%); share gap 45–69% everywhere. B's CRPS gain over A
  is biggest for WR (−2.29% on pass snaps) and smallest for RB snaps (−0.07%).
- **Role stability.** For `role_change` rows the **volume** gap collapses
  (snaps −1.9% vs −7.5% for stable rows) while the share gap holds near −61%.
  When a player's role is moving, the team total is not the thing you are
  missing.
- **Information quality (P3 classes).** The volume gap is consistently *larger*
  in the HIGH class (carries −16.3% vs −9.9% MEDIUM; rz_carries −24.0% vs
  −17.2%). Better availability information shifts the residual uncertainty
  toward the pie — the same mechanism as the p ≥ 0.95 result.

Full tables: `nfl/research/p4b/p4b_results2.json`, key `subgroups`.

---

## 10. Interval calibration — and the reason the first PIT was uninterpretable

Raw coverage, pooled, system A → B:

| level | snaps | pass_snaps | targets | carries | rz_carries |
|---|---|---|---|---|---|
| 50% | 0.638 → 0.659 | 0.611 → 0.662 | 0.650 → 0.671 | 0.664 → 0.708 | 0.684 → 0.722 |
| 80% | 0.867 → 0.888 | 0.836 → 0.886 | 0.868 → 0.888 | 0.867 → 0.897 | 0.871 → 0.904 |
| 90% | 0.928 → 0.947 | 0.897 → 0.943 | 0.936 → 0.953 | 0.933 → 0.957 | 0.936 → 0.962 |
| 95% | 0.954 → 0.975 | 0.924 → 0.971 | 0.969 → 0.981 | 0.968 → 0.983 | 0.959 → 0.986 |

Two things are visible and they point in opposite directions.

1. **At 90%, system A is genuinely too narrow for `pass_snaps` (0.897) and B
   fixes it (0.943).** That is the distributional treatment doing the job it
   was built for.
2. **At 50%, every system is badly over-covered (0.61–0.72 against 0.50).** This
   is not a width problem — it is the **atom at zero**. Roughly 28–31% of rows
   are absences with y = 0, and for those the 25th percentile of the predictive
   is also 0, so the interval contains the outcome by construction. Widening
   would make this worse, not better.

**The ordinary PIT is therefore not a calibration diagnostic here.** A mixed
distribution with an atom does not have a uniform PIT even when the forecast is
perfect, which is why the first pass produced χ² values in the thousands on 9
degrees of freedom. The **randomised PIT**,
`u = F(y⁻) + V·(F(y) − F(y⁻))`, `V ~ U(0,1)`, is uniform under a correct
forecast for any distribution, and that is the number to read:

| target | rPIT χ² A (range) | rPIT χ² B (range) |
|---|---|---|
| `snaps` | 43.9 – 101.1 | 35.6 – 106.2 |
| `pass_snaps` | 162.4 – 236.4 | 67.9 – 112.9 |
| `targets` | 149.4 – 223.8 | 69.6 – 146.4 |
| `carries` | 36.7 – 60.8 | **8.9 – 30.2** |
| `rz_carries` | 203.3 – 265.5 | 74.0 – 144.3 |

Critical value at p = 0.001 on 9 df is **27.877**.

**Read plainly: these distributions are not calibrated.** B improves the
randomised PIT over A in 17 of 20 target-seasons — sometimes by a factor of
three — but only **`carries` 2024 (8.9)** and marginally **`carries` 2023
(29.0)** and **`carries` 2025 (30.2)** come anywhere near the threshold. Per
the platform's rule 8, no equivalence margin was pre-declared and no TOST was
run, so nothing here is written as "calibrated", "stable" or "correct". What is
established is a **direction** (B is better calibrated than A) and a **failure**
(neither is calibrated).

Three seasons of `snaps` are the exception where A's randomised PIT beats B's
(43.9 vs 72.7 in 2022) even though B's CRPS is better. Adding volume spread to a
target whose intervals were already near-nominal at 90% pushes it past nominal.
That is reported rather than smoothed away.

---

## 11. Threshold calibration on the pre-declared grid

Grids fixed in the pre-declaration before any number existed, and probe 8
checks the code grid against the pre-declaration **text**, verbatim:

- carries 5.5 / 9.5 / 12.5 / 15.5 / 19.5
- targets 2.5 / 4.5 / 6.5 / 8.5 / 10.5
- snaps 10.5 / 20.5 / 30.5 / 40.5 / 50.5 (also applied to `pass_snaps`)
- **`rz_carries` had no pre-declared grid, so no exceedance calibration is
  reported for it.** Inventing a grid now, after seeing the distribution, is
  exactly the move a pre-declaration exists to prevent.

Calibration-in-the-large (mean forecast P(Y > t) minus observed rate), pooled
sign pattern:

| | low threshold | mid | high |
|---|---|---|---|
| A | **+0.011 … +0.053** | +0.005 … +0.036 | −0.028 … +0.012 |
| B | **+0.008 … +0.042** | −0.012 … +0.031 | −0.012 … +0.011 |

Two readings:

- **B fixes the high-threshold miss.** `pass_snaps` at 40.5: A is −0.024 to
  −0.028 (systematically under-forecasting the chance of a heavy pass-snap
  workload) and B is +0.002 to +0.004. Same story on `carries` at 19.5. This is
  the volume distribution supplying tail mass that a point total cannot.
- **Both over-forecast the low thresholds by 1–5 points.** This tracks the mean
  bias: B over-predicts in 19 of 20 target-seasons, by 0.03 to 0.72 units
  (the one exception is `pass_snaps` 2023, +0.125 the other way). It is a
  real defect, it is not fixed by the volume treatment, and it is the same
  bias P2/P3 carry.

Brier scores are in `p4b_results2.json` with 5-bin reliability tables.

---

## 12. Monte Carlo specification

1,000 draws per player-game, seed **20260907**, streams offset per component.
Probe 6 shows the declared stream reproduces exactly and a different stream does
not.

**Team-volume draws are shared across every player on a team-game** — the same
column *j* is the same simulated game for every teammate. Probe 5 verifies it at
the array level: two players gathered onto the same team-game receive
byte-identical 1,000-draw vectors, and a different team-game differs.

Cost: the whole study is 98 s for the primary pass and 27 s for the second.

---

## 13. Covariance diagnostics — the J0 preparation, and it found a real defect

Because volume draws are shared, the team-level sum of simulated player
opportunities is a meaningful object. Two findings:

**(a) Sharing the volume draw fixes team-sum coverage.** 90% coverage of the
realised team sum:

| target | system A | system B |
|---|---|---|
| `snaps` | 0.825 – 0.873 | 0.921 – 0.960 |
| `pass_snaps` | **0.676 – 0.735** | 0.919 – 0.954 |
| `targets` | 0.805 – 0.853 | 0.947 – 0.974 |
| `carries` | 0.903 – 0.926 | 0.967 – 0.974 |
| `rz_carries` | 0.773 – 0.804 | 0.945 – 0.960 |

With a deterministic total, independent player draws under-disperse the team
sum badly — 0.68 against a nominal 0.90 for pass snaps. A shared volume draw is
the correct fix and it works.

**(b) But the share layer is incoherent, and this is the finding that matters
for J0.** Drawn shares are sampled independently per player and do not respect
the constraint that they sum to the whole pie:

| target | Σ drawn shares | Σ realised shares | over-allocation |
|---|---|---|---|
| `snaps` | 6.16 – 6.48 | 4.87 – 4.90 | **+27%** |
| `pass_snaps` | 6.20 – 6.53 | 4.92 – 4.94 | **+28%** |
| `targets` | 1.32 – 1.38 | 0.99 | **+34%** |
| `carries` | 1.07 – 1.15 | 0.80 | **+35%** |
| `rz_carries` | 1.13 – 1.21 | 0.77 – 0.80 | **+45%** |

(Realised sums are below 1.0 for `targets`/`carries` because the evaluated set
is restricted to rows with ≥ 1 prior game; the comparison is drawn-vs-realised
on the identical row set, so the ratio is the number to read.)

**Independent share draws allocate roughly a third more of the pie than
exists.** Also visible in the same table: the mean SD of the simulated team sum
under B is 66.3–69.5 for `snaps` against a realised between-game SD of 44.4–47.2
— the simulated team sums are about 50% too dispersed, which is the same defect
seen from the other side.

This is a concrete, quantified constraint that a joint game simulator has to
impose, and it is exactly what P4B was asked to prepare. **It is not fixed
here** — imposing the constraint is new modelling and was not authorised.

---

## 14. Discrimination of the mean forecast (system B)

| target | r | R² | sd(pred)/sd(actual) | bias | MAE | RMSE |
|---|---|---|---|---|---|---|
| `snaps` | 0.718–0.777 | 0.512–0.603 | 0.760–0.771 | −0.03 … −0.72 | 9.72–10.56 | 13.49–14.49 |
| `pass_snaps` | 0.707–0.768 | 0.498–0.590 | 0.744–0.751 | +0.13 … −0.47 | 6.15–6.56 | 8.65–9.19 |
| `targets` | 0.689–0.737 | 0.466–0.541 | 0.725–0.758 | −0.09 … −0.24 | 1.43–1.49 | 2.05–2.16 |
| `carries` | 0.729–0.765 | 0.531–0.581 | 0.721–0.757 | −0.13 … −0.35 | 3.10–3.30 | 4.35–4.76 |
| `rz_carries` | **0.513–0.573** | 0.242–0.326 | **0.538–0.598** | −0.08 … −0.19 | 0.91–0.96 | 1.33–1.40 |

Reported because the platform brief insists calibration and discrimination are
different properties. The SD ratio is the between-player spread of conditional
predicted means against realised spread — it is not evidence about predictive
width, and the coverage table above is the relevant number for that.
`rz_carries` is the weakest target on every measure.

---

## 15. Adversarial probes

**14 probes, 0 failing** (`nfl/research/p4b/p4b_adversarial.json`).

| # | probe | what it actually asserted |
|---|---|---|
| 1 | oracle D cannot be selected | selection handed an unbeatable D returns `'B'`; systems ever chosen: `['B','C']` |
| 2 | **guard-deletion proof for #1** | widening the eligibility tuple makes selection return `'D'` — #1 is load-bearing |
| 3 | volume residuals prior-season only | max training season strictly below eval season in 20/20 |
| 4 | oracle identity exact | largest \|A·T·S − y\| = 7.105e-15 over 20 target-seasons |
| 5 | volume draws shared within a team-game | byte-identical 1000-draw vectors for teammates; different team-games differ |
| 6 | reproducible under the declared seed | declared stream reproduces; a different stream does not |
| 7 | forbidden fields never read | 7 modules scanned for **accesses** (`['x']`, `.get('x')`), not mentions, of 13 banned names; 0 hits |
| 8 | threshold grid matches the pre-declaration | code grid equals the pre-declaration text; `rz_carries` is `None` because none was declared |
| 9 | coverage does not select | a system with exactly nominal coverage and 10× the CRPS is not chosen |
| 10 | leak channel is live | realised-total substitution improves CRPS 20/20 by 11.96% mean — the quarantine matters |
| 11 | share history is prior-appeared only | 47,215 player-games, 1,126 players replayed, 0 mismatches |
| 12 | panel/denominator agree exactly | 409,858 pairs, largest reconstruction error 7.105e-15 |
| 13 | no 2026 data entered | panel seasons [2020…2025]; volume seasons [2020…2025] |
| 14 | no market or wagering artifact | 18 files, none names a market, wager, lineup or book |

Probe 7 is written the way it is because **P4's first version of the same check
matched its own explanatory comment** and passed for the wrong reason.

---

## 16. The negative-result clause, discharged

The pre-declaration said: *if stochastic volume does not improve CRPS, or if
intervals cannot reach approximately nominal coverage without becoming so wide
that CRPS worsens, the return says the distributional treatment does not help,
in those words.*

**It does help, so that clause is not triggered — but the honest version of the
sentence is narrower than the clause anticipated:**

- Stochastic volume **improves CRPS in 20 of 20 target-seasons**, significantly
  under team-game clustering, and it does so while *widening* the intervals
  (w90 up 5–18%). CRPS penalises both, so this is a genuine improvement, not
  bought width.
- **But the improvement is small** — 0.35% to 4.5% — and the oracle
  decomposition says why: the pie is 5.4–18.5% of the problem and the slice is
  45–64%.
- **And the intervals are still not calibrated.** Randomised PIT rejects in 18
  of 20 target-seasons. The distributional treatment moves calibration in the
  right direction without reaching it.

So the answer to the directive's question is: **yes to "better", no to
"well-calibrated".**

---

## 17. Departures from the pre-declaration

| # | declared | done | why |
|---|---|---|---|
| 1 | System A = "the P4 best baseline" | A's point estimator is chosen **walk-forward** from the P4 baseline family on seasons strictly before evaluation | "best baseline" can only be identified after seeing the evaluation season. Choosing it that way would have been post-hoc selection |
| 2 | share residual pool "within position" | run as declared **and** as a (position, decile-of-point) sensitivity, both reported | the additive residual clips 10–28% of draws at the [0,1] boundary; the sensitivity tests whether that matters (it does not: <0.6% CRPS) |
| 3 | targets included `nonqb_carries`, `designed_qb_rush` | **not carried** | neither is modelled as share × denominator in P1, so neither can enter the mandatory product decomposition |
| 4 | snap share from `offense_pct` | recomputed as `offense_snaps / team_off_snaps` | `offense_pct` is rounded to a whole percent; the oracle identity would have failed by the rounding |
| 5 | PIT histogram | ordinary PIT **and** randomised PIT | the predictive is mixed with a 28–31% atom at zero; ordinary PIT is not uniform even for a perfect forecast |

---

## 18. Constraints honoured

Nothing in the standing prohibition list was touched. **NFL-1 was not
authorised or executed. G0A was not modified. The T−90 capture path was not
modified. No 2026 outcome was consumed** (probe 13). **No sportsbook market was
ingested; no market-derived feature exists** (probe 7, probe 14). No
receiving/rushing efficiency, no touchdowns, no fantasy points. **The full joint
simulator was not built** — §13 states what it would have to impose, and stops
there. No DFS, no lineup optimisation, **no wager is recommended and none is
discussable.** `weekly_rosters.status` is not read. Observed-weather fields are
not read. nflfastR's `xpass`/`pass_oe` remain quarantined and are not read. No
frozen 2026 artifact was modified. No new provider was imported.

Repository state is otherwise unchanged: **G0A 11 PASS / 1 FAIL**; **1,230 assertions across 19
suites, 0 failing** (16 NFL suites totalling 1,137 plus 3 platform-governance
suites totalling 93 — re-enumerated from the filesystem for this return, not
quoted from a written-down count); pre-flight 10 checks, 0 failing; first T−90 window
`2026_01_NE_SEA` opens `2026-09-09T22:50:00Z`, and coverage correctly reports
`DEFERRED[NO_WINDOW_HAS_CLOSED_YET]`.

---

## 19. What this changes about the next step, and what it does not

**What P4B establishes.**

1. Treating the team total as uncertain is correct and should be kept. It is
   cheap, it never hurt, and it repairs team-sum dispersion outright
   (0.68 → 0.94 coverage on pass snaps).
2. The **unconditional** distribution is the whole of it. Team- and
   coach-conditioning is not supported and should not be carried forward.
3. **Effort belongs on the slice, not the pie** — except for the near-certain
   starters, where the pie is half the remaining error or more.
4. A joint simulator must impose the share-sum constraint. Independent draws
   over-allocate by roughly a third, and that number is now measured rather
   than suspected.

**What it does not establish.** It does not establish calibration. It does not
establish that any of this survives a season not used in construction — 2022–25
were all used to fit residual pools for later seasons, and the walk-forward
design controls leakage but does not create a sealed holdout. It does not touch
prices, edges, or economic usefulness, and nothing here brings any market
closer to the sample floors.

**Stopping here, as instructed.** No further work is authorised.

---

*Artifacts: `nfl/research/p4b/` — `predeclaration_p4b.md`, `mk_denom.py`,
`p4b_panel.py`, `p4b_volume.py`, `p4b_lib.py`, `run_p4b.py`, `run_p4b2.py`,
`run_p4b_adversarial.py`, `denom_diag.json`, `volume_results.json`,
`p4b_results.json`, `p4b_results2.json`, `p4b_adversarial.json`, and the two
run logs.*

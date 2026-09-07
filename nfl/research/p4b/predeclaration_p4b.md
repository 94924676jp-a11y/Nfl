# P4B pre-declaration — written before any distribution was fitted

Written 2026-09-07, before any coverage, CRPS or threshold number existed.
Departures are labelled where they occur; the original text stays.

## 1. The estimand

For player *i* in team-game *g*:

```
opportunity_i = A_i · T_g · S_i
```

`A_i ∈ {0,1}` appearance · `T_g` the team total for that opportunity class ·
`S_i` the player's conditional share given appearance. The forecast is the
**distribution** of that product, not its mean. Zero is a point mass with weight
`1 − P(A_i)`, exactly as in P2.

## 2. The four systems, fixed now

| id | team total | purpose |
|---|---|---|
| **A** | deterministic point estimate (the P4 best baseline) | the incumbent — pretends the pie is known |
| **B** | wide unconditional predictive distribution | league-wide residuals, no team information |
| **C** | conditional predictive distribution | residuals conditioned on team/coach level, only where P4 supports it |
| **D** | **realized** team total | **DIAGNOSTIC ONLY — never eligible for forecasting** |

All four share an identical share layer, so any difference between them is
attributable to the volume treatment alone.

**D is quarantined by construction**: it is computed in a separate pass, never
enters model selection, and an adversarial probe asserts it cannot.

## 3. Distribution forms, simplest first

Fitted on residuals `y − point_forecast` from seasons strictly before the
evaluation season:

1. empirical residual distribution (resampled)
2. Gaussian approximation
3. Student-t, only if the empirical tails justify it — tested, not assumed
4. team-conditioned empirical, only where a team has ≥ 24 prior games
5. coach-conditioned, only because P4 measured a coach prior as the best simple
   baseline in 13 of 36 target-seasons

**Normality is tested, not assumed.** Excess kurtosis and a tail-ratio check are
reported before any Gaussian is used.

## 4. Share layer — reused, not rebuilt

P1–P3 accepted results are carried over unchanged: the identifier-repaired
panel; appearance × conditional-usage separation; EWMA half-life 3 as the
conditional share model; the information-quality classes; P2's redistribution
conclusions. **No P1–P3 candidate that was not accepted is promoted here.**

Share uncertainty is the empirical distribution of `S_actual − S_EWMA` over
prior seasons, taken within position.

## 5. Targets

`snaps` (team plays × snap share) · `pass_snaps` (team dropbacks × rpr) ·
`targets` (team targets × target share) · `carries` (team carries × carry share)
· `nonqb_carries` · `designed_qb_rush` · `rz_carries` where supported.
Denominators are P1's, unchanged. **True routes are not manufactured** — `rpr`
stays a participation proxy.

## 6. Evaluation

Strict chronological walk-forward, 2022–2025 evaluated separately. Reported per
target and system: MAE of the predictive mean, RMSE, r, R², bias, CRPS, interval
coverage at 50/80/90/95, mean interval width, PIT histogram, and exceedance
calibration on a **predeclared** threshold grid:

- carries: 5.5, 9.5, 12.5, 15.5, 19.5
- targets: 2.5, 4.5, 6.5, 8.5, 10.5
- snaps: 10.5, 20.5, 30.5, 40.5, 50.5

**Thresholds are fixed here and are not adjusted after seeing results.** No
sportsbook price is ingested; these are probability-calibration tests only.

**Coverage alone does not decide anything.** A system that hits nominal coverage
by being uselessly wide is reported as such — coverage and sharpness are judged
together, and CRPS is the single number that penalises both.

## 7. Oracle decomposition, mandatory

Four arms per target: projected×projected, **realized**×projected,
projected×**realized**, realized×realized. The gap between arm 1 and arm 2 is
the cost of not knowing the pie; between arm 1 and arm 3 the cost of not knowing
the slice. Reported by season, position, role stability, appearance uncertainty
and information quality.

## 8. Monte Carlo

1,000 draws per player-game, seed 20260907. Team-volume draws are **shared
across all players on a team-game**, which is what makes the covariance
diagnostic meaningful and is the J0 preparation the directive asks for.

## 9. What would count as a negative result

If stochastic volume does not improve CRPS over the deterministic total, or if
intervals cannot reach approximately nominal coverage without becoming so wide
that CRPS worsens, the return says the distributional treatment does not help,
in those words.

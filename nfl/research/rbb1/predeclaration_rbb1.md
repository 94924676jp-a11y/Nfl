# ROUTE-BB1 PRE-REGISTRATION — clean-room route participation, build vs buy

Written and hashed **before any result was computed**. Frozen.

## 0. What this is and is not

A **build-vs-buy** experiment. Not an attempt to clone FTN, not a route-type
classifier, not a production change. Nothing is promoted.

**The FTN sample is SEALED.** sha256
`56fc32e21cb130c1e14a8b3817f0c43491b310e69cfd4663b5bbd5d973ccffa4`,
1,862,143 bytes, recorded before any work. The contract PDF is sha256
`55b885559320f6c112cfab0eab07e17f7c67fbca5bc2d3e916da5e134f878f8d`.
No FTN observation may enter the audit, the estimator, or any training or
selection decision. §G is performed only if permitted use is established; if
unclear it is marked `CONTRACT_GATED` and not performed.

## 1. The primitive

**MUST-HAVE:** `player × dropback → route_run {0,1}`, aggregating to routes per
player-game, route participation rate, and targets per route.

**NICE-TO-HAVE, explicitly out of scope here:** pass-protection assignment,
alignment, route type, coverage faced.

## 2. Frame

nflverse-derived `panel_p3` player-game panel, seasons 2020–2025, positions
WR/TE/RB with `pass_snaps ≥ 1`. Evaluation seasons **2022–2025**, walk-forward,
prior-only. Seed **20260908**, fixed now.

## 3. The decisive algebraic question, declared in advance

The candidate architecture replaces the denominator:

    CONTROL     targets ~ pass_snaps        × (targets / pass_snaps)
    CANDIDATE   targets ~ estimated_routes  × (targets / estimated_routes)

with `estimated_routes = pass_snaps × p`, `p` the route participation rate.

**Predeclared claim to be tested, not assumed:** if `p` is a function of
position only — constant across a player's games — it **cancels exactly** and
the candidate is algebraically identical to the control, producing ΔCRPS = 0.
The value of route information therefore lies entirely in its **game-to-game
variation**, not in its level.

This is stated before running because it determines what the experiment must
measure, and because a large positive result for a position-constant estimator
would be evidence of an implementation error rather than of route value.

## 4. Estimator family — CLOSED

`E0` position constant · `E1` position × prior-history context · `E2` position
× team pass-rate context. No broad feature search, no hyperparameter garden,
no route-type modelling. Shrinkage K = 4 and EWMA half-life 2 are inherited
constants and are not tuned here.

## 5. The necessity curve — the experiment that decides without labels

True routes are unobservable in every source available to this project, so no
estimator can be **fitted** to them and no accuracy can be **measured** here.
Rather than pretend otherwise, the decisive experiment is a sensitivity
analysis run in the opposite direction:

> inject a route participation rate with **known, controlled** game-to-game
> dispersion, and measure downstream target CRPS as a function of that
> dispersion.

This yields the quantity the purchase decision actually needs: **how much
game-varying route signal must exist before it is worth anything downstream.**
Dispersion grid predeclared as coefficient of variation
`CV ∈ {0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40}`, per position, both as an
oracle (the injected rate is known at prediction time) and as a candidate (only
a prior-only estimate of it is known).

The oracle arm is an **upper bound** on what any route data could buy, FTN's
included. That bound is the number the $5,000 decision should be read against.

## 6. Metrics

Primary: **player target-distribution CRPS**. Also MAE, RMSE, bias, Pearson r,
interval coverage at 50/80/90, season-by-season, and per position.
Game-clustered bootstrap, 400 resamples. Naive intervals are forbidden.

## 7. Accounting

Estimated routes must satisfy, per player-game: `0 ≤ routes ≤ pass_snaps`;
team routes ≤ team dropbacks × eligible receivers; no negative or fractional
counts where counts are claimed. Violations are reported, never clipped.

## 8. Decision vocabulary — exactly one

`BUILD` · `BUILD_REQUIRES_MORE_INFORMATION` · `DATA_BLOCKED_BUY_CANDIDATE` ·
`NO_ROUTE_VALUE_DETECTED` · `CONTRACT_GATED`

The decision follows measured information availability and measured downstream
value. **Avoiding a $5,000 expense is not evidence** and may not influence the
classification.

## 9. Forbidden

No FTN data as input, label, feature, threshold or selection criterion. No
scraping of FTN systems. No market, DFS, props or betting data. No restricted
PFF / SIS / PFR fields. No 2026 outcomes. No fuzzy name matching. No change to
any production model. No promotion. No result-driven change to anything above.

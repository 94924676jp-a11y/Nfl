# Forward-chained verdict: what the multi-season prior actually earns

> **SUPERSEDED 2026-09-28 ON ITS CENTRAL CLAIM. Do not quote the ranking conclusion below.**
>
> Everything here was measured with `forward_chain.historical_band`, which assigns ONE role band per
> player per season from the previous season. **Production does not do that** -- the live path
> rebuilds role state weekly. Reconstructing a point-in-time weekly band (proved point-in-time by
> rebuilding it from a panel with the scored week deleted) and re-running the same comparison flips
> the sign: the season-constant band loses to `CURRENT_SEASON_ONLY` by -0.0364 rho, reproducing the
> finding below, and a **production-matching weekly capped band beats it by +0.0151 (z 3.2) on
> selection and +0.0336 (z 3.7) on confirmation**, and on MAE as well.
>
> So "the prior costs ordering" was a fact about the harness, not about the prior. The magnitude of
> the harness defect (-0.036 rho) is twice the gap this document rested on. See
> `nfl/research/rolestate/VERDICT.md`.
>
> **What still stands:** the split between early-season and week-5-plus regimes, the observation that
> the prior buys level, and the monotone ordering across `DEPTH_CLAIM_BLEND` arms showing that
> player-specific information beats the depth curve. Those were not about the band. The
> re-measurement has not been run in the arm and week-split structure used below, so those rows are
> unconfirmed rather than withdrawn.
>
> **What this does NOT mean:** the projection system is not validated. One cell of the scoreboard
> moved. `PROJECTION_SYSTEM_STATE` remains `NOT_VALIDATED`.


Run after the role-state, prior-weight, share-denominator and allocation changes. Point-in-time:
for evaluation week W of season S the hierarchical prior sees seasons ≤ S−1 only, current-season
evidence is restricted to weeks strictly before W, and club volume likewise. Nothing from week W or
later enters any input.

Arms are `DEPTH_CLAIM_BLEND`: 0.0 means the measured depth curve decides a player's allocated
volume, 1.0 means his own multi-season claim does. The baseline, `CURRENT_SEASON_ONLY`, uses no
multi-season prior at all — it is the thing V1 replaced, and the thing V1 has to beat to be worth
having.

## The headline is a split verdict, not a pass or a fail

**Weeks 5+ (28 weeks, 2024–2025).** The prior does not earn its place.

| arm | MAE | RMSE | r | rho | level |
|---|---|---|---|---|---|
| 0.0 | 6.5201 | 9.2908 | 0.4630 | 0.4691 | 0.634 |
| 1.0 | 5.8991 | 8.3116 | 0.5123 | 0.4999 | 0.759 |
| **CURRENT_SEASON_ONLY** | **5.8920** | 8.3217 | **0.5201** | **0.5180** | 0.755 |

**Weeks 2–4 (6 weeks).** The prior earns its place on magnitude and still loses on ranking.

| arm | MAE | RMSE | r | rho | level |
|---|---|---|---|---|---|
| 0.0 | 6.2758 | 8.8663 | 0.4725 | 0.5171 | 0.740 |
| **1.0** | **5.6779** | **7.8923** | 0.5150 | 0.5442 | **0.880** |
| CURRENT_SEASON_ONLY | 5.8697 | 8.2635 | 0.5076 | **0.5602** | 0.846 |

## Read as one sentence

**The multi-season prior buys level and costs ordering.** Early in a season, when current-season
evidence is thin, it improves MAE by 3.3% and pulls the level ratio from 0.846 to 0.880. In both
regimes it reduces rank correlation, and the paired week-blocked differences are beyond two standard
errors every time — arm 1.0 against baseline is −0.0160 ± 0.0060 on overall rank and −0.0285 ± 0.0084
on the DFS slice early, −0.0181 ± 0.0021 and −0.0413 ± 0.0018 from week 5.

For DFS, ordering is what pays. So on this evidence the prior as currently built is not yet earning
its keep for the thing the product is for, and the one place it clearly helps — early-season level —
is the place with the fewest weeks of evidence behind it.

The monotonic ordering across arms is itself informative and points the same way: the more the
**depth curve** decides (arm 0.0), the worse everything gets; the more the **player's own** history
decides (arm 1.0), the better. Player-specific information wins; it is the shrinkage toward a
positional shape that hurts.

## The hypothesis this suggests, not a conclusion

Shrinkage that improves average magnitude by pulling everyone toward a common shape will compress the
between-player spread, which is exactly what a rank correlation measures. If that is the mechanism,
the repair is not less prior but a prior that preserves between-player variance — and that is a
measurement to make, not an adjustment to apply.

## Four limits that bound every number above

1. **Conditional on playing.** A panel row exists only where a player appeared with opportunity, and
   an absent row is UNKNOWN, never zero. These figures measure allocation and efficiency skill
   *given availability*. They do not measure availability forecasting, they flatter every arm
   equally, and they are upper bounds on live performance. Do not quote them as live performance.
2. **Role state is not exercised.** Predicted lineups and injury reports for past Sundays are not in
   this repository, so the evidence ceiling and the appearance adjustment — including the
   club-wide-depth-rank fix — are **not** tested here. This chain tests allocation given a band.
3. **No market input.** No historical closing lines are held, so the club touchdown pool comes from
   each club's own measured rate rather than an implied total. A declared difference from
   production.
4. **Week 1 is absent** and weeks 2–4 give only six evaluated weeks across two seasons. The
   early-season result is the interesting one and it is the one with the least evidence.

## What this does not license

It does not license removing the prior, and it does not license tuning the blend against these
numbers — the blend constant was already selected on this harness once, so re-selecting it here
would be fitting to the same data twice. It licenses one thing: stating plainly that the proprietary
projection engine has **not** yet demonstrated out-of-sample ranking skill above a current-season
baseline, and that the next measurement is where the between-player variance goes.

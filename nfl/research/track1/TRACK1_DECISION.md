# TRACK 1 — decision

# REJECT

**Research only. Nothing is promoted, R8 is untouched, no market quantity was
an input at any layer, and no threshold was changed.**

Forward-chained over 2022–2025, refit weekly on everything strictly earlier,
training from 2020. 10,727 scored team-games, 72 weekly refits, 1,000 draws,
one change between the arms.

---

## The result

Paired CRPS against the baseline. Negative is better. Intervals are block
bootstraps over whole games; the by-week intervals agree with them throughout
and are in the results artifact.

| metric | ΔCRPS | 95% CI (game-clustered) | r: baseline → Track 1 | seasons improved |
|---|---|---|---|---|
| `team_carries` | **−0.611 %** | [−0.0493, −0.0027] | 0.181 → **0.210** | **3 of 4** |
| `team_dropbacks_part` | +0.821 % | [+0.0083, +0.0681] | 0.189 → 0.192 | 0 of 4 |
| `team_off_snaps` | +0.526 % | [+0.0116, +0.0404] | 0.041 → 0.006 | 0 of 4 |
| `team_targets` | +1.518 % | [+0.0401, +0.0890] | 0.267 → 0.255 | 0 of 4 |
| `team_rz_carries` | 0.000 % | — | unchanged | untreated by declaration |

Downstream, through the fixed propagation harness (QB room, 2,174 team-games):

| | ΔCRPS | 95% CI (game-clustered) |
|---|---|---|
| room dropbacks | +0.573 % | [−0.0025, +0.0549] — not distinguishable from zero |
| room attempts | +0.921 % | [+0.0143, +0.0672] |
| room passing yards | +2.420 % | [+0.8123, +1.1419] |

Three of four treated metrics are **significantly worse**. The predeclared
rule makes that REJECT, and it is REJECT.

---

## Why, and it is not the obvious reason

The response curve itself is not in doubt. On realised state it is large,
monotone and estimated with almost no shrinkage where the data are thick:
fourth-quarter dropback rate is **1.305×** the quarter mean when a team enters
trailing by two scores and **0.584×** when it enters leading by two — a factor
of 2.2. Designed-rush rate runs the opposite way, 0.537 to 1.640.

**A simulated pregame state conflates two channels that do not agree.**

*Within* a game, trailing raises play count and pass rate. That is the curve.

*Across* games, a pregame favourite is simply a **better team**, and better
teams sustain more drives whatever the script. The Track 1 multiplier carries
only the first channel.

Measured directly — correlation of a team's **own** pregame expected margin
with what it actually did, beside which way the multiplier points:

| metric | corr(own expected margin, realised) | corr(own expected margin, multiplier) | channels |
|---|---|---|---|
| `team_carries` | **+0.153** | +0.999 | **agree** |
| `team_off_snaps` | +0.086 | −0.998 | **oppose** |
| `team_dropbacks_part` | −0.048 | −0.999 | agree, but the true effect is tiny |
| `team_targets` | −0.006 | −0.999 | nothing to predict |

And the same thing read as a scaling coefficient — regressing the realisation
on the baseline point and on the multiplier's own contribution, where 1.0 is
correctly scaled:

| metric | coefficient | 95% CI |
|---|---|---|
| `team_carries` | **1.24** | [0.84, 1.63] — consistent with 1 |
| `team_dropbacks_part` | 0.33 | [0.03, 0.62] — applied ≈ 3× too hard |
| `team_targets` | −0.09 | [−0.41, +0.23] — indistinguishable from zero |
| `team_off_snaps` | **−1.47** | [−2.24, −0.70] — **significantly wrong-signed** |

Favourites really do run more snaps (+0.086), while the state channel says
trailing teams run more plays. For snap count the between-team quality channel
is the larger of the two, so a response curve that is correct in-game points
the wrong way out of sample.

### A hypothesis I had, and am withdrawing

Before measuring, I expected the failure to be **double counting**: that a
coach's or team's own trailing average already encodes how often that team
trails, so multiplying it by a state response applies the same fact twice.
`corr(baseline point, multiplier)` is 0.14, 0.02, −0.10 and 0.07 across the
four metrics. The baseline does not carry the script. That explanation is
wrong and is withdrawn rather than kept alongside the one the data support.

### Mean versus width

`TRACK1_MEAN` separates them. For `team_dropbacks_part` the conditional-mean
shift alone is +0.315 % with a CI of [−0.015, +0.045] — **not distinguishable
from zero** — while the per-draw arm is +0.821 % and significant. There, the
damage is the added predictive width, and coverage shows it honestly: 50 %
intervals cover 56.4 % and 95 % intervals cover 96.8 %, against a baseline
51.2 % / 94.7 %. For `team_off_snaps` both arms are equally bad (+0.526 % and
+0.534 %), so there it is the mean that is wrong, not the width.

---

## The boundary, reported rather than averaged away

**The rushing-volume channel works.** `team_carries` improves by 0.611 % of
CRPS with a game-clustered interval excluding zero, improves in three of four
seasons (2023 −0.93 %, 2024 −1.65 %, 2025 −0.31 %; 2022 +0.41 %), raises
discrimination from r = 0.181 to 0.210, and its mechanism is correctly scaled.
It is the one metric where the within-game script channel and the between-team
quality channel push the same way.

That is a real, forward-chained, significant improvement on one metric. It is
not broad, so it is not support — but it is not nothing, and averaging it into
a pooled number would destroy the only informative part of this result.

---

## What would have to be true for a future attempt

Not a tweak to this one. The finding is that **simulated score differential is
the wrong single conditioning variable**, because it carries team quality and
game script in the same number with different signs for different metrics.

1. **Model drive sustain rate and game script as separate channels.** The
   quality channel (better teams get more possessions and more plays) is
   pregame-observable and currently unmodelled. The script channel is what
   this work estimated. They need separate coefficients, not one multiplier.
2. **Estimate the strength of the state response out of sample rather than
   applying the in-game curve at full force.** The coefficients above show the
   right strength varies from 1.24 to −1.47 by metric. That is a per-metric
   quantity to estimate, not a constant to assume.
3. **Fix the estimand before re-testing `team_off_snaps`.** The response was
   estimated on play-by-play play ROWS and applied to a snap-count forecast.
   The multiplier is a ratio, which survives most of that gap, but a
   wrong-signed result is the wrong place to be relying on "most".

---

## Two things worth keeping regardless of the decision

**The offsetting-error rate.** In the baseline, **55.7 %** of team-games have
volume error and efficiency error of **opposite sign**, so the final passing
yardage is closer than either component. A majority of good final numbers are
produced by cancellation. That is now measured on every propagation row rather
than assumed, and it is the reason a yardage CRPS on its own cannot be read as
mechanistic success.

**The response curves themselves.** They are estimated, shrunk by an
empirical-Bayes weight that does visible work (0.04 where there is no signal,
0.998 where there is), committed, and reusable. Nothing about this rejection
makes the in-game mechanism false. What is false is that a pregame-simulated
differential is a sufficient way to reach it.

---

## Firewall

NE@SEA and SF@LA are 2026 games. The evaluation frame is the 2020–2025 regular
season and contains neither, at any point — not in the response curves, not in
the state generator, not in bucket selection, not in the decision rule. The
test module asserts their absence. They motivated two questions; both were
re-derived here from the historical panel.

The bucket edges (±3.5 and ±10.5) were fixed on football grounds — one field
goal, two scores — before any response was estimated, and were not moved after
the results were seen.

## Artifacts

| file | what it is |
|---|---|
| `TRACK1_SPEC.md` | the frozen specification |
| `TRACK1_FORWARD_CHAIN_RESULTS.json` | every metric, every season, every interval |
| `TRACK1_DIAGNOSTICS.csv` | 6,522 propagation rows, volume and efficiency error kept apart |
| `TRACK1_SCORED_ROWS.csv.gz` | all 10,727 scored rows, so the summary is re-derivable |
| `RAW_PROVENANCE.json` | the six source files, url and sha256 each |

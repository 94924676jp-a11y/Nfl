# TRACK 1 — game-state-conditioned offense: specification

**Status: research only. Nothing here is promoted, nothing replaces R8, and no
sportsbook price, line, or market probability is an input at any layer.**

The question is narrow and answerable: does simulated game state materially
improve team offensive volume and the quarterback distributions downstream of
it, without letting realised information into a pregame forecast.

---

## 1. The causal chain, and where each arrow is estimated

```
pregame team strength / environment        estimated: nfl/research/track1/state.py
  -> simulated score differential by phase estimated: state.py  (drift + resampled path)
  -> pace / pass tendency / possession     estimated: response.py (conditional curves)
  -> team plays / dropbacks / rush attempts applied:  forward_chain.py (multiplier)
  -> existing player allocation layers      propagated: forward_chain.py (fixed harness)
```

Every arrow is fitted on data strictly earlier than the week being forecast.

### What may enter the predictor

Results of games already played, who is at home, and the schedule.

### What may not, and how that is enforced rather than promised

Realised score of the game being forecast, closing spread, sportsbook total,
market win probability, and every postgame quantity.

* `build_state_panel.READ` is the complete list of columns read from the
  source play-by-play. It is checked at import against a forbidden-substring
  list, and the two emitted panels are checked again before they are written.
  The source file *does* carry `spread_line`, `total_line` and `vegas_wp`;
  they are never read, and the check is on what this code consumes and emits,
  never on what the upstream happens to ship. A first version checked the
  source header instead and refused the whole build — and `_line` also matched
  `yardline_100`, which is field position, not a price.
* `state.PREGAME_FEATURES` is the generator's entire feature set, three names
  long, and `assert_pregame_only` runs on it at import.

---

## 2. The conditional response curves — characterised, not black-boxed

Estimated on 13,093 team-quarters, 2020–2025 regular season, from
`state_team_quarter.csv.gz`.

### The conditioning variable is the differential ENTERING the quarter

Not the differential during it. A within-quarter differential is partly caused
by the very plays being counted; conditioning a play count on a quantity those
plays moved reports the consequence as the cause and looks like a strong
mechanism. The differential at the quarter boundary is fixed before any of
those plays happen.

### The buckets, predeclared on football grounds

`<=-11 | -10..-4 | -3..+3 | +4..+10 | >=+11`, boundaries at ±3.5 and ±10.5.
A three-point game is one field goal; eleven points is two scores. They were
fixed by that reasoning before any response was estimated, and no grid search
chose them. Quarter 1 is neutral by construction — every game starts 0–0 — so
the curve has 16 cells, not dozens of brittle score states.

### Shrinkage is estimated, never chosen

Empirical Bayes per quarter: the between-cell signal variance τ² is what is
left of the observed spread after the sampling variance is removed, and each
cell is trusted in proportion to τ²/(τ² + its own sampling variance). For
rates the sampling variance is the cluster-linearised variance of a ratio
estimator with the team-quarter as the cluster, because plays inside one
team's quarter are not independent draws.

The shrinkage does visible work rather than being decorative. Second-quarter
play counts carry almost no signal and shrink to roughly 1.00 (weights 0.04 to
0.25). Fourth-quarter dropback rate carries a great deal and barely moves
(weights ≈ 0.998).

### What the mechanism says (full-sample fit, for orientation)

Dropback rate relative to the quarter's own mean:

| entering differential | Q2 | Q3 | Q4 |
|---|---|---|---|
| `<=-11` | 1.026 | 1.094 | **1.305** |
| `-10..-4` | 1.005 | 1.024 | 1.223 |
| `-3..+3` | 1.001 | 0.993 | 1.008 |
| `+4..+10` | 0.991 | 0.962 | 0.770 |
| `>=+11` | 0.981 | 0.927 | **0.584** |

Designed-rush rate runs the other way (Q4: 0.537 when trailing by two scores,
1.640 when leading by two). Play counts respond much more weakly (Q4: 1.079
trailing, 0.874 leading). The tendency response is large; the possession
response is small.

---

## 3. The two arms, and the single difference between them

| | BASELINE | TRACK1 |
|---|---|---|
| point estimator | frozen P4B selection for that season | **same** |
| training window | every team-game strictly earlier than the forecast week | **same** |
| residual form | empirical resampling | **same** |
| residual indices | drawn once | **shared** (common random numbers) |
| draws | 1,000 | **same** |
| state multiplier | none | simulated, per draw |

`TRACK1_MEAN` is a third, diagnostic arm using the *expected* multiplier
instead of a per-draw one. It separates "the conditional mean moved in the
right direction" from "the predictive width changed". Those are different
properties and one CRPS number hides which moved.

### The treatment cannot win by shifting the level

The multiplier is divided by its own training-frame mean, so Track 1 carries
exactly the baseline's average level and differs only in how it distributes it
across games.

### The treatment is not protected from its own width

Per-draw state adds variance. If the state does not explain variance, Track 1
is simply wider for no reason and CRPS punishes it. Nothing rescales that away.

### The residual form is held fixed at empirical in BOTH arms

The frozen P4B form selection varies by metric and season
(`gaussian`/`student_t`/`team_empirical`/`coach_empirical`). Letting it vary
would put a second treatment in the comparison. This makes BASELINE not
bit-identical to production; it makes it the correct control.

---

## 4. What is treated, and what is declared untreated

| baseline metric | driver | treated |
|---|---|---|
| `team_off_snaps` | plays | yes |
| `team_dropbacks_part` | dropbacks | yes |
| `team_targets` | pass attempts | yes |
| `team_carries` | designed rushes | yes |
| `team_rz_carries` | — | **no, multiplier is exactly 1.0** |

Red-zone boundary conventions were never reconciled against this panel, so no
response curve exists for it. A metric passed through unchanged is a declared
boundary, not a silent omission.

### The response is a multiplier and never a level

`plays` in this panel counts offensive play **rows**. The baseline forecasts
`team_off_snaps`, a snap-count quantity that includes penalty-nullified plays
appearing here as separate rows. They are different quantities — the same
estimand trap that scored a 57-play game against a 65.65 snap forecast in the
manual review. A ratio to the same quantity's own neutral-state mean survives
that difference; a level does not.

---

## 5. The pregame state generator

* **Team strength**: exponentially weighted mean of a team's own prior scoring
  margins, carried across the season boundary (last December is stale
  information, but it is not future information).
* **Half-life**: selected inside the training window by leave-one-season-out
  error on margin, from the grid (2, 4, 8, 16). Selected once per evaluation
  season on strictly prior seasons; everything else refits weekly.
* **Expected margin**: ordinary least squares of realised margin on the
  strength difference. The intercept *is* the home-field advantage and the
  slope *is* the shrinkage toward zero, so neither is a second free constant.
* **Within-game path**: each quarter's scoring increment is a fitted drift
  share of the expected margin plus a residual, and the residuals are
  **resampled as four-vectors from whole training games**. That preserves how
  real scoring paths behave — quarters that blow open together, quarters that
  stay tight together — with no distributional assumption. It is the same
  discipline as the shared historical index the team-volume layer already
  uses, for the same reason: drawing dependent quantities apart manufactures
  paths no real game has taken.
* **Both sides of a game share one path**, sign-flipped. A simulated game in
  which both teams trail by two scores is not a game.

Fitted on 2020–2023, the generator gives expected home margin = 1.76 +
0.617 × strength difference, half-life 8, and reproduces the observed
magnitude of the fourth-quarter differential (simulated E|margin entering Q4|
9.78 to 10.93 across the expected-margin range, against 10.34 observed).

---

## 6. Evaluation

Forward-chained / prequential. Response curves, state coefficients, league
means and residual pools are refit **every week** on everything strictly
earlier. Evaluation seasons 2022–2025; training starts at 2020.

**Primary**: CRPS on team volume; CRPS on QB-room dropbacks, attempts and
passing yards. **Secondary**: PIT, interval coverage at 50/80/90/95,
discrimination (Pearson r of the point against the realisation), and the
spread of the conditional mean. MAE is not optimised and is not a criterion.

### Clustering

A slate is not 32 independent observations: the two teams of a game share one
simulated path by construction and every game in a week shares that week's
fitted curves. Every paired CRPS difference is block-bootstrapped over whole
**games** and, separately, whole **weeks**. Where they disagree the wider one
counts.

---

## 7. The downstream harness, and what it does not claim

QB numbers come from a **propagation harness**: a fixed, forward-chained
room-share, dropback-to-attempt conversion and yards-per-attempt model that is
byte-identical across arms including its random indices. A difference in QB
CRPS is therefore caused by the team budget and by nothing else.

It measures **propagation of a volume change**. It is not the production
quarterback layer and is never reported as that layer's quality.

The unit is the **QB room**, not the individual. NE@SEA is why: Seattle's room
aggregate was nearly exact while the split inside it was maximally wrong,
because the starter was replaced in game. No pregame information set can
observe that, and charging it to a volume experiment would measure the wrong
thing.

### Volume versus efficiency, kept apart

Every propagation row carries the dropback error, the attempt error, the
yards-per-attempt error and the final yardage error separately, plus an
`offsetting` flag when volume and efficiency errors have opposite signs. A
good final yardage number produced by two offsetting wrong components is not
mechanistic success and is not counted as one.

---

## 8. Live-evidence firewall

NE@SEA and SF@LA are **2026** games. The evaluation frame is the 2020–2025
regular season and does not contain them at any point — not in the response
curves, not in the state generator, not in bucket selection, not in the
decision rule. They appear in this work only as motivation, and the two facts
they motivated (that the dropback/attempt split moves with game state, and
that a QB room must be scored as a room) were both re-derived here from the
historical panel rather than carried over.

This specification is frozen as of the commit that introduces it, before any
subsequent prospective game outcome is opened.

---

## 9. Simulation coherence

Track 1 alters **team environment generation only**. It does not touch
rushing ownership (A1), QB allocation (R2), the shared passing chain (C3), or
the game-level dependence mechanism (A3G); downstream layers receive changed
team budgets through the existing interfaces. Within-game coherence is
strengthened rather than weakened: the two sides of a game already share a
historical team-game index under A3G, and now also share one simulated score
path.

---

## 10. The decision rule, stated before the numbers were read

* **SUPPORT** — every treated metric improves overall, a majority of treated
  metric-seasons improve, and at least one improvement survives the
  game-clustered bootstrap.
* **WEAK_SUPPORT** — some treated metric improves and none is significantly
  worse under the game-clustered bootstrap.
* **REJECT** — otherwise.

If improvement is confined to a subset, the subset is the finding and is
reported as a boundary rather than averaged away.

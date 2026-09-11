# Q6 — appearance probability and conditional role allocation: specification

**Frozen before evaluation. Research only: nothing is promoted, R8 is
untouched, no market quantity is an input, no 2026 game is fitted, and
`weekly_rosters.status` is never read.**

The question: can pregame information improve player appearance probability and
conditional role allocation without leaking post-kickoff or post-hoc roster
status — and what should production do when the injury report is incomplete?

---

## 0. What the audit found first, because it changes the hypotheses

Three things were checked before anything was built, and two of them removed a
hypothesis rather than supporting one.

**The engine does not collapse appearance into an unconditional share.**
`layers.appearance` draws a **Bernoulli per player per simulation draw**
(`rng.binomial(1, p, size=m)`), and `layers.participation` multiplies that 0/1
draw by the share. The product is zero-inflated per draw, not a diluted point.
The directive's first requirement is already satisfied structurally, and this
work tests the two pieces separately rather than repairing a collapse that is
not there.

**The share is already conditional on appearing.**
`participation_prior.share_prior` is an EWMA of *prior appeared* pass-snap
shares, and `role_prior` builds tier means from rows where `appeared` is true.
So the multiplication is `P(appear) x E[share | appeared]`, which is the right
composition and not a double count.

**The injury designation is already a feature, and already timestamped.**
`appearance_r7.featurise` carries one-hots for Out / Doubtful / Questionable, a
"did not practise" flag and an availability flag, and `stage_a.injuries` keeps
only rows whose own `date_modified` precedes kickoff. I expected to find the
game-status designation missing and it is not.

What remains open is therefore narrower and more specific than "use the injury
report": whether the designation is used at the right **resolution**, whether
the probabilities are **calibrated within role class**, and whether the
conditional role allocation handles **vacancy** correctly.

---

## 1. Frame and population

R8's enriched union frame — the played-panel unioned with the point-in-time
depth listing — 59,784 rows across 2020–2025. Restricted to **RB / WR / TE**
(8,819 QB rows dropped: QB allocation does not pass through this layer,
`qb_accounting.py:377`).

Every row is built from strictly-earlier information plus a depth chart dated
before kickoff. The `no_history_and_not_depth_listed` cell stays refused by
name, exactly as R7 refuses it: its appearance rate is 1.0000 with zero
variance, which is a construction rather than an estimate.

### Allowed inputs, and nothing else

Prior-game participation; recent snap / target / carry shares; pregame injury
designation where `date_modified` precedes kickoff; point-in-time depth
listing; depth and role continuity from prior games.

### Refused by name

`weekly_rosters.status` in any form, game-day active/inactive inference without
authoritative pre-kickoff evidence, any 2026 row, any market quantity, and any
column whose value is only knowable after kickoff. `assert_pregame_only`
refuses a feature-name list carrying any of them, and the 2026 exclusion is
asserted on the frame itself.

---

## 2. Role classes, defined point-in-time

Within (team, week, position), rank players by their **trailing** snap-share
EWMA computed from strictly earlier weeks; where a player has no trailing
history use the point-in-time depth rank; where neither exists, the lowest
class.

| class | definition |
|---|---|
| `starter` | rank 1 |
| `rotational` | rank 2–3 |
| `fringe` | rank 4+ or unranked |

Nothing in the class definition can see the game being forecast.

---

## 3. Appearance arms

| arm | what it is |
|---|---|
| `ROLE_CLASS_FLAT` | the flat fallback: appearance rate by (position, role class) from strictly-earlier rows. No player-level information at all. |
| `R8` | the production candidate, unchanged — `appearance_r8.featurise` and the frozen `stage_a.fit_logistic`, fit on strictly-earlier seasons. |
| `Q6_FEATURES` | R8 plus two additions, both pregame-legal: the injury designation **interacted with depth rank** (a questionable starter and a questionable fifth receiver are not the same event, and R8 carries both as separate main effects with no interaction), and the practice-status **ordinal** (full / limited / did-not-participate / absent) rather than only the improving and worsening flags. |
| `Q6_CALIBRATED` | `Q6_FEATURES` plus a **role-class-conditional recalibration** fitted on strictly-earlier rows, so a systematic over- or under-statement inside one class can be corrected without touching the others. |

The last two are reported separately so a change in the numbers can be
attributed to the features or to the calibration, not to "the candidate".

Everything else is held fixed and shared across arms: the frame, the refused
cell, the training window, the estimator, the L2 constant, and the seed.

---

## 4. Conditional role arms

Estimand: the player's share of his team's **targets** (WR, TE) or **carries**
(RB), **conditional on appearing**.

| arm | what it is |
|---|---|
| `TIER_PRIOR` | the R6 mechanism: the player's own trailing share shrunk toward his point-in-time tier mean with weight n/(n+k), k estimated as the ratio of within-player to between-player variance. |
| `Q6_VACANCY` | the same, plus an explicit **vacancy redistribution**: when a higher-class teammate at the same position is absent, the share the model frees is redistributed by a historically measured pattern rather than by proportional renormalisation alone. |

Proportional renormalisation spreads an absent starter's share across everyone
in proportion to their own share. Whether the direct backup actually absorbs
more than that is a measurable question and is the whole of the `Q6_VACANCY`
hypothesis.

Distributions come from resampling historical residuals of the same
construction on strictly-earlier rows — the same discipline the team-volume
layer uses — so CRPS is computed from draws and not from an assumed form.

---

## 5. Composition, and what is held fixed

Player opportunity draw = `Bernoulli(p_appear) x share draw x team total`.

**The team total is an oracle held identical across every arm.** Using the
realised team target or carry count in all arms isolates the appearance and
role layers, which is the comparison asked for; it is not a claim that the team
total is known pregame, and no arm gains from it because every arm gets the
same number. Team volume, efficiency and touchdown layers are untouched.

### Reported

* **Appearance**: Brier, log loss, calibration in ten probability bins with
  counts, expected calibration error — split by position and by role class.
* **Role | appears**: CRPS of the conditional share.
* **Unconditional**: CRPS of the player's targets or carries.
* **Zero-inflation error**: predicted P(zero) minus realised zero rate.
* **Starter dilution**: mean predicted starter share divided by mean realised
  starter share, conditional and unconditional.
* **Replacement misallocation**: on team-games where the `starter` at a
  position did not appear, the error in the next class's realised share.
* **Team reconciliation error**: the sum of player draws against the team
  total, per draw.

### Clustering

Players on one team-game share an injury report, a depth chart and a game. A
team-game is the cluster; every paired difference is block-bootstrapped over
whole team-games.

---

## 6. Missing-data behaviour

The live failure this answers is real: the week-1 2026 boards carried
`INJURY_REPORT_INCOMPLETE` for teams whose rows had an empty `report_status`.

The injury block is blanked for a held-out set of team-weeks — designation,
practice status and the availability flag all removed, exactly as an
unfiled report presents — and three policies are compared on those rows:

| policy | what it does | confidence it must declare |
|---|---|---|
| `HARD_DEFER` | refuse to forecast the affected players | n/a — it emits nothing |
| `HISTORICAL_ROLE_FALLBACK` | the role-class flat rate | `LOW_CONFIDENCE_ROLE_CLASS_ONLY` |
| `PROBABILISTIC_FALLBACK` | the model with the injury block missing and its own missingness flags firing | `REDUCED_CONFIDENCE_NO_INJURY_REPORT` |

A fallback that does not declare reduced confidence is a failure of the policy
whatever its Brier score, and the comparison reports the **coverage cost** of
`HARD_DEFER` — how many players and team-weeks it silently removes — beside the
accuracy of the two that answer.

---

## 7. Evaluation protocol

Forward-chained by season: for evaluation season Y in 2022–2025, every arm is
fitted on rows from seasons strictly before Y. That is R7's and R8's own
discipline, and it is the discipline the production `fit(season)` uses, so the
comparison is on the same footing as production.

---

## 8. Decision rule, stated before the numbers are read

* **SUPPORT** — the candidate improves appearance Brier **and** log loss
  overall, improves in a majority of position-by-role-class cells, at least one
  improvement survives the team-game-clustered bootstrap, and no cell is
  significantly worse; and the conditional-role or composition metrics do not
  degrade.
* **WEAK_SUPPORT** — some primary metric improves and none is significantly
  worse.
* **REJECT** — otherwise.

If improvement is confined to a subset, the subset is the finding and is
reported as a boundary rather than averaged away.

**No promotion from this task.** R8 stays exactly as it is whatever the result.

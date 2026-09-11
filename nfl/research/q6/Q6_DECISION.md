# Q6 — appearance probability and conditional role allocation: decision

# WEAK_SUPPORT

**Research only. Nothing promoted, R8 untouched, no market input, no 2026 row
fitted, `weekly_rosters.status` never read.**

Forward-chained 2022–2025, every arm fitted on seasons strictly earlier.
34,621 scored player-games across 2,174 team-games, 89 declined by name into
the unsupported cell. Intervals are block bootstraps over whole team-games
(15.9 rows per cluster).

---

## Headline

| arm | Brier | log loss | ECE | verdict under the rule |
|---|---|---|---|---|
| `ROLE_CLASS_FLAT` | 0.193892 | 0.570236 | 0.020324 | the fallback baseline |
| `R8` (production) | 0.090724 | 0.293054 | 0.020746 | — |
| `Q6_FEATURES` | **0.090150** | **0.291345** | 0.018181 | **SUPPORT** (8 of 9 cells) |
| `Q6_CALIBRATED` | 0.090465 | 0.293967 | **0.015804** | **WEAK_SUPPORT** (6 of 9) |

The headline arm was fixed as `Q6_CALIBRATED` before the run, so the decision
is **WEAK_SUPPORT**. `Q6_FEATURES` reaches SUPPORT under the same rule, and
adopting it as the headline after seeing that would be selection on the
outcome. Both verdicts are published in `decision_by_arm`.

---

## What worked: the injury designation needs a depth rank beside it

R8 already carries the game-status designation and already restricts it to
rows timestamped before kickoff — I expected to find that missing and it is
not. What it carries them as is **separate main effects**: Questionable lowers
appearance, rank 1 raises it, and the model cannot say that a questionable
starter and a questionable fifth receiver are different events.

Adding that interaction, plus the practice-status **ordinal** (R8 carries only
the improving and worsening flags, not the level), gives a Brier improvement
of **−0.632 %**, 95 % CI **[−0.000771, −0.000391]**, excluding zero on the
team-game bootstrap. It improves **8 of 9** position-by-role-class cells, five
of them significantly, and no cell is significantly worse.

| cell | R8 | Q6_FEATURES | Δ | significant |
|---|---|---|---|---|
| RB fringe | 0.119307 | 0.118525 | −0.000782 | **yes** |
| RB rotational | 0.090189 | 0.089329 | −0.000860 | **yes** |
| RB starter | 0.043147 | 0.042580 | −0.000567 | no |
| TE fringe | 0.123185 | 0.122875 | −0.000311 | no |
| TE rotational | 0.082891 | 0.081979 | −0.000912 | **yes** |
| TE starter | 0.043437 | 0.042903 | −0.000534 | **yes** |
| WR fringe | 0.121425 | 0.120756 | −0.000669 | **yes** |
| WR rotational | 0.068717 | 0.068745 | +0.000028 | no |
| WR starter | 0.040276 | 0.040183 | −0.000093 | no |

## What did not: the recalibration bought calibration with log loss

Role-class Platt scaling, fitted on a nested forward chain, gives the best
expected calibration error of any arm (0.0158 against R8's 0.0207) and a
**worse** log loss overall (0.293967 against 0.293054). The damage is one
season: 2022, where the nested chain had only 2020 to fit on and 2021 to
calibrate on, log loss goes 0.30056 → 0.31454. From 2023 the recalibration is
the best arm on every metric. The boundary is the training depth, not the
mechanism, and it is reported rather than averaged away.

## What failed outright: the vacancy correction

`Q6_VACANCY` — redistributing an absent starter's share by a measured pattern
rather than by proportional renormalisation alone — is **worse**: role CRPS
+0.135 % on targets (CI spans zero) and **+0.251 % on carries with the
interval excluding zero**. It is the one metric in this work that is
significantly worse than its baseline.

**The misallocation it aimed at is real and large.** On team-weeks where the
starter did not appear, the baseline composition predicts:

| class | predicted targets | actual | ratio |
|---|---|---|---|
| surviving starter | 3.879 | 3.271 | **1.186** |
| rotational | 2.189 | 2.346 | 0.933 |
| fringe | 0.852 | 0.966 | 0.882 |

Proportional renormalisation **over-feeds the surviving starter by 19 %** and
under-feeds the replacements by 7–12 %. The correction I fitted moves 2–6 %,
three to six times too little, because it was estimated on a different
quantity: the ratio of realised share to base-proportional share **among
players who did appear**, whereas the composition averages over draws in which
the starter sometimes appears. Estimating a correction on one definition and
applying it under another is the defect, not the absence of an effect.

Two estimator faults were found and fixed on the way there, and both had
produced confident nonsense first:

* **Denominator.** The first version divided a player's targets by the whole
  team total while normalising predictions inside his own position, so
  predicted shares summed to 1 across three positions whose realised shares
  summed to about 0.55. Every measured vacancy ratio came out near 0.6 for
  that reason alone. The pool is now every RB, WR and TE on the team, and the
  shares sum to exactly one over the same population.
* **Mean of ratios.** Averaging actual/predicted per player let near-zero
  denominators dominate; the carry pool, full of receivers predicted almost no
  carries, produced class ratios of 4 to 8. Summing numerator and denominator
  first weights each observation by the mass it carries. The carry ratios then
  came back as 1.000 and 1.019 — no effect at all, which is the truthful
  answer.

---

## The composition

The team total reconciles **exactly** — maximum error 0.0 over every draw and
both metrics — because opportunity is a multinomial draw over the renormalised
simplex.

| metric | arm | CRPS | Δ vs baseline | significant |
|---|---|---|---|---|
| targets | BASELINE | 0.776946 | — | — |
| targets | Q6 appearance only | 0.774957 | **−0.256 %** | **yes** |
| targets | Q6 role only | 0.776824 | −0.016 % | no |
| targets | Q6 both | 0.775315 | **−0.210 %** | **yes** |
| carries | BASELINE | 0.474680 | — | — |
| carries | Q6 appearance only | 0.472054 | **−0.553 %** | **yes** |
| carries | Q6 role only | 0.475133 | +0.095 % | no |
| carries | Q6 both | 0.472129 | **−0.537 %** | **yes** |

The downstream gain comes **entirely from the appearance layer**. Adding the
role change on top of it gives back a little.

**Zero inflation.** Predicted zero rate is *below* observed by 2.68 points on
targets (0.477 against 0.504) and 1.24 on carries (0.795 against 0.807), and
the better appearance model narrows both slightly. An earlier version of this
harness reported a 16-point gap; that was its own construction — it emitted a
continuous share × total, which is strictly positive for anyone who appeared,
so the only route to a zero was non-appearance. The multinomial draw produces
zeros for small shares the way the production allocator does, and the real gap
is small.

**Starter dilution** is mild in the baseline: starters 1.017, rotational
0.993, fringe 0.982 against realised means. The layer is not systematically
diluting starters.

---

## Missing data: what production should do when the report is not filed

Blanking the injury block on the **4,364 player-games that actually had a
filed report** — the injured subpopulation, where blanking changes anything:

| policy | Brier | log loss | ECE | coverage | declares |
|---|---|---|---|---|---|
| informed | 0.086877 | 0.273049 | 0.0326 | 1.00 | FULL |
| `PROBABILISTIC_FALLBACK` | 0.222179 | 0.705658 | **0.1700** | 1.00 | `REDUCED_CONFIDENCE_NO_INJURY_REPORT` |
| `HISTORICAL_ROLE_FALLBACK` | 0.226535 | **0.654790** | **0.0810** | 1.00 | `LOW_CONFIDENCE_ROLE_CLASS_ONLY` |
| `HARD_DEFER` | — | — | — | **0.00** | emits nothing |

Three things follow, and they point the same way.

1. **The report is worth a great deal on the players who have one.** Brier
   more than doubles without it, and the interval on that cost excludes zero
   by a wide margin for both fallbacks.
2. **The model's own missingness handling is over-confident.** With the block
   blanked it carries an ECE of 0.170 — twice the flat role-class rate's 0.081
   — and a worse log loss. When the report is genuinely unfiled, the model's
   internal fallback is the *less* honest of the two answers, not the more
   informed one.
3. **`HARD_DEFER` refuses 4,364 players across 1,496 team-weeks.** That is a
   forecast of nothing, not a cautious forecast, and its cost is counted here
   rather than described.

**Recommendation, for a later decision and not taken here:** where the injury
report is unfiled, emit the role-class rate under
`LOW_CONFIDENCE_ROLE_CLASS_ONLY` rather than the model's own missing-block
prediction, and never emit either without the confidence label. A fallback
that does not declare reduced confidence is a failure of the policy whatever
its Brier score.

**One limit on that number.** The blanking was applied to players who had a
report, so it measures the cost on the injured subpopulation. A genuinely
unfiled team report also removes the block from the healthy majority, for whom
the loss is much smaller. The figures above are an upper bound on the affected
players and not an average over a team.

---

## What the audit removed before anything was built

Two hypotheses died on inspection and are recorded so they are not raised
again:

* **The engine does not collapse appearance into an unconditional share.**
  `layers.appearance` draws a Bernoulli per player per simulation draw and
  `layers.participation` multiplies that 0/1 draw by the share. The directive's
  first requirement is already satisfied structurally.
* **The share is already conditional on appearing.**
  `participation_prior.share_prior` is an EWMA of *prior appeared* shares and
  `role_prior` builds tier means from appeared rows, so the product is
  P(appear) × E[share | appeared] and not a double count.

---

## Boundary, and what a future attempt needs

**The appearance layer has real headroom and the interaction is where it is.**
Significant, broad across positions and role classes, and worth −0.26 % to
−0.55 % of downstream CRPS on its own.

**The conditional-role layer does not, on this mechanism.** The replacement
misallocation is real (19 % over-feeding of the surviving starter) but a
correction estimated on share-among-present does not transfer to counts under
simulated appearance. A future attempt has to estimate the redistribution on
the same quantity it will be applied to, and should probably be a *joint*
model of who appears and who absorbs rather than a multiplier bolted onto a
renormalisation.

**No promotion.** R8 stays exactly as it is.

## Artifacts

| file | what it is |
|---|---|
| `Q6_SPEC.md` | the specification, frozen before evaluation |
| `Q6_FORWARD_CHAIN_RESULTS.json` | every arm, cell, season, interval and policy |
| `Q6_APPEARANCE_ROWS.csv.gz` | 34,621 scored appearance rows |
| `Q6_ROLE_ROWS.csv.gz` | the conditional-role rows, both arms |
| `Q6_DIAGNOSTICS.csv.gz` | the composition rows, all four arms, both metrics |

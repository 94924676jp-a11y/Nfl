# A3G pre-registration — the game-level extension of the joint residual draw

Written 2026-09-09, **before any parameter was estimated and before any
candidate was scored**. Nothing in this document was chosen after seeing a
candidate's result. Departures found during execution are labelled as
departures in `A3G_FINDING.md` and are not edited back into this file.

Authorised by owner ruling **B10**: *"the two teams in a game are drawn
INDEPENDENTLY"*, with the required result stated as

> "materially reduce the impossible independence; preserve marginal quality;
> eliminate the observed extreme game-total-play behavior; no requirement to
> match historical correlations exactly. We need directionally and
> distributionally credible, not perfect historical correlation replication."

and the design constraint

> "Do not blindly promote the existing per-team implementation. Give both teams
> in the same game the appropriate shared game-level residual/index structure
> while preserving team-specific marginals."

---

## 1. The defect, as measured before this document was written

`team_volume_v1.forecast` draws every team row on its own.

* Independent mode (`joint_residuals=False`): one RNG stream per metric,
  `team_volume_v1.py` ~lines 236-240.
* J1/A3 mode (`joint_residuals=True`): one shared historical team-game index
  per **team row**, drawn with a separate `pick` inside the per-row loop,
  ~lines 279-290.

Neither mode contains anything that pairs the two rows of a game. A3 fixed the
*within-team* cross-metric coupling and left the *within-game* coupling absent.

Measured on `nfl/research/inputs/denom_panel.csv.gz`, 3,230 team-games,
1,615/1,615 games pairing, seasons 2020-2025. Historical figures re-verified for
this document; model figures carried from the audit that preceded it.

| within-game corr(home, away) | historical | model, A3 as it stands |
|---|---|---|
| `team_off_snaps` | **-0.4647** | ~-0.008 |
| `team_carries` | **-0.5347** | ~+0.015 |
| `team_dropbacks_part` | **-0.1921** | not previously reported |
| `team_targets` | **-0.1178** | not previously reported |
| `team_rz_carries` | **-0.1870** | not previously reported |

| total game plays (`team_off_snaps` home + away) | historical | model |
|---|---|---|
| SD | **9.265** | 12.32 (+33%) |
| observed range 2020-2025 | **[106, 173]** | 2.00% of drawn games fall outside it |

The last row is the sharpest statement of the defect: two percent of simulated
games are outside the entire six-season observed envelope of NFL game length.
That is a distributional impossibility produced purely by drawing two dependent
quantities independently.

## 2. Estimand

The **joint predictive distribution of the two teams' five-metric volume
vectors within one game**, on one draw index:

```
  ( team_off_snaps, team_dropbacks_part, team_targets,
    team_carries,   team_rz_carries )_home
  ( ... same five ... )_away
```

Per-team marginals and the within-team cross-metric structure are **not** part
of the estimand: they are frozen by P4B and J1/A3 respectively, and this
experiment must leave both where they are.

## 3. Mechanism — a rank copula on the shared draw index

A3 already selects, for each team row and each draw, **one** historical
team-game key from that team's coach pool, and takes all five residuals from
it. This experiment changes **only which key each side receives**, never the
pool, never the residual values and never any fit.

For a game between sides `A` and `B`, per draw:

1. Draw a bivariate standard normal `(z_A, z_B)` with correlation `rho`.
2. `u_A = Phi(z_A)`, `u_B = Phi(z_B)`.
3. Order each side's own coach pool ascending by a **coupling score** (§4).
4. Side `s` receives the pool key at ordinal position `floor(u_s * n_s)`,
   where `n_s` is that side's pool size.

**Why this preserves the marginal exactly, not approximately.** `u_s` is
Uniform(0,1) marginally by construction of the Gaussian copula, so
`floor(u_s * n_s)` is exactly uniform on `{0, ..., n_s - 1}`. That is the same
distribution as the incumbent `rng.integers(0, n_s, m)`. Each pool key is still
drawn with probability `1/n_s`; the pool is unchanged; the residual vector
attached to a key is unchanged. **No marginal moves, by construction rather than
by measurement**, and no clipping, truncation or renormalisation is used
anywhere. The measured marginal comparison in §7 is therefore a check on the
implementation, not on the mathematics.

Individual drawn numbers *do* change, exactly as they did when A3 was
introduced, because the index sequence changes. That is why this is opt-in
(§9).

## 4. The coupling score, and how it is chosen

One shared index per team means **one** latent factor per game. Five metrics
with five different historical within-game correlations cannot all be matched
by one factor, and the owner has explicitly not asked for that. What must be
chosen is the single axis the coupling acts on. Candidates, declared now,
ordered simplest first, with **no change as the incumbent**:

* **S0 — `none`. The incumbent.** A3 exactly as it stands, per team, no game
  coupling. Retained unless a candidate clears the decision rule in §8.
* **S1 — `off_snaps`.** Score = the pool key's `team_off_snaps` residual.
  Simplest non-trivial choice, and the one aimed directly at the total-game-play
  failure, since total plays is the sum of the two `team_off_snaps` draws.
* **S2 — `zmean`.** Score = the unweighted mean of the five residuals after
  each metric is z-scored across the pool. Spreads the coupling over all five
  metrics equally.
* **S3 — `pc1`.** Score = the first principal component score of the five
  z-scored residuals, loadings estimated by eigendecomposition of their
  correlation matrix over the historical pool, sign-oriented so that the
  `team_off_snaps` loading is non-negative. The best single axis in a
  variance sense.

The score is a property of a historical team-game, so ordering a pool by it is
a permutation of that pool and moves no mass.

## 5. The coupling parameter, estimated and never chosen

`rho` is **estimated from historical paired games**, not selected.

1. Take every historical team-game that carries a residual for all five metrics
   and whose opponent's team-game does too. Pair them by `(ord, team,
   opponent)`.
2. Compute each side's coupling score under the candidate.
3. `rho_spearman` = Spearman rank correlation of the paired scores, computed on
   the **symmetrised** sample — each game contributes `(A, B)` and `(B, A)`, so
   the estimate does not depend on which side is called home.
4. `rho = 2 * sin(pi * rho_spearman / 6)`, the standard Gaussian-copula
   inversion of Spearman's rho.

Rank correlation, not Pearson, is the estimand because the mechanism transports
ranks: under S1 the induced Spearman correlation of the two sides' `off_snaps`
residuals equals `rho_spearman` up to pool discretisation, so this parameter is
self-calibrating on its own axis rather than tuned to hit a target.

S3 additionally estimates five PC loadings the same way — from the historical
pool, at forecast time, from rows strictly earlier than the slate.

**There are no other parameters.** No threshold, no shrinkage, no blend weight,
no hand-set constant enters this mechanism.

## 6. Chronology

Every quantity in §4 and §5 — pool membership, residuals, z-score means and
SDs, PC loadings, `rho` — is computed inside `forecast` from `hist`, which is
already defined as panel rows with `ord < ordinal` for the slate being forecast.
The chronology guarantee is therefore the one production already enforces
(`TEAM_VOLUME_HISTORY_NOT_STRICTLY_EARLIER`), not a new one.

The evaluation slate is **2026 week 1**. Fitting seasons are 2020-2025, all
strictly earlier. **No 2026 outcome is consumed** — none exists in the panel,
and the guard above refuses the run if one appears.

## 7. What will be measured, and how

**Like-for-like rule, fixed here.** Reality supplies one draw per game. Every
model statistic compared against a realised series is computed **one draw per
game, over the games of the slate**, giving one value per draw, and is reported
as a **distribution over draws** (mean, 5th and 95th percentile). Per-game
predictive means are never correlated against a realised series. The historical
comparator is put on the same footing by resampling **16-game subsets** of the
1,615 historical games and reporting the same three numbers, so a 16-game model
statistic is compared against a 16-game historical statistic and not against a
1,615-game one.

Reported for S0 and for every candidate:

1. **Dependence.** Within-game Pearson corr(home, away) per metric, per draw,
   with the 5-95 band; and the Spearman equivalent. Against the historical
   value and its 16-game band.
2. **Game totals.** SD of total game plays per draw with band; and the fraction
   of drawn games outside `[106, 173]`, pooled over draws x games and reported
   with a game-clustered interval.
3. **Marginals, before vs after.** Per metric and per team: mean, sd, p05, p50,
   p95, plus the maximum absolute relative change across all 32 teams. Also the
   exact-uniformity check of the index map described in §3.
4. **Diagnostics.** `rho_spearman`, `rho`, pool sizes, the number of
   prospective rows that fell back to the global pool, and the number of teams
   not covered by a declared pair.

Naive intervals are not reported anywhere. Where an interval is over games it
is game-clustered; where it is over draws it is the draw distribution itself.

## 8. Decision rule, fixed before any candidate is run

Let `D` = the mean, across the five metrics, of
`|corr_model(home, away) - corr_historical(home, away)|`, using the per-draw
mean correlation for the model and the full-sample historical value.

Let `R` = `SD_model(total game plays) / SD_historical(total game plays)`, using
the per-draw mean for the model.

A candidate **replaces S0 as the recommended mode** only if all of:

1. `D` improves on S0 by at least **0.05** in absolute terms;
2. `|R - 1| <= 0.15`;
3. the fraction of drawn games outside `[106, 173]` is **at most half** S0's;
4. every within-game correlation has the **historical sign** for all five
   metrics;
5. no metric's per-team marginal mean, sd, p05, p50 or p95 moves by more than
   **1%** relative against S0 at the reporting draw count (this is a check on
   the implementation, since §3 makes it exact in distribution);
6. the drawn values remain free of any clip introduced by this change — the
   count of draws pushed to the zero floor must not exceed S0's.

Among candidates that clear all six, the **simplest wins**: S1 before S2 before
S3, and a later candidate is preferred only if it improves `D` by at least a
further **0.05** over the earlier one.

**If no candidate clears the rule, S0 is retained and the return says the game
coupling is not recovered by any candidate tested and names what would be
needed.** That is a publishable result, not a failure to be worked around.

**Predeclared expectations, so that a surprise is visible as a surprise.** S1 is
expected to fix `team_off_snaps` and the game-total behaviour close to exactly,
and to under-recover `team_carries`, because a single `off_snaps` axis reaches
carries only through the within-team-game correlation between the two
residuals. S2 and S3 are expected to spread the coupling and therefore to
under-recover `off_snaps`. If S1 recovers carries as strongly as snaps, that is
a result to explain, not to accept quietly.

## 9. Governance

**EXPLORATORY.** 2020-2025 are development data and 2026 week 1 has no
outcomes; nothing here is a confirmatory result and nothing is promoted.

The new mode is **opt-in via a parameter**, `game_coupling`, default `'none'`,
alongside a `game_pairs` argument the caller must supply. `JOINT_RESIDUALS_DEFAULT`
is untouched and remains `False`. **No production default changes** — that is
the lead's decision, not this packet's. Requesting a coupling without pairs, or
without the joint index mode, is a named refusal and not a silent no-op.

Nothing is committed. G0A, T-90 and every frozen artifact are untouched.
`nfl/production/team_volume_v1.py` is the only production file this packet
writes.

## 10. Hash discipline

The sha256 of this file is pinned in `nfl/research/a3g/run_a3g.py`. The runner
recomputes it at start and **refuses to run** if it has moved, so a
pre-registration edited after seeing a result cannot be presented as the
pre-registration the result was produced under.

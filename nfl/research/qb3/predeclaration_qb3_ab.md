# QB3-AB pre-registration — separating planned participation from replacement hazard

Written 2026-09-13, **after** the QB participation causal audit
(`QB_PARTICIPATION_CAUSAL_AUDIT.json`, commit `86bf6f7`) and **before any
estimator for this candidate is built, run or scored**.

This document does not authorise a change to production. R8 is untouched.
Nothing here may reach a live board without a further owner decision.

## 0. The baseline is preserved

`predeclaration_qb3.md`, sha256
`be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e`, remains the
baseline and is not modified. `qb3_lib.cell_of` and `qb3_lib.allocate` are not
edited. This is a **new** candidate scored against that baseline.

It supersedes nothing. `predeclaration_qb3_seasonboundary.md` (QB3-SB, sha256
`6cb5c522e3fbd63bb56c948e0ec7b070bcec2d96e6fde2a345ad1935b8763c08`) proposed a
season-boundary term in the cell definition. **QB3-AB subsumes it**: the audit
showed the season boundary is a symptom of the mixing, not the disease. If
QB3-AB proceeds, QB3-SB should be withdrawn rather than run in parallel, and
that is a decision for the owner, not for this document.

## 1. The defect this addresses

Measured on 2021-2024, 2,278 team-games (`QB_PARTICIPATION_CAUSAL_AUDIT.json`):

| | REALITY, n=1700 | QB3 cell (1, yes), n=2349 |
|---|---|---|
| P(starter takes every dropback) | 0.8682 | 0.7765 |
| **P(starter takes ZERO dropbacks)** | **0.0000** | **0.0736** |
| starter mean share | 0.9641 | 0.8919 |

Conditional on an established incumbent starting with no planned rotation, the
starter took zero dropbacks in **0 of 1,700 team-games**. QB3 assigns that 7.36%
of the mass in its cleanest cell, because `build_frame` builds from the depth
chart and the cell therefore pools a PREGAME event (the charted QB1 never
starts) with an IN-GAME one (given he started, how it unfolded).

## 2. The candidate

**QB3-AB.** The estimand is unchanged -- `s_dropbacks`, a distribution on the
simplex -- and closure by construction is unchanged. What changes is that the
single pool is replaced by an explicit two-stage decomposition:

    P(share) = P(starts) x P(share | starts)

**Stage A -- planned participation.** `P(player i is the team's starting
quarterback)`, from pregame evidence only: depth-chart rank, the incumbent
signal, and -- when a governed ingestion exists for the game -- the official
inactive list. A player ruled officially inactive has Stage A probability
exactly zero, which is a fact and not an estimate.

**Stage B -- contingent replacement hazard.** `P(share | he started)`,
estimated on the population the audit isolated: team-games in which that
quarterback actually took the first snap. Anchors from the audit:

| | |
|---|---|
| P(starter finished) | 0.8688 |
| P(replacement, never returned) | 0.0576 |
| P(blowout relief) | 0.0718 |
| starter mean share given he started | 0.9641 |

**What this candidate may not do**, stated now so no later result can be
reinterpreted:

- it may not clip, floor, bound, or manually rebalance any share;
- it may not assign any quarterback a share of 1.0 by rule. Stage B remains a
  RESAMPLED empirical pool and must retain whatever partial and zero mass the
  conditional data contains;
- it may not introduce a fitted constant. Both stages stay empirical
  frequencies and resampled pools;
- **it may not let a healthy, rostered QB2 or QB3 dilute a normal starter's
  volume merely by existing.** Their Stage A mass must come from evidence that
  they are candidates to start, not from their presence on a roster;
- it may not consume Hard Rock backup-quarterback market availability, or any
  other market signal, as a feature, a rule, a filter or a conditioning
  variable. If such availability is ever recorded it is an external diagnostic
  only;
- it may not consume any forecast-season outcome.

## 3. Training and evaluation partitions

Walk-forward, identical in shape to baseline §7. For evaluation season *Y*,
every rate in both stages is estimated on seasons `< Y`, and the incumbent
feature uses a strictly-earlier ordinal prefix cut.

- **Evaluation seasons: 2022, 2023, 2024.** The committed depth-chart leaves
  stop at 2024; 2021 is retained for fitting only.
- Both arms see the same rows, the same cut and the same seed.
- Stage B is fitted on team-games where the quarterback took the first snap.
  That conditioning is the point of the candidate and is declared here rather
  than discovered later.

## 4. Primary metric

**CRPS of the predicted `s_dropbacks` distribution against the realised
share**, per QB-game, pooled -- the baseline's own primary metric, so the
comparison is like for like.

Reported alongside:

- Brier score on `is_primary`;
- mean absolute share error;
- **P(share = 0) against realised**, reported separately for the established-
  incumbent population. This is the quantity the audit found wrong by 7.36
  points and it must be shown, not folded into an average;
- team-closure violation rate, which must remain exactly zero.

Uncertainty: **team-game clustered bootstrap**, with cluster counts reported
beside every interval. No interval is quoted without one.

## 5. Secondary downstream metrics

`qb/att`, `qb/cmp`, `qb/pyds`: calibration slope and intercept, bias, MAE, and
interval coverage at 50/80/90/95, on the same walk-forward folds.

**Secondary cannot rescue a failed primary.** A candidate that improves passing
yards while worsening share CRPS is rejected: improving a downstream quantity
by degrading the thing that produces it is how a model gets tuned toward an
answer.

## 6. Acceptance and rejection criteria, fixed before any result

QB3-AB is preferred over the QB3 baseline only if **all** of:

1. pooled CRPS improves; **and**
2. the team-game clustered 95% interval on the CRPS difference excludes zero;
   **and**
3. the direction is consistent in **all 3** evaluation seasons; **and**
4. the team-closure violation rate is exactly zero; **and**
5. P(share = 0) for the established-incumbent population moves toward the
   realised rate and does not overshoot into assigning it impossible
   confidence; **and**
6. no stratum is materially degraded -- in particular the genuine committee and
   genuine pregame-uncertainty cases, which are the ones a two-stage model
   could most easily flatten.

If CRPS does not improve but the zero-mass defect does, the return says **the
decomposition fixes the participation mass without improving the distribution,
and is not adopted on that basis alone.**

## 7. Confirmation limitations

The defect was found by inspecting 2021-2024. Those seasons selected the
finding, the conditioning set and the classification rules. A pre-registration
written afterwards does not restore independence, so **every result under this
document is EXPLORATORY** and must be labelled so in every artifact.

Specifically:

- play-by-play cannot separate an injury from a benching. The 5.76%
  replacement rate is `REPLACEMENT_NO_RETURN` and is not an injury rate;
- the classification rules are deterministic and predeclared, but they are
  rules, not ground truth;
- the depth-chart leaves stop at 2024, so no 2025 fold exists;
- "established incumbent" means only that the same man started the club's
  previous game. It is not a health status.

## 8. Prospective role for 2026

2026 is not a fitting season and nothing in 2026 estimates any rate in either
stage.

If QB3-AB meets §6 on the exploratory folds, the proposed role is **prospective
shadow only**: both arms computed and recorded per team-game, neither
published, accumulating toward a genuinely out-of-sample record. Promotion into
R8 requires a separate owner decision on evidence that does not exist yet.

Until then the baseline remains the production layer and every week-1
quarterback market stays inadmissible.

## 9. Governance

New component. `PATH_C_STATE` is not edited, R8 parameters are not edited, Q9
is untouched, and the baseline contract file is not modified. Registered before
any QB3-AB estimator exists; its sha256 is to be cited by any module that
implements it.

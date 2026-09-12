# Q9B pre-registration — model-family comparison

**Written after the identifiability and dispersion audits and before any
family was built or scored. Those two audits are pre-evaluation measurements
whose job is to decide what the comparison contains; the comparison itself is
registered here.**

## What the audits already established

`Q9B_IDENTIFIABILITY.json`, 22,958 appearing player-games, 2022–2025:

| quantity | value |
|---|---|
| observed zero rate | 0.25089 |
| multinomial sampling zero at the **correct** share | 0.22410 |
| mis-estimated-share component | −0.01224 |
| **structural excess** | **+0.02679** (10.68 % of the zero mass) |
| production allocator's implied zero | 0.21186 |

Against the rule fixed in code before the numbers were read — a structural
excess of at least 2 percentage points **and** at least 5 % of the zero mass —
**the hurdle is identified as structural.**

About 89 % of the observed zero mass is ordinary multinomial sampling. The
production allocator's 3.90-point shortfall decomposes into **1.22 points of
mis-estimated share** and **2.68 points of structural excess**.

### The falsifiable prediction this makes

If that decomposition is right, a plain allocator with better shares should
recover roughly **a third** of the production shortfall and no more. `MNL_PLUS`
is the test. If it recovers all of it, the decomposition is wrong and the
hurdle is a reparameterisation; if it recovers about a third, the structural
reading holds.

## Arms

| arm | mechanism |
|---|---|
| `BASELINE` | current R8 allocation: appearance draw × production base share, multinomial over the team budget |
| `MNL_PLUS` | a conditional (multinomial) logit over the appearing players, fitted on the **same pregame covariates Q9's stage 1 uses** plus the log production share, then an ordinary multinomial. **No hurdle, no floor.** |
| `Q9_HURDLE` | the supported Q9 mechanism, **frozen** — imported from `nfl.research.q9.hurdle`, not reimplemented |

`MNL_PLUS` is given the same information the hurdle gets. If the hurdle is
only a reparameterisation of a better share model, this is the arm that shows
it.

### Dirichlet-multinomial is REFUSED, and the reason is measured

The dispersion audit compares realised variance to the multinomial's own
`N·π·(1−π)` **at the correct share**, so a ratio above 1 cannot be an artefact
of a bad share estimate. Median ratio **1.193** against a threshold of **1.25**
fixed in code before the number was read. That is not meaningful
overdispersion for a mechanism whose entire justification is extra variance,
so **no DM arm enters the comparison** — not because the literature is wrong,
but because this system does not exhibit the thing DM exists to model.

## Q9 stays frozen

The hurdle architecture, the one-target floor, the hurdle predictors, the
fallback rules and the decision thresholds are imported unchanged. No refit,
no retune, no threshold movement. Any change would make the frozen candidate a
different candidate.

## Held fixed across all arms

The team target budget (frozen P4B point plus its own residual pool, **no Q8
shrink repair**), production R8 appearance, the class-level prior, the share
shrinkage weight, receiving efficiency, and the touchdown layer. Random
streams are shared where the shapes allow.

## Metrics

The same four blocks Q9 was judged on — zero-target probability, the
positive-target count distribution, the full marginal distribution, and
downstream receiving yards — plus, for this comparison specifically:

* **the falsifiable check**: what fraction of the production zero-mass
  shortfall each arm recovers, against the predicted third;
* the fallback audit and the PIT diagnosis registered below.

Strata: RB/WR/TE, starter/rotational/fringe, appearance certainty, prior
opportunity depth. No stratum the comparison reads is defined from the
realised target count.

Clustering: block bootstrap over whole team-games.

## Fallback audit, registered

For `HURDLE_MORE_CLEARERS_THAN_BUDGET`, measured and **not changed**:

* which roster and volume states produce it — team budget band, number of
  appearing players, number of clearers;
* whether it concentrates in very low team target budgets;
* **whether the weighted subsampling distorts the marginal hurdle
  probabilities** — the realised `P(player is selected)` on affected groups
  against his declared `p_hurdle`;
* its contribution to CRPS and to zero-mass calibration, by comparing rows in
  affected team-games against the rest.

`HURDLE_NO_CLEARERS` is audited separately and its rate is reported whatever
it is.

## PIT diagnosis, registered

Q9 improves CRPS and zero mass while marginal PIT χ² worsens. The
deterioration is located by decomposing the PIT histogram over: the zero mass,
low positive counts, the upper tail, role class, and prior opportunity depth.

**PIT is diagnosed, never optimised.** No arm is selected or tuned on it, and
the decision function does not read it.

## Final status

Exactly one of `PROMOTION_READY_FOR_PROSPECTIVE_TEST`,
`NEEDS_ENGINEERING_REPAIR`, `MECHANISM_NOT_IDENTIFIED`, decided by:

* **MECHANISM_NOT_IDENTIFIED** if the identifiability audit had failed its
  pre-declared rule, or if `MNL_PLUS` recovers the production shortfall as
  well as `Q9_HURDLE` does;
* **NEEDS_ENGINEERING_REPAIR** if the production-interface parity test fails
  any required invariant, or a fallback is shown to distort the declared
  probabilities;
* **PROMOTION_READY_FOR_PROSPECTIVE_TEST** only if the mechanism is
  identified, `Q9_HURDLE` is not matched by the plain family, parity holds
  exactly, and the fallbacks are measured and benign.

**No production promotion in this task.**

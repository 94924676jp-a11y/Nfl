# P4C-CARRY pre-declaration — carry-count error decomposition

Written 2026-09-07. HEAD at task start `68f96e0`.

Written **before** any oracle corner was evaluated, any Shapley value computed,
any CRPS, PIT or coverage number existed for this task. **This is a
decomposition experiment. No component is modified.** Departures are labelled
where they occur.

## 1. The frozen system

The P4C/P4D carry machinery is **imported, not copied and not edited**:
incumbent P3 Stage-A appearance model, P4B unconditional team-volume
distribution, P4C additive carry-share weights, P4C reserved-stochastic-mass
reconciliation, shared team-game draw identity. Verification is a first-class
deliverable: the baseline must reproduce P4C's and P5A's published carry
numbers exactly, and if it does not, this task stops and reports the mismatch.

## 2. What the accepted carry object is, and what it is not

The P4C `carries` class models **RB carries only**, as a share of the team's
total carries. Measured in P4C: the modelled universe holds **0.799** of the
team carry pie and the residual OTHER mass is **20.1%, of which QB rushing is
15.0%** and WR 3.2%.

**QB designed rushes and scrambles are therefore not modelled by this object at
all.** They live inside the OTHER mass. This task diagnoses them as part of the
team-volume component and **does not silently redefine the accepted carry
accounting** to bring them in.

## 3. The factorial, and why `avail` belongs with team volume

Three binary components, each predicted or realised, giving a full 2³ design so
interactions are **estimated, not inferred from one-at-a-time oracles**:

| component | predicted | realised |
|---|---|---|
| **T** team volume | P4B team-carry draw `T_gj` **and** the reconciliation's reserved modelled mass `avail_gj` | realised team carries `T*_g` and realised modelled mass `m*_g` |
| **S** share/allocation | P4C additive weights `w_ij` | realised share `S*_i = c_i / T*_g` (zero for a non-appearance) |
| **A** appearance | Bernoulli(`p_i`) draw | realised `A*_i` |

`avail` is a **team-level** quantity — the mass reserved for the modelled set
after the OTHER component takes its share — so it belongs with team volume.
Putting it there makes the corner algebra exact:

```
count_ij = T_gj * avail_gj * w_ij A_ij / sum_g(w A)
O_ALL:   = T*_g * m*_g * S*_i A*_i / m*_g  =  T*_g * S*_i  =  c_i
```

**The all-oracle corner therefore reproduces the realised carry count exactly**,
and that identity is checked rather than asserted. If `avail` were left on the
predicted side the corner would not close and every attribution would absorb the
gap.

**Zero-carry and non-appearance handling, fixed now:** a realised share of a
player who did not appear is **0**, not undefined; a player drawn as appearing
whose realised share is 0 receives 0 carries, which is coherent; a team-game in
which every appearing modelled player has realised share 0 has a zero
denominator and is guarded to 0 carries rather than to a division error.

## 4. Attribution method

**CRPS does not add linearly across component substitutions, so ordering must
not decide the answer.** Attribution is by **Shapley value** over the three
components, with the characteristic function
`v(S) = CRPS(baseline) − CRPS(oracle set S)`, `v(∅) = 0`. For three components
the weights are 1/3, 1/6, 1/6, 1/3.

**Both are reported**: the raw one-at-a-time oracle improvements *and* the
Shapley attribution, plus the explicit two-way and three-way interaction terms
from the same factorial. Shapley values are computed **per row** as well as
pooled, so subgroup attribution is an average of per-row values rather than a
re-run.

## 5. Metrics

**CRPS on the player carry count is primary.** Also MAE, RMSE, correlation,
bias, randomised PIT (the predictive has a large atom at zero — 43% of
player-games have zero carries), interval coverage at 50/80/90/95, mean interval
width, and threshold calibration.

**Carry-count threshold grid, pre-declared here before any result:**
**0.5, 4.5, 9.5, 14.5, 19.5.** These are the boundaries of the carry-tier
cohorts the directive names, and no sportsbook price was consulted.

Rushing yards are evaluated **only** as a frozen downstream confirmation
(§8), never as a target of this task.

## 6. Component diagnostics

**Team volume:** forecast versus realised team carries — bias, correlation,
variance captured, calibration, upper and lower tail error, by season. Reported
separately for the modelled RB mass and the OTHER mass, with QB rushing and
scrambles identified inside OTHER using P1's accounting unchanged.

**Share:** conditional on realised team volume, how well are carries allocated?
Player-share score, top-RB (RB1) share error, RB2 share error, OTHER share,
within-team allocation error, role-change sensitivity, and **RB1↔RB2
competition** explicitly, because P4C measured genuine negative dependence there
(simulated −0.246 against empirical −0.210 [−0.290, −0.117]).

**Appearance:** carry-specific only. **P4D is not re-run.** The question is
narrower: how much does the appearance draw move the zero-carry mass, the
low-carry tail, high-volume backs and role-change cases, broken out by the
P4D probability bands (<0.25, 0.25–0.50, 0.50–0.80, 0.80–0.95, ≥0.95).

## 7. Cohorts

Carry tiers 0 / 1–4 / 5–9 / 10–14 / 15+; RB versus QB (QB reported as the OTHER
mass, per §2); RB1/RB2 ranked by the **pregame** forecast, never the outcome;
stable versus role change; prior-history depth; appearance-information quality;
season.

## 8. Downstream confirmation

Each carry oracle is propagated through the **frozen P5A conversion control**
(system A, pooled per-carry empirical, location-shift family) with **no
refitting of anything**. The purpose is only to confirm that a decomposition
measured in carry space survives into rushing-yard space.

## 9. The P5A asymmetry question — report only

P5A found its efficiency model helps high-efficiency-history backs (−2.09%
CRPS) and hurts low-efficiency-history backs (+0.67%). **This task does not fix
that and does not alter P5A.** It asks one diagnostic question: are
low-efficiency-history backs systematically **over**-projected in carries and
high-efficiency-history backs **under**-projected? Reported as a measurement.

## 10. Chronology and quarantine

Unchanged. Every fitted quantity comes from seasons strictly before the
evaluation season; within-season histories use strictly earlier games. **Oracles
are diagnostics only, are computed after any selection has happened, are not in
the eligible tuple, and two guard-deletion proofs show what stops them.** No
2026 outcome, no market, no roster status, no observed weather.

## 11. What would count as a negative result

Stated now, in the words the return will use:

- If team volume is not the largest component, the return says so plainly and
  names what is, whatever P5A's framing implied.
- If the interactions are large enough that the main effects are not separately
  meaningful, the return says the decomposition does not identify a single
  bottleneck.
- If the carry distribution's passing randomised PIT coexists with weak
  discrimination, the return says the calibration is hiding it and reports the
  discrimination directly.
- If no component is improvable from information already in the repository, the
  return says the bottleneck is external data and names which.

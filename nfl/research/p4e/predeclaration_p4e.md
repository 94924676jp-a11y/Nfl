# P4E pre-declaration — RB carry share / allocation and competition

Written 2026-09-07. HEAD at task start `95d2fe7` (Part I complete: 1,323
assertions, 1,323 passed, 0 failed).

Written **before** any candidate was fitted, any cohort table inspected, any
CRPS, PIT, coverage or joint-dependence number existed for a candidate.
Departures will be labelled where they occur.

## 1. Why this target

P4C-CARRY's Shapley attribution of RB carry-count CRPS error: **allocation
50.1%**, team volume 29.8%, appearance 20.0%. P5A: carry uncertainty dominates
rushing conversion (50.9% oracle against 16.2%). Allocation is therefore the
largest actionable component in the rushing branch. **This is research only. No
architecture is promoted silently.**

## 2. The four accepted observations to explain

1. realised RB1↔RB2 **share** correlation −0.56 to −0.62;
2. forecast RB1↔RB2 share correlation only −0.25 to −0.43;
3. players with <25 prior carries receive ≈2.23 projected carries against 0.57
   realised;
4. established backs consequently lose predicted mass — measured at −16.3%
   (high efficiency history) and −16.2% (low), i.e. the same for both, so this
   is not an efficiency effect.

**These are observations to explain, not a diagnosis.** In particular I do not
assume the cure is a low-history penalty, and §7 forbids hard-coding one.

## 3. Baseline — untouched control

P4C system **C** (additive share weights + reserved stochastic-mass
reconciliation), with the incumbent P3 Stage-A appearance model and the P4B
team-volume draw, imported unchanged. **It must reproduce its published carry
CRPS exactly — 1.9296 / 1.9973 / 2.1103 / 2.0545 for 2022–2025. If it does not,
P4E stops and reports.**

## 4. What changes, and what may not

Only the **pre-reconciliation share weight** `W_i` may change. The appearance
model, the team-volume distribution, the reconciliation, the stochastic
residual mass and the joint draw identity are frozen and imported. So any
difference is attributable to the allocation weight and to nothing else.

## 5. Candidate feature blocks, all strictly prior-game

| block | contents |
|---|---|
| **A history_depth** | prior career carries; prior-season carries; carries over the prior 4 / 8 / 10 **team-games**; number of prior appearances; an effective-sample-size term |
| **B hierarchy** | prior carry-share rank within the team's RB group; prior snap-share rank; rank persistence; rank uncertainty (spread of recent ranks). **Derived only from prior information.** No present-week depth-chart state: the depth-chart artifact carries no timestamp of any kind (P4D §2) and is quarantined |
| **C competition** | teammates' prior carry shares; teammates' appearance probabilities; teammates' history depth; concentration (HHI) and entropy of the team's prior RB allocation; count of plausible active competitors |
| **D role_change** | prior major carry-share increase/decrease; starter-like transition indicator; returning-from-absence indicator; teammate disappearance / reappearance. All from prior games; **no outcome-derived current-game label** |
| **E carry_snap** | prior snap share and prior snap-to-carry ratio. **Not assumed to help** — tested as its own rung |

**Forbidden and not read:** `weekly_rosters.status`, any postgame roster label,
present-week depth-chart state, observed weather, market data, 2026 outcomes.

## 6. Candidate ladder

`P4C` (control) → `E_A` → `E_AB` → `E_ABC` → `E_ABCD` → `E_ABCDE`, plus each
block **alone** on top of the control so a block's contribution is not read off
a cumulative sequence alone. Every rung uses the frozen reconciliation.

**Model family discipline.** P4C already showed bounded and compositional
families worsen forecasting and manufacture bad dependence (Dirichlet, softmax
latent Gaussian, empirical log-ratio: 5–10% worse CRPS, and a top1↔remainder
correlation of −0.44 where the truth was +0.01). So the starting point is the
**accepted additive weight**, and the candidate change is to what the weight's
**centre** is — a learned conditional mean instead of an EWMA with a flat
position-prior fallback. A different family must earn promotion on
out-of-sample evidence, not on elegance.

## 7. Low-history analysis — a dedicated diagnosis, not a subgroup table

Determine **why** <25-prior-carry players receive 2.23 against 0.57. Separate at
minimum: true emerging backs; replacement/injury opportunity; roster-fringe
non-appearance rows; first-history cases identifiable chronology-safely;
veterans with little recent usage; players whose apparent opportunity is caused
by teammate-absence uncertainty.

Then decide which of these the current prior is: too diffuse, too generous,
insufficiently hierarchical, misconditioned on appearance, or misconditioned on
competition.

**No hard-coded <25-carry penalty.** Any shrinkage must be learned on prior
seasons and validated chronologically.

## 8. Joint competition — marginal CRPS is not enough

Reported for control and every candidate: RB1↔RB2, RB1↔RB3, RB2↔RB3, top1↔
remainder — realised and forecast correlation; concentration distribution; team
allocation entropy; P(RB1 > RB2); P(RB2 materially challenges RB1), defined
**now** as P(share_RB2 ≥ 0.8 × share_RB1); P(two backs both exceed 0.25 share).

**Negative correlation must emerge from the model, not be imposed.** No term is
added whose purpose is to reproduce an observed covariance.

## 9. Evaluation

Strict expanding-window walk-forward; parameters fitted on seasons `< Y`;
within-season histories from strictly earlier games. **Primary: RB carry-count
CRPS downstream of allocation.** Secondary: share CRPS, MAE, RMSE, r, R², bias,
randomised PIT, threshold calibration on P4C-CARRY's pre-declared carry grid
(0.5 / 4.5 / 9.5 / 14.5 / 19.5), coverage, and the §8 joint diagnostics.

**Pooled and every season separately. No pooling that hides a failed season.**

## 10. Cohorts, thresholds fixed now

- rank: RB1 / RB2 / RB3 / RB4+, ranked by the **pregame** forecast;
- prior carries: **<10 / 10–24 / 25–49 / 50–99 / 100+**;
- appearance probability: <0.25 / 0.25–0.50 / 0.50–0.80 / 0.80–0.95 / ≥0.95;
- role: role-change / stable-role;
- backfield shape: **concentrated** if the team's prior-games RB allocation HHI
  ≥ 0.50, **committee** if < 0.50.

## 11. Oracle ceiling

The P4C-CARRY oracle framework is preserved. After the best practical
candidate, recompute the share/allocation Shapley component and report **what
fraction of the original 50.1% allocation error was recovered** — so the return
distinguishes a practically meaningful gain from a statistically detectable but
tiny one.

## 12. Promotion standard — all eight, or no promotion

1. beats P4C on pooled carry CRPS;
2. improves a clear majority of evaluation seasons (≥ 3 of 4);
3. does not materially damage carry randomised PIT (no worse than +25% relative
   on the pooled statistic, and it must still pass the 27.877 critical value);
4. **materially** improves the low-history over-allocation defect;
5. improves, or at minimum does not worsen, RB competition realism;
6. survives the role-change cohorts;
7. survives the leakage and adversarial tests;
8. produces a **practically meaningful fraction of the allocation oracle gap**,
   which I fix now as **≥ 5% of the P4C-CARRY allocation Shapley component**,
   not merely a significant delta.

**If no candidate clears all eight, P4C is retained and P4E is reported as
negative research.**

## 13. Adversarial tests

Seeded: future carry share; current-game realised carries; current-game
realised snaps; postgame roster status; future teammate availability;
current-game RB rank; evaluation-season fitted prior. **At least two
guard-deletion proofs.**

## 14. What would count as a negative result

- If no block improves out-of-sample allocation, the return says the available
  pregame information does not contain the missing allocation signal.
- If the low-history over-allocation is a **consequence of the reconciliation**
  rather than of the weight, the return says so and does not attribute it to a
  prior.
- If a candidate improves marginal CRPS while worsening RB1↔RB2 realism, the
  return refuses it under rule 5 and says which it traded.

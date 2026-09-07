# P4C — Constrained joint player opportunity allocation

**Status:** complete. Research return only. Nothing was authorised, enabled or
promoted to production.

---

## 0. Read this first — a correction to my own P4B return

P4B told you, and this directive repeats as established fact, that

> independent player-share draws over-allocate team opportunity by
> approximately 27–45%.

**That figure is wrong and I withdraw it.** It compared a simulated share sum
computed **without the appearance mask** against a realised sum in which
absences are necessarily zeros. Since roughly 30% of candidate player-games are
absences, the two quantities were never comparable.

Recomputed like-for-like from the same draws
(`nfl/research/p4c/verify_p4b_overallocation.py`):

| class | Σ S (what P4B printed) | Σ A·S (like-for-like) | realised | P4B figure | corrected |
|---|---|---|---|---|---|
| `snaps` | 6.16–6.48 | 4.86–4.96 | 4.87–4.90 | +26.3…+32.3% | **−0.8…+1.3%** |
| `pass_snaps` | 6.20–6.53 | 4.89–5.00 | 4.92–4.94 | +25.8…+32.3% | **−1.1…+1.2%** |
| `targets` | 1.319–1.384 | 1.038–1.063 | 0.987–0.991 | +33.1…+39.8% | **+4.7…+7.3%** |
| `carries` | 1.064–1.149 | 0.820–0.863 | 0.795–0.801 | +32.9…+44.6% | **+2.4…+8.6%** |
| `rz_carries` | 1.132–1.213 | 0.849–0.903 | 0.766–0.803 | +41.4…+58.3% | **+7.2…+17.8%** |

**The defect P4B was pointing at is real, but it is a different defect, and
P4C's own measurement is the one worth having.** Independent draws are close to
unbiased *on average* while being **flatly impossible in 29–56% of individual
team-game draws**:

| class | P(Σ modelled shares exceeds the physical maximum) under independent draws |
|---|---|
| `targets` | **56.2%** |
| `pass_snaps` | **45.6%** |
| `snaps` | **43.8%** |
| `rz_carries` | **35.2%** |
| `carries` | **29.3%** |

Every reconciled system drives that to **0.000–0.006**. An average that happens
to come out right while more than half the individual simulations describe a
football game that cannot exist is exactly the kind of thing this project
exists to catch, and P4B's diagnostic did not catch it — it reported a number
that was too large for a reason unrelated to the problem.

---

## 1. HEAD at task start

`c9e3a70` — "P4B return, and correct two stale counts in the repo docs".
Working tree clean, `main` up to date with `origin/main`.

## 2. Commits

| commit | content |
|---|---|
| `22c7ee2` | P4C pre-declaration and the accounting measurement it rests on |
| `e27a43f` | P4C research: constrained joint player opportunity allocation |
| *(this report)* | `TASK_REPORT_2026-09-07_P4C.md` |

A bot vintage-capture commit (`a42dbaf`) landed during the work and was merged
in; no research artifact was touched by it.

## 3. Files

All under `nfl/research/p4c/`:

| file | role |
|---|---|
| `predeclaration_p4c.md` | written before any allocation was fitted |
| `accounting.py` / `accounting.json` | the constraint, **measured** on training seasons |
| `p4c_lib.py` | accounting modes, allocation, water-filling, scoring |
| `p4c_build.py` | panel prep, walk-forward parameter fitting, weight generators |
| `run_p4c.py` | the A→B→C→D ladder, joint diagnostics, covariance |
| `run_p4c_ablate.py` | calibration attribution, extended oracle, subgroups |
| `run_p4c_adversarial.py` | 10 seeded leaks + 2 guard-deletion proofs |
| `verify_p4b_overallocation.py` | §0 above |
| `p4c_results.json`, `p4c_ablation.json`, `p4c_adversarial.json` | results |
| three run logs | |

## 4. Pre-declaration

`nfl/research/p4c/predeclaration_p4c.md`, committed in `22c7ee2` **before**
`run_p4c.py` existed. It fixes the estimand, the systems, the chronology, the
metric set, the threshold grids (including the newly pre-declared `rz_carries`
grid), the covariance pairs, the boundary-problem test, and the negative-result
wording. Departures are in §22.

## 5. Test counts

Repository suites are **unchanged and re-enumerated from the filesystem**:
**1,230 assertions across 19 suites, 0 failing** — 1,137 across 16 NFL suites
plus 93 across 3 platform-governance suites. P4C adds **12 adversarial probes,
0 failing**, run as a separate research harness (§23).

Governance unchanged: **G0A 11 PASS / 1 FAIL**, pre-flight 10 checks 0 failing,
NFL-1 not authorised, T−90 untouched, no 2026 outcome consumed.

---

## 6. Exact accounting identities, by opportunity class

Measured on **2020–2021 only** so the design was not conditioned on the
evaluation seasons; re-measured on 2022–2025 as verification. Both are in
`accounting.json`. **The directive's warning was right: there are two
accounting regimes, not one.**

### Regime 1 — mutually exclusive events (a true simplex)

Every target and every carry belongs to exactly one player.

```
Sigma over the FULL panel  ==  1.0000   (sd 0.0000, every team-game, every season)
```

| class | Σ modelled universe | OTHER mass | who holds OTHER |
|---|---|---|---|
| `targets` | 0.9891 | **1.09%** | QB 0.12%, OL 0.05%, and modelled-position players with no prior game |
| `carries` | 0.7991 | **20.09%** | **QB rushing 15.0%**, WR 3.2%, TE 0.2% |
| `rz_carries` | 0.7857 | **21.43%** | QB 16.5%, WR 3.1%, TE 0.6% |

For `rz_carries` the OTHER mass is **zero in 41.8% of team-games**, so it is
zero-inflated and cannot be represented by a mean.

### Regime 2 — simultaneous occupancy (NOT a simplex)

Eleven players are on the field for every snap.

```
snaps       Sigma over the FULL panel = 10.9572 (sd 0.0930)
pass_snaps  Sigma over the FULL panel = 10.9999 (sd 0.0029)
```

Composition of the eleven (`snaps`, training): OL 5.037, QB 1.007,
**WR+TE+RB 4.890**.

| class | Σ modelled universe | sd | p01 | p99 |
|---|---|---|---|---|
| `snaps` | **4.8901** | 0.2037 | 3.950 | 5.000 |
| `pass_snaps` | **4.9323** | 0.1920 | 3.957 | 5.000 |

**The constraint here is "sum to K ≈ 4.89", with K itself random**, and each
individual share is separately capped at 1. Forcing a simplex would have been
wrong by a factor of five. Every identity is enforced in code by
`L.CLASSES[cls]['mode']` and nothing selects a mode by inference.

## 7. Player-universe definition

Unchanged from P1–P4B and **entirely pregame**: for each team-week, every
player who appeared for that team in any of the **previous 4 team-games**, with
at least one prior game in the panel (`f_n_prior >= 1`).
`weekly_rosters.status` is never read. The evaluated set therefore **keeps
2,158 of 7,743 player-games (27.9%) in which the player did not appear** —
dropping them would be a postgame definition of the universe, and adversarial
probe 9 asserts we do not.

## 8. Residual / unmodelled mass definition

For a simplex class, `OTHER = 1 − Σ(modelled universe)`, drawn per team-game
from an empirical pool of prior seasons. For an occupancy class the analogue is
`K = Σ(modelled universe)` itself, drawn the same way.

**Mass pools exclude 2020.** The residual has a structural part (positions
outside the modelled set) and a **panel-edge part** — modelled-position players
with no prior game — which is 2.0–4.2% in 2020 against **0.4–0.9%** in
2022–2025, because 2020 is the panel's first season and everyone starts without
history. That is a construction artifact, not a football quantity, and fitting
it would have biased every reconciliation. The decision is in the
pre-declaration §1, taken from a training-season measurement before any result.

## 9. Candidate joint distributions

**The ladder is deliberate, and the pre-declared C had to be split to make it
one** (§22, departure 1):

| id | perturbation family | mass treatment | isolates |
|---|---|---|---|
| **A** | additive share residual + clip (P4B control) | none | — |
| **B** | additive + clip | reserved, **deterministic** (prior-season mean) | reconciliation |
| **C** | additive + clip | reserved, **stochastic** | the mass treatment |
| **C2** | additive + clip | stochastic, **competing** OTHER | whether vacated mass leaks out of the modelled set (simplex only) |
| **D_dir** | **Dirichlet**, α₀ by pooled moment estimator | as C | the family |
| **D_sln** | **softmax latent Gaussian** + zero atom | as C | the family |
| **D_ln** | **logit-normal** marginals (occupancy) | as C | the family |
| **D_emp** | **empirical log-ratio resampling** + zero atom | as C | the family |
| **E** | **realised relative allocation** | as C | **DIAGNOSTIC ONLY** |

Every system shares one marginal point forecast (EWMA half-life 3 on prior
appeared shares), one appearance model (P3 Stage-A), and one team-total draw
(P4B system B). `ELIGIBLE_SYSTEMS` excludes E; probes 7 and 11 prove that line
is what stops it.

Fitted concentration for `targets` 2024: **α₀ = 17.43**. Log-ratio dispersions
and zero-atom rates are in `p4c_results.json` under `params`.

## 10. Chronology design

Strict walk-forward. For evaluation season *Y*: player histories use prior
**games**; appearance model, share-residual pools, log-ratio pools, zero-atom
rates, Dirichlet concentration and mass pools use **seasons strictly before
Y** (mass pools additionally exclude 2020). Verified by probe 6: the shipped
2024 fit uses mass-pool seasons `[2021, 2022, 2023]`; refitting with 2024
included changes α₀ by +0.55%. No same-game realised share, no realised
teammate share, no future role information, no postgame roster status.

---

## 11. Marginal results

Pooled 2022–2025. `E` is the oracle and is never a candidate.

| class | system | MAE | RMSE | r | R² | bias | **CRPS** | log score | c50 | c90 | w90 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `snaps` | A | 10.058 | 13.905 | 0.758 | 0.574 | −0.360 | 6.8201 | 3.185 | 0.660 | 0.947 | 40.81 |
| | **C** | 9.972 | 13.720 | 0.765 | 0.585 | −0.291 | **6.7882** | 3.194 | 0.662 | 0.947 | 41.09 |
| | D_ln | 10.333 | 13.837 | 0.763 | 0.578 | −0.291 | 6.9874 | 3.230 | 0.721 | 0.970 | 48.96 |
| | E\* | 4.061 | 7.036 | 0.948 | 0.890 | −0.283 | 3.2444 | 2.360 | 0.734 | 0.986 | 27.60 |
| `pass_snaps` | A | 6.331 | 8.913 | 0.744 | 0.554 | −0.201 | 4.2922 | 2.849 | 0.663 | 0.944 | 25.31 |
| | **C** | 6.276 | 8.800 | 0.752 | 0.565 | −0.177 | **4.2606** | 2.856 | 0.667 | 0.944 | 25.50 |
| | E\* | 3.024 | 5.263 | 0.921 | 0.844 | −0.173 | 2.3164 | 2.122 | 0.743 | 0.987 | 18.60 |
| `targets` | A | 1.461 | 2.108 | 0.714 | 0.504 | **−0.163** | 0.9448 | 1.553 | 0.670 | 0.952 | 5.82 |
| | **C** | 1.424 | 2.087 | 0.717 | 0.514 | **−0.021** | **0.9360** | 1.546 | 0.661 | 0.942 | 5.40 |
| | D_dir | 1.397 | 2.096 | 0.717 | 0.510 | −0.021 | 0.9430 | 1.576 | 0.569 | 0.931 | 5.67 |
| | D_sln | 1.408 | 2.098 | 0.715 | 0.509 | −0.021 | 0.9946 | 1.642 | 0.755 | 0.956 | 7.08 |
| | E\* | 0.528 | 1.113 | 0.934 | 0.862 | −0.021 | 0.3993 | 0.815 | 0.797 | 0.989 | 3.13 |
| `carries` | A | 3.200 | 4.535 | 0.746 | 0.555 | **−0.257** | 2.0573 | 2.071 | 0.707 | 0.958 | 13.34 |
| | **D_dir** | 3.019 | 4.432 | 0.759 | 0.575 | −0.030 | **2.0166** | 2.057 | 0.635 | 0.954 | 13.37 |
| | C | 3.099 | 4.436 | 0.759 | 0.575 | **−0.006** | 2.0206 | 2.064 | 0.701 | 0.954 | 12.96 |
| | E\* | 1.609 | 3.024 | 0.897 | 0.802 | +0.058 | 1.1837 | 1.437 | 0.773 | 0.985 | 9.67 |
| `rz_carries` | A | 0.934 | 1.376 | 0.547 | 0.290 | −0.123 | 0.5581 | 1.095 | 0.724 | 0.963 | 3.79 |
| | **C** | 0.877 | 1.355 | 0.561 | 0.312 | +0.010 | **0.5508** | 1.087 | 0.720 | 0.951 | 3.37 |
| | D_sln | 0.920 | 1.436 | 0.539 | 0.229 | +0.150 | 0.6148 | 1.203 | 0.747 | 0.972 | 4.12 |
| | E\* | 0.465 | 1.046 | 0.772 | 0.590 | +0.087 | 0.3522 | 0.747 | 0.850 | 0.987 | 2.28 |

Log score is the **discretised** log score — these are integer counts, so
`P(Y = k)` from the draws is exactly valid. The `1/(2M)` floor binds on
0.08–1.4% of rows (`floor_rate` in the JSON), so it is not driving the number.

**Reconciliation improves CRPS by 0.5–2.0% and removes almost all of the P4B
mean bias**: targets −0.163 → −0.021, carries −0.257 → −0.006, rz_carries
−0.123 → +0.010. The bias P4B reported was substantially a symptom of
unconstrained allocation, not of the marginal model.

**Per season with a team-game block bootstrap** (507–544 clusters): B or C beats
A in **19 of 20** target-seasons — the exception is `snaps` 2025, where A wins
by +0.0011 — and the interval excludes zero in **10 of 20**. The wins are
concentrated in the simplex classes and in 2024. The multiplicative families
`D_sln`/`D_emp` are **significantly worse than A in 29 of 32** target-seasons
in which they ran.

## 12. Joint reconciliation results

| class | system | over-allocation | P(share > 1) | P(Σ > physical max) | team-sum 90% coverage |
|---|---|---|---|---|---|
| `snaps` | A | +0.20% | 0.000 | **0.438** | 0.946 |
| | B | −0.12% | 0.007 | 0.000 | 0.883 |
| | **C** | −0.11% | 0.007 | 0.006 | **0.900** |
| `pass_snaps` | A | +0.07% | 0.000 | **0.456** | 0.938 |
| | **C** | −0.11% | 0.010 | 0.003 | 0.904 |
| `targets` | A | +6.47% | 0.000 | **0.562** | 0.959 |
| | **C** | −0.08% | 0.000 | 0.000 | 0.917 |
| `carries` | A | +4.73% | 0.000 | **0.293** | 0.973 |
| | B | −0.31% | 0.000 | 0.000 | 0.857 |
| | **C** | −0.32% | 0.000 | 0.000 | **0.921** |
| `rz_carries` | A | +11.45% | 0.000 | **0.352** | 0.953 |
| | **C** | −2.61% | 0.000 | 0.000 | 0.938 |

Three things to read here.

1. **Impossible allocations go from 29–56% to essentially zero.** That is the
   real answer to success criterion A.
2. **Stochastic mass (C) is worth having even though it is invisible in
   marginal CRPS.** Deterministic reconciliation (B) collapses team-sum
   coverage — `carries` 0.973 → 0.857 — and drawing the mass restores it
   (0.921). A diagnostic that only looked at player-level CRPS would have
   scored B and C as identical and thrown away a real difference.
3. **A residual infeasibility survives in the occupancy classes.** `P(share>1)`
   is 0.7–1.0% for B/C and up to 3.1% for E. It is structural, not numerical:
   when only four modelled players are on the field and K = 4.9, no allocation
   with every share ≤ 1 exists, because the fifth skill player is outside the
   candidate set. Water-filling binds on 236k–645k of 7.7M row-draws. This is a
   real limit of the modelled universe and it is not fixed here.

## 13. Covariance results

Simulated correlation is **within a team-game, across draws**; the empirical
comparison is the **correlation of forecast errors across team-games**, with a
team-game bootstrap interval. Both contain the shared team-total effect, so
they are comparable.

**The directive's caution is vindicated: mechanical negative dependence is not
realism, and imposing it where reality has none makes the simulation worse.**

| class | pair | empirical [95%] | A | B | C | C2 | best D |
|---|---|---|---|---|---|---|---|
| `carries` | **RB1↔RB2** | **−0.210 [−0.290, −0.117]** | +0.153 ✗sign | −0.307 | **−0.246 ✓** | −0.154 ✓ | −0.336 |
| `carries` | **top1↔remainder** | **−0.302 [−0.377, −0.219]** | +0.191 ✗sign | −0.468 | −0.373 | **−0.225 ✓** | −0.473 |
| `targets` | WR1↔WR2 | −0.001 [−0.091, +0.088] | +0.196 | **+0.043 ✓** | +0.048 ✓ | +0.049 ✓ | −0.047 |
| `targets` | top1↔remainder | +0.013 [−0.070, +0.103] | +0.363 | +0.105 | +0.116 | +0.121 | −0.443 ✗ |
| `snaps` | **RB1↔RB2** | **−0.377 [−0.458, −0.290]** | +0.059 | −0.018 | −0.012 | — | −0.049 |
| `snaps` | WR1↔TE1 | +0.217 [+0.124, +0.308] | **+0.149** | +0.090 | +0.101 | — | +0.044 |
| `pass_snaps` | **RB1↔RB2** | **−0.273 [−0.357, −0.186]** | +0.135 ✗ | +0.064 ✗ | +0.067 ✗ | — | +0.003 ✗ |
| `pass_snaps` | WR1↔TE1 | +0.357 [+0.261, +0.448] | **+0.318** | +0.271 | +0.278 | — | +0.126 |
| `pass_snaps` | top1↔remainder | +0.379 [+0.282, +0.479] | **+0.480** | +0.434 | +0.444 | — | +0.218 |

Read plainly:

- **`carries` is the one class where joint allocation reproduces reality.** A
  gets the sign of RB1↔RB2 *wrong* (+0.153 against an empirical −0.210); C lands
  at −0.246, inside the empirical interval. For top1↔remainder, C2 (−0.225) is
  inside the interval and B (−0.468) overshoots badly.
- **For `targets` the empirical teammate structure is indistinguishable from
  zero** (every interval spans zero). The simplex constraint is weak there
  (modelled mass 0.989) and the shared team total cancels it. B and C, which
  induce only mild dependence, match best; the compositional families induce
  −0.44 where the truth is +0.01 and are simply wrong.
- **Same-position snap competition is not reproduced by anything.** RB1↔RB2 is
  −0.377 empirically on snaps and −0.273 on pass snaps; the best any system
  manages is −0.049 and most are the wrong sign. Two backs genuinely trade
  snaps; an occupancy constraint at K ≈ 4.9 spread over five players is far too
  loose to express it.
- **For cross-position occupancy pairs, reconciliation makes correlation
  worse**, moving +0.318 toward +0.278 when the truth is +0.357.

## 14. Calibration results and 15. randomised PIT

Ordinary PIT is not a calibration diagnostic here — the predictive is mixed
with an atom at zero of mass 0.27–0.31. The **randomised PIT** is, and the
critical value on 9 df at p = 0.001 is **27.877**.

| class | A | B | C | C2 | D_dir | D_emp | D_sln / D_ln |
|---|---|---|---|---|---|---|---|
| `snaps` | 81.3 | 83.9 | 91.2 | — | — | 230.4 | 564.1 (D_ln) |
| `pass_snaps` | 95.1 | 95.6 | 97.1 | — | — | 199.1 | 626.9 (D_ln) |
| `targets` | 99.1 | 75.8 | 76.9 | 74.2 | 606.1 | 67.9 | **66.4** |
| **`carries`** | **21.1 ✓** | **12.6 ✓** | **12.7 ✓** | **11.1 ✓** | 46.3 | 65.2 | 74.2 |
| `rz_carries` | 107.5 | 107.1 | 91.5 | 94.2 | 347.8 | **39.2** | **39.6** |

- **`carries` passes**, and reconciliation nearly halves the statistic
  (21.1 → 11.1). This is the first opportunity distribution in the project that
  is not rejected by a proper calibration test.
- **`targets` and `rz_carries` improve materially** (99.1 → 74.2 under C2,
  107.5 → 91.5 under C) but still reject.
- **The occupancy classes do not improve at all** — 81.3 → 91.2 and 95.1 → 97.1.
  Joint incoherence was not their problem.

### Where the failure actually comes from (§7 of the pre-declaration)

Each variant replaces exactly one component with its oracle. **Only an
*improvement* identifies a culprit** — substituting an oracle while leaving the
other components stochastic produces a mis-specified forecast, so a worse
statistic is uninformative.

| class | base | +team total | **+appearance** | +teammate vector | +all shares | +debias |
|---|---|---|---|---|---|---|
| `snaps` | 91.2 | 117.3 | **26.2 ✓** | 1423.3 | 848.2 | 80.4 |
| `pass_snaps` | 97.1 | 116.2 | **36.4** | 1037.1 | 601.2 | 87.4 |
| `targets` | 76.9 | 110.3 | 183.0 | 2776.8 | 272.7 | 75.9 |
| `carries` | 12.7 | 14.1 | 18.3 | 297.4 | 95.0 | 12.6 |
| `rz_carries` | 91.5 | 135.3 | 148.0 | 617.9 | 72.4 | **53.9 (+own share)** |

**The answer differs by regime and it is worth stating separately:**

- **Occupancy classes: appearance.** Oracle appearance takes `snaps` from 91.2
  to **26.2**, below the critical value, and `pass_snaps` from 97.1 to 36.4.
  Nothing else helps. Their calibration failure is an appearance-probability
  problem, not a joint-coherence problem.
- **`targets`: none of the six.** Every single-component oracle makes it worse
  except de-biasing, which does nothing (76.9 → 75.9). The residual
  miscalibration is in the **shape** of the conditional share distribution and
  is not attributable to a component this ablation can isolate.
- **`rz_carries`: the share distribution.** Only the share substitutions help
  (72.4, 53.9). Consistent with `D_sln`/`D_emp` giving it by far the best
  randomised PIT (39.2) — at the cost of 10% worse CRPS.
- **`carries`: nothing to attribute.** It already passes.

### The appearance model itself is calibrated in aggregate but mis-ranked mid-range

Measured directly, since the ablation pointed there:

| season | n | mean p | observed | bias | Brier |
|---|---|---|---|---|---|
| 2022 | 9,111 | 0.6940 | 0.6887 | +0.0053 | 0.1372 |
| 2023 | 8,919 | 0.7104 | 0.7143 | −0.0039 | 0.1284 |
| 2024 | 8,831 | 0.7097 | 0.7064 | +0.0034 | 0.1257 |
| 2025 | 8,896 | 0.7077 | 0.7027 | +0.0050 | 0.1533 |

Calibration in the large is excellent (±0.005). **The reliability curve is not.**
The 0.26 bin observes 0.31–0.39 and the 0.44 bin observes 0.29–0.42, in every
season and in opposite directions. The predictive is a mixture
`(1−p)·δ₀ + p·F`, so a mis-ranked *p* in the 0.25–0.50 band corrupts the PIT
exactly where that band is dense — and the subgroup table confirms it: the
`p 0.50–0.80` cohort has the worst randomised PIT of any cohort (74–87) while
`p < 0.50` is the best (22–40).

## 16. Threshold calibration

On the pre-declared grids. `rz_carries` uses the grid newly pre-declared in
`predeclaration_p4c.md` §6 (0.5 / 1.5 / 2.5 / 3.5) before any P4C exceedance
number existed; the pre-declaration states plainly that I had seen from P4B
that the quantity has mean ≈ 1.0, and that the grid is the integer boundaries
of a small count and nothing else.

Maximum absolute calibration-in-the-large across the grid, pooled:

| class | A | B | C | C2 | D_dir | D_sln |
|---|---|---|---|---|---|---|
| `snaps` | 0.0215 | 0.0191 | **0.0185** | — | — | 0.0195 |
| `pass_snaps` | 0.0268 | 0.0277 | 0.0274 | — | — | **0.0158** |
| `targets` | 0.0292 | 0.0133 | 0.0129 | **0.0123** | 0.0186 | 0.0544 |
| `carries` | **0.0237** | 0.0210 | 0.0244 | 0.0407 | 0.0167 | 0.0437 |
| `rz_carries` | 0.0361 | 0.0272 | **0.0215** | 0.0299 | 0.0755 | 0.1278 |

Reconciliation halves the **low-threshold** over-forecast that P4B flagged —
`targets` at 2.5 goes +0.0292 → +0.0129, `carries` at 5.5 +0.0237 → +0.0021,
`rz_carries` at 0.5 +0.0361 → +0.0082 — and introduces a mild negative error at
mid thresholds. The compositional families are markedly worse (up to 0.128).

## 17. Boundary and clipping results

Additive share residual + clip produces out-of-range draws at:
`snaps` 9.9%, `pass_snaps` 12.9%, `carries` 16.2%, `targets` 18.8%,
`rz_carries` 27.5% — unchanged from P4B, since A/B/C/C2 share that family.

**The bounded families have a clipping rate of exactly zero by construction.**
Dirichlet, softmax latent Gaussian and logit-normal cannot emit a share outside
the simplex or [0, 1] at all.

**And, as the pre-declaration insisted, that is not by itself a success.**

| class | family | clip rate | CRPS vs A | randomised PIT vs A |
|---|---|---|---|---|
| `targets` | additive + reconcile (C) | 18.8% | **−0.93%** | 99.1 → 76.9 |
| | Dirichlet | **0%** | −0.19% | 99.1 → 606.1 |
| | softmax latent Gaussian | **0%** | +5.27% | 99.1 → **66.4** |
| `carries` | additive + reconcile (C) | 16.2% | −1.79% | 21.1 → 12.7 |
| | Dirichlet | **0%** | **−1.98%** | 21.1 → 46.3 |
| | softmax latent Gaussian | **0%** | +5.82% | 21.1 → 74.2 |
| `rz_carries` | additive + reconcile (C) | 27.5% | −1.32% | 107.5 → 91.5 |
| | softmax latent Gaussian | **0%** | +10.15% | 107.5 → **39.6** |
| `snaps` | logit-normal | **0%** | +2.45% | 81.3 → 564.1 |

**Eliminating clipping did not buy predictive quality.** The one place a bounded
family wins outright is **Dirichlet on `carries`** (best CRPS of any eligible
system, zero clipping) — but its randomised PIT is twice as bad as C's. The
multiplicative families (`D_sln`, `D_emp`) are consistently 5–10% worse on
CRPS: a log-normal multiplicative perturbation on a share is far too dispersive,
and the resulting intervals are too wide (`targets` w90 5.40 → 7.08, 50%
coverage 0.661 → 0.755). `D_ln` on the occupancy classes is worse still.

## 18. Appearance subgroup

CRPS, C versus A, pooled:

| class | p < 0.50 | p 0.50–0.80 | p 0.80–0.95 | p ≥ 0.95 |
|---|---|---|---|---|
| `snaps` | −0.40% | −1.41% | −1.26% | **+2.06%** |
| `pass_snaps` | −0.30% | −1.05% | −1.61% | **+0.73%** |
| `targets` | −0.63% | −1.51% | −1.27% | −0.29% |
| `carries` | −2.68% | −2.31% | −0.55% | **−3.39%** |
| `rz_carries` | −3.78% | −2.37% | −0.59% | −1.07% |

**Reconciliation actively hurts near-certain starters in the occupancy
classes** (+2.06% on snaps at p ≥ 0.95). A player who is certain to play and
takes ~90% of snaps is already at the top of his range; forcing him to share a
fixed K with teammates whose appearance is uncertain drags him around for no
reason. It helps most in the mid-uncertainty bands, where redistribution is
what the mechanism is for.

## 19. Role-change subgroup

| class | stable | role change | role_change × MEDIUM info |
|---|---|---|---|
| `snaps` | **+0.30%** | −1.77% | **−3.14%** |
| `pass_snaps` | −0.25% | −1.58% | **−2.85%** |
| `targets` | −0.94% | −0.92% | −1.43% |
| `carries` | −1.63% | −2.14% | **−3.29%** |
| `rz_carries` | −1.31% | −1.33% | −1.63% |

**This answers the directive's question directly: yes.** Joint allocation helps
most exactly where one player's role expands as another's contracts — the
role-change cohort, and most of all the role-change cohort with MEDIUM
information. For the occupancy classes it is the *only* cohort where it helps
at all: on `snaps` it makes stable rows slightly worse (+0.30%) and
role-changing rows better (−1.77%). **"Next man up" is not hard-coded** — no
rule names a replacement; the relative weights and the mass constraint produce
the redistribution.

Note the randomised PIT runs the other way: `stable` rows are badly
miscalibrated (156.4 on snaps) and `role_change` rows are near the critical
value (27.3). Sharper forecasts expose miscalibration; wider ones hide it.

## 20. Information-quality subgroup

| class | HIGH | MEDIUM | LOW |
|---|---|---|---|
| `snaps` | **+1.57%** | −1.26% | +0.17% |
| `pass_snaps` | **+1.43%** | −1.51% | −0.20% |
| `targets` | +0.01% | −1.17% | −0.95% |
| `carries` | −1.80% | −2.56% | −0.26% |
| `rz_carries` | −0.93% | −1.85% | −0.53% |

**Reconciliation hurts the HIGH-information cohort on the occupancy classes.**
Where availability information is good, the marginal forecast is already close
and the constraint is a net cost. Same mechanism as the p ≥ 0.95 result.
Randomised PIT by contrast is *best* in the HIGH cohort (8.4–30.8, several
below the critical value) — again, the well-forecast cohort is the calibrated
one.

## 21. Oracle decomposition, extended

CRPS improvement over the base joint system (C), pooled:

| class | know the **team total** | know **appearance** | know the **teammate vector** | know **all shares** | know **own share** (unallocated) |
|---|---|---|---|---|---|
| `snaps` | −5.6% | −30.3% | **+9.0%** | −52.2% | −62.3% |
| `pass_snaps` | −12.3% | −25.3% | **+6.3%** | −45.6% | −51.7% |
| `targets` | −5.4% | −14.8% | **+4.6%** | −57.3% | −60.9% |
| `carries` | −11.4% | −21.6% | **−6.0%** | −41.4% | −49.3% |
| `rz_carries` | −17.7% | −8.2% | +0.6% | −36.0% | −36.9% |
| *(all five)* | | | | | −75.8% … −97.6% |

**Knowing the teammate share vector is worth nothing, and in four of five
classes it is worth *less* than nothing.** The single exception is `carries`
(−6.0%), the one class whose simplex constraint is tight enough for one
player's share to genuinely inform another's. This is the direct answer to
success criterion H, and it is a negative answer.

The marginal value of knowing a player's **own** share remains overwhelming
(−37% to −62%), exactly as P4B found. Nothing in P4C changes that ranking.

## 22. Ablations and departures from the pre-declaration

| # | declared | done | why |
|---|---|---|---|
| 1 | C = stochastic mass **with a competing OTHER** | **split** into C (stochastic reserved mass) and C2 (competing OTHER); B fixed to reserved-mass so the rungs differ by one thing each | the declared C bundled two changes against B, so a difference could not be attributed to either. **Neither half was dropped.** |
| 2 | D families "inherent / as C" | all D families use C's reserved-mass reconciliation | so C → D isolates the compositional family and nothing else |
| 3 | de-bias ablation | **multiplicative rescale, not an additive shift** | the first version added a constant and clipped at zero, which destroys the 27–31% atom at zero; the randomised PIT then measured that destruction (χ² in the thousands) rather than the bias. Both versions are in the run logs |
| 4 | teammate-oracle adversarial probe | **two versions**, naive and well-posed | the naive version (teammates' realised shares as relative weights) does **not** leak — it makes CRPS 3.6% worse, because a realised share and an EWMA are not on the same scale. The well-posed version (teammates plus the mass give the focal share by subtraction) improves CRPS by 60.8%. Reported rather than dropped |
| 5 | mass pools "prior seasons" | prior seasons **excluding 2020** | pre-declared in §1 from a training-season measurement; 2020 is the panel's first season and its no-prior-game rate is a construction artifact |

## 23. Adversarial tests

**12 probes, 0 failing** (`nfl/research/p4c/p4c_adversarial.json`). Each seeds
the violation, shows the seeded version is materially better — so the channel
is live and a leak would be detectable rather than silent — and then asserts
the shipped pipeline does not contain it. Run on `targets`/2024, n = 7,743.

| # | seeded leak | measured effect of the leak | guard asserted |
|---|---|---|---|
| 1 | same-game realised player share | corr(forecast, realised share) 0.6703 → 0.7560; CRPS **−12.38%** | `prepare_class` assigns the history **before** appending |
| 2 | realised teammate share | naive: **+3.63% (does not leak)**; well-posed by subtraction: **−60.77%** | weight generators never reference a realised share |
| 3 | realised appearance | CRPS **−12.27%** | eligible path draws Bernoulli(p_app) |
| 4 | realised team total | CRPS **−5.74%** | eligible systems read the P4B predictive draw |
| 5 | future role transition (next game's share) | CRPS **−1.68%** | no feature reads an `ord` above the row's own |
| 6 | evaluation-season composition fitting | mass-pool seasons `[2021,2022,2023]` → `[…,2024]`; α₀ +0.55% | shipped fit's max training season is strictly below 2024 |
| 7 | oracle allocation entering selection | selection handed an unbeatable E returns `'C'` | `ELIGIBLE_SYSTEMS` excludes E; ever chosen: A, B, C, C2, D_dir |
| 8 | renormalising to **this game's** excluded-player mass | CRPS **−0.31%** | mass pool seasons all strictly before 2024 |
| 9 | player universe from postgame participation | restricting to appearers moves CRPS +24.35% | 2,158 non-appearing player-games (27.9%) retained; 0 rows without a prior game |
| 10 | roster status / market / weather leak | — | 7 modules scanned for **accesses** of 14 names; 0 hits; the appearance label never appears inside `gen_weights` |

### 24. Guard-deletion proofs

| # | proof |
|---|---|
| **11** | Adding `'E'` to `ELIGIBLE_SYSTEMS` makes selection return `'E'`. **Probe 7 is therefore load-bearing — it fails the moment the guard is deleted.** |
| **12** | Moving the history append above the assignment in `prepare_class` raises corr(point forecast, realised share) from **0.6703 to 0.7545** on 7,743 rows. **The two-line ordering is the entire chronology guarantee for the share history**, and a chronology probe that did not test the bypass would have passed on a pipeline containing it. |

---

## 25. Negative findings, stated plainly

1. **P4B's 27–45% over-allocation figure is withdrawn** (§0). It compared
   incomparable quantities. The like-for-like mean over-allocation is −1.1% to
   +17.8%.
2. **No compositional family beats additive-plus-reconciliation on CRPS.**
   Dirichlet on `carries` is the sole exception and it is worse on calibration.
   Multiplicative log-normal share noise is 5–10% worse everywhere.
3. **Eliminating boundary clipping bought nothing.** Bounded families clip 0%
   of draws and are worse on CRPS, worse on threshold calibration, and better
   on randomised PIT only for `rz_carries` (107.5 → 39.6) and `targets`
   (99.1 → 66.4).
4. **Joint incoherence was not the main cause of the P4B calibration failure.**
   Reconciliation fixed calibration for `carries` and helped `targets` and
   `rz_carries`, but did nothing for the occupancy classes, where the ablation
   points at **appearance probability**.
5. **Knowing the teammate share vector is worth nothing** in four of five
   classes, and negative in three. Appearance-conditioned redistribution is
   **not** materially more predictable jointly than P1–P3 suggested
   independently — with the single exception of RB carries.
6. **The mechanism reproduces teammate correlation for `carries` and gets it
   wrong everywhere else.** Same-position snap competition is −0.38
   empirically; the best system manages −0.05 and most have the wrong sign. I
   am not describing the sign agreement on `carries` as general realism.
7. **Reconciliation hurts the cohorts that were already well forecast** —
   near-certain starters and the HIGH-information cohort on the occupancy
   classes, by +0.7% to +2.1%.
8. **A structural infeasibility remains**: in the occupancy classes 0.7–1.0% of
   row-draws cannot satisfy `share ≤ 1` because the modelled universe sometimes
   cannot hold K ≈ 4.9. Water-filling redistributes but cannot create a sixth
   player.
9. **Four of five classes still fail the randomised PIT.** Only `carries`
   passes.

## 26. Unresolved data debts

Carried forward from earlier tracks, none new, none resolved here:

- **2025 injury vintage has no `date_modified`**, so 2025 carries no injury
  feature at all. The Wayback path is documented for the networked agent;
  nothing in this repository can close it.
- **True routes do not exist in the data.** `rpr` remains a participation
  proxy and was not manufactured.
- **2025 depth charts changed to a daily schema** and are not adapted; the
  depth feature covers 2020–2024 only.
- **The panel begins in 2020**, so evaluation season 2022 has only two prior
  seasons and its mass pool has one (2021, 544 team-games).
- **The modelled universe cannot hold the occupancy mass** in ~1% of
  row-draws (§12); closing it needs a fifth-skill-player component that the
  candidate-set definition does not currently supply.
- **No sealed holdout exists.** 2022–2025 are all used as training seasons for
  later evaluation years. Walk-forward controls leakage; it does not create an
  untouched confirmatory sample.

## 27. Task-report path

`TASK_REPORT_2026-09-07_P4C.md` (repository root, `94924676jp-a11y/nfl`, `main`).

## 28. Recommendation for the next research question only

**Fix the appearance probability's mid-range ranking, and measure whether that
alone closes the calibration gap.**

The evidence points there and nowhere else. Oracle appearance takes `snaps`
from a randomised-PIT χ² of 91.2 to **26.2** — below the critical value — and
`pass_snaps` from 97.1 to 36.4. The model is calibrated in the large (bias
±0.005) but mis-ranks the 0.25–0.50 band in every season and in both
directions, and that band is precisely where the mixture
`(1−p)·δ₀ + p·F` is most sensitive. The `p 0.50–0.80` cohort has the worst
randomised PIT of any cohort measured.

That is one question, it is answerable inside this repository with data already
present, it needs no new provider, and it is upstream of everything else:
every opportunity distribution in the project is a mixture over this
probability, so nothing downstream can be calibrated while it is not.

**Concretely, and nothing beyond it:** does a recalibrated or better-ranked
appearance probability — isotonic or spline recalibration on prior seasons, or
better features for the mid-range band — improve the randomised PIT of the
existing opportunity distributions, at the existing walk-forward discipline,
without harming CRPS?

I am **not** recommending P5, an efficiency model, a joint simulator, or any
further allocation family. The allocation question is answered: reconcile,
use the additive family, draw the mass, and expect it to buy joint coherence
and about 1% of CRPS rather than a calibrated forecast.

---

## Constraints honoured

P5 not started. No receiving, rushing or passing yards. No touchdowns. No
fantasy points. No J0 simulator. **No sportsbook market ingested and no
market-derived feature exists** (probe 10). No DFS, no lineup optimisation,
**no wager recommended and none discussable.** NFL-1 not authorised. G0A
untouched (11 PASS / 1 FAIL). T−90 untouched; pre-flight 10 checks, 0 failing.
**No 2026 outcome consumed** — panel seasons are 2020–2025 and nothing reaches
beyond. `weekly_rosters.status` not read. Observed-weather fields not read.
`xpass`/`pass_oe` remain quarantined. No frozen 2026 artifact modified. No new
provider imported. Repository test count unchanged and re-verified: **1,230
assertions across 19 suites, 0 failing.**

**Stopping after the research return, as instructed.**

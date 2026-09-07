# P4C pre-declaration — constrained joint player opportunity allocation

Written 2026-09-07 **after** the accounting measurement of §1 (which is a
definitional fact about the denominators, measured on training seasons only)
and **before** any allocation mechanism was fitted, any CRPS, coverage,
covariance or threshold number existed. Departures are labelled where they
occur; the original text stays.

HEAD at task start: `c9e3a70`.

## 1. The accounting identities are measured, not assumed

Measured on **2020–2021 only** so the design is not conditioned on the
evaluation seasons; re-measured on 2022–2025 afterwards as verification
(`accounting.py`, `accounting.json`). Both are reported.

The directive's warning is confirmed: **the classes do not share one
constraint.**

### Class 1 — mutually exclusive events (a true simplex)

`targets`, `carries`, `rz_carries`. Every target and every carry belongs to
exactly one player, so the full-panel share sum is **exactly 1.0000, sd
0.0000** in every team-game of every season.

```
targets      Sigma_full = 1.0000   Sigma_modelled = 0.9891   OTHER = 1.09%
carries      Sigma_full = 1.0000   Sigma_modelled = 0.7991   OTHER = 20.09%
rz_carries   Sigma_full = 1.0000   Sigma_modelled = 0.7857   OTHER = 21.43%
```

(2022–2025 figures; modelled universe is WR/TE/RB for targets and **RB only**
for carries.) The OTHER mass for carries is not noise — it is
**QB rushing, 15.0% of the pie**, plus WR 3.2%. It is structural and must be an
explicit component, not an error term. For `rz_carries` the OTHER mass is also
**zero in 41.8% of team-games**, so it is zero-inflated and cannot be modelled
by a mean.

### Class 2 — simultaneous occupancy (NOT a simplex)

`snaps`, `pass_snaps`. Eleven players are on the field for every snap, so the
full-panel share sum is **10.96 (sd 0.09)** and **11.0000 (sd 0.0029)**
respectively — the small shortfall on `snaps` is snap-count recording, not
football. Composition of the 11: OL 5.04, QB 1.01, **WR/TE/RB ≈ 4.89**.

```
snaps        Sigma_full = 10.9572  Sigma_modelled = 4.8901 (sd 0.2037)
pass_snaps   Sigma_full = 10.9999  Sigma_modelled = 4.9323 (sd 0.1920)
```

**The constraint for these classes is "sum to K ≈ 4.9", where K is itself a
random quantity**, not "sum to 1". Forcing a simplex here would be wrong by a
factor of five. Each individual share is separately bounded in [0, 1].

### A panel-edge artifact that must not be fitted

The residual mass has two parts: (i) **structural** — positions outside the
modelled set; (ii) **panel-edge** — modelled-position players with no prior
game in the panel. Part (ii) is 2.0–4.2% in 2020 and **0.4–0.9% in 2022–2025**,
because 2020 is the panel's first season and everyone starts without history.
It is a construction artifact, not a football quantity.

**Decision, taken now:** the OTHER / K mass distributions are fitted on prior
seasons **excluding 2020**. For evaluation season 2022 that leaves 2021 alone
(544 team-games), which is ample for a one-dimensional mass distribution.
Compositional parameters (concentration, dispersion) use all prior seasons,
because players without prior history are outside the modelled universe anyway
and cannot enter those pools.

## 2. Player universe, fixed and pregame

Unchanged from P1–P4B: for each team-week, every player who appeared for that
team in any of the **previous 4 team-games**, plus the requirement of at least
one prior game (`f_n_prior >= 1`). **Knowable before kickoff.**
`weekly_rosters.status` is not read. The universe is never defined from
postgame participation, and an adversarial probe asserts it.

## 3. The systems, as an ablation ladder

Every system shares an identical marginal point forecast (`EWMA` half-life 3 on
prior **appeared** shares), an identical appearance model (P3 Stage-A), and an
identical team-total draw (P4B system B, the accepted unconditional volume
distribution). **A→B isolates reconciliation; B→C isolates the mass treatment;
C→D isolates the compositional family.**

| id | perturbation family | reconciliation |
|---|---|---|
| **A** | additive share residual + clip to [0,1] (the P4B control) | **none** |
| **B** | same as A | proportional to the **mean** available mass |
| **C** | same as A | **stochastic** available mass, with an explicit OTHER component that competes |
| **D_dir** | Dirichlet on the extended simplex (simplex classes) | inherent |
| **D_sln** | softmax-transformed latent Gaussian (simplex classes) | inherent |
| **D_ln** | logit-normal marginals (occupancy classes) | stochastic K mass |
| **D_emp** | empirical compositional residual resampling (log-ratio) | as C |
| **E** | **realised relative allocation** | as C — **DIAGNOSTIC ONLY, NEVER ELIGIBLE** |

`ELIGIBLE_SYSTEMS` excludes E by construction, selection is by CRPS, and both
facts carry a guard-deletion proof.

**Do not assume one family is correct.** Where several D families are valid for
a class, the family is chosen by CRPS on an **inner validation season**
(`ev − 1`), with everything fitted on seasons strictly before that — the P4B
nesting, unchanged. **No evaluation-season tuning.**

## 4. Appearance and redistribution

Preserved from P2/P3: `A_i ~ Bernoulli(p_i)`, zero is a point mass. **Absence
is applied before allocation**, so an absent player's mass is redistributed
through the mechanism rather than independently materialising. **"Next man up"
is not hard-coded** — who absorbs the vacated mass is whatever the relative
weights say. Realised appearance is never used in an eligible system.

An expected asymmetry, stated in advance so it is not discovered as a
surprise: for the occupancy classes K stays near 4.9 whoever is absent (the
team still fields five skill players), so vacated mass should be absorbed
almost entirely inside the modelled set; for the simplex classes a missing RB's
carries can go to the quarterback, so the OTHER component must be able to
absorb. That is precisely the B-versus-C contrast.

## 5. Chronology

Strict walk-forward. For evaluation season Y: marginal EWMA histories use prior
**games**; appearance models, share-residual pools, mass distributions,
concentration and dispersion parameters use **seasons strictly before Y**
(mass pools additionally exclude 2020, §1). No same-game realised share, no
realised teammate share, no future role information, no postgame roster status.
All P1–P4B leakage rules carry over unchanged.

## 6. Evaluation

**Marginal, per system, per class, per season:** MAE, RMSE, r, R², bias, CRPS,
**discretised log score** (these are counts, so `P(Y = k)` from the draws is
exactly valid; a floor of `1/(2M)` prevents `-inf` and the floor rate is
reported), coverage at 50/80/90/95, mean interval width, **randomised PIT**
(the predictive is mixed with an atom at zero, so ordinary PIT is not a
calibration diagnostic — established in P4B §10), and exceedance calibration.

**Threshold grids.** Carried unchanged from P4B: `carries` 5.5/9.5/12.5/15.5/19.5;
`targets` 2.5/4.5/6.5/8.5/10.5; `snaps` and `pass_snaps`
10.5/20.5/30.5/40.5/50.5. **`rz_carries` is newly pre-declared here, before any
P4C result exists: 0.5 / 1.5 / 2.5 / 3.5.** Stated plainly: I have seen from
P4B that this quantity has mean ≈ 1.0 and sd ≈ 1.6, so the grid is the integer
boundaries of a small count and nothing else; it is not tuned to any exceedance
result, because none exists yet.

**Joint, per system, per class, per season:** distribution of the simulated
share sum; distribution of the simulated absolute sum; reconciliation error
against the simulated team total; teammate covariance and correlation (sign,
magnitude, interval) for the named pairs; concentration (HHI, top-1 share);
top-player share distribution; remaining/unmodelled mass; **probability of
impossible allocations** (share > 1, share < 0, sum exceeding the class
maximum); boundary-clipping frequency.

**Named teammate pairs**, fixed now: targets — WR1↔WR2, WR1↔TE1, WR1↔RB1,
top-target↔remainder; carries — RB1↔RB2, RB1↔OTHER(includes QB rushing),
top-carry↔remainder; occupancy — same-position 1↔2 and starter↔replacement.
Ranking is by the **pregame** marginal forecast, never by the outcome.

**Do not claim correlation realism merely because an accounting identity
mechanically induces negative dependence.** Any reconciliation forces a
negative correlation. The test is therefore against the **empirical
out-of-sample** teammate correlation, with the magnitude and sign compared, not
merely the sign.

## 7. Calibration attribution, by controlled ablation

P4B failed randomised PIT in 18 of 20 target-seasons. P4C attributes that
failure by turning one thing at a time to its oracle value and re-measuring the
randomised PIT: (a) joint coherence — the A→D ladder; (b) marginal share
distribution shape — oracle share, projected everything else; (c) appearance —
oracle appearance; (d) systematic mean bias — recentre the predictive on the
realised mean; (e) boundary treatment — bounded families versus additive+clip;
(f) role transition — the role-change subgroup split.

## 8. Boundary problem

P4B clipping rates: snaps 9.9%, pass_snaps 12.9%, carries 16.2%, targets 18.7%,
rz_carries 27.5%. The bounded families (Dirichlet, logit-normal, softmax latent
Gaussian) cannot produce an out-of-range share at all, so their clipping rate
is zero by construction. **A clipping rate of zero is not by itself a success.**
It counts only if CRPS, coverage and the randomised PIT are preserved or
improved, and the return says so explicitly if they are not.

## 9. Oracle decomposition, extended

P4B's arms plus two new ones. Marginal value of knowing: (1) the team total;
(2) this player's own share; (3) the **teammate share vector**; (4) appearance;
(5) the **joint allocation structure** (relative weights). Diagnostic only,
never eligible.

## 10. Monte Carlo

1,000 draws, seed **20260907**. Team-volume draws shared across a team-game, as
in P4B. Allocation is computed per team-game per draw, so teammate dependence
is induced by the mechanism and not imposed afterwards.

## 11. What would count as a negative result

Stated in advance, in the words the return will use if they apply:

- If joint allocation removes the over-allocation but **worsens** marginal CRPS,
  the return says the constraint costs more marginal information than it buys.
- If it removes the over-allocation and leaves the randomised PIT still
  rejecting, the return says joint incoherence was **not** the main cause of the
  P4B calibration failure, and names what the ablation says the cause is.
- If simulated teammate correlation matches in sign but not magnitude, the
  return says the mechanism induces dependence of the wrong size, and does not
  describe the sign agreement as realism.
- If no class is mature enough to feed P5, the return says so.

# P4F pre-declaration — mean-preserving rectification of additive carry-share draws

Written 2026-09-07, **before any P4F number existed**. HEAD at writing:
`7f6c2f2` (Rule 006 registered; suite 1,362 assertions, 0 failed).

Owner directive of 2026-09-07 authorises mean-preserving rectification as
**development research only**. Departures will be labelled where they occur.

## 0. Status, fixed before anything else

2022–2025 have already exposed the exploratory MPR result (P4E §7). Therefore
**no result on 2022–2025 can promote P4F into the accepted architecture.** The
purpose here is mechanism verification and, if warranted, freezing a candidate
for prospective evaluation.

Every predictive number in the return will be labelled *previously exposed
development sample — not confirmatory and not promotion-eligible*. A block
bootstrap will be computed because it describes sampling variability within
this sample; **it will not be described as independent confirmation**, and no
p-value will be presented as though this were a fresh test.

The only two admissible conclusions are **REJECT** and **RETAIN AS PROSPECTIVE
CANDIDATE**. P4C system C remains the accepted architecture either way.

## 1. The scientific question

P4C builds the pre-reconciliation share weight as `W = clip(C + eps, 0, 1)`.
Rectification at the lower boundary is asymmetric, so `E[W] > C` whenever `C` is
small relative to the spread of `eps`. P4E measured the inflation at **+62% to
+123%** for backs with under 10 prior carries and **+0.1% to +1.0%** at 100+.

Can a deterministic mean-preserving correction remove that estimator-induced
bias while retaining or improving calibration, allocation coherence and joint
competition behaviour?

## 2. The mechanistic requirement

For each player-game *i*, solve a deterministic shift `delta_i` such that

```
mean_m clip(C_i + eps_im - delta_i, 0, 1) = C_i
```

**Solver, fixed now.** `g(delta) = mean_m clip(C_i + eps_im - delta, 0, 1)` is
continuous and non-increasing in `delta`. Bracket:

```
delta_lo = C_i + min_m eps_im - 1     ->  g = 1
delta_hi = C_i + max_m eps_im         ->  g = 0
```

so a root exists by the intermediate value theorem for every `C_i` in `[0, 1]`.
Bisection, **80 iterations**, in float64. **Tolerance: `|g(delta_i) - C_i| <=
1e-9` absolute.** A row that does not reach it is reported, never silently
accepted.

**What may enter the solution:** `C`, the already-generated residual draws, and
the fixed solver mechanics. Nothing else. No outcome, no fitted constant, no
evaluation-season tuning, no player-specific outcome-derived term.

**Degenerate solution sets are flagged, not hidden.** At `C = 0` and `C = 1` the
root is not unique (any `delta >= C + max eps` gives 0; any `delta <= C + min
eps - 1` gives 1). The bisection endpoint is reported together with a
`DEGENERATE_SOLUTION_SET` flag and a count.

**Infeasible cases are detected, not altered.** `C` outside `[0, 1]`, or any
non-finite `eps`, is refused with a named state. No row is quietly clipped into
feasibility.

**The correction targets the SAMPLE mean of the drawn residuals, not the
population mean.** This is stated in advance because it is the confound in §3.

## 3. Systems

The four the directive names, plus one control that the directive's own
mechanism question requires:

| id | centre | draw treatment |
|---|---|---|
| **A `P4C`** | P4C EWMA | P4C clipping — **untouched control** |
| **B `MPR_ONLY`** | P4C EWMA | mean-preserving rectification |
| **C `ABC_ONLY`** | P4E `E_ABC` ridge | P4C clipping |
| **D `ABC_MPR`** | P4E `E_ABC` ridge | mean-preserving rectification |
| **E `MC_ONLY`** | P4C EWMA | **confound control**: residuals recentred to zero sample mean, then P4C clipping |

**Why E exists and is not an extra feature block.** MPR does two things at
once: it removes the rectification bias, and it removes the Monte-Carlo error in
the sample mean of the draws. The second is a variance-reduction artifact that
would improve CRPS on its own, with no bias fix at all. `MC_ONLY` removes the
sampling error while leaving the rectification bias in place, so **B minus E is
the bias fix and E minus A is the artifact.** Without it the mechanism claim is
not identified. No features are added and no hybrid is tuned.

No additional feature blocks. No hybrid constructed after seeing these results.

## 4. First-principle tests, before any predictive scoring

On synthetic data with analytically or numerically known answers:

1. P4C clipping is mean-biased near zero;
2. the bias is monotone in proximity to the boundary under controlled residual
   distributions;
3. the correction restores the requested mean within `1e-9`;
4. the correction does not change `C`;
5. the correction reads no outcome (argument-level proof);
6. the correction is deterministic given identical inputs (bit-identical on
   repeat);
7. `C = 0` handled, degeneracy flagged;
8. `C = 1` handled, degeneracy flagged;
9. very small residual variance handled;
10. very large residual variance handled;
11. infeasible and pathological cases explicitly detected;
12. the raw residual identity remains auditable — `eps` recoverable from the
    corrected draws and `delta`.

## 5. Baseline reproduction

The P4C control must reproduce `p4c_results.json`'s carry CRPS **exactly**,
loaded through **Rule 006** (`assert_gate`, tolerance `0.0`, artifact hash
printed). A transcribed literal is not admissible as the comparison value. If it
does not reproduce, P4F stops.

## 6. Metrics

**Carry-count:** CRPS, MAE, RMSE, r, R², bias, randomised PIT, threshold
calibration on the P4C-CARRY grid (0.5 / 4.5 / 9.5 / 14.5 / 19.5), interval
coverage at 50/80/90/95.

**Share diagnostics, per system and per history band:** centre `C`,
pre-rectification `E[W]`, post-rectification `E[W]`, centre-preservation error,
clipping probability, and the distribution of `delta`.

**Joint:** RB1↔RB2, RB1↔RB3, RB2↔RB3, top1↔remainder, team allocation entropy,
concentration, impossible allocations, residual-mass accounting.

Pooled **and** every evaluation season separately. No pooling that hides a
failed season.

## 7. Low-history analysis

Bands **<10 / 10–24 / 25–49 / 50–99 / 100+**, as pre-declared in P4E §10. For
each: `C`, original `E[W]`, corrected `E[W]`, mean `delta`, carry prediction
bias, CRPS.

The question to answer explicitly: does the correction remove the **mechanical**
centre inflation without suppressing genuine emerging backs? P4E measured that
the low-history cohort is not one population — fringe non-appearers are
over-predicted by +1.10 and true emerging backs under-predicted by −5.20. A
correction that improves the pooled band by flattening both is a worse answer
than the number suggests, and will be reported as such.

## 8. Appearance interaction

Bands **<0.25 / 0.25–0.50 / 0.50–0.80 / 0.80–0.95 / ≥0.95**, crossed with the
history bands. **The appearance model is not modified.** The question: does MPR
fix conditional-share bias while appearance remains the dominant term for fringe
cases? Reported as a two-way table of bias and CRPS.

## 9. Rule 5 repair — a matched-estimand competition criterion

P4E's rule 5 compared a **within-team-game across-draws** simulated correlation
against an **across-team-game** realised correlation. Those are different
estimands and the comparison was not admissible. It is withdrawn.

**Replacement, fixed now.** For each draw index *m*, take the vector over team-
games of the ranked backs' shares and compute the **across-team-game** Pearson
correlation `r_m`. That is the same estimand as the realised across-team-game
correlation `r*`, computed on the same population. This gives a posterior
predictive distribution for the quantity actually observed.

Reported per pair and per season:

- the model's median `r_m` and its central 95% interval;
- whether `r*` falls inside that interval (a posterior predictive check);
- the standardised discrepancy `z = (r* - median r_m) / sd(r_m)`.

**Criterion, fixed before scoring:** a candidate does not worsen competition
realism when, across the four evaluation seasons,

1. `|z|` is no larger than the control's in **at least 3 of 4** seasons, and
2. the number of seasons in which `r*` falls inside the 95% predictive interval
   is **at least** the control's.

Ranking is by the **pregame** forecast, never the outcome. If the matched
construction turns out not to be honestly computable for a pair (fewer than 30
team-games with that rank present), the pair is reported `NOT_APPLICABLE` with
the count, and no substitute comparison is invented.

## 10. Oracle accounting

The P4C-CARRY 2³ factorial (team volume T, share S, appearance A) is
**recomputed with the candidate's allocation in the baseline corner**, giving a
new allocation Shapley component and a new residual allocation ceiling. This
closes P4E debt #4, which reported only a ratio against the old component.

Both are reported: raw CRPS gain against P4C, and the newly recomputed residual
allocation oracle ceiling. **This recomputation is not used to invent a new
promotion threshold**, and the 5% rule is not relaxed, restated or applied here
— there is no promotion decision in P4F.

## 11. Adversarial

Seeded probes, materiality threshold **0.010 CRPS**, fixed now and not lowered
after observation:

current-game realised carry share · current-game realised carries · current-game
realised snaps · future teammate availability · postgame roster state ·
current-game RB rank · evaluation-season fitted correction · **outcome-dependent
delta** · **future residual pool** · forbidden-identifier scan.

At least **two load-bearing guard-deletion proofs** — a guard whose deletion
demonstrably changes the result. P4E left GD1 (the `season < ev` fit guard) and
GD4 (the out-of-fold residual pool guard) UNRESOLVED because deleting them did
not move CRPS materially. Each is either **strengthened** here — retested with a
probe that can fire — or **remains explicitly UNRESOLVED**. Neither is converted
to a pass by lowering a threshold.

## 12. Candidate freeze

If `MPR_ONLY` or `ABC_MPR` survives §4 and §11, a frozen specification is
written pinning: algorithm; feature set; solver and its bracket, iteration count
and tolerance; residual construction; seeds and draw protocol; artifact hashes;
and eligibility rules.

It will state, in those words: **Candidate frozen for prospective evaluation;
NOT promoted.** The accepted P4C production and research architecture is not
modified.

## 13. What would count as a negative result

- If the correction does not restore the requested mean within tolerance on real
  data, the mechanism is reported as not achieved and the candidate is rejected.
- If `B − E` is negligible while `E − A` carries the gain, the return says the
  apparent improvement was Monte-Carlo variance reduction and not a bias fix.
- If the correction fixes the low-history band average by flattening genuine
  emerging backs, the return says so and does not present the band average as
  the result.
- If joint competition behaviour worsens on the matched criterion, the candidate
  is rejected under §9 regardless of marginal CRPS.

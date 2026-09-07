# P4D — Appearance probability calibration and mid-range ranking

**Status:** complete. Research return only. Nothing was authorised, enabled or
promoted to production — **including the best candidate**, which failed the
pre-declared selection rule (§21, §31).

---

## The answer in one paragraph

**The mid-range defect is ranking, not levels — and inside 0.25–0.50 the
incumbent is not ranking at all.** Its within-band AUC there is 0.510–0.564,
and its log loss in that band (0.6494) is *worse than the entropy of a constant
forecast at the band's own base rate* (0.6466). **Recalibration cannot fix it
and made things worse** in three seasons of four; a monotone map cannot change
a ranking, and this one over-expanded the probabilities. **Added features fix a
large part of it**: within-band AUC 0.536 → 0.686 in 0.25–0.50, log loss −4.5%
to −7.6% depending on season, AUC +0.019 to +0.022, and downstream CRPS −3.0%
on snaps. **But it does not close the
calibration gap**: downstream randomised PIT for `snaps` and `pass_snaps` gets
*worse* pooled (91.2 → 105.2, 97.1 → 106.7) and improves in only 2 of 4
seasons each. P4C's oracle-appearance result identified **a bound, not an
achievable gain**. Under the rule I fixed in advance, **the incumbent is
retained.**

---

## 1. HEAD at task start

`0a7b6cb` — "P4C return". Working tree clean, `main` level with `origin/main`.

## 2. Commits

| commit | content |
|---|---|
| `cf7acac` | P4D pre-declaration, and a defect found in the incumbent before building |
| `ca83b62` | P4D research: appearance probability calibration and mid-range ranking |
| *(this report)* | `TASK_REPORT_2026-09-07_P4D.md` |

## 3. Files

All under `nfl/research/p4d/`:

| file | role |
|---|---|
| `predeclaration_p4d.md` | written before any candidate was fitted |
| `conv_check.py` | the convergence diagnostic of §8 |
| `p4d_lib.py` | converged fitting, new feature blocks, three calibrators, metrics |
| `run_p4d_app.py` | Experiments 1 and 2, nested out-of-fold calibration |
| `run_p4d_decomp.py` | the fixed-band test, subgroups, block ablations |
| `run_p4d_downstream.py` | each system through the **frozen** P4C machinery |
| `run_p4d_adversarial.py` | 10 seeded leaks + 2 guard-deletion proofs |
| `p4d_appearance.json`, `p4d_decomp.json`, `p4d_downstream.json`, `p4d_adversarial.json` | results |
| four run logs | |

## 4. Pre-declaration

`nfl/research/p4d/predeclaration_p4d.md`, committed in `cf7acac` before
`p4d_lib.py` existed. It fixes the estimand, the systems, the feature blocks,
the nested chronology, the bands, the metric set, the calibration-versus-ranking
test, the downstream freeze, **the selection rule**, and the negative-result
wording. Two pre-fitting diagnostics of the *control* are recorded in it (§8,
§9 below). Departures: none.

## 5. Test counts

Repository suites **unchanged and re-enumerated from the filesystem**:
**1,230 assertions across 19 suites, 0 failing** (1,137 across 16 NFL suites +
93 across 3 platform-governance suites). P4D adds **12 adversarial probes, 0
failing**. Governance unchanged: **G0A 11 PASS / 1 FAIL**, NFL-1 not
authorised, T−90 untouched, no 2026 outcome consumed.

## 6. Appearance estimand — unchanged

`A_i = 1` iff the player appears in the team-game (`did_not_appear == 0`),
exactly as P2/P3/P4B/P4C. Pregame universe unchanged: appeared for this team in
any of the previous 4 team-games, and `f_n_prior >= 1`. **No integrity defect
was found in the definition, so it was not changed.** The 2024 evaluation set
retains 2,593 of 8,831 (29.4%) player-games in which the player did not appear
— a postgame universe would contain none (probe 10).

## 7. Chronology rules

For evaluation season *Y*: the prediction model trains on seasons `< Y`; the
calibrator is fitted on pooled **out-of-fold** pairs `(p̂_s, y_s)` for
`2021 ≤ s < Y`, each produced by a model trained on seasons `< s`; the
calibration family is chosen on the **inner season `Y−1`** with everything
fitted before it. **No calibrator, family or threshold ever sees the evaluation
season**, and none is chosen using randomised PIT. Probe 7 measures what
breaking this would buy (−1.94% log loss); probe 11 is the guard-deletion proof.

## 8. A defect in the incumbent, found before anything was built

`stage_a.fit_logistic` is plain gradient descent, fixed step 0.5, **300
iterations**, no convergence check. On the 2024 training set (34,603 rows, 49
features):

```
incumbent (GD, 300 iters) : objective 0.403347   ||grad||_inf 2.03e-03   ||w|| 2.0961
converged (Newton, 11 it) : objective 0.402229   ||grad||_inf 1.30e-16   ||w|| 2.7508
```

**It stops at 76.2% of the converged coefficient norm** and needs ~30,000 GD
iterations to reach the Newton solution — an undeclared extra ~24% of shrinkage
on top of the L2 penalty, and precisely the shape that compresses probabilities
while leaving the intercept right.

**The control was not changed.** `A` remains the incumbent as P2/P3/P4B/P4C ran
it; the converged fit is candidate `A1`. Its effect is real but small (§13).

## 9. A second finding: two pregame fields exist and are never used

`featurise_p3` omits four `f_*` fields the panel builds.

| field | decision |
|---|---|
| `f_prev_report` (prior week's injury designation) | **eligible** — same chronology status as the incumbent injury feature, a prior-week row stamped more than a week before this kickoff |
| `f_depth` (depth-chart rank; 78–87% for 2020–2024, **0% for 2025**) | **NOT eligible** — the depth-chart artifact carries **no timestamp of any kind**, so it is neither prospectively captured nor retrospectively chronology-testable. Diagnostic arm only (§12) |

## 10. Incumbent Stage-A results (the control)

| season | n | Brier | log loss | ROC AUC | PR AUC | cal intercept | **cal slope** | ECE | MCE | bias |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 9,111 | 0.13724 | 0.41983 | 0.8589 | 0.9288 | −0.0472 | **1.0143** | 0.0244 | 0.1360 | +0.0053 |
| 2023 | 8,919 | 0.12839 | 0.39656 | 0.8688 | 0.9410 | +0.0010 | **1.0457** | 0.0242 | 0.1093 | −0.0039 |
| 2024 | 8,831 | 0.12574 | 0.38881 | 0.8783 | 0.9441 | −0.0807 | **1.0872** | 0.0296 | 0.0707 | +0.0034 |
| 2025 | 8,896 | 0.15331 | 0.46816 | 0.8175 | 0.9073 | +0.0299 | **0.8916** | 0.0223 | 0.1151 | +0.0050 |

**Calibration slope > 1 in 2022–2024 means the probabilities are
under-dispersed — compressed toward the base rate.** That is the fingerprint of
§8's un-converged optimiser, arriving independently. 2025 is the exception
(0.8916, over-dispersed) and is also the season with no injury feature at all.

**Calibration-in-the-large is excellent (±0.005) and is not evidence of
calibration**, as ECE 0.022–0.030 and MCE 0.071–0.136 immediately show.

## 11. Probability-band reliability — the incumbent

Bands pre-declared in the directive and in §8 of the pre-declaration.

| band | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| | n / gap / AUC-within | | | |
| **0.00–0.25** | 676 / **−0.053** / 0.859 | 619 / −0.053 / 0.807 | 650 / −0.046 / 0.815 | 427 / **−0.098** / 0.651 |
| **0.25–0.50** | 1,775 / **+0.046** / **0.510** | 1,630 / +0.027 / **0.526** | 1,601 / **+0.048** / **0.564** | 1,961 / −0.007 / **0.545** |
| **0.50–0.80** | 2,219 / +0.011 / 0.600 | 1,964 / +0.013 / 0.586 | 1,892 / +0.030 / 0.594 | 1,966 / +0.024 / 0.597 |
| **0.80–0.95** | 2,624 / −0.006 / 0.641 | 2,806 / −0.019 / 0.651 | 2,792 / −0.021 / 0.661 | 2,930 / +0.010 / 0.648 |
| **0.95–1.00** | 1,817 / −0.002 / 0.641 | 1,900 / −0.010 / 0.652 | 1,896 / −0.009 / 0.701 | 1,612 / +0.014 / 0.560 |

**Both defects are present in 0.25–0.50 and both are severe.** The level is
over-forecast by 2.7–4.8 points in three seasons, and the within-band AUC of
**0.510–0.564 is barely distinguishable from a coin toss.** The 0.00–0.25 band
is under-forecast by 4.6–9.8 points in every season and no candidate fixes it.

## 12. Recalibration candidates (Experiment 1) — they fail

Families: **Platt** (logistic on the logit), **isotonic** (exact PAVA),
**monotone spline** (isotonic on 12 quantile knots, linearly interpolated).
Family chosen on the inner season: Platt for 2022–2023, isotonic for 2024–2025
under `R+cal`, Platt for 2024 under `A1+cal`.

| system | 2022 LL | 2023 LL | 2024 LL | 2025 LL | slope 2024 |
|---|---|---|---|---|---|
| **A** | 0.41983 | 0.39656 | 0.38881 | 0.46816 | 1.0872 |
| A+P | 0.44508 | 0.40873 | 0.39464 | **0.46729** | 1.2641 |
| A+I | 0.44813 | 0.40889 | 0.39346 | 0.46744 | 1.2188 |
| A+S | 0.44981 | 0.41186 | 0.39854 | **0.46659** | 1.2981 |

**All three recalibrators raise log loss and Brier in 2022, 2023 and 2024**, and
help only marginally in 2025. **The cause is measurable, not mysterious.** The
nested calibrator is fitted on out-of-fold pairs produced by models trained on
*fewer* seasons, which are *more* compressed; the expansion map it learns is
therefore too aggressive for the final model, and the calibration slope goes
from 1.087 to **1.22–1.30** (and to 1.41–1.56 in 2022). **A correct nesting can
still produce a wrong calibrator when the training window expands.** That is a
methodological finding about nested calibration, and it is why the numbers move
the way they do.

Band-level, the damage is visible: `A+S` drives the 0.80–0.95 gap to **−0.122**
(2022) where the incumbent's was −0.006.

## 13. Ranking-model candidates (Experiment 2)

| system | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| | LL / AUC | | | |
| **A** (incumbent) | 0.41983 / 0.8589 | 0.39656 / 0.8688 | 0.38881 / 0.8783 | 0.46816 / 0.8175 |
| **A1** (converged only) | 0.41757 / 0.8611 | 0.39520 / 0.8704 | 0.38648 / 0.8803 | 0.46754 / 0.8188 |
| **R** (converged + blocks) | **0.39568 / 0.8776** | **0.36730 / 0.8904** | **0.35913 / 0.8987** | **0.44730 / 0.8368** |
| X_depth *(diagnostic)* | 0.32691 / 0.9208 | 0.30497 / 0.9262 | 0.30261 / 0.9292 | **0.68591 / 0.8288** |

- **A1 (convergence alone) is a real but small gain**: −0.5% to −0.6% log loss,
  +0.0013 to +0.0022 AUC, in all four seasons.
- **R is a large gain**: log loss −4.5% (2025) to −7.6% (2024), AUC +0.019 to
  +0.022, in all four seasons including 2025.
- **X_depth is not usable and its own numbers say so.** It looks spectacular
  on 2020–2024 (AUC 0.929) and **collapses on 2025** (log loss 0.686, bias
  −0.286) because the depth artifact is absent that season. Two separate
  reasons to refuse it: no timestamp, and no 2025 coverage. Its size (+0.05 AUC
  over R) is itself a caution — a feature that large from an untimestamped
  weekly file is as consistent with partial outcome contamination as with real
  pregame signal, and nothing in this repository can tell the two apart.

## 14. Mid-range metrics — the test that settles the question

**Named in the pre-declaration before it was computed:** AUC inside 0.25–0.80
with the region fixed by the **incumbent's** probability. A monotone map cannot
change it, because the row set is fixed and monotone maps preserve within-set
order.

| system | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| **A** | 0.6918 | 0.6854 | 0.6950 | 0.6665 |
| A+P | 0.6918 | 0.6854 | 0.6950 | 0.6665 |
| A+I | 0.6917 | 0.6854 | 0.6950 | 0.6665 |
| A+S | 0.6918 | 0.6854 | 0.6950 | 0.6665 |
| A1 | 0.6986 | 0.6909 | 0.7002 | 0.6704 |
| **R** | **0.7254** | **0.7512** | **0.7537** | **0.7182** |
| X_depth *(diag.)* | 0.8322 | 0.8422 | 0.8366 | 0.7209 |

**The three recalibrators reproduce the incumbent to four decimals — which
validates the test — and the ranking model moves it by +0.034 to +0.066 in
every season.** Within 0.25–0.50 specifically, R lifts the within-band AUC from
0.510/0.526/0.564/0.545 to **0.660/0.716/0.713/0.663**, and shrinks the level
gap from +0.046/+0.027/+0.048/−0.007 to +0.024/+0.017/+0.036/−0.004 —
**without any calibrator at all.**

**Answer to criterion A: primarily ranking.** The level error in 0.25–0.50 is
real, but it is a *consequence* of ranking failure — when a band's members
cannot be ordered, their mean cannot be right for each of them, and the fix
that works is the one that orders them.

## 15. Season results (criterion D)

**R improves every metric in all four seasons**, 2025 included: log loss
−5.7%/−7.4%/−7.6%/−4.5%, AUC +0.0188/+0.0217/+0.0204/+0.0193, Brier
−6.0%/−8.7%/−8.5%/−5.7%. 2025 is the weakest season for every system
(A AUC 0.8175 against 0.8783 in 2024) and it is the season with **no injury
feature at all** — the cost of that debt, measured.

## 16. Position results

| position | n | A log loss | R log loss | Δ | A AUC | R AUC | Δ |
|---|---|---|---|---|---|---|---|
| WR | 14,272 | 0.4275 | 0.3989 | **−6.7%** | 0.8446 | 0.8674 | +0.0228 |
| RB | 8,960 | 0.4154 | 0.3895 | −6.2% | 0.8630 | 0.8800 | +0.0170 |
| TE | 8,211 | 0.3846 | 0.3572 | **−7.1%** | 0.8601 | 0.8813 | +0.0212 |
| QB | 4,314 | 0.4589 | 0.4440 | −3.2% | 0.8533 | 0.8646 | +0.0113 |

Broad, not concentrated. QB gains least.

## 17. Injury-availability results

| cohort | n | A log loss | R log loss | Δ | A AUC | R AUC | Δ |
|---|---|---|---|---|---|---|---|
| injury feature **available** | 4,714 | 0.2825 | 0.2874 | **+1.7%** | 0.9331 | 0.9310 | **−0.0021** |
| injury feature **unavailable** | 31,043 | 0.4390 | 0.4084 | −7.0% | 0.8411 | 0.8662 | +0.0251 |

**Where a real injury designation exists, the new features add nothing and
slightly hurt.** The whole gain is in the 87% of rows with no injury report.
That is a clean statement of what the long-window features are substituting
for: they are a proxy for availability information we do not have, and they are
redundant where we do.

## 18. Role-change results

| cohort | n | A log loss | R log loss | Δ | A AUC | R AUC | Δ |
|---|---|---|---|---|---|---|---|
| stable | 25,809 | 0.3825 | 0.3653 | −4.5% | 0.8772 | 0.8889 | +0.0117 |
| **role change** | 9,948 | 0.5114 | 0.4627 | **−9.5%** | 0.7892 | 0.8346 | **+0.0454** |

The gain is more than twice as large where the role is moving — the cohort P4C
identified as the hardest.

## 19. Information-quality results

MEDIUM −8.1% log loss / +0.0277 AUC; LOW −5.0% / +0.0205; **HIGH +1.7% /
−0.0021**. HIGH is exactly the injury-available cohort of §17.

## 20. Feature ablations (blocks, not columns)

Δ log loss and Δ AUC when a block is removed from R (positive log loss = the
block was helping):

| block removed | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| **`long_window`** | **+0.01524 / −0.0112** | **+0.01801 / −0.0127** | **+0.01723 / −0.0118** | **+0.01322 / −0.0113** |
| `trajectory` | +0.00366 / −0.0021 | +0.00268 / −0.0018 | +0.00079 / −0.0005 | +0.00337 / −0.0024 |
| `prior_injury_history` | +0.00069 / −0.0008 | +0.00218 / −0.0014 | +0.00290 / −0.0016 | +0.00028 / −0.0000 |
| `depth_of_history` | +0.00021 / −0.0006 | +0.00078 / −0.0007 | +0.00132 / −0.0010 | +0.00063 / −0.0007 |
| `teammate_context` | +0.00031 / −0.0002 | +0.00011 / +0.0000 | +0.00044 / −0.0002 | +0.00040 / −0.0003 |
| `streak` | +0.00010 / +0.0001 | +0.00002 / −0.0000 | **−0.00012 / +0.0001** | +0.00006 / −0.0000 |
| *all blocks (= A1)* | +0.02189 / −0.0166 | +0.02790 / −0.0200 | +0.02736 / −0.0184 | +0.02025 / −0.0180 |

**One block carries 62–70% of the entire gain: `long_window` — appearance rate
over the prior 8 and 10 games, the whole prior career, and season to date.**
The incumbent's memory (`rate3`, `rate5`, EWMA half-life 3) is simply too
short. `streak` is worth nothing at all. `depth_of_history` — the interaction
block I designed *specifically* as the targeted mid-range fix — is worth
+0.0002 to +0.0013, i.e. almost nothing. **My hypothesis about what would fix
the mid-range was wrong; the data says it is window length, not sample-size
interaction.**

## 21. Ranking-versus-calibration decomposition (mandatory)

| arm | log loss 2024 | AUC 2024 | mid-band AUC (fixed) | downstream snaps CRPS |
|---|---|---|---|---|
| 1. incumbent ranking + incumbent probabilities | 0.38881 | 0.8783 | 0.6950 | 6.7882 |
| 2. incumbent ranking + recalibrated probabilities | 0.39854 | 0.8783 | **0.6950 (identical)** | 6.8487 (+0.89%) |
| 3. improved ranking + raw probabilities | **0.35913** | **0.8987** | **0.7537** | **6.5843 (−3.00%)** |
| 4. improved ranking + chronology-safe recalibration | 0.36485 | 0.8986 | 0.7537 | 6.6620 (−1.86%) |
| 5. oracle appearance *(diagnostic)* | 0.000001 | 1.0000 | 1.0000 | 4.7338 (−30.26%) |

**Arm 2 is identical to arm 1 in every ranking statistic and worse in every
other one. Arm 3 moves everything.** The remaining defect is:

- **not** the calibration mapping — arm 2 proves a monotone map cannot help and
  in fact hurts;
- **partly** ranking — arm 3 captures a third of the mid-band AUC gap to the
  oracle;
- **mostly missing information and irreducible uncertainty** — §31, criterion J.

## 22. Downstream P4C CRPS results

The P4C modules are **imported, not copied**: share point models, share residual
pools, reconciliation, stochastic residual mass and team-volume draws are
byte-identical, the allocation system is P4C's `C`, and the appearance draw uses
the same seed stream for every system. **Verification: under `A` the machinery
reproduces P4C's published numbers exactly** — snaps CRPS 6.7882 / rPIT 91.2,
pass_snaps 4.2606 / 97.1, targets 0.9360 / 76.9, carries 2.0206 / 12.7,
rz_carries 0.5508 / 91.5.

| class | A | A1 | **R** | A1+cal | O *(diag.)* |
|---|---|---|---|---|---|
| `snaps` | 6.7882 | 6.7824 (−0.08%) | **6.5843 (−3.00%)** | 6.8320 (+0.64%) | 4.7338 (−30.26%) |
| `pass_snaps` | 4.2606 | 4.2571 (−0.08%) | **4.1523 (−2.54%)** | 4.2762 (+0.37%) | 3.1821 (−25.31%) |
| `targets` | 0.9360 | 0.9355 (−0.05%) | **0.9236 (−1.33%)** | 0.9335 (−0.26%) | 0.7971 (−14.84%) |
| `carries` | 2.0206 | 2.0181 (−0.12%) | **1.9961 (−1.21%)** | 2.0318 (+0.55%) | 1.5843 (−21.59%) |
| `rz_carries` | 0.5508 | 0.5506 (−0.03%) | **0.5481 (−0.48%)** | 0.5497 (−0.19%) | 0.5059 (−8.15%) |

**R improves downstream CRPS on all five classes**, and it does so by sharpening
(mean 90% width falls slightly: snaps 41.09 → 40.95) rather than by widening.

## 23. Downstream randomised PIT — and this is where it fails

Critical value on 9 df at p = 0.001 is **27.877**.

| class | A | A1 | **R** | A+S | A1+cal | O *(diag.)* |
|---|---|---|---|---|---|---|
| `snaps` | 91.2 | 85.8 | **105.2** | 351.3 | 336.9 | **26.2 ✓** |
| `pass_snaps` | 97.1 | 92.4 | **106.7** | 314.2 | 311.0 | 36.4 |
| `targets` | 76.9 | 78.1 | **67.9** | 42.2 | **39.2** | 183.0 |
| **`carries`** | **12.7 ✓** | **12.5 ✓** | **13.1 ✓** | 35.8 ✗ | 32.8 ✗ | 18.3 ✓ |
| `rz_carries` | 91.5 | 91.0 | **86.6** | 53.8 | 54.0 | 148.0 |

Per season for the two classes the rule turns on:

| | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| `snaps` A → R | 73.1 → **128.1** ✗ | 122.8 → **145.8** ✗ | 111.5 → 98.2 ✓ | 57.9 → 47.5 ✓ |
| `pass_snaps` A → R | 71.3 → **121.6** ✗ | 132.4 → **154.9** ✗ | 116.9 → 102.0 ✓ | 68.7 → 47.0 ✓ |

**A better appearance model makes downstream calibration worse in 2022 and 2023
and better in 2024 and 2025.** The mechanism is not mysterious: R is sharper, so
more rows sit near 0 and 1; where the extra sharpness outruns the true
discrimination, PIT mass piles at the edges. It improves CRPS *because* it
sharpens, and it costs PIT for the same reason.

**Criterion E is answered NO for R.** The oracle reaches 26.2 on snaps, so the
bound P4C identified is real — but it is a bound, not something the available
pregame information can reach.

## 24. Downstream interval coverage

| class | system | 50% | 80% | 90% | 95% | mean w90 |
|---|---|---|---|---|---|---|
| `snaps` | A | 0.662 | 0.889 | 0.947 | 0.976 | 41.09 |
| | **R** | 0.667 | 0.891 | 0.951 | 0.977 | **40.95** |
| | A+S | 0.705 | 0.918 | 0.966 | 0.985 | 46.99 |
| | O | 0.645 | 0.876 | 0.933 | 0.966 | 27.41 |
| `targets` | A | 0.661 | 0.875 | 0.942 | 0.974 | 5.40 |
| | **R** | 0.667 | 0.878 | 0.943 | 0.974 | **5.39** |
| | A1+cal | 0.687 | 0.894 | 0.955 | 0.981 | 5.80 |

**R does not buy anything by widening** — its intervals are marginally narrower
than the incumbent's at every level. The recalibrated systems do widen (snaps
w90 41.09 → 46.99) and that is where their PIT damage comes from. The
over-coverage at 50% (0.66 against nominal) is the atom at zero, unchanged from
P4C and not an appearance problem.

## 25. Downstream threshold calibration

Maximum absolute calibration-in-the-large across each class's frozen P4C grid
(probe 8 asserts the downstream runner defines no grid of its own):

| class | A | A1 | R | A+S | A1+cal |
|---|---|---|---|---|---|
| `snaps` | 0.0185 | 0.0186 | 0.0186 | **0.0139** | 0.0152 |
| `pass_snaps` | 0.0274 | 0.0275 | 0.0269 | **0.0163** | 0.0154 |
| `targets` | 0.0129 | 0.0129 | 0.0128 | 0.0073 | **0.0067** |
| `carries` | 0.0244 | 0.0244 | **0.0231** | 0.0233 | 0.0232 |
| `rz_carries` | 0.0215 | 0.0216 | **0.0212** | 0.0252 | 0.0254 |

R is neutral-to-slightly-better everywhere. **The recalibrated systems are
better on threshold calibration** (snaps 0.0185 → 0.0139) even while being far
worse on randomised PIT — a reminder that these are different properties and
one does not imply the other.

## 26. Carries preservation check (criterion G)

| system | pooled rPIT | passes (< 27.877)? |
|---|---|---|
| A | 12.7 | **yes** |
| A1 | 12.5 | **yes** |
| **R** | **13.1** | **yes** |
| A+S | 35.8 | **no** |
| A1+cal | 32.8 | **no** |
| R+cal | 20.5 | yes |

**`carries` remains calibrated under A, A1 and R.** Every system that applies a
calibrator to the incumbent breaks it. Per the pre-declared regression clause,
that alone refuses `A+S` and `A1+cal` whatever else they improve.

## 27. Target residual diagnosis (criterion H)

**Targets remain miscalibrated after appearance is improved, and the evidence
says appearance was never their problem.**

- R improves targets rPIT 76.9 → 67.9 — better, still rejecting.
- **Oracle appearance makes targets *much worse*: 76.9 → 183.0.** Perfect
  appearance information degrades target calibration.
- The systems that help targets most are the **recalibrated** ones (A1+cal
  39.2, A+S 42.2) — they help by *widening*, and they break `carries` doing it.

This reproduces P4C's finding from the opposite direction. P4C found targets'
miscalibration unattributable to any single component; P4D confirms it by
intervention: making appearance better, or perfect, does not fix it. **Targets
have a conditional-share distribution-shape problem.**

## 28. Red-zone carry residual diagnosis (criterion I)

Same pattern, more extreme. R improves rz_carries 91.5 → 86.6; **oracle
appearance makes it 91.5 → 148.0.** The recalibrated systems reach 53.8–54.0 by
widening. P4C attributed this class to a share/tail problem and P4D's
intervention confirms it: **appearance is not the binding constraint for
red-zone carries.**

## 29. Adversarial tests

**12 probes, 0 failing** (`p4d_adversarial.json`). Each seeds the violation,
shows the seeded version is materially better, then asserts the shipped
pipeline does not contain it. Appearance probes on 2024, n = 8,831,
R log loss 0.35913.

| # | seeded leak | effect of the leak | guard asserted |
|---|---|---|---|
| 1 | realised appearance | log loss 0.35913 → 0.000001 | oracle built in a separate pass, never in selection |
| 2 | final roster status | — | no P4D module reads `weekly_rosters` or a status field |
| 3 | same-game snap count | **0.35913 → 0.03628 (−89.9%)** | no shipped feature reads `y_*` or `offense_snaps` |
| 4 | same-game targets/carries | 0.35913 → 0.17549 | feature builder reads no `y_*` field |
| 5 | future appearance streak | 0.35913 → 0.31825 | every block uses strictly earlier `ord` |
| 6 | future injury designation | **weak version does NOT leak** (0.35929); strong version (games missed over the next three weeks) 0.35913 → 0.32989 | as above |
| 7 | evaluation-season calibrator | 0.36485 → 0.35779 (−1.94%) | shipped pools are seasons 2021–2023 only |
| 8 | evaluation-season threshold tuning | — | downstream runner defines no grid; reads P4C's frozen `THRESHOLDS` |
| 9 | 2025 final-file injury leakage | — | 2025 carries **0** injury rows against 1,577 in 2024, and the 2025 design matrix has **71 columns against 80** — the block is structurally absent, not zeroed. The 2026 artifact is never read |
| 10 | postgame player universe | — | 2,593 of 8,831 (29.4%) retained rows are non-appearances; 0 rows without a prior game |

Probe 6 is reported in both halves because the obvious construction **did not
leak**: a next-week `Out` designation moves log loss by +0.0002, because the
prior-appearance blocks already carry it. Recording that is more useful than
quietly replacing the probe.

## 30. Guard-deletion proofs

| # | proof |
|---|---|
| **11** | **Fitting the calibrator on the evaluation season** drives the worst band gap to **0.0262** against **0.0684** for the shipped out-of-fold calibrator. It would look like success and is entirely circular; the nesting in `run_p4d_app.oof_pairs` is what prevents it. |
| **12** | **Realised appearance improves downstream CRPS in 20 of 20 class-seasons by 19.98% on average** (min 5.78%, max 35.02%) — reproducing the effect P4C observed. The channel is live and large, which is why the oracle is computed in a separate pass and never enters selection. |

## 31. Negative findings

1. **R is not promoted.** Under the rule fixed in §12 of the pre-declaration:
   rule 1 (log loss and Brier both improve) **passes**; rule 2 (AUC not down
   > 0.002) **passes**, AUC is *up* 0.019–0.022; rule 3 (no class CRPS worse by
   > 0.25%) **passes**, worst class −0.48%; **rule 4 (downstream randomised PIT
   improves on `snaps` and `pass_snaps`) fails** — 2 of 4 seasons each, and
   pooled it is worse. **The incumbent is retained.**
   *Post-hoc observation, not a decision and not a rule change:* a rule keyed to
   pooled CRPS and appearance quality alone would have promoted R comfortably. I
   wrote rule 4 before seeing any of this and I am not rewriting it now.
2. **Recalibration fails.** All three families raise log loss and Brier in three
   seasons of four, over-expand the calibration slope to 1.22–1.56, and break
   `carries`' passing randomised PIT.
3. **My own mid-range hypothesis was wrong.** `depth_of_history` — the
   interaction block designed specifically to distinguish "50% over 6 games"
   from "50% over 20 games" — is worth +0.0002 to +0.0013 log loss. The gain is
   almost entirely `long_window`: the incumbent's memory is too short, which is
   a duller answer than the one I expected.
4. **P4C's oracle attribution was a bound, not an achievable gain.** Oracle
   appearance takes snaps rPIT to 26.2; the best real model takes it to 105.2,
   worse than the incumbent's 91.2.
5. **Where injury information exists, the new features are redundant and
   slightly harmful** (+1.7% log loss, −0.0021 AUC on the HIGH cohort).
6. **The 0.00–0.25 band is under-forecast by 4.6–9.8 points in every season and
   nothing tested fixes it.**
7. **Depth-chart rank is a large signal that cannot be used.** No timestamp, no
   2025 coverage, and a gain large enough to be as consistent with contamination
   as with signal.

## 32. Unresolved debts

- **2025 injury artifact has no `date_modified`** — 2025 carries no injury
  feature and is the worst season for every system (AUC 0.8175 against 0.8783).
  The cost of this debt is now measured. The Wayback path remains documented for
  the networked agent.
- **Depth charts carry no timestamp of any kind** and stop in 2024. A
  timestamped depth or inactives feed is the single most valuable missing input
  identified anywhere in P1–P4D.
- **No sealed holdout.** 2022–2025 are all training seasons for later years.
- **Nested calibration under an expanding training window is mis-specified** by
  construction (§12). A calibrator trained on weaker models does not transfer.
  Unsolved here.
- **True routes still do not exist**; `rpr` remains a participation proxy.
- **The panel begins in 2020**, so 2022 has only two prior seasons.

### What remains irreducible (criterion J)

Log loss against the entropy of a constant forecast at each band's own base
rate, pooled 2022–2025, bands fixed by the incumbent:

| band (by A) | n | observed | H(observed) | A | **R** | R vs H |
|---|---|---|---|---|---|---|
| 0.00–0.25 | 2,372 | 0.1741 | 0.4624 | 0.3784 | 0.3568 | −0.1055 |
| **0.25–0.50** | 6,967 | 0.3486 | 0.6466 | **0.6494 (worse than a constant)** | 0.5957 | **−0.0509** |
| **0.50–0.80** | 8,041 | 0.6555 | 0.6440 | 0.6330 | 0.6106 | **−0.0334** |
| 0.80–0.95 | 11,152 | 0.8951 | 0.3357 | 0.3238 | 0.2970 | −0.0387 |
| 0.95–1.00 | 7,225 | 0.9744 | 0.1191 | 0.1159 | 0.1126 | −0.0065 |
| **all** | 35,757 | 0.7029 | 0.6084 | 0.4184 | 0.3924 | −0.2159 |

**Inside the mid range, 92–95% of the uncertainty is irreducible with the
features available.** R extracts 7.9% of the 0.25–0.50 band's entropy and 5.2%
of the 0.50–0.80 band's; the incumbent extracts *negative* 0.4% of the first.
Overall the features explain 35.5% of the base entropy, up from 31.2%. The
diagnostic depth arm reaches 15.9% inside 0.25–0.50 — **which is where the
remaining signal is, and it is behind a timestamp we do not have.**

## 33. Task-report path

`TASK_REPORT_2026-09-07_P4D.md` (repository root, `94924676jp-a11y/nfl`, `main`).

## 34. Recommendation for the next research question only

**Establish whether a timestamped pregame availability source exists for the
2020–2025 window, and if one does, what it is worth.**

Every road in P4D ends at the same wall. The mid-range is 92–95% irreducible
with what we have. The one arm that broke through — depth-chart rank, mid-band
AUC 0.85 against R's 0.71 — is refused for exactly one reason: the artifact
carries no timestamp, so we cannot distinguish pregame signal from contamination
by the outcome. The 2025 season, which has no injury feature at all, is the
worst season for every system by a wide margin, which prices the same debt from
the other side.

That question is **not** answerable inside this repository — it needs bytes from
outside this checkout — so per `docs/AGENT_PROTOCOL.md` it is **assigned, not
blocked**, and belongs in `AGENT_OUTBOX.md` for the networked agent: official
inactives lists, depth charts, or practice reports with a retrievable
`retrieved_at`, for 2020–2025 regular seasons. The G0A T−90 capture path already
captures exactly this class of artifact prospectively; the question is whether a
historical equivalent can be recovered.

**I am not recommending** more appearance modelling, a more complex ranking
model, P5, an efficiency model, or another calibration family. The simple models
have been tested, the residual has been measured, and the measurement says the
next gain is in data, not in method — which is precisely the condition under
which the pre-declaration says complexity has not earned promotion.

---

## Constraints honoured

P5 not started. No receptions, receiving yards, rushing yards, passing yards,
touchdowns or fantasy points. No J0. **No market ingested and no market-derived
feature exists.** No DFS, no lineup optimisation, **no wager recommended and
none discussable.** NFL-1 not authorised. G0A untouched (11 PASS / 1 FAIL).
T−90 untouched. **No 2026 outcome consumed** — panel seasons are 2020–2025.
`weekly_rosters.status` not read (probe 2). **The 2026 injury artifact is never
read and is not used as evidence about the 2025 file** (probe 9). The appearance
estimand is unchanged. The P4C machinery is imported, not edited, and reproduces
its published numbers exactly under the incumbent. Repository test count
unchanged and re-verified: **1,230 assertions across 19 suites, 0 failing.**

**Stopping after the research return, as instructed.**

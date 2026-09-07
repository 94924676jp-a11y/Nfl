# P4C-CARRY — Carry-count error decomposition: team volume vs share vs appearance

**Status:** complete. Decomposition experiment only. **No component was
modified.** Nothing authorised, enabled or promoted.

---

## 0. Read this first — a live governance regression, unrelated to this task

**The repository test count is 1,230 assertions with 4 now FAILING.** In my P4D
and P5A returns earlier today I reported "1,230 assertions, 0 failing". That was
true when measured; it is not true now, and the change is not mine.

**What changed.** Two `practice`-kind T−90 targets are now reported **covered**:

| target | window | discharged by |
|---|---|---|
| `2026_01_NE_SEA` / `practice_a` | 2026-09-07T20:00Z → 09-08T16:00Z | `official_injury_report` at 20:05:40Z, **game_id `None`** |
| `2026_01_SF_LA` / `practice_mon` | same window | `official_injury_report` at 20:37:36Z, **game_id `None`** |

Those two timestamps are the bot's own periodic vintage sweeps — commits
`NFL vintage capture 20260907T200538Z` and `20260907T203734Z`. They carry **no
game attribution**, and the coverage summary says so in the same breath:

```
covered: 2      attributed_captures: 0      total_captures: 309
state: DEFERRED[NO_WINDOW_HAS_CLOSED_YET]  ->  PASS
```

**Two targets are marked covered on the strength of zero game-attributed
captures, and the state has flipped to a green.**

**Mechanism.** `GAME_SPECIFIC_KINDS = ['inactives']`, so a `practice` target is
not game-specific and `schedule._clears` accepts any capture inside the window,
including an unanchored periodic sweep. The anchored path forbids exactly this —
`DISCHARGING_BASES = (BASIS_ANCHORED,)`, and Directive 7 §5 is explicit that a
baseline sweep landing in a window does not discharge. The coverage path does
not apply that rule to non-game-specific kinds.

**The system caught itself.** Pre-flight check *"the first target is not already
covered"* fails with `TARGET_ALREADY_COVERED` and the message "coverage reports
a covered target before the event. Nothing should be covered yet." The first
T−90 window does not open for another 49.5 hours. Four repository assertions
fail — 1 in `test_coverage.py`, 3 in `test_preflight.py` — and they are the
assertions that exist to catch precisely this.

**I have not fixed it.** The hard stop forbids modifying T−90 and G0A, and this
is squarely inside both. It is recorded here, in §28, and it is the first thing
I would want looked at.

---

## The decomposition, in one paragraph

**Within carry-count error, player share allocation is the largest component at
50.1%, team volume is 29.8%, and appearance is 20.0%** — stable across all four
seasons and confirmed in rushing-yard space (48.5 / 29.0 / 22.4). **That inverts
the framing this task inherited**: P5A correctly established that carries are
51% of rushing-yard error against 16% for conversion, and it was natural to read
that as "team volume is the bottleneck". It is not. **Interactions are large** —
team×share alone is +23.8% of the total reduction — so the one-at-a-time oracles
must not be read as an attribution, which is why Shapley was pre-declared. And
the answer moves sharply with the cohort: **for RB1 team volume is the largest
single component (42.9%); for everyone else share dominates.**

---

## 1. HEAD at task start

`68f96e0` — "P5A return". Working tree clean, level with `origin/main`.

## 2. Commits

| commit | content |
|---|---|
| `4d4c270` | P4C-CARRY pre-declaration |
| `b76fd1c` | P4C-CARRY research: carry-count error decomposition |
| *(this report)* | `TASK_REPORT_2026-09-07_P4C_CARRY.md` |

## 3. Pre-declaration

`nfl/research/p4c_carry/predeclaration_p4cc.md`, committed in `4d4c270` before
any corner was evaluated. Departures: none.

## 4. Files

Under `nfl/research/p4c_carry/`: `predeclaration_p4cc.md`, `run_p4cc.py`
(the factorial), `run_p4cc_diag.py` (component diagnostics and cohorts),
`run_p4cc_down.py` (frozen P5A propagation), `run_p4cc_adversarial.py`,
results `p4cc_results.json`, `p4cc_diag.json`, `p4cc_downstream.json`,
`p4cc_adversarial.json`, four per-season row-level pickles, and three run logs.

## 5. Frozen-system verification

**The baseline reproduces P4C's published `carries` CRPS to 0.00e+00 in all four
seasons** — 1.9296 / 1.9973 / 2.1103 / 2.0545, identical to
`p4c_results.json`. Guard-deletion probe 10 shows that a 2% perturbation of the
frozen appearance probability changes 2,000 of 2,000 inputs, so the exact match
is evidence the components were untouched rather than a coincidence.

Imported unchanged: incumbent P3 Stage-A appearance model, P4B unconditional
team-volume distribution, P4C additive carry-share weights, P4C reserved
stochastic-mass reconciliation, shared team-game draw identity.

## 6. Decomposition design

A full 2³ factorial over **T** (team volume, including the reconciliation's
reserved mass `avail`), **S** (share weights), **A** (appearance). Placing
`avail` with team volume is what makes the corner algebra close:

```
count_ij   = T_gj * avail_gj * w_ij A_ij / sum_g(w A)
all-oracle = T* * m* * S* A* / m*  =  T* * S*  =  realised carries
```

**Verified: the all-oracle corner reproduces the realised carry count with a
largest absolute error of 3.81e-06** (float32 rounding). Left on the predicted
side the corner would not close and every attribution would silently absorb the
gap.

Attribution is by **Shapley value** over the three components with
`v(S) = CRPS(baseline) − CRPS(oracle set S)`, computed per row as well as
pooled. Both the raw oracle improvements and the Shapley values are reported,
alongside the explicit factorial interaction terms.

## 7. Carry-count baseline

Pooled 2022–2025, n = 8,960 RB player-games, 2,174 team-games:

| metric | value |
|---|---|
| CRPS | 2.0206 |
| MAE / RMSE | 3.099 / 4.436 |
| r / R² | 0.759 / 0.575 |
| bias | −0.006 |
| randomised PIT χ² | **12.7** (critical 27.877 — passes) |
| coverage 50 / 90 | 0.701 / 0.954 |
| mean 90% width | 12.96 |
| P(zero) predicted vs actual | 0.423 vs 0.427 |

## 8–12. The oracle factorial

| corner | CRPS | vs baseline | MAE | r | R² | rPIT |
|---|---|---|---|---|---|---|
| **A_baseline** | 2.0206 | — | 3.099 | 0.759 | 0.575 | 12.7 |
| **O_T** team volume | 1.7275 | **−14.51%** | 2.674 | 0.824 | 0.676 | 11.8 |
| **O_S** share | 1.1839 | **−41.41%** | 1.609 | 0.897 | 0.802 | 95.0 |
| **O_A** appearance | 1.5843 | **−21.59%** | 2.316 | 0.837 | 0.701 | 18.3 |
| **O_S_T** | 0.4099 | −79.71% | 0.749 | 0.970 | 0.939 | 24.5 |
| **O_A_T** | 1.2251 | −39.37% | 1.784 | 0.907 | 0.821 | 27.6 |
| **O_A_S** | 0.9487 | −53.05% | 1.350 | 0.921 | 0.846 | 10.9 |
| **O_A_S_T** | 0.0000 | −100.00% | 0.000 | 1.000 | 1.000 | 311.0\* |

\* the all-oracle corner is a point mass; a PIT statistic on a degenerate
forecast measures the degeneracy and is reported as an artifact, not a finding.

**O_S_T at −79.7% is the number to notice**: knowing the team total *and* the
allocation, while still drawing appearance, removes four fifths of the error.

## 13. Shapley attribution and interactions

| component | Shapley (CRPS) | share of the 2.0206 total |
|---|---|---|
| **S — player share / allocation** | 1.0128 | **50.1%** |
| **T — team volume** | 0.6028 | **29.8%** |
| **A — appearance** | 0.4050 | **20.0%** |

Per season: S 50.7 / 50.9 / 49.6 / 49.2 %, T 31.3 / 29.5 / 28.5 / 30.1 %,
A 17.9 / 19.6 / 21.9 / 20.8 %. **Stable.**

Factorial terms on the reduction scale:

| term | value | % of total |
|---|---|---|
| main S | +0.8367 | +41.4% |
| main A | +0.4363 | +21.6% |
| main T | +0.2931 | +14.5% |
| **interaction T×S** | **+0.4809** | **+23.8%** |
| interaction S×A | **−0.2012** | **−10.0%** |
| interaction T×S×A | +0.1087 | +5.4% |
| interaction T×A | +0.0661 | +3.3% |

**The interactions are 22.5% of the total reduction and the main effects sum to
only 77.5%, so the one-at-a-time oracles are not an attribution.** T×S is
strongly positive — team total and allocation are complements, each worth much
more once the other is known. S×A is negative — they overlap, as they must,
since a realised share is zero for a non-appearance.

## 14. Team-volume diagnostics

| season | n | pred | real | bias (pred−real) | MAE | r | R² | cov90 | low-decile bias | high-decile bias |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 542 | 27.04 | 27.25 | −0.21 | 6.233 | +0.178 | **−0.006** | 0.884 | **+10.93** | **−13.57** |
| 2023 | 544 | 27.24 | 26.85 | +0.39 | 5.994 | +0.209 | +0.025 | 0.908 | +11.34 | −11.91 |
| 2024 | 544 | 27.07 | 27.00 | +0.07 | 6.084 | +0.209 | +0.034 | 0.912 | +10.65 | −12.68 |
| 2025 | 544 | 27.17 | 26.84 | +0.33 | 5.866 | +0.149 | +0.003 | 0.895 | +11.63 | −13.04 |

(Figures from `p4cc_diag.json`; the low/high-decile biases are the mean signed
error in the bottom and top realised deciles.)

**The team-carry point forecast has R² of essentially zero and r of 0.15–0.21.**
It is close to a constant, which reproduces P4's finding on a different
denominator. Its *distribution* is well behaved (90% coverage 0.887–0.910), and
that is why the carry forecast is calibrated while being weakly discriminating.
The decile biases are the mechanical regression-to-the-mean of a near-constant
forecast: **+10.6 to +11.6 carries in the lowest realised decile and −11.9 to
−13.6 in the highest.**

**Composition of the team carry pie** (mean of per-team-game shares, 2024):
**RB 0.807, QB 0.159, other positions 0.034**, with **scrambles 0.075** as a
subset of the QB share. **QB rushing sits inside the OTHER mass and is not
modelled by the accepted carry object.** The accounting was not redefined to
bring it in.

## 15. Share diagnostics

Conditional on realised team volume (`O_T`), the allocation still leaves
CRPS 1.7275; adding realised shares on top (`O_S_T`) takes it to 0.4099.
**If team volume were known exactly, allocation error would still be 76% of what
remains.**

**RB1↔RB2 competition, the sharpest single finding here:**

| season | pairs | corr(realised S1, S2) | corr(forecast C1, C2) | mean S1 | mean S2 |
|---|---|---|---|---|---|
| 2022 | 542 | **−0.578** | −0.434 | 0.470 | 0.190 |
| 2023 | 544 | **−0.559** | −0.386 | 0.457 | 0.207 |
| 2024 | 544 | **−0.624** | −0.251 | 0.459 | 0.214 |
| 2025 | 544 | **−0.570** | −0.373 | 0.479 | 0.210 |

**The model under-produces RB1/RB2 competition in every season**, by 0.14 to
0.37 of correlation. P4C measured this on absolute carries and found the
reconciled mechanism roughly right (−0.246 against an empirical −0.210); measured
directly on *shares*, which is where the mechanism actually operates, the
forecast is systematically too independent. **Not fixed here.**

## 16. Appearance diagnostics (carry-specific; P4D was not re-run)

Shapley share by the P4D probability band:

| band | n | mean carries | zero rate | CRPS | T | S | **A** |
|---|---|---|---|---|---|---|---|
| p < 0.25 | 363 | 0.32 | 0.915 | 0.285 | 6.0% | 34.9% | **59.1%** |
| 0.25–0.50 | 1,891 | 1.36 | 0.761 | 1.097 | 11.1% | 41.9% | **47.0%** |
| 0.50–0.80 | 2,323 | 2.98 | 0.507 | 1.886 | 16.5% | 57.0% | 26.5% |
| 0.80–0.95 | 3,295 | 6.74 | 0.251 | 2.462 | 31.5% | 53.9% | 14.5% |
| ≥ 0.95 | 1,088 | 13.76 | 0.044 | 3.156 | **54.8%** | 37.8% | **7.4%** |

**P4D's generic appearance defect is a major contributor only in the low-probability
bands, and those bands carry little carry mass.** The 363 rows below p = 0.25
average 0.32 carries. Weighted by CRPS, appearance is 20.0% of carry error
overall — real, but a third of allocation. **For the high-volume backs who
dominate rushing-yard variance, appearance is 7.4%.**

Appearance also controls the zero-carry mass, and there the baseline is
essentially right: predicted P(zero) 0.423 against actual 0.427.

## 17. RB1 / RB2 / QB

| rank (by **pregame** forecast) | n | mean carries | zero rate | CRPS | **T** | **S** | **A** |
|---|---|---|---|---|---|---|---|
| **RB1** | 2,174 | 12.49 | 0.142 | 3.506 | **42.9%** | 39.1% | 17.9% |
| RB2 | 2,174 | 5.59 | 0.280 | 2.494 | 25.3% | 55.4% | 19.3% |
| RB3 | 2,079 | 2.43 | 0.498 | 1.509 | 16.7% | 58.5% | 24.8% |
| RB4+ | 2,533 | 0.96 | 0.739 | 0.759 | 11.9% | **65.3%** | 22.8% |

**Criterion F answered: yes, decisively.** For the lead back **team volume is the
largest single component (42.9%)**; for everyone below him allocation dominates
and rises to 65.3%. A single "the bottleneck is X" answer would be wrong.

**QB is not in this table by construction** — the accepted carry class models RB
carries only, and QB rushing (15.9% of the team pie, of which 7.5 points are
scrambles) sits in the unmodelled OTHER mass. Improving QB rushing is a *team-volume*
question here, not a share question.

## 18. Role-change results

| cohort | n | mean carries | CRPS | T | S | **A** |
|---|---|---|---|---|---|---|
| stable | 7,040 | 4.85 | 1.799 | 31.4% | 52.3% | 16.3% |
| **role change** | 1,920 | 6.60 | 2.834 | 26.2% | 45.1% | **28.7%** |

**Criterion G answered: yes.** In role-change games appearance nearly doubles as
a share of the error (16.3% → 28.7%) at the expense of both other components.

## 19. Carry-tier results

| tier | n | mean carries | CRPS | T | S | A |
|---|---|---|---|---|---|---|
| 0 | 3,823 | 0.00 | 0.794 | **−0.2%** | 67.1% | 33.1% |
| 1–4 | 1,691 | 2.23 | 1.395 | 20.8% | 71.4% | 7.8% |
| 5–9 | 1,264 | 6.94 | 2.617 | 35.4% | 41.6% | 23.0% |
| 10–14 | 1,063 | 11.95 | 3.164 | 38.0% | 39.9% | 22.1% |
| **15+** | 1,119 | 19.25 | 5.396 | **40.8%** | 43.6% | 15.5% |

Team volume is worth nothing at all for a zero-carry game — it cannot explain a
zero — and rises monotonically to 40.8% for the heaviest workloads.

## 20. Yearly results

| season | n | CRPS | **T** | **S** | **A** |
|---|---|---|---|---|---|
| 2022 | 2,365 | 1.9296 | 31.3% | 50.7% | 17.9% |
| 2023 | 2,255 | 1.9973 | 29.5% | 50.9% | 19.6% |
| 2024 | 2,166 | 2.1103 | 28.5% | 49.6% | 21.9% |
| 2025 | 2,174 | 2.0545 | 30.1% | 49.2% | 20.8% |

**The attribution is stable to within ±1.5 points on every component.**

## 21–22. Calibration and randomised PIT

Threshold calibration on the pre-declared carry grid (forecast minus observed):

| threshold | >0.5 | >4.5 | >9.5 | >14.5 | >19.5 |
|---|---|---|---|---|---|
| observed rate | 0.5733 | 0.3846 | 0.2435 | 0.1249 | 0.0487 |
| **baseline error** | +0.0041 | +0.0121 | **−0.0244** | −0.0126 | +0.0040 |

Maximum absolute error 2.4 points, at >9.5.

**Randomised PIT χ² = 12.7 against a critical value of 27.877 — the carry
distribution passes.**

### Criterion H — is the good PIT hiding poor discrimination?

**Partly yes, and the place it hides it is team volume.** The carry forecast's
own discrimination is decent (r = 0.759, R² = 0.575) because share and
appearance carry real signal. But its **team-volume input has R² of essentially
zero** (§14) and is close to a constant, and the reason that does not show up in
the PIT is that the P4B distribution around that near-constant is well
calibrated (90% coverage 0.887–0.910). **A well-calibrated distribution around an
uninformative centre passes PIT and discriminates nothing** — which is exactly
what P4B said about team volume and what this task now shows propagating into
carries. Calibration and discrimination are different properties and the carry
object is a clean example of one being satisfied while the other is not.

## 23. Downstream frozen P5A propagation

Conversion is P5A's **control** — pooled prior-season per-carry empirical,
location-shift family, **zero shift, nothing refitted**. Only carry counts
differ between corners.

| corner | rushing-yard CRPS | vs baseline |
|---|---|---|
| A_baseline | 10.6334 | — |
| O_T | 9.4192 | −11.42% |
| O_S | 7.8463 | −26.21% |
| O_A | 9.0953 | −14.46% |
| O_S_T | 6.1044 | −42.59% |
| O_A_T | 7.6841 | −27.74% |
| O_A_S | 7.1394 | −32.86% |
| O_A_S_T | 5.2131 | −50.97% |

**Shapley in rushing-yard space: S 48.5%, T 29.0%, A 22.4%** — against
50.1 / 29.8 / 20.0 in carry space. **The decomposition survives propagation
essentially unchanged**, and O_A_S_T at −50.97% reproduces P5A's independently
measured realised-carry oracle of −50.94%.

## 24. The P5A subgroup-asymmetry diagnostic — report only

P5A found its efficiency model helps high-efficiency-history backs (−2.09% CRPS)
and hurts low-efficiency-history ones (+0.67%). The question was whether carry
misspecification explains it.

| efficiency history | n | predicted carries | realised | bias | relative |
|---|---|---|---|---|---|
| **high** | 2,629 | 8.915 | 10.651 | −1.736 | **−16.3%** |
| **low** | 1,946 | 7.001 | 8.357 | −1.357 | **−16.2%** |
| **none** (<25 prior carries) | 4,385 | 2.226 | 0.574 | +1.652 | **+287.7%** |

**No — it does not explain it.** High- and low-efficiency backs are
under-projected by **16.3% and 16.2%** respectively: the same, to a tenth of a
point. The hypothesis in the directive was that low-efficiency backs might be
systematically over-projected; they are not, they are under-projected exactly as
much as everyone else with a history.

**What the table does show is a different and larger defect.** Players with
fewer than 25 prior carries are allocated **2.23 carries against 0.574
realised**, and because the reconciliation conserves team mass **that surplus
comes directly out of the established backs**, which is what produces the
uniform −16% on both history cohorts. The pooled bias is −0.006, so this is
invisible in aggregate and only appears on the split. **Not fixed here.** The
mechanism is the share layer's fallback to a position prior for players without
history.

## 25. Adversarial probes

**10 probes, 0 failing** (`p4cc_adversarial.json`).

| # | seeded leak | measured channel | guard |
|---|---|---|---|
| 1 | realised team attempts | carry CRPS −14.50% (4/4 seasons) | baseline reads `store["B"]`, never `store["realized"]` |
| 2 | realised player share | **−41.41%**, the largest single channel | weights are prior-game EWMA shares only |
| 3 | realised appearance | −21.60% | Bernoulli(p_app) from the incumbent model |
| 4 | realised carries | −100%, identity error 3.81e-06 | the corner identity is checked, not asserted |
| 5 | same-game rushing yards | correlate **+0.7249** with the realised share on 5,137 rows | `rush_yards` is read once, only to score the downstream propagation |
| 6 | future carry share | next game's share correlates **+0.6890** with this one | accumulators advance strictly in `ord` order, read before update |
| 7 | future team volume | next game's team total correlates only **+0.1311** — weak, which is itself P4's finding | `store["realized"]` appears once, on the oracle side |
| 8 | roster status / market / weather | — | no such field is read anywhere in P4C-CARRY |

Probe 8 initially failed for the wrong reason — my filename pattern `ev` matched
inside `rowlevel_2025.pkl`. Anchored to word boundaries and re-run; the fix is
in the committed module.

## 26. Guard-deletion proofs

| # | proof |
|---|---|
| **9** | Selection handed a zero-CRPS oracle returns `'B'`; adding the oracle to `ELIGIBLE_SYSTEMS` makes it return `'O_A_S_T'`. **No corner of this factorial was offered to selection — this task selects nothing.** |
| **10** | The baseline reproduces P4C's published carries CRPS to **0.00e+00** in all four seasons, while a 2% perturbation of the frozen appearance probability changes 2,000/2,000 inputs. **The exact match is evidence the frozen components were untouched, not a coincidence.** |

## 27. Negative findings

1. **Team volume is not the largest component of carry error.** It is 29.8%;
   allocation is 50.1%. The framing this task inherited from P5A — true about
   carries versus conversion — does not survive one level down.
2. **The main effects do not add up.** Interactions are 22.5% of the total
   reduction, so a one-at-a-time oracle table is not an attribution and is not
   reported as one.
3. **No single bottleneck exists across cohorts.** For RB1 team volume leads at
   42.9%; for RB4+ allocation leads at 65.3%.
4. **The team-carry point forecast has R² ≈ 0.** Its calibration is fine and its
   discrimination is nil, and the carry object's passing PIT hides that.
5. **The model under-produces RB1/RB2 competition** by 0.14–0.37 of correlation
   in every season.
6. **Players without carry history are allocated ~4× the carries they get**, and
   that mass is taken from established backs, who are under-projected by 16%.
7. **The P5A efficiency asymmetry is not explained by carry misspecification.**
   Both cohorts are under-projected by the same amount.
8. **Appearance matters least where carries matter most** — 7.4% of error above
   p = 0.95, where mean carries are 13.76.

## 28. Unresolved debts

- **The T−90 coverage false green of §0.** Two practice targets covered with
  zero attributed captures; state flipped DEFERRED → PASS; four repository
  assertions failing. **Not fixed here — it is inside the T−90/G0A hard stop.**
- **RB1/RB2 competition is under-produced** (§15). Not fixed.
- **The no-history over-allocation** (§24). Not fixed.
- QB rushing (15.9% of the team carry pie) and other non-RB carries (3.4%) are
  unmodelled, sitting in the OTHER mass.
- Carried forward: no sealed holdout; 2025 has no injury feature; depth charts
  carry no timestamp; PFR advanced rushing exists for 2024 only.

## 29. Task-report path

`TASK_REPORT_2026-09-07_P4C_CARRY.md` (repository root,
`94924676jp-a11y/nfl`, `main`).

## 30. Recommendation for next research question only

**Fix the share layer's treatment of players without carry history, and measure
what that alone recovers.**

It is the largest measured, clearly-diagnosed, in-repository defect this task
found. Players with under 25 prior carries receive 2.23 carries against 0.574
realised — a fourfold over-allocation — and because reconciliation conserves the
team pie, that surplus is exactly what makes every established back come out 16%
light. It is a single mechanism (the share layer falls back to a position prior
for players without history), it sits inside the component the decomposition
identified as the largest (allocation, 50.1%), it is measurable against the
frozen baseline, and it needs no data this repository does not have.

The RB1/RB2 under-produced competition (§15) is the natural second question and
plausibly the same defect seen from another angle — if the fallback prior is
inflating third and fourth backs, the top two will look more independent than
they are — but it should be asked **after**, so the two are not confounded.

**I am not recommending** a new team-volume model (its R² is ~0 and P4 already
established why), further appearance work (P4D showed the mid-range is 92–95%
irreducible with present data), receiving, touchdowns, J0, or anything
downstream. And I am not recommending that the share layer be *rebuilt* — only
that this one identified mechanism be measured and, if the measurement supports
it, corrected.

---

## Constraints honoured

**No component was modified.** No new team-volume model, no change to appearance,
no change to the carry model, no refit of P5A conversion. No receiving, targets,
touchdowns. **No J0.** No market ingested, **no EV calculated, no wager
recommended and none discussable.** No fantasy points, no DFS, no lineup
optimisation. NFL-1 not authorised. **G0A and T−90 untouched — including the
regression in §0, which I diagnosed and deliberately did not fix.** No 2026
outcome consumed. Every oracle is diagnostic, computed after the fact, never
offered to selection.

**Repository test state, stated accurately: 1,230 assertions across 19 suites,
4 failing** — `test_coverage.py` 49/1 and `test_preflight.py` 11/3, both
failing on the §0 coverage regression, neither caused by this task.

**Stopping after the research return, as instructed.**

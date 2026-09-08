# Task report — canonicalization, Rule 006, and P4F

Date 2026-09-08. Canonical repository `94924676jp-a11y/nfl`, branch `main`.

**Headline.** The three local commits are now on canonical `main` and pushed.
The artifact-reference failure class is registered as executable Rule 006. P4F
ran as development research and returns **`ABC_MPR` RETAINED AS A PROSPECTIVE
CANDIDATE, `MPR_ONLY` REJECTED**, and **NOT PROMOTED** — P4C system C remains
the accepted carry-allocation architecture.

---

## 1. Canonicalization proof and SHAs

The local commits were genuinely absent from canonical `main`: the owner's
inspection was right and my earlier reports were describing local-only history.
This session's GitHub scope was `mlb-prop-system-v7`; `add_repo` with push
access attached `94924676jp-a11y/nfl`, so no substitute repo was created and no
NFL work was written into the MLB repository.

Canonical `main` was at `eea1909` with **three append-only vintage-capture
commits made after my branch point**. Local and canonical had diverged 3/3 from
merge base `7af5447`. My three commits were **rebased onto canonical**, which
replays mine and rewrites none of the canonical history beneath them.

```
$ git rebase FETCH_HEAD          # clean, no conflicts
$ git diff --name-only eea1909..HEAD | grep -c '^nfl_vintage/'
0
```

No vintage manifest and no raw evidence file was touched. Push:

```
   eea1909..54158d1  main -> main
```

Note for the record: the remote reports the repository has moved to
`https://github.com/94924676jp-a11y/Nfl.git` (capital N). The push follows the
redirect and succeeds; worth normalising the remote URL at some point.

**Canonical SHAs, in order:**

| SHA | commit |
|---|---|
| `c66ff89` | Close the volatility-test debt (was `95d2fe7` locally) |
| `6035ffc` | P4E pre-declaration (was `3716f5a`) |
| `54158d1` | P4E research, results and report |
| `7f6c2f2` | Register `ARTIFACT_REFERENCE_INTEGRITY` as Rule 006 |
| `f78d1f5` | **P4F pre-registration** |

The three rebased commits carry new SHAs because a rebase re-parents them; the
trees are unchanged.

## 2. Full-suite green proof

Re-run after canonicalization and again after Rule 006:

| location | modules | assertions | failed | non-zero exits |
|---|---|---|---|---|
| `nfl/tests/` | 17 | 1,230 | 0 | 0 |
| `sportsplatform/governance/` | 4 | 132 | 0 | 0 |
| **total** | **21** | **1,362** | **0** | **0** |

Plus, outside the suite, the P4F mechanistic tests: **66 passed, 0 failed**.

## 3. Rule 006 — `ARTIFACT_REFERENCE_INTEGRITY`

`sportsplatform/governance/artifact_reference.py`, 39 assertions in
`test_artifact_reference.py`.

A gate must load its comparison value from the canonical artifact, hash the
artifact, and report that hash in the run output. Display-only sources
(`.log`, `.txt`, `.out`, `.md`, `.rst`) are refused at source with
`GATE_SOURCE_IS_DISPLAY_ONLY` and cause `GOVERNANCE`. A comparison value with no
artifact behind it is refused as `GATE_VALUE_UNSOURCED`, because a typed float
and a loaded float are indistinguishable once both are floats.

**The seeded test the directive asked for** is section B: the exact literal that
shipped in P4E, `2.1102566719055176`, is put back in place of the artifact read.
The gate fails at `1.82e-05`, and `transcription_signature()` reports that the
two agree to **4 decimals** — the precision `run_p4c.log` prints. A hand-built
`ArtifactRef` carrying the same literal is refused as
`GATE_VALUE_NOT_FROM_ARTIFACT`. Section G deletes two guards and shows the catch
disappears with each.

One correction inside the rule itself: `transcription_signature` first returned
the *first* agreeing precision, which is 1 for almost any pair of numbers. It
now returns the *largest*, which is where the agreement stops and is the thing
that identifies a transcription.

`CURRENT_STATE.md` carries the appended governance record. The P4E task report
is left exactly as written.

## 4. P4F pre-registration

`f78d1f5`, `nfl/research/p4f/predeclaration_p4f.md`, written before any P4F
number existed. It fixes the bisection bracket and its IVT argument, the 1e-9
tolerance, degenerate and infeasible handling, the twelve first-principle tests,
the 0.010 CRPS adversarial materiality threshold, and the replacement rule 5.

Two things in it are departures worth naming up front:

- **A fifth system, `MC_ONLY`, was added as a confound control.** Mean-preserving
  rectification removes the rectification bias *and* the Monte-Carlo error in
  the draw mean. Without a system that removes only the second, the mechanism
  claim is not identified. It is not a feature block.
- **P4E's rule 5 was withdrawn, not adjusted.** It compared a within-team-game
  across-draws simulated correlation against an across-team-game realised one.
  Those are different estimands and the comparison was never admissible.

## 5. Synthetic mechanistic tests

`test_p4f_mpr.py`, **66 passed, 0 failed**, on data whose answer is known before
the solver runs.

Test 1 checks `E[max(0, C + eps)]` against the closed form for
`eps ~ N(0, 0.08)`:

| C | measured | closed form | inflation |
|---|---|---|---|
| 0.02 | 0.04290 | 0.04291 | **+114.5%** |
| 0.05 | 0.06297 | 0.06295 | +25.9% |
| 0.10 | 0.10411 | 0.10405 | +4.1% |
| 0.30 | 0.30008 | 0.30000 | +0.0% |

So the field measurement in P4E (+62% to +123% under 10 prior carries) is the
analytic behaviour of the estimator, not a data artifact.

Tests 2–12 all pass: monotonicity in both relative and absolute bias; the mean
restored within 1e-9 for normal and Laplace residuals across four spreads; `C`
and the draws untouched; no outcome channel, by signature and by source scan;
bit-identical on repeat; `C = 0` and `C = 1` handled with
`DEGENERATE_SOLUTION_SET` flagged; residual sd from 0 to 50 handled; centres
outside `[0, 1]` and non-finite residuals detected and left alone with `NaN`
shifts rather than imputed; shape and range errors raising named exceptions; and
the interior identity `eps = W − C + delta` exact, with the clipped fraction
(19.7% in that fixture) itself reported.

**One test expectation of mine was wrong and was corrected, not the solver.** At
`C = 0` I had asserted the mean is *exactly* zero. Bisection stops just short of
the exact threshold, so it lands at ~3e-20. That is the pre-declared 1e-9
contract met; the assertion was stricter than the contract and is now written
against the contract with the residual reported.

## 6. Baseline reproduction

Through Rule 006, tolerance **0.0**, artifact hash printed:

```
2022: PASS observed 1.929561163321  artifact 1.9295611633207923  sha256 5d8d34c22c01
2023: PASS observed 1.997281732179  artifact 1.9972817321788165  sha256 5d8d34c22c01
2024: PASS observed 2.110274841595  artifact 2.110274841594967   sha256 5d8d34c22c01
2025: PASS observed 2.054493485112  artifact 2.054493485111525   sha256 5d8d34c22c01
```

The oracle re-run's P4C baseline corner is separately asserted against
`p4cc_results.json` (sha256 `068b9836a867`) at `|diff| 0.00e+00` in all four
seasons.

## 7. MPR solver verification on real data

| season | state | max abs centre error | degenerate rows | infeasible |
|---|---|---|---|---|
| 2022 | PASS | 4.44e-16 | 63 | 0 |
| 2023 | PASS | 6.66e-16 | 33 | 0 |
| 2024 | PASS | 3.33e-16 | 54 | 0 |
| 2025 | PASS | 5.55e-16 | 85 | 0 |

(`ABC_MPR`: 48 / 114 / 98 / 107 degenerate, 0 infeasible, max error 5.55e-16.)
Six orders inside the 1e-9 tolerance, no infeasible row anywhere.

An audit inside the run confirms the residual draws used by MPR are
**byte-for-byte** the ones P4C's own weight is built from:
`eps_reproduces_P4C_weight: True` and `eps2_reproduces_ABC_weight: True` in all
four seasons. Without that, MPR would be compared against a control it does not
actually share draws with.

## 8. Developmental 2022–2025 metrics

**Previously exposed development sample — not confirmatory and not
promotion-eligible.** The block bootstrap below describes sampling variability
*within* this sample. It is not independent confirmation and no p-value is
offered as one.

Carry CRPS:

| system | 2022 | 2023 | 2024 | 2025 | pooled | Δ vs P4C | seasons better | 95% CI |
|---|---|---|---|---|---|---|---|---|
| P4C | 1.9296 | 1.9973 | 2.1103 | 2.0545 | 2.0206 | — | — | — |
| MPR_ONLY | 1.9174 | 1.9885 | 2.1126 | 2.0441 | 2.0132 | −0.0074 | 3/4 | [−0.0127, −0.0008] |
| MC_ONLY | 1.9289 | 1.9996 | 2.1115 | 2.0566 | 2.0218 | +0.0012 | 1/4 | [+0.0004, +0.0021] |
| ABC_ONLY | 1.9311 | 1.9543 | 2.0892 | 2.0372 | 2.0009 | −0.0197 | 3/4 | [−0.0268, −0.0119] |
| **ABC_MPR** | **1.8953** | **1.9362** | **2.0874** | **2.0231** | **1.9831** | **−0.0376** | **4/4** | [−0.0452, −0.0293] |

**The mechanism split, which is what `MC_ONLY` exists for:**

| component | pooled CRPS |
|---|---|
| Monte-Carlo artifact (`MC_ONLY − P4C`) | **+0.0012** |
| bias fix (`MPR_ONLY − MC_ONLY`) | **−0.0086** |
| both (`MPR_ONLY − P4C`) | −0.0074 |

Removing the sampling error in the draw mean, on its own, makes things very
slightly **worse**. The whole of MPR's gain is the bias fix. The confound is
ruled out rather than assumed away.

Randomised PIT (critical value 27.877):

| system | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| P4C | 10.7 | 21.3 | 9.0 | 9.7 |
| MPR_ONLY | **30.0** | 8.9 | 15.8 | 15.1 |
| ABC_MPR | 18.3 | 8.4 | 11.4 | 11.4 |

`MPR_ONLY` breaches the critical value in 2022. `ABC_MPR` does not, anywhere.

## 9. Low-history analysis

`E[W]` against its own centre, pooled over the four seasons, and what the
correction does to it:

| bucket | n | C | P4C E[W] | MPR E[W] | mean delta | P4C clip rate |
|---|---|---|---|---|---|---|
| established | 6872 | 0.3110 | 0.3168 | **0.3110** | 0.0128 | 0.102 |
| fringe non-appearance | 809 | 0.0752 | 0.1073 | **0.0752** | 0.1654 | 0.332 |
| veteran low recent usage | 754 | 0.0247 | 0.0712 | **0.0247** | 0.3047 | 0.458 |
| low-history other | 240 | 0.0993 | 0.1271 | **0.0993** | 0.1656 | 0.298 |
| returning from absence | 147 | 0.0776 | 0.1095 | **0.0776** | 0.1566 | 0.327 |
| true emerging | 134 | 0.1848 | 0.1976 | **0.1848** | 0.0452 | 0.165 |

The correction restores `E[W] = C` exactly in every sub-population. The
mechanical inflation is gone.

**And this is where `MPR_ONLY` fails.** Carry bias by sub-population:

| bucket | n | P4C | MPR_ONLY | MC_ONLY | ABC_ONLY | ABC_MPR |
|---|---|---|---|---|---|---|
| established | 6872 | −0.091 | +0.049 | −0.094 | −0.140 | −0.038 |
| fringe non-appearance | 809 | +1.099 | +0.777 | +1.109 | +1.225 | +1.014 |
| veteran low recent usage | 754 | +0.577 | **−0.351** | +0.598 | +0.692 | −0.061 |
| returning from absence | 147 | −1.224 | **−1.595** | −1.216 | −1.066 | −1.217 |
| **true emerging** | 134 | **−5.196** | **−5.267** | −5.182 | −4.720 | **−4.642** |

and CRPS on that last row: P4C 4.5358, **MPR_ONLY 4.7228**, ABC_MPR **4.1408**.

A uniform mechanical correction takes mass away from everyone whose centre is
low — including the backs whose true share was genuinely above it. `MPR_ONLY`
overshoots the veteran low-usage group past zero, worsens the returning group,
and makes genuine emerging backs worse on both bias and CRPS. That is
`predeclaration_p4f.md` §13 bullet 3 exactly, and it is the pre-declared ground
for rejecting it. **`ABC_MPR` does not do this** — it improves emerging backs on
both measures, because a better centre is what those players needed.

The band average alone would have hidden all of this.

## 10. Appearance interaction

The appearance model was not modified. Carry bias by history × appearance
(cells with n ≥ 40):

| cell | n | P4C | MPR_ONLY | ABC_MPR |
|---|---|---|---|---|
| <10 \| 0.50–0.80 | 428 | +0.289 | **−0.373** | +0.167 |
| <10 \| 0.80–0.95 | 246 | +0.709 | **−0.285** | +0.267 |
| 10–24 \| 0.80–0.95 | 356 | +0.462 | **−0.317** | −0.033 |
| 100+ \| ≥0.95 | 983 | −0.337 | **+0.276** | +0.051 |
| 100+ \| 0.80–0.95 | 2030 | −0.424 | −0.174 | −0.235 |

`MPR_ONLY` **flips the sign** of the bias in the low-history high-appearance
cells and in the established high-appearance cell — it does not converge on
zero, it crosses it. `ABC_MPR` stays near zero in all of them.

The answer to the directive's question: **MPR fixes conditional-share bias, and
appearance remains the dominant term for the fringe cases.** The largest
remaining positive bias anywhere is fringe non-appearance at +1.014 under
`ABC_MPR`, and it is not a share problem — those players never took the field,
so their conditional share is not the quantity that is wrong.

## 11. Joint metrics on matched estimands

Every quantity below is an **across-team-game** correlation on both sides. The
model side is computed per draw index, giving a posterior predictive
distribution for the same statistic the realised data produces.

RB1↔RB2 share correlation, `|z| = |r* − median r_m| / sd(r_m)`:

| system | 2022 | 2023 | 2024 | 2025 | inside 95% PI |
|---|---|---|---|---|---|
| P4C | 1.55 | 1.63 | 3.39 | 1.10 | 3/4 |
| MPR_ONLY | **0.08** | **0.67** | **2.71** | **0.02** | 3/4 |
| MC_ONLY | 1.81 | 1.85 | 3.38 | 1.03 | 1/4 |
| ABC_ONLY | 1.36 | 2.03 | 2.90 | 0.49 | 2/4 |
| **ABC_MPR** | **0.26** | **1.30** | **2.47** | **0.35** | 3/4 |

Criterion (fixed in §9 before scoring): `|z|` no worse in ≥3 of 4 seasons **and**
interval coverage at least the control's.

- `MPR_ONLY` **PASS** (4/4, 3 vs 3)
- `ABC_MPR` **PASS** (4/4, 3 vs 3)
- `ABC_ONLY` **FAIL** — 3/4 on the first leg but 2 inside vs the control's 3
- `MC_ONLY` **FAIL** — 2/4 and 1 inside

**The repair changed an answer.** P4E's withdrawn post-hoc reading passed
`E_ABC`; the matched criterion fails `ABC_ONLY` on the coverage leg. The rule-5
repair was not cosmetic. Note also that no system gets 2024 inside the interval:
the realised RB1↔RB2 correlation that season was −0.667 and every model's
predictive band tops out near −0.63. That is an unexplained season, and it is
left stated rather than absorbed.

## 12. Recalculated oracle accounting

The 2³ factorial re-run **with each system in the baseline corner**, which is
what P4E debt #4 asked for and what the old ratio was not.

| system | mean baseline CRPS | mean allocation Shapley | remaining, as % of P4C's | raw gain |
|---|---|---|---|---|
| P4C | 2.0229 | 1.0135 | 100.0% | — |
| MPR_ONLY | 2.0157 | 1.0086 | 99.5% | +0.0073 |
| MC_ONLY | 2.0241 | 1.0154 | 100.2% | −0.0012 |
| ABC_ONLY | 2.0030 | 0.9960 | 98.3% | +0.0199 |
| **ABC_MPR** | **1.9855** | **0.9765** | **96.3%** | **+0.0374** |

Allocation remains **48–51% of total error** under every system, so the P4C-CARRY
finding that allocation dominates survives the candidate.

The recomputed accounting lands within 0.03 percentage points of P4E's ratio
(3.7% removed either way). So the ratio was not misleading in magnitude — it was
simply the wrong quantity, and the right one now exists. **It is not used to
define a promotion threshold; the 5% rule is neither applied nor relaxed here,
because P4F has no promotion decision.**

## 13. Adversarial results

Eval season 2024, clean `ABC_MPR` CRPS 2.0874, materiality **0.010 CRPS** fixed
in advance. **18 probes: 12 PASS, 6 UNRESOLVED, 0 FAIL.**

| probe | state | seeded | gain |
|---|---|---|---|
| current-game realised carry share | PASS | 1.2324 | 0.8550 |
| current-game realised carries | PASS | 1.4086 | 0.6788 |
| current-game realised snaps | PASS | 1.6813 | 0.4062 |
| current-game RB rank | PASS | 1.6737 | 0.4137 |
| **outcome-dependent delta** | PASS | 1.3502 | 0.7372 |
| postgame roster state (well-posed) | PASS | 1.7624 | 0.3250 |
| future carry share | PASS | 2.0323 | 0.0551 |
| future teammate availability | PASS | 2.0669 | 0.0205 |
| forbidden-identifier scan | PASS | — | 0 hits |
| postgame roster state (weak) | UNRESOLVED | 2.0874 | −0.0000 |
| **future residual pool** | UNRESOLVED | 2.0906 | −0.0032 |
| evaluation-season fitted correction | UNRESOLVED | 2.0834 | 0.0040 |
| ditto, STRENGTHENED | UNRESOLVED | 2.0860 | 0.0014 |

The weak postgame-status probe is degenerate — the fit is conditional on
appearance, so the seeded column is constant across the training set and can
carry no coefficient. It is re-posed rather than counted as safe.

**The forbidden-identifier scan flagged my own code**, twice: `OUT['status']`
and then `OUT['research_status']`, because `weekly_rosters.status` is a banned
field and a token scan cannot tell my output key from a data read. I renamed the
key to `research_phase`. Narrowing the guard so my code passes would have been
the wrong way round; the code moved instead of the guard.

## 14. Guard-deletion proofs

**Three fire**, against the pre-declared minimum of two:

| proof | with guard | guard deleted | result |
|---|---|---|---|
| **GD-A** the solver targets `C`, never an outcome | 2.0874 | 1.3502 | **PASS**, 0.7372 |
| **GD-C** the infeasible-centre detector | 50 caught | 0 caught, 50 rows silently outside tolerance | **PASS** |
| **GD-D** seed a forbidden identifier past the scan | — | scan fires | **PASS** |
| GD-B the residual-pool chronology guard | 2.0874 | 2.0906 | UNRESOLVED |
| GD4 (P4E) the out-of-fold pool guard, retested | 2.0874 | 2.0915 | UNRESOLVED |

**On the two P4E guards the directive asked about.** GD1 was retested in
strengthened form, with the evaluation season entering **both** the coefficient
fit and the residual pool: gain 0.0014, still far under materiality. GD4 was
retested under MPR, where the pool also sets the shift: change −0.0040. Both
**remain explicitly UNRESOLVED**. The guards are required and are in place; what
has not been demonstrated is that they are load-bearing for CRPS. No threshold
was lowered to convert either into a pass.

Worth stating plainly: the residual-pool chronology guard deletion makes CRPS
slightly *worse*, which is evidence the pool is not a leakage channel of any
size in this design — not evidence the guard is unnecessary.

## 15. Negative findings

1. **`MPR_ONLY` is rejected.** It flattens genuine emerging backs (bias −5.196 →
   −5.267, CRPS 4.5358 → 4.7228), overshoots the veteran low-usage group past
   zero, worsens returning backs, and breaches the PIT critical value in 2022.
   A uniform mechanical correction cannot distinguish a low centre that is wrong
   from a low centre that is right.
2. **Removing Monte-Carlo error in the draw mean does not help** — `MC_ONLY` is
   +0.0012, slightly worse than P4C, and fails the matched competition
   criterion. Had this not been controlled for, the mechanism claim would have
   been unidentified.
3. **The correction does not close the allocation gap.** 96.3% of the allocation
   error remains under the best candidate, and allocation is still ~49% of total
   error. This is a bias repair, not a discrimination gain.
4. **Appearance, not conditional share, is what is wrong for fringe cases.**
   The largest remaining bias is +1.014 on players who never took the field.
5. **2024's realised RB1↔RB2 correlation (−0.667) is outside every model's
   predictive band.** No system explains that season.
6. **Four probes and two guard-deletion proofs remain UNRESOLVED.**

## 16. Candidate freeze

`nfl/research/p4f/CANDIDATE_FREEZE_ABC_MPR.md` pins the algorithm, feature set
(base + blocks A, B, C; D and E excluded on P4E evidence), solver with bracket,
iteration count, dtype and tolerance, residual construction, ridge grid and
selection rule, seeds and draw protocol, source sha256s, input-artifact sha256s,
and eligibility rules.

It records honestly that `panel_enriched.pkl` and `volume_store.npy` are **not
in the repository** — the same debt P4B and P4C carry — and that a prospective
run must verify those hashes or it is a different input generation.

## 17. Explicit statement

**NOT PROMOTED.**

P4C system C remains the accepted carry-allocation architecture and was not
modified. `MPR_ONLY` is **REJECTED**. `ABC_MPR` is **RETAINED AS A PROSPECTIVE
CANDIDATE** and is frozen for future prospective evaluation only. No result on
2022–2025 can promote it; promotion requires genuinely new prospective evidence
under a separately pre-declared rule.

## Constraints honoured

No 2026 outcomes. No markets. No DFS. No fantasy optimisation. No receiving. No
touchdown model. No J0. NFL-1 not authorised and not touched. G0A untouched at
11/12. T−90 capture not modified — the three canonical vintage-capture commits
were preserved, not rewritten. No `weekly_rosters.status`, no present-week
depth-chart state, no observed weather, no fuzzy name matching, no wager
recommended, no parlay mentioned.

---

## OWNER DECISION REQUIRED

1. **Accept the freeze of `ABC_MPR` and the rejection of `MPR_ONLY`?** The
   rejection rests on a pre-declared negative-result condition (§13 bullet 3),
   with the PIT breach as corroboration.
2. **What constitutes the prospective window?** The freeze is inert until one is
   named. 2026 outcomes are forbidden and G0A is 11/12, so there is currently no
   admissible prospective sample — the candidate is frozen against a window that
   does not yet exist, and that should be a conscious choice rather than a
   drift.
3. **The 2024 RB1↔RB2 anomaly** (realised −0.667, outside every model's
   predictive band) is unexplained and is not on any current work item. Worth a
   pre-registration of its own, or worth recording as an accepted open question.
4. **`panel_enriched.pkl` and `volume_store.npy` are still uncommitted.** Every
   research phase from P4B onward depends on them and none can be independently
   reproduced without them. This is the same shape as the MLB project's M0-D,
   and it is getting worse with each phase that builds on it.
5. **The remote URL redirect** (`nfl` → `Nfl`) should be normalised before it
   surprises a future push.

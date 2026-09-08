# TD2 — TOUCHDOWN RECOVERABILITY RETURN

**EXPLORATORY.** 2022–2025 heavily mined. **Nothing is promoted.**

| | |
|---|---|
| **Starting HEAD** | `536fd7a` |
| **Pre-registration** | `nfl/research/td2/predeclaration_td2.md` |
| **sha256** | **`31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83`** |

## 1. Estimand

**Primary, chosen on causal grounds before any result:** `P(TD | opportunity)`
— the unconditional per-target and per-carry rate. TD1's identity already
carries location as its own component `Z`; conditioning conversion on realised
red-zone opportunity would fold part of `Z` into `K`. Unit of evaluation is the
**opportunity**, so trial-level metrics are exact from counts.

Ten estimands were measured for support first; all ten have it. Base rates:
receiving 0.0457 (target) → 0.4765 (inside-5); rushing 0.0347 (carry) → 0.4133
(inside-5). **End-zone targets remain UNAVAILABLE.**

## 2. Sample

| | opportunities | TDs | base rate |
|---|---|---|---|
| receiving \| target | 67,672 | 3,087 | 0.04562 |
| rushing \| carry | 56,293 | 1,956 | 0.03475 |

QB rushing included: 7,627 carries, 432 TDs; designed (1,838 TDs) kept separate
from scrambles (140).

## 3. Ladder — the pooled baseline wins

| arm | rec log loss | vs best baseline | rush log loss | vs best baseline |
|---|---|---|---|---|
| B_league | 0.185463 | −0.347% | 0.150944 | −0.638% |
| **B_pos** (best baseline) | **0.184822** | — | **0.149987** | — |
| B_pos_loc / L0 | 0.184895 | −0.040% | 0.150685 | −0.465% |
| L1 empirical-Bayes | 0.186218 | −0.755% | 0.151807 | −1.213% |
| L2 EWMA | 0.307201 | **−66.2%** | 0.232858 | **−55.3%** |
| L3 shrunk EWMA | 0.197967 | −7.112% | 0.158061 | −5.383% |
| **L4 logistic** (best rung) | 0.184741 | **+0.043%** | 0.150175 | **−0.125%** |

**AUC 0.5442 (rec) and 0.5628 (rush)** — barely above chance. The best rung's
95% game-clustered CI on log loss overlaps the baseline's almost entirely.

**Resolution gain over the baseline: −5.3e-06 (rec), +2.9e-05 (rush).** So
receiving's tiny log-loss gain comes with **negative** resolution — it is
**shrinkage, not signal**, exactly the case the metric set was built to catch.

**Recency is actively harmful.** L2 loses 66% (rec) and 55% (rush).

## 4. Persistence — the decisive evidence

The hypothesis was tested, not assumed, and **opportunity and conversion were
measured identically** so the comparison means something.

| horizon | | conversion r | **opportunity r** |
|---|---|---|---|
| split-half | receiving | +0.2912 | **+0.9441** |
| | rushing | +0.4594 | **+0.9702** |
| year-to-year | receiving | +0.2153 | **+0.7865** |
| | rushing | +0.3538 | **+0.7699** |
| prior→next game | receiving | +0.0826 | **+0.5909** |
| | rushing | +0.1223 | **+0.6764** |

**Opportunity persists dramatically more than conversion at every horizon and
in both kinds.** At the game level — the level a forecast operates at —
conversion persistence is +0.08 / +0.12 against opportunity's +0.59 / +0.68.

Rushing conversion persists more than receiving (+0.46 vs +0.29 split-half),
and established players show more than low-history ones in rushing (+0.147 vs
+0.060). Both are exploratory subgroup observations, not findings.

## 5. Composition — the mandatory gate

`V`, `S`, `Z` frozen; substitution draw-preserving.

| | control CRPS | L4 CRPS | rel | 95% CI on the difference |
|---|---|---|---|---|
| receiving | 0.135617 | 0.135460 | +0.1155% | **[−0.000359, +0.000639]** |
| rushing | 0.061035 | 0.060784 | +0.4125% | **[−0.000129, +0.000630]** |

**Both intervals span zero.** Receiving is split 2/2 by season; rushing 3/4.
Composition does not worsen, and it does not distinguishably improve.

## 6. Recovered oracle opportunity

**This model family recovered 0.15% (receiving) and 0.55% (rushing) of the
measured TD conversion oracle opportunity** — 0.000157 / 0.10382 and
0.000252 / 0.04582 CRPS.

TD1's 76.55% and 75.07% attributions are **not** modelability, and this is the
measurement that separates them.

## 7. State classification

# `SIGNAL_WEAK` — both receiving and rushing

Per the predeclared rules: log-loss gain below 1% in both kinds, and for
receiving the gain carries **no** resolution. Not `COMPOSITION_FAILED` —
composition did not worsen.

**TD2 does not establish an information ceiling and does not claim one.**

## 8. Adversarial tests and guard deletions

`nfl/tests/test_td2_recoverability.py` — **52 assertions, 0 failures.**
Current-game, future-game and same-week leakage (1,318 collisions, 0 leaks);
current TD not entering historical conversion; current red-zone opportunity not
entering predictors; two-point, defensive TD and fumble/blocked-kick TD
exclusions; no pass/rush double attribution (measured over 281,339 plays, **not
inferred from a missing key**); null yardline excluded rather than coerced to 0;
denominators; walk-forward fitting; metric correctness.

**Guard deletions:** the chronology prefix cut (bypassed → 449 shared-ordinal
pairs leak) and `td2_lib.metrics` (bypassed → a constant-at-base predictor
reports resolution 1.0 and reads as signal).

## 9. Defects discovered — three, all mine

1. **AUC was inverted.** The block accumulator counted positives *below* rather
   than above, returning 0.253 for a perfect predictor. Fixed; now matches the
   hand calculation 60.5/81 = 0.7469 exactly.
2. **The Murphy decomposition did not close.** Quantile bins leave a within-bin
   variance residual (~1e-4 — small enough to look like rounding, large enough
   to be wrong). Both are now reported: an **exact** unique-value decomposition
   that closes to 7e-18, and the **binned** resolution which is the
   interpretable discrimination measure and which the state rules use.
3. **My own test assertion was wrong.** I asserted a shrunk predictor gains less
   resolution than an unshrunk one. It does not — quantile bins preserve
   ranking, so resolution is **invariant to shrinkage**. That is *better* than
   what I assumed and is exactly why resolution is the right discrimination
   test. The assertion now states the true property, and adds that destroying
   the ranking destroys resolution.

Also: TD1's audit JSON was a `Counter`, so `td_BOTH_pass_and_rush` was *absent*
rather than zero. Re-measured explicitly — the absence-as-zero trap again.

## 10. Production decision (§5A)

**Production uses the accepted control** — TD1's per-player history shrunk
toward positional pools. No candidate distinguishably beats it, `B_pos` is
close but nominally worse on receiving composition, and switching would be a
promotion from mined data. **No production change is required.**

## 11. Unresolved information gaps

Registered in `nfl/INFORMATION_GAP_REGISTRY.json`: end-zone targets
(UNAVAILABLE), receiver-specific coverage/matchup (HOLD), true routes
(BLOCKED). TD2 changes none of them.

## 12. Recommended next question — **recommendation only, not begun**

**Does TD *opportunity* allocation — specifically red-zone and goal-line share
— carry recoverable signal?** Persistence says opportunity is where the
predictable structure lives (+0.59 to +0.97 against conversion's +0.08 to
+0.46), and TD1 put red-zone allocation `Z` at ~13% of oracle attribution —
larger than player share `S` and team environment `V`. That is the highest-value
unblocked TD question, and it is the opposite of where the 75% attribution
pointed.

---

**G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. P4C unchanged. ABC_MPR
unchanged. No candidate promoted. No 2026 outcomes used. No FTN used.**

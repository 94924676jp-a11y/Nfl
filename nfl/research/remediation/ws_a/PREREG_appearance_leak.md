# WS-A PREREGISTRATION — the appearance V1-presence leak

**Written before any candidate was implemented or fitted.** The only numbers in
this file are the ones already in `nfl/research/remediation/WAVE0_BASELINE.json`
and `nfl/research/parallel_pass/ws04/WS04_NONQB_APPEARANCE.md`, plus four
structural counts re-measured from the frame on 2026-09-14 to confirm the
defect is still live (§1.1). Nothing here was chosen after seeing a candidate
result. The hash of this file is cited in `WS_A_APPEARANCE_LEAK.md`.

Repository `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `837d52f0d448527bd52a2aedc26362cb17611a08`. Interpreter python3.12.

**Scope limits, declared up front.** Research only. No production file is
modified. `nfl/production/nonqb/appearance_r8.py`, `appearance_r7.py` and
`layers.py` are imported read-only and never edited; `layers.py` is hashed by
Q9's frozen candidate identity `481f005f682cd721`. No sportsbook data of any
kind is opened. No coefficient is hand-set or tuned; every arm is fitted by
`stage_a.fit_logistic` with the same hyperparameters.

---

## 1. The defect, stated as a structural claim

`appearance_r8._panel_v1_features` (`appearance_r8.py:99-118`) keys the V1
feature block on the rows of the **frozen P3 panel**, and
`enriched_frame` (`:196-198`) joins it onto the **union frame** by
`(season, week, team, gsis_id)`. A player has a panel row for a team-week iff
he took a snap or was a `LOOKBACK_CANDIDATE` zero row. A union-frame row that
the depth chart contributed and the panel did not therefore has no block.

At prediction time `predict` (`appearance_r8.py:415-424`) fills the block for
**every** player from `AM.prospective_feature_rows`, because at serve nobody
knows who played.

So `featurise`'s last column (`appearance_r8.py:295`,
`f.append(1.0 if r.get('v1') is None else 0.0)`) plus the twelve
per-feature missingness flags carry, in training, a quantity that is a function
of the realised label, and at serve carry a constant. That is simultaneously
**leakage** (a covariate determined by the outcome) and **train/serve skew**
(its distribution at serve is not the one fitted on).

### 1.1 The four structural counts re-measured 2026-09-14, before any candidate

| quantity | value |
|---|---|
| union frame rows (`R8.enriched_frame`) | 59,784 |
| rows with the V1 block | 53,626 (appearance rate 0.7119) |
| rows without the V1 block | 6,158 (appearance rate **0.0000**) |
| `v1_present == in_panel` | 0.999615 |

`P(appeared = 1 | V1 block absent) = 0` exactly, on 6,158 rows. This is not an
estimate with a confidence interval; it is a property of how the join key is
built, and no resampling scheme can make it otherwise. WS04's counts (53,381 /
6,158) differ from the present-row count only because WS04 counted after
dropping the `no_history_and_not_depth_listed` cell; the absent count and its
0.0000 rate reproduce exactly.

---

## 2. Why an in-frame walk-forward cannot detect this, and what replaces it

The leak is **not** a train/test skew. A held-out season built the same way
carries the same deterministic cell, so a forward-chained evaluation *on the
frame* rewards the leak instead of exposing it. `nfl/research/q6/
Q6_FORWARD_CHAIN_RESULTS.json` reports exactly such a figure for the R8 arm —
n = 34,621, Brier 0.090724, log loss 0.293054 — and that number is flattered by
the defect rather than a measurement of it.

The evaluation therefore has to reproduce **the serve-time feature basis** on
weeks whose labels are known. Three bases are defined, and every arm below
declares which one it trains on and which one it is scored on.

**P-join** — the current production basis. Block keyed on panel rows.
Absent on 10.3% of frame rows.

**S-serve** — production as actually deployed, replayed on a historical week.
For target week `(S, W)`: take the panel truncated to `ord < S*100 + W`, append
one zero-opportunity panel-shaped row for **every** union candidate at
`(S, W)` with `did_not_appear = None`, run `appearance_model._walk` then
`p3_features.enrich`, and read the block off the target-week rows. This is what
`appearance_model._prospective` does for 2026, with the panel truncated so that
no row at or after the target week enters any history. Presence = 1.0 by
construction.

**U-union** — the Candidate B basis. The same walk, but the panel is extended
with a zero-opportunity row for every union candidate at **every** week, so the
history each row is built from is the union candidate universe rather than the
panel. Presence = 1.0 by construction.

---

## 3. Arms

Two of these are promotion candidates. The other three are controls and are
declared as controls so that the multiple-comparison budget is spent on two
arms, not five.

| arm | role | train basis | score basis | featuriser |
|---|---|---|---|---|
| `BASE_INFRAME` | diagnostic control | P-join | P-join | `R8.featurise` verbatim |
| `BASE_SERVE` | **the pre-repair failure** | P-join | S-serve | `R8.featurise` verbatim |
| `A` | **candidate** | P-join, presence-neutralised | S-serve | `featurise_A` |
| `B` | **candidate** | U-union | U-union | `featurise_B` |
| `A0` | bounding control | no V1 block | no V1 block | `featurise_A0` |

`BASE_INFRAME` exists only to quantify how much the leak flatters an in-frame
walk-forward. `A0` exists only to bound how much of the V1 block's contribution
was legitimate. Neither is eligible for promotion and neither enters the
multiplicity correction.

### Candidate A — presence-neutralised featuriser, frame untouched

**Mechanism.** Keep the panel join exactly as it is. In the featuriser:
delete the `v1 is None` column; delete all twelve per-feature missingness
flags; and replace every `0.0`/`or 9`/`or 0.0` default for an absent V1 value
with the **mean of that feature over the training rows that have the block**,
computed on `s < S` only and recomputed at each walk-forward cut. Nothing else
changes. At serve no imputation ever fires, because the block is always present.

**Predicts.** The explicit presence channel is gone, so the presence bit cannot
be read directly. `BASE_SERVE`'s mean-prediction inflation should shrink
substantially, the cold-start and long-absence cells should stop being driven
to ~1, and the sign of the association between prior participation and the
prediction should return to positive.

**Falsified if** the S-serve calibration-in-the-large gap, the cold-start cell
and the carried-absence cell are statistically indistinguishable from
`BASE_SERVE` under the predeclared margin. That outcome would say the leak does
not travel through the explicit flags but through the imputed value vector
itself being identifiable — which is the hypothesis motivating B, and A failing
this way is informative rather than wasted.

**Known weakness, stated in advance.** Mean imputation places every absent row
at one point in 12-space. A linear model can still partially separate that
point. A is therefore *not* expected to be structurally clean, only
empirically better. It is preregistered because "delete the flag" is the
cheapest possible repair and the project is entitled to know whether the
cheapest repair is enough.

### Candidate B — recompute the block over the candidate universe

**Mechanism.** Build the V1 block on the **U-union** basis: extend the panel
with a zero-opportunity panel-shaped row for every union candidate row the
panel lacks, then run the same frozen `_walk` + `enrich`. Every union frame row
then has a block. The featuriser is `R8.featurise` with the `v1 is None` column
deleted (it is identically zero and a constant column is not a feature). The
twelve per-feature missingness flags are **kept**, because under this basis a
missing `f_rate3` means "no prior row at all", which is a causal cold-start
fact and not the label.

**Predicts.** Feature presence becomes a constant, so it carries no information
in training and cannot skew at serve. The 6,158-row deterministic-zero cell
disappears. Discrimination should be at least as good as `BASE_SERVE`, because
the leaked bit was worth AUC 0.6425 *in training* but is uninformative at
serve. Calibration by carried absence and by prior participation should be
monotone and correctly signed, matching the frame's own rates
(.1436 / .2479 / .4951 / .7898 / .9041 by `app_ewma`).

**Falsified if** any of: presence is not 1.0000 in both train and serve
populations; the label-flip invariance test in §5 fails; B's S-serve-equivalent
Brier is worse than `BASE_SERVE`'s by more than the non-inferiority margin;
the prior-participation association remains negative.

### Candidates considered and rejected before implementation

**C-roster — rebuild the frame over the full pregame-eligible roster universe.**
This is the ideal version of B and it is **not constructible in this
repository**. Weekly roster membership is available for 2026 through the
capture vintages; for 2020-2025 the repository holds the panel, the weekly
depth charts `dc_2020..dc_2024` and `dc25_daily`, and nothing that enumerates
the 53-man roster. Building it would require bytes from outside this checkout
and is therefore a request for the networked agent, not a candidate here. Its
absence is a measured limit on B, recorded in §7, not a silent one.

**C-refit — refit R8 on the existing design with regularisation raised on the
presence columns.** Rejected: it is a coefficient patch on a leaking design,
which is the named work to stop doing.

**C-drop-frame-rows — drop the 6,158 blockless rows from the fit.** Rejected,
and it is the tempting one. Dropping them restores exactly the
`LOOKBACK_CANDIDATE` censoring that R7 exists to lift: the dropped rows are
precisely the depth-listed non-appearers, so the fit would again see a
population in which absence is under-represented. It would also make the
training appearance base rate 0.7119 against a frame rate of 0.6606.

**C-two-model — one model for blockless rows, one for block-bearing rows.**
Rejected: the router is the leaked bit, so this hard-codes the leak as
architecture.

---

## 4. Acceptance criteria

All of these are conditions on the evidence, not on the direction of the
result. A candidate that fails any structural criterion is not recommended
regardless of its score.

**Structural (pass/fail, no statistics involved).**

- S1. **No label-dependent feature presence.** For the candidate's own basis,
  the fraction of training rows carrying the V1 block must be 1.0000, and
  `P(appeared | block absent)` must be undefined for want of any such row.
- S2. **Label-flip invariance.** Recompute the target-week feature block with
  every target-week row's `did_not_appear` flipped, and assert every V1 value
  on every target-week row is bit-identical. This demonstrates structurally,
  not just empirically, that no current-week label enters a current-week
  feature.
- S3. **Train/serve feature-availability parity.** Presence rate and the
  marginal mean and sd of each of the twelve V1 numerics, reported side by side
  for the training population and the serve-shaped population. Declared in
  advance: parity is *claimed* only where presence rates are equal to four
  decimals and every numeric's standardised mean difference is below 0.10. A
  feature failing that is named, not averaged away.
- S4. **No sportsbook input.** The feature-name list of every arm is checked
  against the `FORBIDDEN_INPUTS` list `nfl/research/q6/frame.py` already uses,
  and no odds, price or line file is opened by this harness.
- S5. **Forward-chained, never in-sample.** For evaluation season `S` every arm
  is fitted on rows with `s < S` only, and the reliability constant `k` is
  estimated with `cut = S*100`. Any row with `s >= S` reaching a training set
  is a named failure of the harness, not a filtered surprise.

**Quantitative (predeclared endpoints).**

- Q1. Primary endpoint: **Brier score on the serve-shaped evaluation rows**,
  pooled over evaluation seasons. For a Bernoulli forecast the continuous
  ranked probability score is identical to the Brier score, so CRPS is reported
  as that identity rather than as a separate number.
- Q2. Log loss, and AUC as the ranking statistic.
- Q3. Calibration-in-the-large: mean predicted minus observed rate.
- Q4. Calibration **by week bucket** (1, 2-4, 5-9, 10-18), **by depth rank**
  (r1, r2, r3, r4plus, unlisted), **by prior participation** (`app_ewma`
  None, <0.05, [0.05,0.5), [0.5,0.95), [0.95,1]) and **by carried absence**
  (`cm_carried` 0, 1-3, 4-8, >=9).
- Q5. Cold start: rows with `n_prior == 0`, and rows with `n_cur == 0`.
- Q6. Ranking sanity: pooled AUC, plus the within-team-week Spearman
  correlation between the prediction and the depth rank, plus the mean
  prediction of the top-5-by-prediction cell against its realised rate.
- Q7. The inversion diagnostic that WS04 found: `pearson(app_ewma, p)` and
  `pearson(cm_carried, p)` among listed, non-designated rows. Signs are
  predeclared: the first must be positive and the second negative.

**Uncertainty (predeclared).**

- U1. Games are not independent. Every interval is a **cluster bootstrap**
  resampling whole `(season, week, team)` clusters with replacement,
  `B = 1000`, seed `20260914`. A second set is reported clustering by date
  `(season, week)`. Naive binomial intervals are not reported at all.
- U2. Paired differences between arms are computed on the **same** resampled
  clusters, so an arm-vs-arm interval is a paired one.
- U3. **Equivalence margin for calibration-in-the-large: ±0.02 absolute.**
  A two-one-sided test at α = 0.05 against that margin is the only thing that
  licenses the word "calibrated" in the results. Failure to reject a null is
  reported as failure to reject and nothing more.
- U4. **Non-inferiority margin for the primary endpoint: +0.005 Brier.**
  A candidate is non-inferior to `BASE_SERVE` if the upper bound of the paired
  cluster-bootstrap interval on (candidate − `BASE_SERVE`) is below +0.005.
- U5. **Multiplicity.** Two promotion candidates, one primary endpoint.
  Bonferroni: each candidate is tested at α = 0.025 two-sided on the primary
  endpoint. Subgroup results in Q4-Q7 are descriptive and are reported without
  inferential claims.

**Pathological cases, tested explicitly (Q8).** Each is defined as a structural
cell so that it can be evaluated on labelled historical weeks:

- clear RB1 — `pos == 'RB'` and `rank == 1`
- WR1 — `pos == 'WR'` and `rank == 1`
- long-absence player — `cm_carried >= 9`, and separately `app_ewma < 0.05`
- practice-squad / reserve candidate — depth-listed with `rank >= 4` and
  `n_prior < 4`; and the harder cell, `rank is None` with `n_prior > 0`
- week-1 cold start — `w == 1` and `n_cur == 0` and `n_prior == 0`
- a known governing inactive — **there is no labelled historical analogue.**
  The repository's only ingested governing inactive list with skill positions
  is TB@CIN 2026 week 1 (WS04 finding 4: Jack Endries INACTIVE at p = 0.9920,
  Ke'Shawn Williams INACTIVE at 0.5016). DAL@NYG has **no** governing list —
  its earlier `OFFICIAL_INACTIVE` labels came from a `governing: false`
  screenshot and are now `DISCOVERY_ONLY_NOT_GOVERNING`. Endries is a 2026
  rookie and appears in no historical frame row, so the cell he occupies —
  cold start, depth-listed, week 1 — is reported instead, and the substitution
  is stated rather than hidden. Whether any appearance model can know about a
  gameday inactive list it never reads is a **specification** question
  (WS04 finding 3), not something these candidates address, and no candidate
  here claims to fix it.

---

## 5. What will be reported even if it is unflattering

- The in-frame figure beside the serve-shaped figure, so the size of the
  self-deception is visible.
- Every subgroup where a candidate is worse than `BASE_SERVE`.
- The residual universe gap: union-frame rows are panel-or-depth-listed, while
  production at serve scores a roster list (DAL@NYG 178 -> 106 -> 30 players).
  A player with history, not depth-listed, who does not play still produces no
  frame row under B. B narrows the censoring; it does not close it, and the
  claim will be stated that narrowly.
- If the data cannot separate the candidates, that is the finding.

## 6. What is exploratory and what is confirmatory — declared now

**Exploratory, all of it, with one exception.** The hypothesis was selected from
the 2026 week-1 slate and the historical panel, and every evaluation below runs
on that same historical panel. Freezing it does not make it a holdout and
writing this file first does not restore independence. Every score in the
results document is labelled EXPLORATORY.

**The exception is not statistical.** S1 and S2 are structural properties of a
construction — a presence rate of exactly 1.0000 and bit-identical features
under a label flip are proofs, not estimates, and they do not become more or
less true on a different sample. They are labelled STRUCTURAL and are the only
claims made without a holdout.

**What would make a confirmatory claim possible** is stated in the results
document and is not available today.

## 7. Declared limits

- Evaluation seasons `(2022, 2023, 2024, 2025)`; 2020 and 2021 are the training
  runway. The choice matches `nfl/research/q6/frame.py:EVAL_SEASONS` and was
  not selected on any result.
- The full pregame-eligible roster universe is not constructible for 2020-2025
  in this checkout (§3, C-roster). B is evaluated over the union candidate
  universe, which is the largest one this repository can build.
- All four seasons are pooled for the primary endpoint. Per-season figures are
  reported but each season is a single walk-forward fold and no per-season claim
  is made.
- `l2 = 1.0` and `iters = 300` for every arm, inherited from
  `stage_a.fit_logistic` and `appearance_r8.fit`, not chosen here.
- Nothing in this document authorises a production edit. The deliverable is a
  recommendation with its evidence, or an explicit statement that none is
  supported.

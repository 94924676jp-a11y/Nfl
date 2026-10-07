# Showdown cheap rotation-player ownership successor — pre-registration (SC-OWN-ROTATION-1 shadow)

Written 2026-10-07 **before any model below was fitted or scored**. Its sha256 is recorded in the result artifact
(`nfl/postgame/dupe_research/CHEAP_OWNERSHIP_LOSO.json`, key `prereg_sha256`), and the code refuses to run if the
file is absent or empty. Status of everything here: **SHADOW_ONLY**. Nothing changes the football forecast, the
simulator, the DFS portfolio objective, the readiness rules, the shadow field module or any production lineup.

## 0. What is being fixed, and contamination stated first

The frozen prelock shadow ownership (`nfl/field/showdown_shadow_field.py`: K = 5,000 DK-legal optimizer builds over
a public projection with lognormal noise, sigma 0.6) gives near-zero ownership to cheap active rotation players that
the optimum leaves out. The ATL@NO postgame recorded the miss (B. Robinson Jr. 17.6% FLEX actual vs 0.0 / 1.0
shadow; Bryce Lance 21.8 vs 6.4 / 9.4; `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_REPORT.md`).

**The defect was found on ATL@NO, and the bucket thresholds and features below were written by someone who has read
that report.** The ATL@NO fold is therefore **development data**. The PIT@CLE fold is less contaminated — its
actual per-player ownership of cheap players has not been looked at by the author of this document — but the
feature list was still written after ATL@NO. The salaries of both pools (prelock information) were looked at while
writing the thresholds. **Every result is EXPLORATORY.** A confirmatory test is prospective only (section 8).

## 1. Slates, baselines and what is available

| slate | contest (primary) | DK salaries | prelock baseline ownership forecast | testable |
|---|---|---|---|---|
| PIT_CLE | 196187080 (20-max) | yes (owner DK export) | **no frozen prelock forecast exists**. Reconstructed after the game from prelock-dated inputs only (section 1.1); labelled `RECONSTRUCTED_POSTGAME_FROM_PRELOCK_INPUTS` | yes, with that label |
| PHI_CHI | 196036243 (20-max) | **no** (outbox request 2026-10-07 filed) | **none** (no salaries, no public projection) | **NOT_AVAILABLE** — never reported as a pass |
| ATL_NO | 196285160 (20-max, primary); 196285137 (150-max) and 196285161 (2-entry) supplementary | yes | **frozen prelock**: FC_ONLY `SHADOW_RW_INACTIVES_CHARTFIX/` and BLEND `SHADOW_RW_INACTIVES_CHARTFIX_BLEND/` (committed 9736516 before lock) | yes |

### 1.1 The PIT@CLE baseline reconstruction

The same function, the same constants and the same seed as the frozen ATL@NO run: `showdown_shadow_field.field()`
at sigma = 0.6 (the sigma the frozen ATL@NO production run chose), K = 5,000, seed 20261005, over the PIT@CLE
FantasyCruncher sheet (`THIRDPARTY_showdown_PIT_CLE_2026W4_CONTEXT_ONLY.csv`, supplied 2026-10-01, game day; its
capture time relative to lock is NOT recorded in the repository) with the suffix-alias reconciliation already used
by `showdown_history_calibration.generated_fields` (E4), and the official inactives
(`OFFICIAL_INACTIVES_PIT_CLE_2026W4.json`) as the absent set. Before use, the code re-runs the same function on the
ATL@NO frozen inputs (official FC file 330fdd51, frozen absent list) and refuses to continue unless it reproduces
the frozen FC_ONLY ownership exactly. That shows the method reproduces; it does not make the PIT@CLE baseline a
frozen forecast.

### 1.2 FC boundary (unchanged)

FantasyCruncher enters **only** through the baseline shadow ownership, exactly as it already does in
`showdown_shadow_field.py` (its FLEX `FC` projection column, nothing else). No FC column (pDepth, Inj, VegasPts,
Exp., Floor, Ceiling) is a feature of the successor. FC is never a football model input; this work is not a
football model.

## 2. Prelock features (all knowable before the slate locks)

Built by a function that **does not accept contest entries** (the evaluated slate's or any other's):

| feature | source | rule |
|---|---|---|
| salary (FLEX, CPT) | DK pool in the owner's export | as priced |
| position, club | DK pool | as priced |
| active / absent | ATL: the frozen absent list fed to the frozen baseline (`SHADOW_ABSENT_RW_INACTIVES_CHARTFIX.json`); PIT: official inactives | absent players are excluded from evaluation; their realised ownership is reported, not scored |
| snap share history | nflverse `snap_counts_2026` (`raw/showdown_atl_no_2026W4/snap_counts_2026.53720f39...csv`) | **2026 REG weeks strictly before the slate week (both slates are week 4: weeks 1-3)**; the file also holds week 4 rows for PIT/CLE (the evaluated game) and those are dropped by the week filter, which a test asserts |
| targets, carries history | `nfl/derived/USAGE_HISTORY_2021_2026.json` (2026 weeks 1-3) | weeks < slate week; a missing week is UNKNOWN, never zero |
| identity (name -> gsis) | nflverse `roster_weekly_2026` | identity columns only; the `status` column is a post-hoc gameday outcome and is NOT read |
| routes | — | **NOT_AVAILABLE** in this repository; not used |
| depth rank (all) | snap share history | rank of mean prior-week offensive snap share inside club x position group (QB; RB incl. FB; WR; TE) over every club player with a prior row |
| depth rank (active) | same | the same rank among players in the DK pool who are not absent |
| injury-created opportunity | depth ranks | 1 if depth rank (active) < depth rank (all): a teammate ahead of him is absent or no longer in the pool |
| starter designation | depth rank (active) | starter if rank <= QB 1 / RB 1 / WR 3 / TE 1 (PRIOR) — stored, not fitted |
| role evidence | snap history + depth rank | at least one prior week AND (depth rank (active) <= QB 1 / RB 2 / WR 4 / TE 2, OR mean prior snap share >= 0.20) (PRIORS) |
| salary relief | salary | (50,000 / 6 - FLEX salary) / 1,000 — stored, not fitted |
| optimizer feasibility | baseline | 1 if the baseline field rosters him at all — stored, not fitted |
| scarcity | buckets | number of CHEAP_ROTATION players on the slate, and his salary rank inside that bucket — stored, not fitted |
| role uncertainty | snap history | number of prior weeks with a row, and the SD of prior snap share — stored, not fitted |

## 3. Buckets (prelock fields only)

Evaluated in this order; the first match wins:

1. **K_DST** — position K or DST.
2. **PUNT_FRINGE** — FLEX salary <= $1,000, or no role evidence (this includes backup QBs priced at $6,000 with no
   prior snaps).
3. **STAR** — role evidence and FLEX salary >= $8,000.
4. **MIDRANGE** — role evidence and $4,000 <= FLEX salary < $8,000.
5. **CHEAP_ACTIVE_ROTATION** — role evidence and $1,000 < FLEX salary < $4,000.

Threshold sources: $1,000 is `CHEAP_SALARY` in `nfl/dfs/showdown/candidates.py` (the candidate generator's punt
line). $4,000 and $8,000 are **declared PRIORS** (round lines on the DK Showdown FLEX scale; $8,000 is where the six
highest-priced players of both available pools end), chosen after reading the ATL@NO report, in which the
motivating miss was priced $3,800. The role slots and the 0.20 snap-share line are **declared PRIORS**.

## 4. Candidate model (few parameters)

For each slot s in {CPT, FLEX} separately, over the active players of a slate:

    q_i  proportional to  exp( t0 * log(b_i + kappa) + t1 * CHEAP_i + t2 * FRINGE_i + t3 * snap_share_i + t4 * injury_opp_i )
    predicted % = q_i * M_s,   M_CPT = 100, M_FLEX = 500

b_i is the baseline forecast (%) for that slot. At t = (1, 0, 0, 0, 0) the candidate is the baseline with a kappa
floor, renormalised, so the model is a multiplicative correction of the baseline by bucket and role features.
snap_share_i is the mean prior-week offensive snap share (0 when there is no prior row; the row count is stored).

- kappa = 0.5 percentage points (PRIOR; so a zero baseline is correctable at all).
- Fitted per slot by penalised maximum likelihood of the training slate's realised slot shares
  (multinomial cross-entropy, Newton's method), with a Gaussian prior centred on t = (1, 0, 0, 0, 0),
  penalty (lambda / 2) * ||t - t_prior||^2, lambda = 0.01 (PRIOR, for a finite unique solution).
- 5 parameters per slot, 10 in all, fitted on ONE training slate per fold.

## 5. Held-out design

Leave-one-slate-out. A slate's entries are never used to fit anything scored on that slate, and the code refuses a
fold whose training set contains its test slate.

| fold | train | test | baseline on the test slate |
|---|---|---|---|
| A | PIT_CLE (reconstructed FC_ONLY baseline; contest 196187080 realised shares) | ATL_NO 196285160 (primary); 137 and 161 supplementary | frozen FC_ONLY **and** frozen BLEND (the correction fitted on FC_ONLY is applied to each) |
| B | ATL_NO (frozen FC_ONLY baseline; contest 196285160 realised shares) | PIT_CLE 196187080 | reconstructed FC_ONLY |
| C | — | PHI_CHI | **NOT_AVAILABLE** (no salaries, no baseline) |

## 6. Metrics (per test contest)

Over active players: MAE and signed bias (predicted - actual, percentage points) of CPT % and FLEX % for each bucket,
with the bucket's n; MAE of total ownership (CPT + FLEX) over all active players. Actual ownership = share of the
contest's filled entries rostering the player in that slot, computed from the entries. Reported but not in the bar:
FLEX RMSE and KL(actual || predicted) over FLEX shares with predictions floored at 1e-4 (the SC-OWN-ROTATION-1 bar
registered in `ATL_NO_SUCCESSOR_CANDIDATES` / `showdown_atl_no_final.py`), the per-player rows of the cheap bucket,
and the realised ownership of absent players.

## 7. Pass bar (per testable fold; fixed here, never loosened afterwards)

A fold **PASSES** only if all of the following hold on its primary test contest, against every listed baseline
(fold A: both FC_ONLY and BLEND):

1. CHEAP_ACTIVE_ROTATION FLEX MAE: candidate **strictly lower** than baseline.
2. CHEAP_ACTIVE_ROTATION FLEX |signed bias|: candidate <= baseline.
3. CHEAP_ACTIVE_ROTATION CPT MAE: candidate <= baseline + 0.5 pp.
4. Every other bucket (STAR, MIDRANGE, PUNT_FRINGE, K_DST), each slot: candidate MAE <= baseline MAE + margin,
   margin **1.0 pp FLEX, 0.5 pp CPT**.
5. Total-ownership MAE over all active players: candidate <= baseline + 1.0 pp.

Margin sources: 1.0 pp is half of the 2-point ownership materiality tolerance already declared in
`showdown_history_calibration.TOL['OWNERSHIP_POINT_PCT_PTS']` (ledger DATA-05); 0.5 pp is
`TOL['RECOUNT_FLAG_PCT_PTS']`. Both are PRIORS for this use.

A fold is **NOT_TESTABLE** (never a pass) if the test slate lacks salaries or a baseline, if its training slate
lacks either, or if the test slate has fewer than 3 CHEAP_ACTIVE_ROTATION players.

**Overall verdict:** `FAIL` if any testable fold fails; `PASS_EXPLORATORY_SHADOW_ONLY` only if every testable
fold passes and at least 2 folds are testable; otherwise `NOT_TESTABLE`. Supplementary contests (ATL_NO 137 / 161)
are scored against the same bar and reported, and do not enter the verdict. Sensitivity runs (lambda = 0;
kappa = 1.0) are reported and do not enter the verdict.

**The evidence is weak and this document says so in advance.** Two testable folds, each one slate, each one
training slate of roughly 30-45 active players. Players on one slate are not independent observations (one field,
one news cycle, one optimizer); the unit of evidence is the slate, so n = 2. A PASS is a reason to keep the shadow
running, never a promotion.

## 8. Confirmatory test (prospective)

On each future Showdown slate with DK salaries, the frozen shadow baseline and the successor (fitted on all prior
archived slates) are both written before lock and scored after standings arrive, against this bar. Promotion
requires the owner's rule; the SC-OWN-ROTATION-1 proposal is >= 8 Showdown slates.

## 9. Known limitations (declared before fitting)

PIT@CLE has no frozen prelock forecast (reconstructed); the PIT@CLE FC sheet's capture time vs lock is not
recorded; snap counts and usage for weeks 1-3 were captured after the PIT@CLE game (week filter applied; later
revisions by nflverse cannot be ruled out); no routes data; ATL@NO is development data; thresholds and priors were
chosen after the motivating miss; PHI@CHI is unusable for a salary model; the model is fitted on one slate per fold.

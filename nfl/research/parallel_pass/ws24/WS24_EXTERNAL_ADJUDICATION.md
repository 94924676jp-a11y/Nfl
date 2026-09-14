# WS24 — Adjudication of the external DAL@NYG forensic audit

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws24/` was
written. No production module, no sealed artifact, no test was modified. No
market data was opened. Nothing here authorises a repair.

**Reviewed document:** `98995c6c-DAL_NYG_EXTERNAL_FORENSIC_AUDIT.md`
(24,345 bytes, read in full).

---

## 0. The scope error that governs half the verdicts

The external review audits **one** of two sealed artifacts that sit side by side
in `nfl/research/live/2026_01_DAL_NYG/`, and it does not say which. Every number
it quotes — Abanikanda 4.79, Harris 4.79, DAL non-QB budget 17.54, NYG 20.11,
Milton above Prescott — reproduces **exactly** from
`pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0/`, and **none** of them
reproduces from `FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/`, where
Abanikanda and Harris are at 0.000 carries and Milton is at 0.000 dropbacks.

Measured, from the sealed draw matrices (`player_draws.npz`, 8,000 draws):

| quantity | PRE `3dddf9f6` | FORENSIC `4b186a21` |
|---|--:|--:|
| Abanikanda `rushing/carries` mean | **4.791287** | **0.000000** |
| Najee Harris `rushing/carries` mean | **4.790998** | **0.000000** |
| Joe Milton III `qb/db` mean | **21.675** | **0.000** |
| Dak Prescott `qb/db` mean | 16.799 | 22.019 |
| DAL modelled-RB carry sum | 17.540 | 16.830 |
| NYG modelled-RB carry sum | 20.110 | 20.110 |

So the review's headline defects were, at the time it was written, already
measured and already re-run internally. That does not make the review wrong —
it audited what it was given — but it does mean "the artifact does not reflect
them" is a statement about one artifact, not about the system.

A second consequence: the review's §7 arithmetic is **arithmetically right and
structurally misleading**, because the quantity it was handed as "the stated
non-QB rush budget" (17.54) is the *sum of the published players*, not the
budget. The real budget is A1's `rb` category. See claim R8.

---

## 1. Claim-by-claim crosswalk

Classification vocabulary as directed: CONFIRMED BY CODE/DATA | DIRECTIONALLY
CORRECT, WRONG MECHANISM | FALSIFIED | UNRESOLVED | OUT OF SCOPE.

| # | Claim as the review states it | Classification | Deciding code path | Deciding measurement | What a repair driven by the review's version would have got wrong |
|---|---|---|---|---|---|
| R1 | Roster membership is sound; all 13 team assignments football-correct; Likely/Ricard/Harris are genuine 2026 moves | **OUT OF SCOPE** (external bytes), consistent internally | `depth_vintage.py:231`, vintage blob `depth_charts.a14e8dfe…` retrieved 2026-09-13T15:45:56Z | This executor has no network (403 CONNECT, recorded in `INACTIVES_DISCOVERY_QUARANTINED.json`). Internally: DAL carry pool is exactly 4 backs, matching the review's ACT list | Nothing — the review is right that membership is not the defect, and internal work agrees ("Neither is a crosswalk or join defect") |
| R2 | Dallas rush pool correctly excludes Malik Davis, so no stale preseason vintage | **CONFIRMED BY CODE/DATA** | `football_engine.py:502`, `CARRY_POS=('RB',)` at `:50` | `rushing` row_ids = 4 DAL + 5 NYG backs; no fifth DAL back in any sealed matrix | — |
| R3 | The stale **club** (dallascowboys.com) depth chart is an inherited input risk | **FALSIFIED as an input path** | `depth_vintage.py` reads `nfl/vintage/depth_charts.*.reduced.csv.gz` (nflverse), never a club page | The consumed depth chart is one hashed blob, `a14e8dfe865a4b03`, declared in `information_set.sources` | Chasing a club-page scraper that the pipeline does not have. The staleness question that *is* live is about the nflverse vintage, which is untested — see §2 item U1 |
| R4 | Two officially inactive players hold material carry projections | **CONFIRMED BY CODE/DATA** (for the PRE artifact) | `layers.py:234` → `inactives.apply_to_appearance` never received ids on that run | Abanikanda 4.791, Harris 4.791 in `3dddf9f6`; `qb_inactive_ownership.official_inactive_evidence_ingested = false` | — |
| R5 | "…and that volume is **not redistributed** to the players who will play" | **FALSIFIED as a system property** | `inactives.py:609 apply_to_appearance` zeroes appearance **before** allocation; the simplex renormalises over survivors | Forensic rerun: NYG carry sum 20.110 → 20.110 **exactly**; Javonte Williams 7.42 → 9.24; Tracy 6.12 → 7.98 | Building a bespoke redistribution rule. One already exists and conserves exactly; a second would be an undeclared substitution model (the thing `inactives.py` explicitly refuses) |
| R6 | Inactive-evidence non-consumption is **the earliest demonstrable failure** | **DIRECTIONALLY CORRECT, WRONG MECHANISM** | `appearance_r8.py:263 featurise` (`n_prior`, `cm_carried`) | The ordering inversion survives any inactive filter: from the sealed draws, **P(0 carries)** Abanikanda (inactive) **0.1870** vs Javonte Williams (active RB1) **0.3366**; Najee Harris (inactive) **0.0403** — the *lowest* zero mass of any NYG back, below Skattebo 0.0452 | An inactive-list filter alone. It removes two names and leaves the active RB1 still carrying the highest zero mass on his own roster. Every week-1 board without an inactive list inherits the inversion untouched |
| R7 | QB specification defect: a practice-squad QB projected above a club-declared starter | **CONFIRMED symptom; DIRECTIONALLY CORRECT, WRONG MECHANISM as to cause** | `run_forecast.py:638` `nonqb = [q for q in players if q.get('position') != 'QB']` (R5 exemption) **and** `qb3_lib.py:129 cell_of` | Milton is DAL's week-18 2025 primary passer → `was_prev_primary=1` → cell `('2+',1)`, `p_primary` **0.6167**, against Prescott's cell `(1,0)` at **0.4922**. `cell_of` reads exactly two things: clipped depth rank and the incumbent bit | **This is the measured counter-example.** The repair the review implies (constrain the QB pool to the active 53) *was run* — commit `d652afb`, "Removing the wrong quarterback moved the defect, it did not fix it". Result: Prescott 0.5416, Howell 0.4584, **P(Prescott takes 0 dropbacks) = 0.4273**, corr(Prescott,Howell) = **−0.9240**. Eligibility was never the binding mechanism |
| R8 | "There is zero unowned opportunity inside the non-QB pool on either side" | **FALSIFIED** | `football_engine.py:501-560`; `p4c_lib.allocate` simplex branch | It is an identity, not a measurement: 7.42+4.79+3.52+1.81 = 17.54 because 17.54 *is* that sum. The pool's real budget is A1's `rb` category. Implied for NYG: 20.11 / (1−0.1989) = **25.10**, against rush-play budget 28.895 → 0.869, matching A1's league `rb` share **0.860235** (`C1_EVALUATION.json`). About **5.0 NYG carries and 4.5 DAL carries are unowned *inside* the RB pool** | Declaring the player pool clean and looking only upstream — which is exactly what the review then does, and it sends the search to the wrong layer |
| R9 | The ~20% residual is located "in the allocator", systematic, present on both sides | **DIRECTIONALLY CORRECT, WRONG MECHANISM** | `p4c_build` fits `pool = mall − ms` on the **team_carries** denominator; `run_forecast` hands the allocator A1's **`rb` category**; `football_engine.py:509-533` (the C1 block, added *after* these artifacts sealed) | Fitted `other` = **0.198875** (`own5_rush_ownership.json`) against a historical non-RB mass of **0.1918**; on the `rb` denominator the correct residual is **0.008754** → the mass is overstated **22.7×** and **0.1901 of the running-back budget is subtracted twice** (`predeclaration_c1_denominator.md`, sha256 `9d0443e1…`). Walk-forward 2022-24, 1,630 team-game clusters: CRPS 2.171 → 1.849, bias −1.624 → −0.809, interval excludes zero | Redistributing the residual to the named backs. That would hand RB1s the ~1.6-1.8 carries per club that genuinely belong to `kneel`, `wr`, `te` and `fringe`, destroying A1's partition — the invariant `A1_RUSH_ALLOCATION` (PASS, "every carry has exactly one owner in every draw") would still pass while the football became wrong |
| R10 | "Fixing the identities will not close the residual — two separate defects" | **CONFIRMED BY CODE/DATA** | as R5/R9 | NYG player-side sums conserve exactly across the identity change (20.110 both ways) while the residual is unmoved | — |
| R11 | Sam Howell "does not appear in the described QB specification at all" | **FALSIFIED** | `qb` row_ids in `player_draws_manifest.json` | Howell `00-0037077`, depth_chart QB2, **2.180 dropbacks** in the PRE artifact and **18.634** in the forensic rerun | Adding a QB2 that is already there |
| R12 | Abanikanda and Harris carry "the identical value 4.79" — anomaly, possible shared allocator template, UNRESOLVED | **FALSIFIED** | — | Exact means **4.791287** and **4.790998**. They agree only to the two decimals the review was shown. Both are their club's non-lead back at a similar `C` weight on a similar budget | Hunting a duplicated slot value that does not exist |
| R13 | Giants RB ordering (Tracy above Skattebo) departs from the club chart — flagged, not called a defect | **UNRESOLVED**, and the review's restraint is correct | `appearance_r8` + `role_prior` | Skattebo `p(0 carries)` 0.0452 vs Tracy 0.1075 — the model does rank Skattebo *more likely to carry*; the mean ordering differs because of weight, not appearance | — |
| R14 | Luepke RB/FB dual labelling is a live collision risk — UNRESOLVED | **DIRECTIONALLY CORRECT, narrow** | `football_engine.py:50 CARRY_POS=('RB',)` | The engine keys on the vintage `position` field (RB) and carries the club label only as display (`depth_chart: "FB1"`). Both are present on the same board row; no collision occurred | Renaming or re-keying positions. The exposure is confined to a vintage that labels him FB — untestable from this game alone |
| R15 | Player-id / crosswalk contamination NOT SUPPORTED | **CONFIRMED BY CODE/DATA** | — | Agrees with `DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md`: "Neither is a crosswalk or join defect" | — |
| R16 | Practice-squad contamination is general | **FALSIFIED as general; CONFIRMED for QB only** | `run_forecast.py:630-644`; `roster_status.py` (R5) | R5 **was applied** (`candidate_components_applied` includes R5) and restricts the non-QB pool to `status == ACT`, removing DEV/RES/CUT — measured 22.5 → 14.5 players per team-game with sum(C) 2.14 → 1.46. Milton reached the room **only** through the QB exemption | Auditing the whole pool for practice-squad players. One line at `run_forecast.py:638` is the entire exposure |
| R17 | Multiple simultaneous, independent defects is the correct characterisation | **CONFIRMED BY CODE/DATA** | — | Three distinct mechanisms measured: cell routing, the `other`-mass denominator, the appearance ordering | — |
| R18 | Verdict "PARTIAL: trust membership, do not trust status filter, QB spec, or budget decomposition" | **CONFIRMED BY CODE/DATA**, with the mechanism corrections above | — | — | — |

### The nine directed items

Five of these are **not advanced by this external review at all**. They come
from the earlier hypothesis set that `DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md`
answers. They are adjudicated anyway, and their absence from the review is
itself a finding: a reader who merges the two documents will otherwise attribute
falsified claims to a review that never made them.

| # | Item | In this review? | Classification | Deciding code path | Deciding measurement |
|---|---|---|---|---|---|
| 1 | "Dallas historical QB churn" explains the split | **No** | **FALSIFIED** | `qb3_lib.py:129-134 cell_of` | `cell_of(rank, was_prev)` reads exactly two scalars. Dallas's roster history, Prescott's participation record and Howell's are not inputs. Counterfactual on the sealed run: flipping `was_prev_primary` 0→1 for Prescott alone moves him 0.5474 → 0.8937 — **one bit is worth 35 points of dropbacks** |
| 2 | Stage2 `ewma_hl2` is on the QB path | **No** | **FALSIFIED** (third independent falsification) | `participation_prior.py:45` `POSITIONS=('WR','TE','RB')`; `s2_lib.py:16` `POS=('WR','TE','RB')`; `qb3_lib.py:15-21` imports only `bisect, collections, csv, gzip, os, numpy` | `grep -n "import" qb3_lib.py` returns six stdlib/numpy lines and nothing else. The string `Stage2 ewma_hl2` is the `spec_version` of the **non-QB** participation stage |
| 3 | Starter-selection mixture, not contingent replacement | **No** (the review reaches an adjacent conclusion by football reasoning) | **CONFIRMED BY CODE/DATA** — recomputed today, not inherited | `qb3_lib.py:171` identity draw → `:182` bimodal pool resample → `:186-192` remainder to the others | From `4b186a21`'s 8,000 draws: **corr(Prescott,Howell) = −0.9240**, P(exactly one > 10 dropbacks) = **0.9795**, P(both > 10) = **0.0205**, P(Prescott = 0) = **0.4273**, P(Prescott ≥ 31) = **0.4971**. Cell (1,0) is bimodal by construction: P(share=0) 0.4735, P(share=1) 0.4424. Against realised football: `QB_PARTICIPATION_CAUSAL_AUDIT.json`, established incumbent, no rotation, n = 1,700 team-games, **P(starter share = 0) = 0.0** |
| 4 | Team-volume suppression | **No** — but the review's §7 framing points at the same place | **FALSIFIED at the team level; the SYMPTOM is real one layer down** | `team_volume` layer; graded via `research/postgame.py` | 18 team-games: carries z **+0.02**, targets **+0.07**, dropbacks **+0.46**. DAL is **above** the slate mean on carries (+0.72), targets (+2.90), dropbacks (+4.01). **But** at the player level, recomputed today from `slate_rows.csv` (415 rows, 9 games): `qb/db` bias **−7.20 (z = −3.45)**, `rushing/carries` **−3.12 (z = −3.22)**, `receiving/targets` **−0.69 (z = −2.74)**, `receiving/receiving_yards` −3.04 (z = −1.11). The suppression is **entirely between the team budget and the player**, which is where R9 and item 3 both live |
| 5 | P3 appearance inversion | **No** (the review sees only the inactive-status half) | **CONFIRMED BY CODE/DATA** — verified from sealed bytes, independent of the recomputed latent | `appearance_r8.py:263 featurise`, fields `n_prior`, `cm_carried` | Recomputed latent: Camden Brown (inactive, `n_prior`=0) **0.9895**, Abanikanda (inactive, `cm_carried`=13) **0.9465**, Lamb 0.8760, Javonte Williams (RB1) **0.6580**. Independent confirmation that needs no recomputation: `P(0 carries)` from the sealed draws, 0.1870 / 0.0403 for the two inactive backs against 0.3366 for the active RB1; and the published `p_opportunity_ge_1` column, **Harris 0.9291 vs Javonte Williams 0.6630** |
| 6 | RC1 / no air yards | **No** | **CONFIRMED symptom, mechanism is a declared ruling not an absence** | `RC1_RECEIVING_CONVERSION_RETURN.md` §2 | pbp `air_yards` is populated on essentially every target (null on 1/1/0/0/0/0 targets, 2020-25) and **was read, descriptively**. It is excluded as a *decomposition axis* on provenance: `receiving_yards` is authoritative for caught-ball yardage and AY+YAC is not used to reconstruct it. `ngs_air_yards` is quarantined on measured coverage — **36.31% of 2022 plays, 0.00% of 2023 and 2025**. Measured consequence: conversion holds 46.14% of oracle CRPS reduction and the closed ladder recovers 4.89% of it (0.96% of baseline) → `SIGNAL_WEAK`. On the graded slate `receiving_yards` is the **one** metric not significantly biased (z = −1.11) |
| 7 | Ineligible opportunity (practice-squad and unranked players receiving volume) | **Yes** | **CONFIRMED, scope narrower than stated** | `run_forecast.py:638` (QB exemption); `qb_allocation.py` "a rostered QB with no depth rank is ranked last, not dropped" | Milton (DEV) 21.675 dropbacks and Jake Haener (no depth rank → rank 3) 1.021 dropbacks both reached the room. Non-QB pool: R5 ACT filter applied, so Slayton/Campbell are *rostered* WRs with small shares, not ineligible ones. The internal audit's "no pregame eligibility signal exists at all" is **too strong**: `roster_status.py` uses the pregame ACT/DEV/RES/CUT partition, guarded on a clock check and a POSTHOC content check. What does not exist is a pregame *dressed-tonight* signal, which is a different claim |
| 8 | Confidence inversion | **No** | **CONFIRMED BY CODE/DATA**, and visible in a published product artifact | `confidence.py:121 _role()` | `_role` computes `sh = v.mean() / tot.sum(0).mean()` — magnitude of share, no variance, IQR, entropy or P(zero) term — and `tot` spans **both teams** while the docstring says "his own team's opportunity". In `DAL_NYG_PROJECTION_CONFIDENCE_RANKING.csv`: **Najee Harris (officially inactive) rank 62, confidence 0.6023**, above **Javonte Williams (active RB1) rank 64, 0.5042**. On receiving, Harris rank 20 (0.7505) above Javonte Williams rank 27 (0.7056) |
| 9 | Warning-vs-gate | **Yes**, implicitly (the review calls the defects "disqualifying" for a board that sealed) | **DIRECTIONALLY CORRECT, WRONG MECHANISM** | `artifact.py:74-116` `INVARIANT_CLASSES`, `HARD_REFUSING_STATES = ('FAIL','BLOCKED')` | It is **not** true that nothing gates. HARD invariants refuse on FAIL/BLOCKED and the table is declared in one place. What gates nothing is (a) the free-text `spec_version` / `warnings` tokens — `conversion` is PASS carrying `SIGNAL_WEAK; governance HOLD_CHARACTERIZED + CALIBRATION_DEFECT` inside a string — and (b) **DEFERRED**, which carries debt without refusing: this board sealed with `qb_inactive_owns_nothing` DEFERRED ("no official inactive list was supplied for this game") and `qb_inactive_ownership.enforced = false`, publishing QB numbers at full precision. A repair that made warnings refuse would refuse internally coherent artifacts, which `artifact.py:88-92` argues against explicitly; the correct repair is to give the tokens a declared level, as `INVARIANT_CLASSES` already does |

---

## 2. What the review raises that internal work has **not** tested

These are the items with no internal measurement behind them. They are the most
valuable part of this adjudication.

**U1 — Is the nflverse depth-chart vintage stale in the same way the club chart
is?** The review proves the *club* chart is stale (Malik Davis at RB2 while on
RES). Internal work has never diffed the consumed vintage against an official
53. The DAL pool is *consistent* with a current chart (four backs, no Davis),
but consistency on one club on one night is not a test.
*What would settle it:* parse `nfl/vintage/depth_charts.a14e8dfe….reduced.csv.gz`
for all 32 clubs and compare each club's listed skill players against the
official 53 the other agent can fetch. One pass, no model change. A club whose
chart names a RES or CUT player is the signature.

**U2 — Should A1's `rb` share condition on which backs are eligible?** Named in
commit `d652afb` as "a football assumption this repository does not contain" and
never tested. Measured there: DAL's `rb` budget **fell** while its rush-play
budget **rose** when the QB room changed.
*What would settle it:* a pre-registered split of historical team-games on
whether the club's lead back was inactive, comparing realised `rb` share.

**U3 — Is the post-C1 residual correctly sized for a specific game?** C1 is
evaluated pooled over 2022-24. Nobody has checked one game's kneel/wr/te/fringe
against a realised box score, because **A1's six category draws are not
persisted** in `player_draws.npz` (22 matrices; none of them a category).
*What would settle it:* persist the A1 category draws in the draw artifact, then
grade `kneel + wr + te + fringe` against play-by-play per team-game.

**U4 — Does the QB-side eligibility repair still leave a reachable 0/0?**
`qb_allocation.allocate` now conditions the categorical before sampling and
refuses `QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE`. The measured near-miss is on
record (New Orleans "would have refused on 13 of 40 seeds"). There is no seed
sweep of the *conditioned* path.
*What would settle it:* a 40-seed sweep on the conditioned allocator across the
graded slate, counting refusals.

**U5 — Is proportional renormalisation the right substitution model?**
`inactives.py` zeroes appearance and lets the simplex redistribute, and says so:
"a bespoke reallocation would be a second, undeclared model of substitution".
That choice is declared, not measured.
*What would settle it:* Track 3 as already scoped — realised share of an
inactive back's carries by surviving depth rank, historical.

**U6 — The review's own source manifest.** Its §11 points at
`/home/user/workspace/forensic/` with per-club `manifest.jsonl` and two SHA-256
digests of the league inactive report. **Those bytes are not in this checkout.**
They are the one thing that would let `official_inactive_evidence_ingested` flip
to true through the governed path rather than through an aggregator screenshot.
*What would settle it:* the other agent retrieves
`https://www.nfl.com/news/inactive-reports-sunday-week-1-2026-nfl-season` and
checks it against `70cdd5e38da89d2f6f7cf5d544bd5e95bf0ee4bc67c70eff2001a552a9b16293`.

---

## 3. Where the review corroborates the quarantined capture

`INACTIVES_DISCOVERY_QUARANTINED.json` holds a RotoWire screenshot transcribed
verbatim and explicitly governing nothing. The review's independently retrieved
official lists agree with it **12 names for 12** — DAL: Abanikanda, Camden
Brown, Carson, Cornelius, Wheat; NYG: Cambre, J.C. Davis, Fidone, Najee Harris,
Jamison-Travis, Jones, Pinnock.

That raises confidence in the quarantined capture substantially. It does **not**
supersede the quarantine: the review is a third-party document, its preserved
bytes are outside this checkout (U6), and `NFL_ROSTER_STATUS_GOVERNANCE` requires
official bytes with an official URL. Two agreeing secondary sources are still
not the primary one.

---

## 4. Evidence ceiling

1. **No network.** Every football fact in the review — rosters, depth charts,
   the inactive report, its SHA-256s — is accepted as the review's own evidence
   and was **not** re-verified here. Egress returns 403 CONNECT for
   `www.nfl.com:443` and `site.api.espn.com:443`, recorded contemporaneously in
   `INACTIVES_DISCOVERY_QUARANTINED.json`.
2. **A1 category draws are not persisted.** The residual decomposition in R8/R9
   uses A1's **league-mean** `rb` share (0.860235, from `C1_EVALUATION.json`),
   not this game's drawn categories. The per-game split of the 6.08 DAL and 6.19
   NYG unowned carries into "double-subtracted" and "genuinely kneel/wr/te/
   fringe" is therefore **reconstructed arithmetic, not a read measurement**.
   Best estimate: DAL ≈ 4.5 + 1.6, NYG ≈ 5.0 + 1.2.
3. **The appearance latent is not persisted.** The 0.9895 / 0.9465 / 0.6580
   figures are recomputations through the production path at the sealed evidence
   clock. What *is* readable from the sealed bytes is the zero mass, which
   confirms the ordering independently (item 5).
4. **Nine graded games, 18 team-games, 415 rows, one audited game.** Every rate
   quoted from the 2026 slate is descriptive. No confirmatory claim is available
   from it.
5. **The player-level bias figures in item 4 are conditioned on having played.**
   A row enters `slate_rows.csv` only when an `actual` exists, so a model that
   spreads mass across players who may not appear is graded only on the ones who
   did. This inflates the apparent suppression for exactly the mechanism item 3
   describes, and the −7.20 dropback bias must not be quoted as an unconditional
   mean error.
6. **The two sealed artifacts share an evidence clock by construction**
   (`observed_before` 2026-09-13T23:12:33Z on both). They are not independent
   runs and must never be treated as two observations.
7. **Superseded-by-chronology.** The C1 repair (`3f5fc82`, 2026-09-14T00:36:30Z)
   post-dates both sealed artifacts (code commit `d954110`,
   2026-09-13T23:10:24Z, `+dirty[33]`). Verified with
   `git merge-base --is-ancestor`: it is **not** an ancestor. Any statement that
   the audited artifact "contains" or "lacks" C1 must say which side of that
   line it is on.

---

## 5. One-paragraph verdict

The review is right about every symptom it names and wrong, or incomplete, about
the cause of the two that matter most. Its membership audit is sound and its
refusal to convert "not listed inactive" into ACTIVE is the correct standard.
But it locates the QB defect in eligibility, when the measured driver is a
one-bit cell routing across the season boundary — and the eligibility repair it
implies has already been run and demonstrably failed. And it declares the
non-QB pool free of unowned opportunity by restating an identity, when the RB
pool's real budget is A1's `rb` category and roughly 4.5-5.0 carries per club
are lost inside it to a denominator mismatch that is separately diagnosed,
pre-registered and evaluated. A repair programme built from this review would
have filtered two names, deleted one exemption, gone looking for the residual
one layer above where it lives, and left the appearance inversion, the
starter-selection mixture and the double-subtracted carry mass all in place.

**CODE CHANGED: NO.**

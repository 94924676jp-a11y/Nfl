# NFL V1 research ledger — the one authoritative status list

**Written 2026-09-09.** This supersedes the status claims in `CURRENT_STATE.md`,
`README.md` and `CLAUDE.md`, which are stale in the ways §7 records.

## Rule 0 — re-derive, never quote

Nine documents in this repository carry a test-suite count, and **every one of
them was true when written**. The same is true of capture counts, refusal-code
counts and injury-feed coverage. Re-derive these before using them:

| quantity | how |
|---|---|
| suite size | `python3.12 nfl/tests/run_suite.py` |
| capture/manifest counts | `nfl/vintage_manifest.jsonl` |
| refusal codes | `nfl/production/refusal.py` |
| injury coverage | `nfl/production/nonqb/readiness.py` |

A count in prose is a snapshot, not a fact.

---

## 1. Accepted production baseline — what actually executes

QB V1 (aggregate-then-allocate) · D1 `team_volume_v1` (frozen P4B) · P4C system C
(carry/target simplex) · Stage-2 `ewma_hl2` participation · P3 Stage-A appearance
logistic · RC1 receiving-conversion control · TD2 `B_pos` control · OWN-4
`conserve_allocated_mass` · OWN-7 `seeds.py` stream registry and the P4C units
contract · OWN-1 `reconcile_allocation_share` · `reconcile_team_volume` and the
seven per-draw QB identities · `nfl/production/derived.py` · the 14-stage
entrypoint with 18 named refusal codes.

**None of it is publication-eligible.** `NFL-1` is NOT AUTHORIZED and every
layer's runtime role in `nfl/production/nonqb/eligibility.py` is REHEARSAL_ONLY.

## 2. Rehearsal-only candidates — accepted, deliberately not promoted

**QB3** (dropback-share allocation) · **A3** (`joint_residuals`, ships defaulting
off) · **C3** (shared passing event, `SHARED_PASS_DEFAULT='off'`) · **C0**
(cold-start passthrough, `include_cold_start=False`) · **A1** (single-owner
rushing; validated as research, not implemented) · **ABC_MPR** (frozen) ·
`ewma_hl1`.

Each stays rehearsal-only until separately authorised. Three of them are the
fix for a live V1 blocker, which is why §5 escalates rather than resolves.

## 3. Rejected — do not re-propose

Rushing: MPR_ONLY, MC_ONLY, ABC_ONLY, the whole P4E ladder, A2 (both the OWN-10
latent and the J1 causal split), A0, and the naive "carve QB carries first".
Allocation: Dirichlet, softmax-latent-Gaussian, logit-normal, empirical
log-ratio, deterministic reserved mass. Cross-layer: C1. Cold start: the C1
participation correction; Platt, isotonic and monotone-spline recalibration; the
R ranking model; `X_depth`. Receiving: RC2 repairs R1–R4; every R-study context
block. Rushing efficiency: the entire P5A ladder. Opportunity: proportional
redistribution, low-history shrinkage, the `pfr_id` bridge, fuzzy name matching.
Team environment: PROE as a predictor, the opponent block, announced-starter
knowledge. Vendor: FTN route participation and matchup, the personnel/formation
proxy, `ffopportunity` (oracle), `nflverse.route` as a routes substitute.

## 4. Falsified diagnoses — the wrong claim, and the correction

Fifty are catalogued across the return documents. The ones most likely to be
re-asserted:

| wrong | right |
|---|---|
| P4B over-allocates opportunity by 27–45% | −1.1% … +17.8%; the real defect is that 29–56% of individual **draws** are impossible |
| cross-layer passing↔receiving is a ~45% level error | sides agree within 2.7%; it is a pure **dependence** defect |
| D1 `team_targets` is 9.2% low | −4.4% against 2025; the 9.2% used a six-season mean of a declining series |
| A1 couples designed QB rush to carries at +0.507 | **+0.3065** [+0.2768, +0.3388] per draw against observed +0.3140 |
| 172 of 275 cold-start QBs are a data/identity defect | **zero**, once history is keyed by week rather than season |
| G0A item 1 fails on egress alone | egress works — 168 successful captures; two code defects would each have blocked discharge |
| snap_share MAE 0.0015 · scramble MAE 0.0000 · role-change AUC 0.9999 | a double division, a NULL passer id, and a label that is a function of its own history |
| the point-for-distribution class | **six** recorded instances, the latest reaching a headline number in an accepted return |

## 5. Unresolved V1 blockers

See `NFL_V1_CONVERGENCE_RETURN.md` §B for the full table with severity and
evidence. In short: the passing chain generates one football event twice (C3
is the built fix, unpromoted); teams within a game are drawn independently
(A3-per-game is the candidate); RB1↔RB2 competition is wrong-signed; the QB
composition stretches small draws; QB allocation share leaks 2.3–6.9% of
dropbacks; production emits four quantiles and no draws.

## 6. Data-blocked, and not fixable by engineering

`injuries_2026` covers 2 of 32 slate teams (remaining teams file later in the
week) · `pbp_participation_2026` and `snap_counts_2026` are 404 · true routes
run · player tracking · end-zone targets · coverage matchup · play-caller
identity · offensive-line context · 2025 point-in-time injury vintage · every
external vendor (all hosts unreachable from this executor).

## 7. Documents that are stale, and how

`CURRENT_STATE.md` is the most stale artifact here: dated 2026-09-07,
self-contradictory (§1 says the MLB `nfl/` drift is RESOLVED, §5 still lists it
open), and asserting four things now false — that nothing NFL-related is
scheduled (four GitHub Actions workflows run), that a scheduled repo-attached
capture is not expressible (it is), that `injuries_2026` is 404 (published),
and that no predictive model exists (QB V1 and the non-QB chain both execute).
`CLAUDE.md` and `README.md` carry the same "no predictive model" claim and the
911/1,230-assertion counts.

**`nfl/research/PATH_C_STATE.json` is the registered authority and is ~5 days
behind**, carrying no entry for QB, QB3, C0, C3, A3, A1/A2, cross-layer
passing↔receiving, kneel mass, or any OWN-* verdict. It may not be edited
without owner authorisation, so this ledger records the gap rather than closing
it.

`NFL_DECISION_LEDGER.md` contains only 2026-09-09 entries; every decision from
09-06 to 09-08 lives solely in the return documents.

## 8. Hypotheses already investigated more than once

"Carve QB rushing out of the team carry budget first" — **7 passes**, settled:
ownership is component-specific. Team offensive volume is forecastable — **5
passes, all negative**. Vacated opportunity redistributes proportionally — **3
passes, all negative**. Shrinkage helps low-history players — **5 passes**;
cause settled, naive fix rejected. True routes run — **7 passes**; the negative
is now structural. "Opportunity persists more than efficiency" — **6 passes**;
holds at player level, **false** for team passing volume. RB1↔RB2 competition —
**6 passes**; 2024's realised −0.667 is registered as not-under-research.

Re-opening any of these needs materially new information, not another estimator
on the same inputs.

## 9. Governance, unchanged by anything here

**G0A 11/12. NFL-1 NOT AUTHORIZED.** Item 1 needs an anchored capture inside a
real T−90 window and cannot be discharged by engineering. `PATH_C_STATE`
untouched. No 2026 outcome was read.

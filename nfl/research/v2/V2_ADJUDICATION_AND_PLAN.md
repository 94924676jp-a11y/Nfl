# NFL V2 — ADJUDICATION AND IMPLEMENTATION PLAN

Written 2026-09-14, at V1 HEAD `9c3c29a` plus the uncommitted live-path work of
2026-09-14. Adjudicates the owner's V2 directive (XLIV) and the independent
28-area adversarial review, against repository evidence.

**Rule applied throughout:** a recommendation is accepted on evidence, not on
sophistication. Where the repository disproves a claim, the claim is rejected
and the measurement is cited. Where two methods are plausible, a contest is
preregistered rather than a winner chosen by taste. An architectural
requirement is distinguished from an estimator that still needs empirical
selection.

---

## 0. THE FOUR REJECTIONS, FIRST, BECAUSE THEY MATTER MOST

### R-1. REJECT — "Candidate B's denominator changed; easy negatives inflated AUC"

Review §B2 objection 1, and the premise of the owner's four-cell experiment as
worded ("OLD/NEW FRAME" read as cohort).

**Measured, `nfl/research/remediation/ws_a/WS_A_RESULTS.json`:**

| arm | n | train_basis | score_basis |
|---|--:|---|---|
| BASE_INFRAME | 40,593 | P | P |
| BASE_SERVE | 40,593 | P | S |
| A | 40,593 | P | S |
| B | 40,593 | U | U |
| A0 | 40,593 | N | N |

All five arms are scored on the **identical 40,593 rows** with an identical
`observed_rate` of **0.628803**. No rows were added to any arm's evaluation
cohort. Adding easy negatives necessarily lowers the base rate; the base rate
is the same to six decimals. **AUC cannot have been mechanically inflated by
cohort enlargement, because the cohort did not change.**

**What survives, and it is real.** The *feature basis* differs (P / S / U / N).
That is a genuine confound and the four-cell experiment is genuinely
incomplete — but the missing cells are **model x BASIS**, not model x cohort.
Run: old-model scored on basis U, and B scored on basis S. WS-A ran P/P, P/S,
A-on-S, U/U and N/N; it did not run the two cross cells.

**Adjudication: REJECT the stated mechanism. ACCEPT the experiment, reframed.**
The owner's instinct to demand four cells is right; the reason given is not the
operative one, and building the experiment around "cohort" would measure the
wrong thing.

### R-2. REJECT — "AUC 0.9153 is earned on the easy part; it measures your data plumbing on inactives"

Review §B2 objection 2 asserts a model with lawful access to inactives should
approach determinism, so the gain may be plumbing.

**Neither arm reads the inactive list.** Inactives are applied one layer later,
at `nfl/production/nonqb/layers.py:236` (`inactives.apply_to_appearance`),
after `appearance_r8.predict` has returned. `predict` has no eligibility input
at all — this is WS04 finding 4, and it is the defect that lets a
governing-inactive player carry a near-certain appearance probability.

**Direct measurement, L2, TB@CIN replayed at a pre-kickoff clock:** Jack
Endries, on the ingested official inactive list — incumbent **p = 0.99197,
rank 3 of 43**; Candidate B **p = 0.46417, rank 25 of 43**.

A model that scored 0.99197 on a player who was officially inactive is not
reading the inactive list. The AUC is not measuring inactives plumbing,
because there is no such plumbing on that path.

**Adjudication: REJECT.** The stratified re-scoring the review proposes
(all candidates / active-only / active non-starters) remains **ACCEPTED** and
valuable — it answers a different and legitimate question about *where* the
gain lives.

### R-3. REJECT AS STATED — review C2, "kneel-downs are not a modeled category"

`nfl/production/nonqb/rushing_a1.py` already names `kneel` as an explicit
category in its frozen ownership graph:
`team_carries - scrambles = kneel + designed_qb + rb + wr + te + fringe`,
league share **0.0288**, measured **0.760 kneels/game** in `own5`.

**What is genuinely missing** is that the kneel share is an EWMA of team
history rather than a function of game state, when kneels are close to
deterministic given score and clock. **ACCEPT_WITH_MODIFICATION:** the category
exists; the *conditioning* is what to build, and it belongs to the shared
game-state latent (C3), not to a new category.

### R-4. REJECT AS STATED — directive §IV, "do not create half a player by multiplying every downstream projection by an availability probability"

The system does not do this. `layers.py:222` draws
`rng.binomial(1, p, size=m)` **per player** — some simulated worlds already
contain the player and some do not. The discrete-world requirement §IV asks for
is already met in form.

**The actual defect is different and worse:** those Bernoullis are
**independent, with no shared team or game latent** (WS04 finding 1 — indicator
variance equals the Poisson-binomial value in all 3 games and 6 team groups,
ratio 0.9678-1.0260; mean pairwise correlation +0.00033 / -0.00083 / -0.00049).
The only same-team coupling is **negative**, from simplex renormalisation
(-0.00911 / -0.01024 / -0.00938), i.e. the opposite sign from a shared
availability latent.

**ACCEPT_WITH_MODIFICATION:** the requirement to keep discrete worlds is
already satisfied and must be preserved; the work is **correlated
availability**, which is a game-state-latent problem.

---

## 1. ADJUDICATION TABLE — major recommendations

Columns: ADJ = adjudication; MC = model-changing; PR = requires
preregistration; SH = can run in shadow; PH = implementation phase.

| # | Recommendation | Repo state / V1 evidence | ADJ | MC | PR | SH | PH |
|---|---|---|---|---|---|---|---|
| 1 | **Block-aware prequential promotion harness** (dir §VI, review #1) | Absent. WS-F had to state its clustering convention by hand; the market grader's 0.4444 rests on **4 game clusters**, naive SE 0.0552 vs game-clustered 0.0724 | **ACCEPT** — top priority | no | n/a | n/a | V2-1 |
| 2 | **Candidate B four-cell, reframed as model x BASIS** | See R-1. Two cross cells missing | **ACCEPT_WITH_MODIFICATION** | no | yes | yes | V2-1 |
| 3 | **Stratified re-scoring: all / active-only / active non-starters** | Never run | **ACCEPT** | no | yes | yes | V2-1 |
| 4 | **Product-distribution scoring (CRPS, log, randomized PIT, coverage, sharpness)** | Partial: CRPS exists in C1 and shadow scoring; no PIT for discrete outcomes; WS22 found one shared uniform per run, flagged `pit_interpretable: false` | **ACCEPT** | no | n/a | n/a | V2-1 |
| 5 | **Clean-room reproduction from manifest** (dir §XXIII, review #8) | Absent. L5 proved *same-workspace* determinism today (SF_LA, 22 arrays, run id stable while dirty count moved 132→141→148). That is determinism, not reproducibility | **ACCEPT** | no | n/a | n/a | V2-1 |
| 6 | **Machine-readable PROJECT_STATE.json** (dir §XXXVI) | Absent; CLAUDE.md has drifted | **ACCEPT** | no | n/a | n/a | V2-1 |
| 7 | **Stage-0 deterministic eligibility, choice-set restriction** (dir §IV, review #3) | Eligibility is "four disconnected half-implementations" (WS05). QB pool bypassed the filter entirely until today (L7). Allocate-then-zero is current behaviour | **ACCEPT** | **yes** | no (structural) | yes | V2-2 |
| 8 | **Explicit OTHER mass** (dir §XI, review C1) | **Exists for carries** — A1's `kneel/designed_qb/wr/te/fringe`. **Absent for targets.** WS24 R8 measured ~5.0 NYG / ~4.5 DAL carries unowned *inside* the RB pool | **ACCEPT_WITH_MODIFICATION** — extend to targets; do not rebuild what A1 has | **yes** | yes | yes | V2-2 |
| 9 | **Per-metric publication verdict + dependency DAG** (dir §XXIX, review #7) | **Mechanism built today** by L4: `may_publish(ctx)`, 13 facts, ALLOW/REFUSE/UNEVALUABLE/UNDECIDED. DAG not yet built | **ACCEPT** | no | n/a | n/a | V2-3 |
| 10 | **Honest missingness states** (dir §XXX) | Partial | **ACCEPT** | no | n/a | n/a | V2-3 |
| 11 | **Retire scalar confidence** (dir §XXXI, review #10) | WS-M: `sd(s)` Spearman **+0.9411** vs mean own-team share, against **+0.9547** for the field it would replace — every scalar dispersion statistic of a bounded share is mean-entangled. Three gates averaged with two scores contribute a fixed 0.5427/0.5200 | **ACCEPT** | no | n/a | n/a | V2-3 |
| 12 | **Hurdle participation: eligible → appears → opp>0 → opp\|opp>0** | Q9 is already a hurdle for targets (`q9-target-hurdle-1`, frozen). Appearance is not decomposed | **ACCEPT** | **yes** | yes | yes | V2-4 |
| 13 | **Joint allocation replacing marginal+renormalize** (dir §IX, review #4) | Confirmed mechanism: WS04 finding 2 measures the simplex-induced negative coupling. **But WS09 J-11 FALSIFIED that it propagates to priced metrics** (cross-team receiving r −0.07…−0.11) | **EXPERIMENT_REQUIRED** — architecture joint; estimator by tournament. Do **not** presuppose Dirichlet | **yes** | yes | yes | V2-5 |
| 14 | **Shared game-state latent** (dir §XII, review C3) | **WS09 J-17 FALSIFIED any pace/shootout latent exists** — the only cross-team term is a negative snap copula (r ≈ −0.466). So this is a genuine addition, not a repair | **ACCEPT** | **yes** | yes | yes | V2-5 |
| 15 | **QB-P2: first-snap starter label, joint room state, mechanical allocation** | QB-P1 preregistered (`88c671e1…`); first-snap ≠ arg-max in **61/2,174** team-games (2.81%) and that 2.81% *is* the replaced-starter population. **No `pbp_2025` ⇒ no confirmatory fold** | **ACCEPT** | **yes** | yes | yes | V2-6 |
| 16 | **RNG partitioning by logical coordinate** (review C6) | **Corroborated today.** Appearance uses ONE stream per game consumed over a player dict, which is exactly why L6's team-scope repair **cannot** be draw-preserving in the mixed case. C6 would have made it trivially safe | **ACCEPT — raise to V2-1** | **yes** | no (mechanical) | yes | V2-1 |
| 17 | **Recalibration as an owned layer** (review C4) | Absent | **EXPERIMENT_REQUIRED** | **yes** | yes | yes | V2-7 |
| 18 | **MCSE / Monte Carlo error budget** (review C5) | Partial — `forensic_corrected._mc()` returns mean + MC standard error; not systematic | **ACCEPT** | no | n/a | n/a | V2-1 |
| 19 | **Regression catalogue of historical defects** (review C7) | Partial — each repair added tests; not systematised as a catalogue | **ACCEPT** | no | n/a | n/a | V2-1 |
| 20 | **Late-arriving/corrected data policy** (review C8) | Absent as policy; the state machine (§XXXIII) implies it | **ACCEPT** | no | n/a | n/a | V2-3 |
| 21 | **Game-day state machine, immutable runs per stage** (dir §XXXIII) | Partial: PRE/POST-inactives regimes exist; T-stages do not | **ACCEPT_WITH_MODIFICATION** — see conflict K-1: **FINAL is unreachable from this executor** | no | n/a | n/a | V2-3 |
| 22 | **Capture observability** (dir §XXXIV) | **Proved necessary**: `preflight_t90.py` printed `10 checks, 0 failing` with the executor dead 83h and 47 targets lost | **ACCEPT** | no | n/a | n/a | V2-1 |
| 23 | **Exact draw-based probability extraction with push semantics** (dir §XXXII, review #9) | Draws are stored; extraction interface not exposed | **ACCEPT** | no | n/a | n/a | V2-3 |
| 24 | **Preserve team volume; do not reopen** (dir §XV) | WS07: model r **0.327/0.319/0.266** against ceiling **0.315/0.383/0.337** (√ω², 2,174 team-games) | **ACCEPT** | no | n/a | n/a | — |
| 25 | **Keep air-yards rejected** (dir §II) | WS08: reaches 0.4-1.0% of the reachable residual, indistinguishable from zero clustered by game | **ACCEPT** | no | n/a | n/a | — |
| 26 | **No deep learning; ML only where justified** (dir §XVII) | No dispute | **ACCEPT** | no | n/a | n/a | — |
| 27 | **Market post-seal only** (dir §II) | L1 proved exclusion with key scan, value scan, gate check, closure and a negative control that correctly flips to NOT_PROVEN | **ACCEPT — already enforced** | no | n/a | n/a | — |
| 28 | **`cmp + inc + int = attempts`** (dir §XIV) | **No `inc` array exists.** QB arrays: att, cmp, db, int, ptd, pyds, rtd, rush_opp, ryds, sacks, scr | **ACCEPT_WITH_MODIFICATION** — as written it is tautological unless `inc` becomes a separately generated stored array. Decide which | **yes if stored** | no | yes | V2-3 |
| 29 | **Injury availability vs performance limitation** (dir §XVIII) | Absent | **ACCEPT** — separate track, not Stage-0 | **yes** | yes | yes | V2-7 |
| 30 | **Red-zone opportunity over "red-zone talent"** (dir §XIX) | `team_volume/team_rz_carries` already drawn | **ACCEPT** | **yes** | yes | yes | V2-7 |
| 31 | **Data-rights review** (review C10) | Absent | **ACCEPT** — precedes productisation, not modelling | no | n/a | n/a | V2-3 |
| 32 | **Model cards / datasheets** (review C9) | Absent; candidate freezes carry much of the content | **ACCEPT_WITH_MODIFICATION** — derive from the freeze artifacts, do not duplicate | no | n/a | n/a | V2-3 |

---

## 2. (A) PROPOSED V2 ARCHITECTURE — accepted with one amendment

The owner's stage ordering (0-9) is accepted. **Amendment:** insert
**RNG coordinate derivation** as a cross-cutting service beneath stages 1-8,
not as a stage. Every draw's stream derives from
`(execution_id, game_id, draw_index, layer, row_id)`.

This is promoted from V2-7 to **V2-1** on today's evidence: L6's repair could
not preserve draws in the mixed case *solely* because appearance consumes one
sequential stream over a player dict. Any future change to a choice set has the
same problem. Fixing the RNG coordinate makes choice-set changes safe by
construction and is a prerequisite for debugging a single draw in isolation.

## 3. (B) RETAIN UNCHANGED

Team volume (§XV, at ceiling) · air-yards rejection · market separation
(proved, with negative control) · A1 carry ownership graph including its
`kneel`/`fringe` categories · C3 team passing closure (exact in 100% of draws,
WS09 J-1) · Q9 target hurdle (frozen, `481f005f682cd721`) · the
evidence-first CLAIM→EVIDENCE→REPLICATION→CORRECTION chain · immutable
candidate history · `Outcome` five-state governance.

## 4. (C) REPAIR

Eligibility → Stage 0 · appearance leak (B, after four-cell) · warning
transport → per-metric DAG · confidence → separate fields · kneel conditioning
→ game state · RNG coordinates · capture observability.

## 5. (D) REPLACE

Marginal+renormalize allocation → joint (estimator by tournament) ·
QB3 cell table → QB-P2 room state · scalar confidence → typed fields ·
board-wide publication → per-metric verdict.

## 6. (E) EXPERIMENT BEFORE DESIGN

Allocation estimator family · recalibration map · efficiency pooling depth ·
hurdle vs ZINB for opportunity · whether drive/play-level simulation earns its
complexity.

## 7. (F) RETIRE

Scalar `confidence.score` · `arg-max dropbacks` as a starter label (it is
determined using postgame information) · `assert_no_stale_labels` as currently
written (a guard that cannot fire) · the board-wide-only `may_publish()`
(superseded today).

## 8. (G) CANDIDATE REGISTRY / CHAMPION-CHALLENGER

Registry entry = `{layer, role (CHAMPION|CHALLENGER), spec_version,
train_data_identity, feature_contract, parameter_hashes, causal_source_identity,
evaluation_protocol, promotion_state, freeze_sha256}`. Promotion states:
`DEVELOPING → PROMISING → VALIDATED → CHAMPION`, with `DEMOTED` terminal.
Champions serve; challengers run on identical lawful inputs, seal before
outcome, and are scored by the same harness. Candidate B enters as
**CHALLENGER/PROMISING** with its freeze `32ea294a98145b24…`.

## 9. (H) PROMOTION PROTOCOL

Block unit = **game**, secondary **week**; paired champion-vs-challenger loss
differences aggregated to blocks; block bootstrap or HAC; preregistered
primary proper score, margin, horizon, stopping and demotion rules, all
declared before forward observation. **The harness must be validated against
synthetic candidates of known effect size and known null**, and its
false-promotion rate measured, before any real promotion is decided by it.
No promotion from player-row standard errors.

## 10. (I) PHASE V2-1 — EXACT PLAN

1. Block-aware prequential harness + synthetic-candidate validation of its own
   false-promotion rate.
2. Candidate B four-cell **model x basis** (two missing cross cells) +
   stratified re-scoring (all / active-only / active non-starters) + per-block
   leak audit + feature-block ablation.
3. Product-distribution scoring: CRPS, log score, randomized PIT with a
   **per-row** uniform (WS22 found one shared uniform per run), coverage,
   sharpness, conditional calibration.
4. Clean-room reproduction harness: manifest + immutable inputs → independent
   environment → identical predictive draw digest.
5. `PROJECT_STATE.json` + CLAUDE.md split into stable principles vs state.
6. **RNG coordinate derivation** (promoted from later phase — see §2).
7. MCSE budget per metric; common random numbers for candidate comparison.
8. Regression catalogue: one executable test per historical defect.
9. Capture observability: EXPECTED vs ACTUAL per window, with deliberate
   failure injection (kill the inactives source near T-90 and assert the
   product does not call the board FINAL and does not reuse stale inactives).

## 11. (J) LIVE PROJECTIONS CONTINUE

V1-remediated champion serves. V2 challengers shadow. Tonight's DEN@KC run
proceeds under this rule: incumbent appearance is champion-by-default,
Candidate B runs as a recorded shadow arm, both stamped per row. Nothing in
V2 blocks a live forecast; nothing live promotes a V2 layer.

## 12. (K) CONFLICTS

**K-1. FINAL is unreachable.** Directive §IV's authoritative post-inactives
stage, §XXXIII's FINAL state, §XLI's readiness criterion and the review's hard
gate 1 all require official inactives. `www.nfl.com` returns **403 to CONNECT**
at the proxy gateway (verified, `$HTTPS_PROXY/__agentproxy/status`). No
reachable source can discharge kind `inactives` (`registry.can_discharge`).
**This blocks a V2-ready criterion and is not solvable in code.**

**K-2. RET-001 R7 forbids reduction outright** while `depth_charts` and
`weekly_rosters` are `durability="reduce"`. §XXII requires raw retention;
WS-K made reduction auditable without making it authorised. Unresolved since
the previous phase.

**K-3. Prior Ruling 1 vs §V.** The previous directive authorised Candidate B
to "advance immediately"; §V says do not promote. These are compatible only
under the reading "advance = shadow", which is how it has been implemented.
Confirmation wanted.

**K-4. §XLI requires live capture "observable and current"**, but the capture
executor stopped 2026-09-11T00:44:04Z and the cause is outside the checkout
(OUT-011).

**K-5. §XXVI names "strong public projections where legally and practically
available"** as a baseline. Most such sources are unreachable from this
executor (ESPN, nfl.com blocked). Practical limit, not a design flaw.

**K-6. Review gate 4 ("a sealed board reconstructed independently")** and
§XXIII require a second environment. This session has one.

## 13. (L) OWNER RULINGS REQUIRED

1. **Inactives executor** — largest single blocker to FINAL-state forecasts and
   to Stage-0's authoritative branch.
2. **RET-001 R7** — authorise reduction with retained raw, or forbid reduction.
3. **Confirm Candidate B is shadow-only** until the four cells close.
4. **Storage topology** (§XXXV) — vintages are ~10.7 MB/day with raw retention
   on; decide whether the data plane leaves git before it grows.
5. **QB3 §4** — confirm QB-P2 *replaces* rather than amends (§4 says "No other
   feature enters").
6. **`inc` array** — store incompletions as a generated quantity, or accept the
   identity is definitional.

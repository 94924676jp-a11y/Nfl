# NFL MASTER WORK RETURN

Executed 2026-09-08. **Nothing is promoted. G0A remains 11/12. NFL-1 remains
NOT AUTHORIZED.**

---

## A. Canonical repository

| | |
|---|---|
| Repository | `94924676jp-a11y/Nfl`, branch `main` |
| **Starting HEAD** | **`0d04119`** (`NFL vintage capture 20260908T160625Z`) |
| **Final HEAD** | see the last line of this section |
| Repository-wide tests at start | **256 functions, 0 failures** |
| **Repository-wide tests at end** | **285 functions, 0 failures** (+29) |

**Capture-bot rebase behaviour, recorded as §0.5 asks.** `nfl-capture.yml`
pushes to `main` every 30 minutes; 10 of the last 25 commits at session start
were `NFL vintage capture`. This branch was rebased onto bot commits **four
times** during the session. A rebase rewrites every short hash below it, so
**stable identity here is the commit title and the artifact sha256**, never an
embedded short hash. Pre-registration hashes are hashes of file *content* and
survive rebasing.

**No scientific artifact is silently ignored.** `.gitignore` excludes only
`__pycache__`, `nfl_vintage/` (ephemeral capture blobs; the append-only
manifest is tracked and *is* the audit trail) and two derived research pickles
proved byte-for-byte regenerable via `nfl/research/repro/regenerate.py`. Every
exclusion carries its reason in the file.

### A.1 Commits, by stable title

| # | Title |
|---|---|
| 1 | Stage 1: record RC1 owner acceptance as SIGNAL_WEAK |
| 2 | Stage 2.1: RC2 pre-registration, receiving baseline calibration repair |
| 3 | Stage 2: RC2 calibration repair — CALIBRATION_DEFECT_CONFIRMED |
| 4 | Stage 5: team/player accounting invariants, measured on real data |
| 5 | Stage 3.1: TD1 pre-registration, touchdown / red-zone decomposition |
| 6 | Stages 7 and 8: canonical player draw schema and deterministic scoring engine |
| 7 | Stage 3: TD/red-zone decomposition — DECOMPOSED, conversion-dominated |
| 8 | Stages 9-13: prospective contract, registries, evaluation protocol, NFL-1 guard |
| 9 | Stages 14-18: T-90 readiness, RET-001 verification, FTN-neutral adapter, registries |
| 10 | Stage 4 (partial): QB definition audit — BASELINED, decomposition NOT run |
| 11 | (this return) |

### A.2 New and changed files

**New modules:** `nfl/accounting/{invariants,audit_real}.py`,
`nfl/schema/player_draw.py`, `nfl/scoring/engine.py`,
`nfl/prospective/{artifact,registries,nfl1_readiness}.py`,
`nfl/adapters/routes_source.py`.

**New research:** `nfl/research/rc2/` (diagnosis, pre-registration, run,
finding), `nfl/research/td1/` (audit, pre-registration, run, finding),
`nfl/research/qb1/` (audit, finding).

**New governance:** `nfl/NFL_RC1_ACCEPTANCE_DECISION.json`,
`nfl/INFORMATION_GAP_REGISTRY.json`, `nfl/TECHNICAL_DEBT_REGISTRY.json`,
`nfl/prospective/PROSPECTIVE_EVALUATION_PROTOCOL.md`.

**New tests:** `test_accounting_invariants.py`, `test_schema_and_scoring.py`,
`test_prospective_contract.py`, `test_routes_adapter.py`.

**Changed:** `nfl/research/PATH_C_STATE.json` (two subsystems added, one open
question registered).

---

## B. Owner-state preservation

| | status | changed? |
|---|---|---|
| **G0A** | **11/12** | NO |
| **NFL-1** | **NOT AUTHORIZED** | NO |
| **P4C** | accepted carry-allocation model, system C | NO |
| **ABC_MPR** | frozen prospective candidate, **NOT promoted** | NO |
| **P** (participation) | Stage 2 `ewma_hl2` accepted; `ewma_hl1` development candidate only | NO |
| **R** | `SIGNAL_WEAK / COMPOSITION_FAILED` | NO |
| **RC1** (receiving conversion) | `SIGNAL_WEAK`, accepted as RC1-ACCEPT-001 | recorded, not altered |
| **Participation retention** | RET-001 `commit_raw` | verified, not altered |
| **FTN** | externally pending; nothing assumes it | NO |
| Cold-start freeze | intact, untouched | NO |
| Receiving information state | `PROSPECTIVE_DATA_PATH_ONLY` | NO |

---

## C. Stage-by-stage results

### Stage 1 — RC1 acceptance recorded

Recorded as `RC1-ACCEPT-001`. No conversion component promoted. **No
information ceiling declared** — a four-rung ladder on already-authorized
inputs cannot establish one. The methodological lesson is preserved as a
**binding constraint**, not a footnote: *primitive-level rankings can reverse
after composition* (C gains +0.680% as a primitive and costs 0.465% downstream;
V gains +0.050% and costs 0.951%). Ranking candidates on primitive metrics
alone is now recorded as **not an acceptable basis for a priority claim** in
this project.

### Stage 2 — receiving calibration → `CALIBRATION_DEFECT_CONFIRMED`

Pre-registration sha256 `65c5e295ba864a1dc5b82f39f29667c295b100a66a80e4602129b6fc8f74db0e`.

**The diagnosis corrected RC1's own reading before any repair was chosen.**

- Bias is **target volume, not conversion**: T over-predicted **+8.65%**, V
  +1.18%, compounding to Y's +9.8%.
- The own-history mean's bias **flips sign with history length**: −0.345 at 1–3
  prior games, **+0.287** at 25+.
- **The intervals are NOT globally too wide.** Implied total predictive SD
  30.033 against actual 29.937 — ratio **1.0032**; within/residual 0.985.
- **The over-coverage is largely a zero-point-mass artifact.** 54.9% of rows
  have a predictive 25th percentile of exactly 0, and 49.45% of those have
  `Y = 0`, which an inclusive interval contains **by construction**. Where the
  lower bound is strictly positive, nominal-50% coverage is **0.4823 — slightly
  UNDER**.

| arm | CRPS | bias | r | PIT χ² | verdict |
|---|---|---|---|---|---|
| R0 control | 11.1798 | +2.1801 | 0.6019 | 178.9 | — |
| **R1** draw-centring | **11.1545** | +1.6702 | **0.6031** | **135.9** | FAILS (bias only) |
| R2 zero-mass | 11.2522 | **+0.8078** | 0.5960 | 76.6 | FAILS |
| R3 variance | 11.4172 | +2.2420 | 0.6020 | **12,420** | FAILS |
| R4 all three | 11.4706 | +0.4138 | 0.5959 | 11,409.6 | FAILS |

**All four fail.** R1 improved CRPS, MAE, r and PIT *together* and cut bias to
1.67, failing only the predeclared `|bias| < 1.00`. **The bar was not moved.**

**R3 vindicated the pre-registration's refusal to chase the coverage headline**
— it is exactly the interval-squeeze that §1d argued would attack an artifact,
and it drove cov50 from 0.650 to 0.406 while making PIT **70× worse**.

**Defect found:** R1's fitted factors show short-history rows need target draws
scaled **down ~15%** — the opposite sign from the own-history diagnosis. Both
are true: a short-history player's own mean under-predicts him, but the
simulator leans on the position pool for exactly those rows and the pool
(WR 4.103) badly over-predicts a low-usage player (actual 1.708).

### Stage 3 — TD / red-zone → `DECOMPOSED`

Pre-registration sha256 `8effcb5a95ec1cfe721dde743c3f394889135c3e8c423156163e34ad849f2d6c`.
Identity `TD = (TeamOpp × Share) × [Z·k_rz + (1−Z)·k_nrz]` reproduces realised
TD **exactly** (max |err| 2.2e-16–4.4e-16, all seasons, both kinds). Shapley
efficiency gap **0.00e+00**.

| | V team env | S share | Z red-zone | **K conversion** |
|---|---|---|---|---|
| **Receiving TD** | 2.69% | 7.78% | 12.98% | **76.55%** |
| **Rushing TD** | 4.45% | 7.90% | 12.59% | **75.07%** |

**Both TD layers are conversion-dominated — the opposite of receiving yards**
(opportunity 53.86%). Same players, same games, different outcome layer,
different structure. Inside opportunity the ordering is stable: **where** you
get the ball (~13%) beats **how often** (~8%) beats team environment (3–4%).

**The caveat is recorded prominently.** TD is rare and near-binary (mean 0.137 /
0.068). Oracling conversion *for that game*, conditional on realised
opportunity, is close to being handed the outcome — so K's share **overstates**
what a forecaster could reach. State is `DECOMPOSED`, deliberately not
"conversion-dominated" as a verdict. **The recoverability ladder and
composition test were NOT run.**

### Stage 4 — QB → `BASELINED` (audit only, decomposition NOT run)

**`pass_attempt` includes sacks — 5,308 of 5,308 — and spikes, 278 of 278.**

| | |
|---|---|
| **WRONG** | `attempts = dropbacks − sacks − scrambles` → 71,354 |
| **RIGHT** | `dropbacks = pass_attempts + scrambles − spikes` |
| real attempts | **76,941** — the naive form errs by **5,586 plays** |

Identity closes to within **one play**, named: `2025_03_LA_PHI` play 3600, a
blocked field goal mislabelled upstream, left visible.

**Every sack carries a `passer_player_id`; no scramble does** — 4,091 dropbacks
lack one, exactly the scramble count. Scrambles are charged to the rusher.

### Stage 5 — accounting invariants

Run on **3,230 real team-games**. Eight invariants hold **exactly** with **no
OTHER mass required**: team targets, receptions, receiving yards, carries and
rushing TD each equal the player sum; team passing TD equals summed receiving
TD; receptions ≤ targets; red-zone targets ≤ targets.

**One fails and is named:** team passing yards ≠ receiving yards on **76 of
3,230** team-games. **75 are laterals**; the remaining **one** (IND 2022 wk16,
13.0 vs 12.0, no lateral) is an upstream inconsistency **left visible** rather
than folded into the lateral bucket. The policy forbids widening the exception.

A test proves the per-group form matters: a positive residual cancelling a
negative passes an aggregate check and fails here.

### Stages 7–8 — draw schema and scoring engine

Orderings checked **per draw index, not on the mean** — a test proves
receptions `[7,1,2,5,3]` against targets `[5,6,4,7,5]` passes a mean check and
is impossible on draw 0. Every draw must carry a complete trace or is refused.

**The football/fantasy separation is enforced, not promised:**
`player_draw.validate` **refuses** a draw set carrying a fantasy score, and
tests assert the schema and research modules do not import the scoring engine.
Three scoring profiles, hand-calculated fixtures, bonuses either side of the
threshold, negative scoring, fractional points, ragged sets refused.
**No optimizer, ownership, salary, contest or betting logic exists.**

### Stages 9–13 — prospective machinery

Ordering gate `retrieved_at ≤ written_at < kickoff` with **no grace period**;
artifacts **immutable** after `written_at` (correction = new artifact naming
`supersedes`); **arms A/B/C never pooled**. Professional projections are
**benchmark-only, never training labels**, and registered as **unavailable**
rather than backfilled. The evaluation protocol is predeclared with sample
floors 200/400/800, game-clustered intervals, Holm–Bonferroni, and **the
FIRST eligible artifact scored** so late information cannot be rewarded.

**Question 8 answers NO, and is enforced:** no basis except an explicit,
identified owner decision moves NFL-1 to AUTHORIZED — not a passing test, not a
discharged checklist, not a green suite.

**Question 7 caught a false positive of my own making.** The first 12/12 scan
flagged three artifacts, all legitimate (two saying the gate *requires* 12/12,
one recording an owner overrule). A guard that fires every run is ignored, so it
was made precise — structured state checked structurally, prose matched only on
an assertion of current status — and a test proves it still catches a seeded
claim while **not** flagging a requirement.

### Stage 14 — T−90 readiness

**10 checks, 0 failing.** No proof manufactured; no manual dispatch represented
as the real proof.

### Stage 15 — RET-001 verified

No vintage deleted, manifest append-only, no orphan blobs, `commit_raw`
enforced on both sources. Neither watched source can discharge any T−90 kind;
predictive authorization is `False`. The first-seen ledger and blob directory
**correctly do not exist** — nothing has been observed available. **Polling
cadence unchanged.** 2026 remains 404 for both.

### Stage 16 — FTN wait state

Adapter **fails closed**: no implementation, no sample rows, no default that
returns data, no vendor endpoint. Rights are **not inferred from silence** — a
provider is refused without model-training, retention **and** derived-output
ownership plus a licence id. `nflverse.route` is named a **forbidden
substitute** with its reason.

### Stages 17–18 — registries

10 information gaps, 11 technical debts, each with causal layer, proxy, proxy
adequacy, evidence status, licensing, PIT status and action state.

### Stage 6 — joint simulator v2: **NOT REACHED**

Recorded as `DEBT-JOINT-TARGETS` and `DEBT-SNAP-IMPOSSIBILITY`. The prior
diagnostics are preserved and were not tuned to.

---

## D. Updated causal architecture

| layer | state |
|---|---|
| team volume | `RECOVERABILITY_CHARACTERIZED` |
| appearance | `DECOMPOSED` (information-constrained) |
| RB carry allocation | `DECOMPOSED` → P4C accepted; ABC_MPR `CANDIDATE` |
| participation (P) | `DECOMPOSED` / `RECOVERABILITY_CHARACTERIZED` |
| target allocation (R) | `RECOVERABILITY_CHARACTERIZED` (`SIGNAL_WEAK`) |
| **receiving conversion** | **`RECOVERABILITY_CHARACTERIZED`** (`SIGNAL_WEAK`) |
| **receiving baseline calibration** | **`DEVELOPMENT`** (`CALIBRATION_DEFECT_CONFIRMED`) |
| **TD / red-zone** | **`DECOMPOSED`** — ladder and composition open |
| **QB** | **`BASELINED`** — audit only |
| joint dependence | `UNEXPLORED` (diagnostic only) |
| routes / true route participation | **`BLOCKED`** (licensing) |
| player draw schema | infrastructure — complete |
| fantasy scoring | infrastructure — complete |
| prospective contract & protocol | **`PROSPECTIVE`** — predeclared, unused |

---

## E. Master checklist

| item | state |
|---|---|
| RC1 acceptance recorded | **DONE** |
| Receiving calibration repair | **DONE** — `CALIBRATION_DEFECT_CONFIRMED` |
| TD/red-zone decomposition | **DONE** |
| TD recoverability ladder + composition | **OPEN** |
| QB definition audit | **DONE** |
| QB decomposition | **OPEN** |
| Accounting invariants | **DONE** |
| Joint simulator v2 | **OPEN** |
| Player draw schema | **DONE** |
| Fantasy scoring engine | **DONE** |
| Forecast artifact contract | **DONE** |
| Benchmark registry | **DONE** |
| Evaluation protocol | **DONE** |
| Candidate registry | **DONE** |
| NFL-1 readiness package | **DONE** |
| T−90 readiness | **DONE** — real proof `WAITING_PROSPECTIVE` |
| Participation watch verification | **DONE** — 2026 `WAITING_EXTERNAL` |
| FTN | **WAITING_EXTERNAL** |
| Information gap registry | **DONE** |
| Technical debt registry | **DONE** |
| Adversarial test expansion | **DONE** |
| Repository hygiene | **DONE** |

---

## F. Top 5 next actions (Path C, no fabricated EV score)

1. **TD recoverability ladder + composition.** Blocker: none. Leverage: high —
   TD1 measured 75–77% oracle share in conversion but the caveat says much is
   irreducible. Cost: low, the machinery exists. Contamination risk: low.
   **Action: CHEAP_PROBE.** Without it nobody can tell whether the 75% is
   opportunity for modelling or noise, and funding on the raw share alone is
   the exact RC1 mistake.
2. **QB oracle decomposition.** Blocker: none, and the audit that had to
   precede it is done. Leverage: high — an entire unmeasured layer. Cost:
   medium. **Action: INVEST.**
3. **A new receiving-calibration pre-registration for the R1 direction.**
   Blocker: none. Leverage: medium — R1 improved every metric together and
   missed one predeclared bound. Contamination risk: **elevated**, because R1's
   direction is now known; a fresh pre-registration must say why a
   history-cohort factor is calibration and not a model change. **Action:
   CHEAP_PROBE.**
4. **Joint simulator v2.** Blocker: none. Leverage: medium — target dependence
   and snap impossibilities are both open. Cost: high. **Action: HOLD** until 1
   and 2 report, since both change what the joint layer must couple.
5. **True routes acquisition.** Blocker: **licensing, external**. Leverage:
   potentially the highest of any item — it is the only path to separating P's
   measurement error from its modelling error. Cost: unknown. **Action:
   BLOCKED**, owner/vendor track only.

---

## G. Tomorrow's T−90 readiness

| | |
|---|---|
| **Target** | **NE @ SEA** (`2026_01_NE_SEA`) |
| **Kickoff** | **2026-09-10 00:20 UTC** |
| **Acceptance window** | **2026-09-09 22:50 UTC → 2026-09-10 00:10 UTC** (Sept 9, 6:50–8:10 PM ET) |
| Window shape | 80 minutes, opening exactly at kickoff − 90 |
| Workflow | `nfl-t90.yml`, 16 cron entries, identity `SCHED-2a2924d4966fbd3d` |
| Preflight | **10 checks, 0 failing** |
| Prior evidence | 164 captures verify byte-for-byte, 0 failures |
| **G0A** | **11/12 — unchanged** |

**Evidence required for owner review:** a capture whose `retrieved_at` falls
inside the window, **carrying the `game_id`**, from `official_inactives` or
`official_injury_report`, taken by the **anchored** workflow (only
`SCHEDULED_WINDOW_ANCHORED` may discharge), with raw bytes stored before
parsing and the manifest row appended.

**A manual dispatch can never discharge it. No practice run counts.**

---

## H. External waits

- **FTN** — unsigned agreement; ML/training rights, local retention,
  derived-output ownership, post-termination rights, `skp_role` coverage and
  identifier crosswalk all unresolved. Nothing here assumes any of it.
- **2026 `pbp_participation` / `snap_counts`** — both 404 as of 2026-09-08.
  Watch running under RET-001 `commit_raw`, twice daily, cadence unchanged.
  **Not authorized for predictive use.**

---

## I. Explicit prohibitions — restated

Nothing in this work:

- authorizes **NFL-1** (remains NOT AUTHORIZED, and no code path can);
- changes **G0A** (remains **11/12**);
- promotes any candidate, mined-data or otherwise;
- alters **P4C**, **ABC_MPR**, Stage 2 `ewma_hl2`, or the cold-start freeze;
- uses 2026 outcomes, sportsbook odds, betting markets, DFS salary or ownership;
- begins DFS, props, market, optimization or portfolio work;
- uses FTN, PFR-restricted fields, `weekly_rosters.status`, or treats
  `nflverse.route` as routes run;
- treats a final historical file as a point-in-time vintage;
- pools prospective arms.

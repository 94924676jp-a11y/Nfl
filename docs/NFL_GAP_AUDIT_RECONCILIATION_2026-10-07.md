# External gap audit: reconciliation against current HEAD, and next-Showdown readiness — 2026-10-07

This document replaces the readiness draft I was writing for the 2026-10-07 readiness directive; its content is
folded in here. Every claim below cites a file or commit in this repository. The external package was read as a
set of hypotheses, not as repository truth.

Audit ladder, used verbatim throughout:
`IMPLEMENTED ≠ ON_EXECUTION_PATH ≠ CONSUMED_BY_NEXT_STAGE ≠ SUCCESS_TESTED ≠ REFUSAL_TESTED ≠ ADVERSARIAL_TESTED ≠ PROSPECTIVELY_VALIDATED ≠ PROMOTED`

## A. Current HEAD

- **Branch:** `claude/nfl-greenfield-architecture-stsxmk`. **HEAD:** the commit that adds this file; its parent is
  `c1a5f329`. The working tree was clean before this commit, apart from this file.
- **The audit's capture head was `5479b606`.** It was then my latest pushed commit, so the audit inspected this
  sprint's own work up to that point. Nothing it read had been superseded at capture time.
- **Supersessions since the capture**, all made after reading the audit:

| Commit | What it supersedes |
|---|---|
| `113b7fc8` | Suite completion certificate and its sabotage fixtures (the audit's "evidence gap, not a fresh failure"). |
| `cd5f6aa2` | Hard Rock capture contract and four settlement states. |
| `ba7f1df4` | Copy-count semantics for B4/B3S (all copies vs other copies). |
| `c6c09b1d` | Stat-api verification-sample request (no purchase). |
| `6b7fa22f` | SC-APPEAR-1 end-to-end propagation into the simulated draws. |
| `8b6803db` | The clean SC-COH-1 evaluation. It reclassifies `SC_COH_1_MEASUREMENT.json` as development evidence. |
| `a77fa3e4`, `c1a5f329` | Certificate hardening after real run #1, and both certificates recorded. |
| `fba8cddb` | `regenerate.py` working again (broken since 2026-09-10); P4B binaries placed by the rebuild script. |

- **Input package.** The "Evidence_Ledger.jsonl" upload was an iOS file-reference stub (a binary plist), not the
  JSONL itself. The Markdown ledger (59 records, GAP26-001…059) was used. It and the JSONL are one source in two
  formats, never two.

## B. Reconciliation table

Status vocabulary: COMPLETED_ON_CURRENT_HEAD · PARTIALLY_SUPERSEDED · STILL_OPEN · INVALIDATED_BY_NEWER_REPO_EVIDENCE ·
BLOCKED_BY_MISSING_EVIDENCE · OWNER_DECISION_REQUIRED

| Item | External audit says | Current repo says | Status | Action |
|---|---|---|---|---|
| Authoritative suite runner | Has completion checks; the log mixes runs; no clean completion established | `run_suite.py` judges every function and refuses zero-check and NOT_EXECUTED runs. It now catches `SystemExit` at import and in tests (`5479b606`). | COMPLETED_ON_CURRENT_HEAD | none |
| Completion certificate / manifest | Needs a parent supervisor: manifest identity, terminal record, timeout, signal, `os._exit`, stale and truncated records | `nfl/tests/certify_suite.py` (`113b7fc8`, `a77fa3e4`, `c1a5f329`), with 42 sabotage and control checks; nested-runner isolation added after real run #1 caught contamination. Real run #2: complete, FAILED. | COMPLETED_ON_CURRENT_HEAD | Owner decision 6 |
| `sys.exit()` protection | Recommended fixtures | Runner fixed. Four modules had import-level exits and now run under `__main__`. One had numpy counters, now coerced to int. | COMPLETED_ON_CURRENT_HEAD | none |
| Shallow-clone recovery | Not mentioned | `rebuild_derived.sh` unshallows. A pinned-blob test failed in the post-reset shallow clone and passes 91/91 once history is fetched. | COMPLETED_ON_CURRENT_HEAD | none |
| Deterministic rebuild | Needs dependency lock, hashes, order/worker determinism | Derived cache manifest: a rebuild from an empty cache matched all six artifacts. The ATL@NO upload is byte-identical three ways. Two report files depended on `PYTHONHASHSEED`; now fixed (`12451ada`). The certificate records interpreter and numpy/pandas versions. There is **no pinned dependency lock file**. | PARTIALLY_SUPERSEDED | Lock file: STILL_OPEN |
| Specialist detector | Identity/role safety for specialists | Default-on in the slate state (`01896f90`). 17 role-family cases plus an end-to-end run with the hand tag removed. Upload unchanged. | COMPLETED_ON_CURRENT_HEAD | **OWNER_DECISION_REQUIRED**: keep default-on? |
| B4 / B3S | Do not promote from three games; all vs other copies; unique vs entry-weighted; legal-lineup sampling | Shadow only, on the runner path, non-blocking. Research actuals are ALL copies; other-copies ratios are now recorded (B4 1.01 / 1.03 / 0.70). The universe is the full enumeration of legal lineups over the top-32 players (declared). No entry-weighted panel. Three contests from one game plus two other slates. | PARTIALLY_SUPERSEDED | More full fields: BLOCKED_BY_MISSING_EVIDENCE |
| Legal-field ownership model `p_c(L) ∝ 1[legal]·exp(θ·φ(L))` | Proposed as new | **Already the B-family form** (`nfl/field/showdown_dupe_research.py`). But its slot marginals are profiled to an ownership forecast, so it does not forecast ownership itself. | PARTIALLY_SUPERSEDED | A legal-field *ownership forecaster*: STILL_OPEN |
| Cheap-player ownership successor | Thresholds were ATL-motivated; PIT reconstruction; PHI has no salaries | Pre-registered and LOSO, and **FAILS** on both testable folds (`3d057bc6`). The baseline misses in opposite directions on the two slates. All three limitations are recorded in its artifact. | INVALIDATED_BY_NEWER_REPO_EVIDENCE (that candidate) | A player-level successor: STILL_OPEN |
| SC-APPEAR-1 (allocator) | A retrospective production-allocator replay exists; check the sim consumer and the prospective gap | Replay passes its declared bar (`e0ea0fa0`). **New:** `p_plays` never reaches the draws (0 references in 13 sim-path files). RB2 carries: projected P(0) 0.36, frozen ATL worlds 0.015–0.04 (`6b7fa22f`). | STILL_OPEN | see D |
| SC-APPEAR-1 (states) | Eligibility, appearance, special-teams-only, opportunity and count are distinct | Traced. Only eligibility and the projection's opportunity are separate states; special-teams-only appearance and the positive count do not exist in the sim. Active zero-snap players: **NOT_IDENTIFIABLE_FROM_CURRENT_DATA**. | STILL_OPEN | Rosters/inactives: outbox |
| SC-COH-1 contamination | Market lines, outcome-derived pools, evaluation-year leakage | **Verified, and worse than stated.** The candidate picked analogue games by sportsbook total and spread (`sc_coh_1_candidate.py:43,104-111,323`), which is a governance rule-1 violation for production use. The pool was the evaluated game's snaps. The incumbent's inputs saw 2025. | COMPLETED_ON_CURRENT_HEAD (audit) | old result is now DEVELOPMENT_EVIDENCE |
| SC-COH-1 clean replay | Training cutoff, football-only, point-in-time pools, same consumer, post-transform conservation, full metric panel | Done (`8b6803db`). Pre-registration locked before any score; incumbent refit through 2024; injection-tested guard against market fields. **Candidate fails:** 1 of 4 primary endpoints passes. Conservation counted after every stage: the live **yards rescale and DST anchor re-break both arms**. | STILL_OPEN | Event-linked world; post-step repair |
| Next-slate runner | Live recovery: stale inputs, partial writes, interruptions | `showdown_next_slate.py` (`d423eff1`): fail-closed gates, write-once freeze, FINAL_VERIFY re-hashes inputs and reproduces the upload. Rehearsed on ATL@NO. 19 refusal checks. Not live-tested. | COMPLETED_ON_CURRENT_HEAD | First live slate |
| Generic slate config | — | Template plus `showdown_slate_env.py`. ATL outputs unchanged, verified by rerunning the full finishing chain. | COMPLETED_ON_CURRENT_HEAD | none |
| Prop-seal chronology | Football sealed, then props sealed, then capture, then compare | The freeze precedes projection. A prop seal at or after kickoff is refused. `market` is refused before the seal, and `price_history.comparable` refuses a price from before the seal or after kickoff. | COMPLETED_ON_CURRENT_HEAD | none |
| Hard Rock capture workflow | Book, jurisdiction, product, settlement rules, hash; win/loss/push/void | Capture-sidecar contract enforced; non-Hard-Rock boards refused; WIN_OVER / WIN_UNDER / PUSH / VOID_NO_ACTION / UNRESOLVED (`cd5f6aa2`). There is still no live capture. | PARTIALLY_SUPERSEDED | Capture: external |
| Finalization / READY gates | Gate, not count | Runner FINAL_VERIFY plus the prelock board. READY needs an OFFICIALLY_VERIFIED inactive list; a secondary source or a rehearsal is never READY. | COMPLETED_ON_CURRENT_HEAD | none |
| Portfolio objective ablation | Hold pool, worlds, field, payout and seeds constant; coverage vs EV vs any-winner vs CVaR | `DUPE_PORTFOLIO_STUDY.json` holds pool, worlds (selection seed vs held-out seed), field models and tie rule constant, and reports coverage, split EV, P(any hit) and best score. It lacks CVaR, ownership perturbation, a real payout table (the curve is assumed) and self-competition. | PARTIALLY_SUPERSEDED | Remaining: STILL_OPEN; objective change: OWNER_DECISION_REQUIRED |
| Stat-api archive | Verify a sample before any purchase | A verification-sample request is filed for our five contest ids (`c6c09b1d`). No purchase. | BLOCKED_BY_MISSING_EVIDENCE | Purchase or rights: OWNER_DECISION_REQUIRED |
| DK CSV 10-day window | Capture lawful exports, initial and final | ATL@NO is done. Future slates need an owner manual export inside the window. | STILL_OPEN | owner action per slate |
| Route / participation data | FTN participation arrives post-season; route is the primary receiver only | The repo uses no route-denominator feature. | COMPLETED_ON_CURRENT_HEAD (no exposure) | keep refused |

## C. Authoritative suite status

**Certificate #2 — the authoritative result for this report.**
`nfl/tests/certificates/SUITE_CERTIFICATE_20261007T083657Z-18364.json`:

- **Commit and isolation.** Run on commit `a77fa3e4`, in an isolated worktree.
- **Environment.** Python 3.12.3, numpy 2.5.3, pandas 3.0.6, full history (not shallow). One dirty entry: the
  derived-cache symlink.
- **Verdict: FAILED, with no completeness reason.** This is a complete, honest red result, not a truncated one:
  - expected modules **368**, completed **368**, each exactly once;
  - one terminal record, whose verdict agrees with the exit code (1) and the printed line;
  - 5,308 s; no timeout and no signal.
- **Executed:**
  - 3,673 test functions and **16,090 checks**;
  - **174 failing checks, 127 raised, 5 zero-check functions** (each fails the suite), and 36 declared BLOCKED
    functions;
  - detectors 256 VALIDATED, 9 UNVALIDATED_CONTROL_NOT_EXECUTED, 1 UNVALIDATED_CONTROL_DID_NOT_TRIP;
  - **58 FAIL modules plus 9 raise-only modules = 67 of 368 with at least one defect.**
- **Housekeeping.**
  - 10 nested runs were recorded apart, in `…nested.jsonl`.
  - The run modified **10 tracked files**: readiness, the Sunday-run report, the Q9 dry-run seal ledger, the slate
    status boards and others. Recorded, not judged. A test suite that writes tracked files is itself a hygiene
    defect.

**Certificate #1** (commit `cd5f6aa2`) was **INCOMPLETE_NOT_CERTIFIED**, and for a true reason:
- the harness self-tests' nested runners appended 10 other runs' records into the certified progress file;
- the certifier refused, as designed;
- fixed in `a77fa3e4` (under a certificate, nested runners write to a sibling file).

**Baseline comparison.** The same 58 failing modules were re-run at the pre-sprint commit `6a9b9bf` in the same
environment:

| Comparison | Result |
|---|---|
| Identical failing-check count | 54 modules |
| Better now | 2 |
| Worse in the main-tree run | 2, both since explained: `test_autonomy_transport` passes once `origin/main` is fetched; `test_showdown_family` matches the baseline on current code |
| Certified vs main-tree FAIL sets | differ by exactly one module each way: `test_autonomy_transport` (environment) and `test_own9_write_guard` (fails only because the worktree path does not name the NFL root; passes 21/21 in the main tree) |

**New regressions from this sprint: none found.**

**Failure classes** (all pre-existing at the baseline):

| Class | Examples |
|---|---|
| Environment: data outside this checkout | `nfl/vintage/weekly_rosters.197453cb51cb7383.raw.csv.gz` (only `.reduced` was ever committed), `nfl_vintage/raw/…`, the DET_BUF live candidate outputs, nflverse payloads, A1 PBP sources |
| Governance / deployment state | no `capture-prod` branch, capture surface ≠ approved release, workflows not on the default branch, retention runs from more than one tree |
| Stale generated artifacts | `HANDOFF.md` must name HEAD (impossible on a committed tree, by construction), discovery / system state / guard census / read inventory need regenerating, ratchet baselines exceeded |
| Known reported model / data state | `test_p6_false_greens` ("18 P6 reproductions are still failing — the reported state"), NYJ kicker vintages disagree, QB-room reconstruction, stat-contract counts |

**Fixed during this reconciliation:**
- `regenerate.py` had refused every run since R7 on 2026-09-10 (`LEAF_UNPLACED dc25_daily.csv`). With that fixed,
  both P4B binaries regenerate byte-identically (`fba8cddb`), and `test_rc1_receiving` (72/72) and
  `test_td2_recoverability` (52/52) now pass.
- `test_qb2_production` now runs, and shows 13 failures of its own.

**One unexplained observation.** `test_harness_audit` failed once (1 check), when run after `test_certify_suite`
and `test_non_evidentiary_refusal`. It did not reproduce on the same triple, on either ordered pair, or alone. It is
recorded here as unexplained, not called a flake; it passed in both certified runs.

**Certification verdict: FAILED (complete).** The suite completes, and that completion is now proven by an
independent parent. It does not pass, and it did not pass before this sprint either.

## D. Model-candidate status

| Candidate | IMPL | ON_PATH | CONSUMED | SUCCESS | REFUSAL | ADVERSARIAL | PROSPECTIVE | PROMOTED |
|---|---|---|---|---|---|---|---|---|
| SC-COH-1 (clean analogue candidate) | yes | no | no | yes | yes | yes | no | no |
| SC-APPEAR-1 rates | yes (research hook) | no (replays the production allocator only) | no | yes | yes | yes | no | no |
| SC-APPEAR-1 appearance gate | yes (in-memory prototype) | no | no | yes | yes | yes | no | no |
| Cheap ownership successor | yes | no | no | yes | yes | yes | no (failed its bar) | no |
| B4 duplication shadow | yes | **yes** (runner, after the upload, non-blocking) | **no, by design** | yes | yes | yes | no | no |
| B3S duplication shadow | yes | **yes** (same report) | no, by design | yes | yes | yes | no | no |

### SC-COH-1, clean evaluation

On 136 confirmation games (2025 weeks 10–18, read once):

| Endpoint | Ratio (candidate / incumbent) | Bar | Result |
|---|---|---|---|
| Energy score | 1.000 [0.989, 1.013] | superiority | fail |
| Variogram score | 1.011 [0.995, 1.028] | superiority | fail |
| Team-points CRPS | 1.037 [1.002, 1.075] | non-inferiority, margin 1.02 | fail |
| Player DK CRPS | 0.980 [0.973, 0.988] | non-inferiority | pass |

- **Player-DK interval coverage** (50 / 80 / 90%): incumbent .50 / .69 / .78, candidate .60 / .80 / .87.
- **Raw-draw accounting.** The candidate breaks no identity. The incumbent breaks many: 103,757 receiving-yards-
  without-a-catch and 26,238 receiving-TD-without-a-catch per 1.82M player-worlds.
- **The production post-steps break both arms.** After the yards rescale, QB yards ≠ receiving yards in about
  106,000 worlds. After the DST anchor, DST points ≠ tier + components in about 104,000.
- **Interpretation.** These post-steps are a defect on the live path, independent of either candidate. Repairing
  them is a production change. The candidate's structural coherence did not turn into better joint proper scores.
- **Not ready.**

### SC-APPEAR-1

- **Projection layer.** Zero-opportunity Brier .223 → .062 for qualifying players (`e0ea0fa0`).
- **Draws.**
  - Ungated, the candidate improves draw-level Brier by +0.033 (z 13.6), because it shifts mean shares.
  - The gate alone **worsens** it, by −0.048 (z −20.6). That was the primary comparison declared before scoring, so
    the gate FAILS its bar.
  - Candidate plus gate improves by +0.027 (z 8.2), but under candidate rates the gate makes things slightly worse
    than no gate (−0.006).
- **Interpretation.** The plumbing defect is real: no projection zero mass reaches a draw. But the right fix is not
  "turn on the gate": rates and gate must be fixed together, and a strict hurdle may be needed.
- **Status.** 2025 has now been read three times, so it is not a holdout for any variant chosen next.

### Cheap ownership successor

FAILED its bar on both folds (`3d057bc6`).

### B4 and B3S

- **Leave-one-slate-out, other copies on our lineups:** B4 1.01 / 1.03 / 0.70 against B0 2.92 / 5.00 / 5.70.
- **ATL@NO dry run** (ATL excluded from training): B4 predicts 2.1× to 6.5× E1's copy totals.
- **Not promotable on this sample.**

## E. Data gaps (genuinely external)

1. **Next-slate inputs.** The DKEntries export, a depth-chart capture for both clubs, confirmed starters, contest
   prize/fee/cap/field size, the FC context file (optional), and the official inactive list with an
   OFFICIALLY_VERIFIED provenance record (outbox 2026-10-07).
2. **The Hard Rock board** after SEAL_PROPS and before kickoff, with its capture sidecar (outbox).
3. **nflverse 2024–2025 weekly rosters and game-day inactives** (outbox). Without them, active zero-snap players and
   elevations stay NOT_IDENTIFIABLE.
4. **A Stat-api verification sample** for our five contest ids, plus its written terms (outbox; no purchase).
5. **Full-field DK standings** for every future Showdown, exported by the owner inside DK's 10-day window. These are
   the only way B4/B3S and any ownership model get more held-out slates.
6. **PHI@CHI DK salaries** (outbox, earlier).
7. **For the remaining environment-class suite failures:** the raw capture-storage files those modules read (the
   `nfl/vintage/weekly_rosters…raw.csv.gz` vintages, `nfl_vintage/raw/`, the DET_BUF live candidate outputs, nflverse
   payloads). The P4B binaries were regenerable and are now rebuilt; these are not regenerable from git.

## F. Next Showdown readiness

**Production, unchanged except:**
- the default-on specialist detector;
- slate-generic finishing tools (ATL outputs unchanged);
- deterministic tie order in two report files.

The football model, simulator, coverage objective and DK export are unchanged.

**Shadow, non-blocking, sealed prelock:**
- the B4 duplication report and the B3S report;
- the prop distribution seal, then the Hard Rock comparison.

**Offline shadows, not on the slate path:** SC-APPEAR-1 rates and gate, the SC-COH-1 clean candidate.

**Unresolved defects** (known and measured; none is fixed for this slate):
- the simulator ignores `p_plays`, so mid-depth zero mass is too low;
- the yards rescale and DST anchor break accounting identities;
- the incumbent's raw draws break receiving and TD identities;
- cheap-rotation ownership has no working forecaster;
- HANDOFF.md's HEAD check can never pass on a committed tree;
- 54 pre-existing suite-module failures (section C).

**Blockers:** see the final block.

**Sequence:** see the final block.

## G. Owner decisions

1. **Specialist detector default-on.** Keep it, or flip `SPECIALIST_AUTO` to default off? It changed no output on
   ATL@NO.
2. **SC-APPEAR-1 rates plus appearance gate as a production change.** Not now. When proposed it would be its own
   commit with its own baseline. It is also the only fix the evidence supports for the zero-mass defect.
3. **Repairing the yards-rescale and DST-anchor post-steps.** A simulator production change.
4. **Stat-api.** Only after a verified sample: purchase, licence and permitted use.
5. **The 1.02 non-inferiority margin** used in the SC-COH-1 pre-registration. It is a declared value judgement and you
   may override it before any next run.
6. **The suite-certificate verdict policy.** Today a FAILED certificate with only pre-existing failures is still
   FAILED. Changing that would be a governance change and I have not made it.

---

## COMPLETED SINCE THE EXTERNAL AUDIT
- **Suite completion certificate.** An independent parent with a frozen manifest, identity-matched completion and a
  terminal record. It refuses `os._exit`, signals, timeouts, stale or foreign records, duplicate-plus-missing swaps,
  torn writes, mid-run file changes and restricted runs, and isolates nested runners.
  - 42 sabotage/control checks.
  - Two real certified runs: #1 INCOMPLETE (true contamination), #2 FAILED complete.
- **Baseline comparison of every failing module** against the pre-sprint commit, in the same environment: no
  regression.
- **SC-COH-1 contamination audit and clean evaluation.** The candidate fails 3 of 4 pre-registered endpoints. The
  old result is reclassified as development evidence.
- **SC-APPEAR-1 end-to-end trace.** `p_plays` never reaches the draws. The gate prototype fails alone and helps only
  together with corrected rates.
- **Copy-count semantics for B4/B3S.** All copies vs other copies; unique-lineup units.
- **Hard Rock capture contract** and win / loss / push / void / unresolved settlement.
- **Stat-api verification-sample request.** No purchase.
- **`regenerate.py` repaired** (broken since 2026-09-10); both P4B binaries are EXACT_REPRODUCIBLE again.
- **The certificate's own misclassification of OWN_PROCESS results** found and fixed.

## STILL OPEN
- **An event-linked football world.** Neither the incumbent nor the clean analogue candidate passes. The live
  yards-rescale and DST-anchor post-steps break accounting in both arms.
- **Simulator consumption of `p_plays`.** It must go in together with corrected rates, never the gate alone. A
  prospective test on a sealed forward window is still needed.
- **A player-level cheap-rotation ownership forecaster.** A legal-field ownership forecaster (B-family currently
  takes marginals as given).
- **B4/B3S evidence:**
  - more held-out full fields;
  - an entry-weighted panel;
  - a prospective pre-registration-section-7 test on the next slate.
- **Portfolio ablation:**
  - CVaR / downside objective;
  - ownership-perturbation stress test;
  - a real payout table;
  - self-competition between our own entries.
- **Suite health:**
  - 67 of 368 modules with defects (pre-existing);
  - the suite writes 10 tracked files;
  - the HANDOFF HEAD check is impossible by construction;
  - no dependency lock file;
  - one unexplained single failure of `test_harness_audit`.

## INVALIDATED OR SUPERSEDED
- **SC-COH-1** (`SC_COH_1_MEASUREMENT.json`): the candidate-vs-history result is now DEVELOPMENT_EVIDENCE. It used a
  market-matched candidate, an outcome-derived pool, and an incumbent that had seen 2025.
- **The first cheap-ownership successor:** FAILED its bar on both folds.
- **The "OTHER entries" label** on the B4 shadow and its sealed dry runs: they are all-copies figures (the note
  supersedes the wording).
- **The audit's "SC-APPEAR-1 needs production-path validation"**: superseded. The allocator replay exists, and the
  remaining gap is now located precisely at `showdown_draws.py:103`.
- **The audit's legal-lineup ownership formula**: already implemented as the B-family maxent.
- **The audit's suite evidence gap**: closed by certificate #2.

## SHADOW MODELS READY FOR NEXT SHOWDOWN
- **B4 duplication shadow** and **B3S duplication shadow**: prelock, sealed, non-blocking, on the runner path, and
  never read by selection.
- **The prop-distribution seal** and the Hard Rock comparison (downstream only).

## PRODUCTION CHANGES REQUIRING OWNER APPROVAL
- **PRODUCTION CHANGES APPROVED: NONE unless explicitly authorized.**
- **The automatic specialist detector is default-on in production** (made under readiness directive item 6; it
  changed no output). Confirm it stays on, or say so and it will be flipped off.
- **Not proposed for this slate:**
  - SC-APPEAR-1 rates plus a draw-level appearance gate;
  - repair of the yards-rescale and DST-anchor post-steps.
- **Purchase or licence of any historical contest archive (Stat-api):** only after a verified sample.

## EXTERNAL DATA STILL NEEDED
- **Next-slate inputs:**
  - the DKEntries export;
  - depth charts for both clubs;
  - confirmed starters;
  - contest prize, fee, entry cap and field size;
  - the FC context file;
  - the official inactive list with an OFFICIALLY_VERIFIED provenance record.
- **The Hard Rock board** with its capture sidecar, after SEAL_PROPS and before kickoff.
- **nflverse 2024–2025 weekly rosters and game-day inactives.**
- **A Stat-api verification sample** plus its terms.
- **Owner DK full-field exports** for every future Showdown, inside the 10-day window.
- **PHI@CHI salaries.**
- **The raw capture-storage vintages** read by the environment-class suite modules.

## NEXT SHOWDOWN BLOCKERS
- Next-slate inputs not yet captured.
- Official inactives with OFFICIALLY_VERIFIED provenance (without them the run is NOT_READY by design).
- The Hard Rock board, needed only for the market comparison, not for the DFS upload.
- After any container reset: `bash nfl/tools/rebuild_derived.sh` must print DERIVED_READY before anything else.

## NEXT EXECUTION STEP
1. `bash nfl/tools/rebuild_derived.sh` (expect DERIVED_READY).
2. Fill `SLATE.json` from `nfl/dfs/salaries/NEXT_SLATE_CONFIG_TEMPLATE.json` with the captured files.
3. `python3.12 nfl/tools/showdown_next_slate.py run SLATE.json --mode precompute` (never READY).
4. At the inactive deadline, add the official list and its provenance, under a new scenario name, and run
   `python3.12 nfl/tools/showdown_next_slate.py run SLATE.json`. This goes DISCOVER → VERIFY → FREEZE FOOTBALL
   REALITY → PROJECT → SIMULATE → BUILD DFS PORTFOLIOS → RUN B4 SHADOW → SEAL PROP DISTRIBUTIONS → FINAL VERIFY.
5. The networked agent captures the Hard Rock board plus its sidecar.
6. `python3.12 nfl/tools/showdown_next_slate.py market SLATE.json BOARD.csv`.
7. Commit the ledger, freeze, B4 shadow and prop seal before kickoff.

After the game:
- grade the B4 pre-registration section 7;
- settle the props;
- obtain the owner's full-field export.

Nothing in this path uploads to DraftKings or enters a contest, and no wager is recommended.

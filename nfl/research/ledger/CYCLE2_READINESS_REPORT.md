# Cycle 2 readiness report (owner OD-001 and OD-002, 2026-10-14)

**Verdict: neither Classic nor Showdown is production-ready, and nothing here is production-certified.**

The cycle repaired and proved specific defects. What the code itself now refuses is listed under
"Release blockers" below.

**No certified release is possible today.** Every Classic or Showdown release refuses on the eligibility evidence gate
until game-day elevation records exist (ELIG-D5, RES-009). That refusal is the gate working.

## 1. Head, commits, and where the code is

| commit | content |
|---|---|
| `59d9424b` | Suite trust (P0-B): zero-check functions, tracked-file writes, counted point-in-time checks, live pins |
| `d08e2123` | PERF-D1: vintage-manifest encodings cached; equivalence proven |
| `e0a45d9f` | Point-in-time fail-closed; shared three-state eligibility contract (OD-001, OD-002); ENG-014, ENG-017 |
| `08c8443e` | Production-critical gate: `run_suite.py --gate` |
| `3fc67181` | Ledger (85 issues), f0d2e104 baseline, red-module and PIT audits, OD-002, RES-009 |
| (this commit) | Evidence-watch test under OD-002; SC-APPEAR-1 staleness recorded; this report |

**Where the code is.** All of it is committed and pushed to `claude/nfl-greenfield-architecture-stsxmk`.
- It is **not** merged to `main`.
- No production slate has been run with it.
- Nothing remains only in an overlay. The overlays used for testing were removed after their files were copied and
  committed.

## 2. Test results, reported separately

### Full suite (authoritative)

Run: `python3.12 nfl/tests/run_suite.py`, sorted order, isolated overlay. Record: `BASELINE_CYCLE2.json`.

| head | modules | checks | failing | raised | zero-check fns | blocked fns | red modules | tree writes |
|---|---|---|---|---|---|---|---|---|
| 68130941 (cycle 1) | 405 | 18,182 | 188 | 111 | 5 | 24 | 67 | 3 |
| f0d2e104 (before cycle 2) | 406 | 18,373 | 184 | 109 | 5 | 24 | 63 | 3 |
| **3fc67181 (cycle 2)** | **411** | **18,784** | **164** | **88** | **0** | 29 | **61** | **0** |

The verdict is still **SUITE FAIL**.

**From f0d2e104 to 3fc67181:**
- **Turned green:** `test_showdown_family`, `test_uncalled_governance_guards`, `test_v1_projection` and
  `test_world_clock`.
- **Newly red, `test_classic_evidence_watch`:** the OD-002 gate blocked its pre-contract fixture. **Fixed after the run**
  (19 checks, 0 failing).
- **Newly red, `test_sc_appear_1_production_path`:** a shadow result pinned to old production bytes. **Left red on
  purpose** as a staleness signal (SA1-STALE).
- **The 59 other red modules** each have one cause class in `RED_MODULES_68130941.json`. In the f0d2e104
  classification, 17 are real defects and 4 are unknown. The rest are stale pins, assertions on live data, missing
  data, environment dependence, or bugs in the tests themselves.

### Production-critical gate (not a suite result)

`nfl/tests/PRODUCTION_GATE.json` lists 32 modules across nine categories:

- eligibility
- point in time
- release and lock
- lineup rules and selection
- market and FC firewall
- identity
- accounting
- state builders
- governance and harness

| run | order | verdict | checks | blocked |
|---|---|---|---|---|
| fresh overlay, cycle-2 code | sorted | **PASS** | 1,443 | 0 |
| `3fc67181` | shuffled, seed 20261014 | **PASS** | 1,716 | 0 |

A BLOCKED function fails the gate.

**Excluded, each with its reason:**

| module | reason |
|---|---|
| `test_spending_gate`, `test_autonomy_transport` | they depend on remote git state |
| `test_qb2_production` | open defect TEST-D9 |
| `test_field_model` | open defect FIREWALL-D1 |
| `test_dfs_eligibility`, `test_dfs_identity_crosswalk` | no production entrypoint reaches the code they guard |

**What the exclusions do and do not mean:**
- **No known production-critical failure was excluded to make the gate green.**
- The two open defects are excluded *because* they are red. They are recorded as gate gaps, and they are admitted
  when fixed.

## 3. Defects

**Fixed and proven this cycle.** Each has a failing regression test that now passes, and a mutation control:

| id | what was wrong | proof |
|---|---|---|
| AVAIL-D1, ELIG-D1, ELIG-D3 | see section 4 | integration to zero draws; 10 mutations caught |
| AVAIL-D2, LOCK-D1 (ENG-014) | a Showdown run with no roster capture, or after kickoff, could release | `test_showdown_release_status`; 3 mutations caught |
| ENG-017 | configuration was not recorded; environment variables were undeclared | `EFFECTIVE_CONFIG.json`; an undeclared `NFL_SHOWDOWN_*` refuses |
| WC-D1 | world_clock counted game days on or after the as_of | `test_world_clock` |
| TEST-D2, D7, D8, D10; TREE-D1; ZERO-D1; GOV-D1 | suite-trust defects | full suite: 0 zero-check, 0 tracked-file writes |
| PERF-D1 | the manifest was re-encoded on every call | 25.7 s → 1.4 s per call; identical output at three cutoffs, warm and cold; invalidation tested |

**Still open.**
- **PIT-D1 (partial):** see section 5.
- **P1 open or gated:**
  - selector: SEL-D1, SEL-D2
  - candidate generation: CAND-D1, CAND-D2
  - receiver spread: REC-SPREAD-C2
  - depth and roles: L4-DEPTH, PART-D1, ROLE-D1, ALLOC-1
  - quarterback change: QB-D1
  - world accounting: ACC-D1 (owner-gated)
  - full-slate rehearsal: REHEARSAL-D1
  - test fixture: TEST-D9
  - eligibility: ELIG-D4 (owner standard), ELIG-D5 (data)
  - prize and field model: FIELD-D1 (data)
  - week-5 play-by-play: DATA-D1 (data)
  - source rights: RIGHTS-D1 (owner)

  The ledger holds all 86 issues.

## 4. Eligibility (OD-002): integration evidence and coverage

**The contract.** Shared code is `nfl/tools/roster_eligibility.py`.

| state | treatment |
|---|---|
| **Confirmed ineligible** | Zero opportunity before projection. Covers RES/EXE/CUT on a current capture, released players, and practice-squad players not named by supplied elevation records. |
| **Unresolved** | Kept in the forecast as the incumbent had him; never selectable; the missing evidence is named. |
| **Conflict** | Roster status against a reported activation. Left as the incumbent had him; refuses release. |

A certified release refuses while any unresolved player carries projected opportunity:
- Classic: `classic_release` blocks.
- Showdown: `showdown_tonight` marks the run DIAGNOSTIC.

**Integration** (`test_roster_eligibility_contract`, 49 checks):

| pipeline | result | control |
|---|---|---|
| Classic W5 | Confirmed-ineligible players get no projection and no share of club volume in the simulator. Unresolved players keep their projection. | With the rule removed, they are projected again. |
| Showdown ATL@NO | A confirmed-ineligible player draws zero DK points in all 200 worlds. An unresolved player keeps nonzero draws, and the release gate names him as material. | With the rule removed, he has nonzero draws. |

In both pipelines, no other player's status moves.

**Coverage, W5 Classic.** Full audit: `nfl/research/contract45/AUDIT_W5_ELIGIBILITY_COVERAGE.md`.

- **Counts:** 270 confirmed eligible, 56 confirmed ineligible, 99 unresolved.
  - The 99: 92 practice-squad players with no elevation records, and 7 absent from the capture.
- **Truly ineligible among the 99:** none can be proven from this repository.
  - The league's two-elevation limit implies at least 60, but not which 60. The limit is unverified here, because
    engineering has no network.
- **Distortion from the earlier withholding:** small. 3.13 projected DK across 99 players; no club's total moved by more
  than 0.055 DK.
- **The unresolved now carry 7.64 DK.** Every certified release refuses until RES-009 supplies the elevation records.

**Roster-source freshness.**
- The W5 capture is `20261010T074137Z`, **33.3 h before kickoff**, before the Saturday transaction window.
- Both W5 conflicts (Tim Patrick, Ben Yurosek) are activations reported after the capture.
- Freshness is recorded in the state and in the release record. What counts as current enough is **ELIG-D4, an owner
  standard.**

## 5. Point in time: negative controls and what remains

**Proven.** Each was mutation-tested; seven mutations were caught.

- **Live mode refuses a past cutoff.** It is refused whenever any guarded capture, TEAM_GAME, `nfl/derived` cache or
  `nfl/sim` fitted model has content first seen after the cutoff. At the W4 cutoff, derived caches are refused.
  - Control: a fitted model injected with a post-cutoff clock is refused.
- **Manifest mode refuses a manifest sealed after the run's cutoff.**
- **Injection is refused.** An injected capture, even one claiming a pre-cut clock, cannot move a sealed reader. With
  no manifest it does move the reader (the control). An unwired direct open is refused.
- **Removal leaves a sealed forecast unchanged.** Removing the post-cut capture leaves the sealed pick unchanged.
- **A refusal in kicker rates propagates.** It no longer becomes KICKER_RATES_ABSENT.
- **The exemption cannot reach a release.** A `pit_exempt` state is NOT_POINT_IN_TIME and RELEASABLE false; the release
  record and `showdown_tonight` refuse it. A Classic as_of at or after kickoff is also RELEASABLE false.
- **No production caller passes `pit_exempt`**, and no environment variable disables the gate (PIT audit).

**Still open.** PIT-D1 stays OPEN. Audit: `nfl/research/ledger/PIT_AUDIT_CYCLE2.json`.

| id | gap |
|---|---|
| PIT-D2 | readers take every captured week; they need date filtering against the cutoff |
| PIT-D5 | per-slate inputs are never time-checked |
| PIT-D6 | stages after the state are not bound to the manifest |
| PIT-D7 | fitted files outside `nfl/sim` |
| PIT-D8 | pins are declared, not proven |
| PIT-D9 | the Classic run rewrites a pinned cache |

## 6. Release blockers and uncertainties

**Release blockers the code enforces today:**
- ELIGIBILITY_UNRESOLVED_MATERIAL, on every slate until elevation records exist.
- ELIGIBILITY_CONFLICT.
- ELIGIBILITY_NOT_APPLIED, for a Classic slate without a roster capture.
- NOT_POINT_IN_TIME_STATE.
- RUN_AFTER_KICKOFF (Showdown).
- DIAGNOSTIC_NOT_RELEASABLE.
- The existing chain, lock and verify checks.

**Owner decisions outstanding:**
- ELIG-D4: the freshness standard.
- OD-001 and OD-002 entries in `OWNER_DECISIONS.md`. They are recorded in OWNER_INBOX; agents cannot write the file.
- RES-009 authorization.
- The Perplexity historical player-game dataset: not found in this session or the repository.

**Uncertain:**
- The 12 ledger entries taken from the agent classification. Each is REQUIRES_REPRO unless re-read (CAP-D1 was re-read: VERIFIED).
- Whether the two-elevation league rule is as stated.
- SA1-STALE: shadow results recorded on older production bytes.

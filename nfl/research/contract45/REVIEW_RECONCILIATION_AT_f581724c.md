# Owner review, step 1: reconciliation of the #45 checkpoint at HEAD `f581724c` (2026-10-11, 20:56 UTC)

- **Scope:** read-only. No code was edited for this step. The checkers were re-run on the three Week 5 worlds
  (incumbent production, CORRECTED_V1, and its no-participation control).
- **Status labels:** VERIFIED (code path executed and output read), FAIL, UNVERIFIED (code exists but no run proves
  it), PLANNED (not built).

## 1. What HEAD contains

| item | value |
|---|---|
| commit | `f581724c8263ef3c0460623965849eb2a29ea372`, 28 commits since `4c80a712` (step A audit), 116 files |
| uncommitted | `nfl/dfs/inbox/INBOX_LEDGER.jsonl` (owner inbox, private; deliberately not committed) |
| fixtures | `nfl/tests/fixtures/release_w5_2026-10-11/` (19 files, 5.5 MB); `nfl/tests/fixtures/contract45_w5_2026-10-11/` (6 files + MANIFEST, 8.2 MB, SHA-256 per file) |
| preregistrations | PM-1, PM-2 (VOID), PM-3; ECW-2 (+A1); ECW-3; SIM-D9; acceptance measure C3 (`ECW3_ACCEPTANCE_MEASURE.md`) |
| production files | PROJ `87f826b1…`, DRAWS `5dbe7836…`, WORLDS `b6cec1bd…`, UPLOAD `cce6dfb5…`: unchanged |
| run ids | **none.** Every Week 5 build, production and replay, was run stage by stage. The replay's ledger is the dry run's (`2026W5-DRY`); draws and portfolios carry `run_id: null`. |

## 2. Is each #45 control invoked by the governed Classic entry point?

`nfl/tools/classic_slate_pipeline.py` is the governed entry point.

| control | in the entry point | executed end to end, non-dry | status |
|---|---|---|---|
| lock check (fresh clock) | `run()` calls `lock_check` before any stage (`classic_slate_pipeline.py:212-223`) | dry run only. It recorded `AFTER_LOCK` at 20:06:17Z in the replay's ledger. Unit-tested at 4 clock times (`test_classic_pipeline` 04). | VERIFIED as a function; UNVERIFIED as a refusal on a live run |
| run lock, crash recovery | `acquire_run_lock` / `release_run_lock` around `_run` | tested in `test_classic_evidence_watch` | VERIFIED in tests, never on a real run |
| ledger after every stage | `_run`, written after each stage | never on a W5 run | UNVERIFIED |
| release record (lineage, accounting, overlap, defects) | stage `release` (`stages()`, line 95) | the tool was run by hand on the replay, not through the pipeline | VERIFIED as a tool; UNVERIFIED as a pipeline stage |
| finalize refuses without a non-BLOCKED release | `classic_finalize.py:161-163` | never on W5 | UNVERIFIED |
| evidence watcher, launches a rebuild on new evidence | `classic_evidence_watch.py --launch` | **nothing invokes it**: no workflow, no schedule, no caller outside its own test | **PLANNED** (decision logic is tested; triggering is not wired) |
| immutable snapshot of each build | stage 0 `snapshot` | never on W5 | UNVERIFIED |

**Integration is PARTIAL.** The controls exist and each is tested in isolation, but no money-facing Classic build has
gone through them. The Week 5 replay repeated the same hand-run pattern the step-A audit found.

## 3. Answers to the owner's questions

**Q1. Which 2 of 30 checks failed?**
- Both are receiver spread only: `test_contract45_integration` 06b, corrected 1.2363 and control 1.2287, against
  [0.85, 1.15].
- The QB checks (06) and the scoring checks pass.
- They remain registered failures.

**Q2. What do 35,234 and 0 count, and does 35,234 agree with 30,281/32,000?**

The release record sums `world_accounting_check` (spec `world-accounting-1`) violations by law. **The sum mixes units:**

| law | incumbent 16:17Z | unit | CORRECTED_V1 | control |
|---|---|---|---|---|
| PASS_YDS_EQ_REC_YDS | 30,281 | club-worlds of 32,000 (16 × 2,000) | 0 | 0 |
| PASS_TD_EQ_REC_TD | 76 | club-worlds of 32,000 | 0 | 0 |
| POINTS_GE_6_PER_TD | 1,068 | club-worlds of 32,000 | 0 | 0 |
| YDS_WITHOUT_CATCH | 2,000 | worlds of 2,000 (any player) | 0 | 0 |
| REC_TD_WITHOUT_CATCH | 1,809 | worlds of 2,000 | 0 | 0 |
| TARGETS_LE_ATTEMPTS, REC_LE_TARGETS, INT_LE_ATTEMPTS, INT_LE_OPP_TAKEAWAYS, INACTIVE_NO_EVENTS, DK_FROM_PUBLISHED | 0 | — | 0 | 0 |

- The 30,281/32,000 figure **is** the first row: the same law, the same worlds.
- **35,234 is not a meaningful single number.** It adds club-worlds to worlds. It should be reported per law with its
  denominator, never as a total. That is a reporting defect in `classic_release.world_accounting` and in my own
  summaries.

A **second checker**, `event_consistent_worlds.event_checks`, was run on the same three files for this review:

| law | incumbent | CORRECTED_V1 | control |
|---|---|---|---|
| REC_TD_LE_RECEPTIONS | 1,849 of 2,000 worlds | 0 | 0 |
| RUSH_TD_LE_CARRIES | 1,010 of 2,000 | 0 | 0 |
| RUSH_YDS_WITHOUT_CARRY | 4 of 2,000 | 0 | 0 |
| **POINTS_EQ_EVENT_SUM** | NOT_MEASURABLE | **NOT_MEASURABLE** | **NOT_MEASURABLE** |
| **KICKER_DK_FROM_EVENTS** | NOT_MEASURABLE | **NOT_MEASURABLE** | **NOT_MEASURABLE** |

- The Classic worlds artifact stores no per-world scoring events. PREREG_ECW2 section 2 requires "club points ==
  the event sum in every world", and **that has not been verified on the published Classic worlds**. The builder does
  it by construction, but nothing checks it after publication.
- The release record runs only the first checker, so these three incumbent laws are not in its count.
- "0 violations on every law" in `ECW3_RESULT.md` and `CORRECTED_V1_W5_REPLAY.md` is true of the first checker's laws
  only. It is corrected here.

**Q3. Was PM-3 fitted on a truly untouched split?**
- **No untouched historical split exists for PM-3.**
  - PM-3's φ was fitted on 2016-2023 only.
  - PM-3 itself was designed after PM-1's 2024-2025 hold-out had been read, and after PM-2's REUSED 2024-2025
    calibration had been read.
  - Keeping PM-1's P(no participation) over PM-2's was also decided after reading 2024-2025 (`PM2_RESULT.md:31-32`).
- No REUSED score is claimed for PM-3 (`PREREG_PM3_PARTICIPATION.md:32`).
- **The reserved hold-out is prospective:** 2026 weeks 6-11, graded once nflverse publishes 2026 participation. That
  is after the season, so PM-3 will have no evidence before then.

**Q4. Why are the two 20-max contests disjoint?**
- **Policy, not validated optimality.** It comes from the owner's contract clause 6 ("must not share identical lineups
  by default"), as encoded in `classic_release.MAX_SHARED_LINEUPS_EQUAL_SIZE = 0`.
- The cost was measured and recorded: bar-clearing proxy 0.4355 → 0.4255 / 0.3955 on the incumbent.
- No contest-economics evaluation (payouts, field, duplication) has been run. This is now an owner conflict between
  clause 6 and the review's step 6, and it waits on the owner.

**Q5. Does a money-facing orchestrator consume the new controls?** No run proves it. See section 2: **PARTIAL**.

**Q6. Can the corrected simulation pass accounting and still fail realism?**
- Yes, and it does now:
  - accounting: 0 on 11 + 3 laws;
  - realism: receiver spread FAIL (1.23 against ≤ 1.15).
- The gates are separate in the code. The release record carries only accounting. The realism checks
  (`ecw2_acceptance.py`) are in no release or finalize gate, so a build failing realism can read
  CURRENT_BUT_UNCERTIFIED. That is a gap.

**Q7. Where are licensing and acquisition recorded?**
- `nfl/research/participation_pm1/NOTICE.md` and `ACQUISITION.json` record URL, retrieval time and SHA-256 per
  file.
- Participation data: FTN Data via nflverse, **CC-BY-SA 4.0**.
- Injuries: terms **UNKNOWN**.
- **Both raw sets, and the tables derived from them (PM1_TABLE, PM3_PHI, PM2_TABLE), were committed and pushed to
  this repository.**
  - Under CC-BY-SA the derived tables carry a share-alike obligation, which is not declared on them.
  - The injury files are redistributed under unknown terms.
  - **This needs the owner's decision** (see section 5).

## 4. Status of every remaining requirement

| # | requirement (owner review) | status | evidence |
|---|---|---|---|
| 1 | HEAD frozen and reconciled | VERIFIED | this document |
| 2 | 2/30 failures closed | **FAIL** (kept failing) | W5 [0.85, 1.15] FAIL preserved. C3 registered after W5 was seen, so W6 is not confirmatory (`ECW3_ACCEPTANCE_MEASURE.md`). |
| 2 | Week 6+ hold-out pre-registered, confirmatory sample reserved | PLANNED | not yet written |
| 3 | QB and opponent joint conditioning | PARTIAL / FAIL | receiver yards and pass volume respond (06 VERIFIED); passer scoring, sacks, turnovers, DST and game script do not |
| 3 | trait-distinct vs trait-identical QB negative controls | PLANNED | — |
| 4 | inactive vs dressed-zero-snap vs low-usage vs injury-limited | UNIDENTIFIED for the first two | `pbp_participation` is per play. It has no active-roster indicator, so zero snaps cannot separate inactive from active-unused (PM1_RESULT limitation). |
| 4 | fit by role and injury with uncertainty, hierarchy and dates | PARTIAL | PM-1 cells with back-off levels; no hierarchy; role band mapped from the projection, not measured |
| 4 | licensing and share-alike review | **OWNER DECISION** | section 3, Q7 |
| 5 | realism beyond identities (distributions, catch rate, score, margin, ties, turnovers, DST/K, correlations) on untouched chronological samples | PARTIAL | ties pass; receiver spread fails; SIM-D9 and SIM-D10 measured; the rest not measured; **points == event sum NOT_MEASURABLE** on Classic artifacts |
| 6 | contest-economics evaluation of overlap vs disjoint | PLANNED; **OWNER DECISION** on clause 6 | needs contest payout tables (owner export) |
| 7 | one-command current-evidence rebuild, triggered | PARTIAL | entry point exists; watcher not triggered by anything; no non-dry W5 run |
| 7 | crash restart, idempotency, immutable snapshots, scratch isolation, hash enforcement, strict lock | UNVERIFIED on a real run | run lock and stale recovery tested; snapshot stage never run on W5; the hash chain is checked after the fact by the release, not enforced by each consumer at read time |
| 7 | no hidden production bypass | **FAIL** | every stage tool can still be run by hand. That is how W5 production and the replay were both built, and only the release record names it (NOT_ORCHESTRATED, uncertified, not blocked). |
| 8 | prospective incumbent vs corrected on the same frozen pre-lock slates | PLANNED | PREREG_ECW2 section 3 (weeks 6-11) exists; the pre-lock archive job does not |

## 5. Escalations (owner)

1. **Data rights.**
   - CC-BY-SA participation files and derived tables, plus injury files of unknown terms, are in the pushed public
     history.
   - Options:
     - (a) keep them, and declare CC-BY-SA with attribution on the derived tables;
     - (b) remove the injury files at the tip and stop publishing derived tables;
     - (c) rewrite history.
   - (c) is destructive and needs explicit approval. Nothing has been changed pending the owner's choice.
2. **Clause 6 vs the review's step 6.** Zero overlap stays enforced until the owner rules. Testing overlap as a
   shadow arm needs the contest payout tables.

## 6. Corrections to my earlier reports

- "0 violations on every law" covered the first checker only. Event-sum scoring is not measurable on the published
  Classic worlds.
- "35,234 violations" summed incompatible units.
- Twice during the session I stated a UTC time without reading the clock ("20:03Z" at about 19:58; "21:00Z" at
  20:55). The standing rule is to read the clock first.

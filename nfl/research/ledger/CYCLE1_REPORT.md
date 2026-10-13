# Permanent-repair mandate: cycle 1 report (2026-10-13)

- **Machine-readable evidence:**
  - `ISSUE_LEDGER.json`: 43 issues. It is validated by `nfl/tests/test_issue_ledger.py`: the mandated fields, the
    vocabulary, and that every cited file and line exists.
  - `BASELINE_CYCLE1.json`.
  - `CALLGRAPH_AT_2f510449.json`.
- **Nothing was promoted, submitted or wagered.** No owner export or private file entered the repository.

## 1. Ledger delta and the top 5 root causes by impact

**The atlas, checked against HEAD.**

- **WRONG:**
  - receiver-spread figures (1.27/1.48; the repository has 1.236/1.445 against a bar of 1.15);
  - "35,234 and 30,281 are two counts" (they are one count).
- **SUPERSEDED:**
  - Palmer/LA;
  - the Showdown reserve gate (still conditional);
  - overtime field goals (corrected arm only);
  - the 20/20 duplicate.
- **Falsified, kept withdrawn:** the solver defect and the RB2 tail.
- **Not exhaustive.** Cycle 1 found the following that the atlas omits:
  - **GAME-ID-D1:** the Showdown game was chosen by club pair, not orientation;
  - **TALLY-D1:** two guard modules were invisible to the suite;
  - **UPL-D2:** the verifier did not check completeness;
  - **TEST-D4:** a guard read the live warehouse and silently stopped running.

**Top 5 root causes:**

1. **A step that returns partial or no evidence is read as success.** Every TALLY-D1, TEST-D4, AVAIL-D2 and UPL-D2
   instance had this shape.
2. **Selection and generation share worlds and are coupled across contests** (SEL-D1/D2/D3, CAND-D2). That
   instability is what Monday exposed.
3. **The incumbent forecast arm is the default although its worlds break box-score laws and miss calibration**
   (ACC-D1, REC-SPREAD-C2). Changing that is gated by the owner.
4. **Identity is resolved in several places that disagree** (ID-D1, GAME-ID-D1, AVAIL-D3).
5. **Roles are not conditioned on who else is active, and a QB change does not propagate** (ROLE-D1, QB-D1, ALLOC-1).

## 2. Code references and call chain

- **Showdown:** `showdown_tonight.run` → `showdown_slate_state.build` → `showdown_slate_run` (worlds) →
  `showdown_portfolio` (`near_optimal_candidates` → `build_contests` / `ladder` / `select` / `swap_polish` →
  `verify_upload`).
- **Classic:** `classic_slate_pipeline` stages: `classic_slate_state`, `classic_slate_run`, `nfl/opt/classic_portfolio`
  (`exact.solve_structured`), `classic_upload_verify`, `classic_release`. That is 16 stage scripts in all.
- **Reachable from no entrypoint:** `nfl/dfs/classic/optimizer.py`, `nfl/opt/contest.py`, `nfl/field/ownership.py`.

## 3. Pre-registered hypotheses, cohorts and independent evaluation

- **`PREREG_SEL2_PROSPECTIVE_W6.md` (`2f510449`)**, plus amendments 1-2 (`d65afa39`), written before any W6 data.
  - Confirmatory unit: 3 ≤ n < 100 contests from W6 onward. W4 and W5 are excluded.
  - One analysis, at 6 non-tied contests.
- **Registered next, as queue items, not yet written:** CG-1 (ENG-015) and ALLOC-1 (ENG-016). Each prereg is
  committed before its run.

## 4. Input rights and time

| input | rights and time |
|---|---|
| Play-by-play | nflverse, public. The newest blob holds **weeks 1-4 only** (file time 2026-10-07). Week 5 is requested as RES-008 from the network agent. |
| `TEAM_GAME` vintage for the frozen ATL@NO replay | `8feac0f3` (2026-10-01), from git |
| FC files and owner contest exports | private; not read into the football model |

## 5. Before and after tests, with negative controls

| repair | before | after | mutation | controls |
|---|---|---|---|---|
| TALLY-D1 (`033f19c5`) | 0 checks counted, UNRECOGNISED_TALLY ×2, SUITE FAIL | 282 checks, 0 failing | an inverted check → SUITE FAIL | — |
| UPL-D2 (`f3c8565a`) | a partial upload verified PASS | refused, as is a within-contest repeat | block off → 2 failures | the TB@DAL (190 rows) and ATL@NO (172 rows) production uploads still PASS; one dropped or repeated real row is refused |
| GAME-ID-D1 (this cycle) | a W17 slate could read W4 | orientation match; ambiguity refuses | reverting → 2 failures | — |
| TEST-D1 / ENG-013 (this cycle) | the re-key and reserve fixes had no test | 13 checks | re-key off → 2 failures; roster block off → 1 failure | — |
| TEST-D4 (this cycle) | 1 failure, specialist checks skipped | 30 checks, 0 failing, at the slate's own vintage | — | — |

**Authoritative full suite at `68130941`** (log `nfl/tests/certificates/SUITE_LOG_CYCLE1_68130941.txt`):

- 405 modules, 18,182 checks, 188 failing checks, 67 failing modules: **SUITE FAIL**.
- **Against the 2026-10-07 certificate:** 53 modules still red, 5 now green, 35 new modules, and 11 newly red. All 11 are
  classified in `BASELINE_CYCLE1.json`:
  - 4 are time-dependent tests reading live data (TEST-D4 and TEST-D6 fixed; TEST-D7 and TEST-D8 open);
  - 2 are environment (ENV-D1: stale `origin/main`);
  - 2 are now fixed by this cycle (TALLY-D2, TEST-D5);
  - 1 is guard scope (FIREWALL-D1; the protected property holds);
  - 2 need reproduction (TEST-D9, GOV-D1).
- None of the 11 traces to a cycle-1 code change.

## 6. Production no-change proof

- **No forecast, world or portfolio selection changed.**
- **The repairs only add refusals** (the verifier, game ambiguity) or tests.
- **The frozen production uploads re-verify PASS.**
- **SEL-2 stays opt-in**, by the owner's decision.

## 7. Unfinished and blocked

**Owner decisions:**

- **AVAIL-D1.** Your 2026-10-11 ruling ("a roster snapshot alone never zeroes a player") conflicts with this mandate
  ("no reserve/practice squad usage absent current elevation") for Classic DEV players.
- **ENG-014.** Make the direct Showdown path refuse a run without a roster capture, or after kickoff.
- **ENG-017.** Record the selector, overlap policy and arm in the audit, and strip inherited env vars.
- **ACC-D1 / ARM-D1.** Which arm is production.
- **OD-1 / OD-2.** Source rights (RIGHTS-D1).
- **FIELD-D1.** Prize tables.

**Blocked on data:** DATA-D1 (week 5, RES-008).

**Open, authorized:**

- CG-1 (ENG-015);
- ALLOC-1 (ENG-016);
- `test_showdown_family`'s stale pin (ENG-018);
- the Showdown verifier's name-only inactive check (UPL-D1);
- the lock-check gaps (LOCK-D1, LOCK-D2).

## 8. Next autonomous task

1. Read the suite tally at `68130941` and add every newly red module to the ledger.
2. Commit the GAME-ID-D1, ENG-013 and TEST-D4 repairs.
3. Write and commit the CG-1 pre-registration (ENG-015), then build its harness.

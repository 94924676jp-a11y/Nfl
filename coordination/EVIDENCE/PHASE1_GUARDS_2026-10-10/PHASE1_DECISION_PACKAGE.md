# Phase 1 decision package: N1 floor guard and N2 git/PR guard (NFL, report-only)

Branch `claude/phase1-guards-report-only`, pushed for review, **not merged, nothing armed**. Base `0c5bf600`.
Evidence directory `coordination/EVIDENCE/PHASE1_GUARDS_2026-10-10/` (paths below are relative to it unless they start
with `nfl/` or `coordination/`).

## Verdict

**Phase 1 PASSES as a report-only capability.** Three reviewers who did not write the guards measured them on
fixtures and history they had never seen. The last held-out measurement, of commit `ca7a85af`, found:
- git_guard caught every protected case: 25/25, plus 23/23 supplementary variants, with no false positives on
  ordinary commands (0/15 and 0/7);
- floor_guard's findings on untouched history were right 78 times out of 84 (92.9%);
- floor_guard caught 12 of 12 seeded cases.

Every critical finding of all three reviews is fixed and pinned by a test. Numbers after each fix are labelled
in-sample.

**Guaranteed protection is BLOCKED on the owner.** GitHub has no branch protection and no rulesets on any branch
(measured 2026-10-11), and nothing an agent builds substitutes for that.

## Acceptance criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Isolated branch; nothing changed in production, protected governance, forecasting, simulation, portfolios or the baseline | PASS | `git diff --name-status 0c5bf600` lists guard code, tests, the hook matcher in `.claude/settings.json`, `.gitignore` and evidence. Nothing under `nfl/sim`, `nfl/dfs`, `nfl/production` or `nfl/postgame`; no baseline, seal or entry file. |
| 2 | N1 report-only, not a gate | PASS | `ENFORCEMENT = 'REPORT_ONLY'`, pinned by `nfl/tests/test_floor_guard.py::test_06`. Nothing calls it. |
| 3 | N2 extends mode_guard; no competing hook | PASS | One PreToolUse entry (`nfl/tests/test_git_guard.py::test_08`). |
| 4 | Protected operations fail closed when authorization is missing or invalid | PASS (as would-deny records) | Each of these leaves a would-DENY record: a missing or corrupt policy; a non-object, non-string, oversized, non-UTF-8 or unparseable payload; an import failure; a runtime error; an unknowable push destination; an agent-written approval file. Tests 04, 05, 09, 11, 13; `coverage_review_2/results_task_c_git_FINAL_IN_SAMPLE.txt`. |
| 5 | Must not block legitimate work unnecessarily | PASS | Nothing is printed while REPORT_ONLY (253 fixture and 13 malformed payloads through the real hook). Hook output is byte-identical to base on 81 calls in three modes, 11 of them denials (`test_12`), and on 2,314 real calls (`REAL_CALL_REPLAY_FINAL.json`). Cost 0.8 ms per call. |
| 6 | No self-approval | PASS | No file, token or flag is honoured; writing one is SELF_APPROVAL (`test_05`). |
| 7 | Independent proof against defects the rules were not designed around | PASS | Three held-out reviews; see the table below. |
| 8 | In-sample and held-out results kept apart | PASS | Every row below is labelled. `SUPERSEDED.md`; `coverage_review_3/PROVENANCE.md`. |
| 9 | Tests ran in the authoritative runner | PASS | `SUITE_HEAD_FINAL.txt`: 14 modules, 128 functions, 815 checks, 0 raised, 0 blocked. Run on the final code (checksums recorded). |
| 10 | Baseline unchanged; pre-existing failures explained | PASS | The same 3 failing checks, word for word, at base (`SUITE_suite_BASE.txt`) and head; every shared module has the same check count. Two are a stale `GUARD_REACHABILITY.json` census (regenerate with `nfl/tools/guard_reachability.py`). One is a governance guard with no production caller. |
| 11 | Reproducible test environment; missing inputs reported explicitly | PASS | `TEST_ENVIRONMENT.md`. `test_env_check` is COMPLETE 17/17 in the worktree and in the main checkout. A fresh checkout's gaps read BLOCKED with a cause; an input without provenance reads INCOMPLETE. |
| 12 | Enforcement boundary stated | PASS | `ENFORCEMENT_BOUNDARY.md`, including a blind spot observed in this session. |
| 13 | Nothing armed, nothing merged | PASS | Code constants; branch unmerged. |
| 14 | Guaranteed server-side protection | **BLOCKED (owner)** | `main`, `capture-prod` and the shared branch all report `protected: false`; rulesets `[]`. |

## Measured performance

| Measurement | Set | git_guard (N2) | floor_guard (N1) |
|---|---|---|---|
| Phase 1 fixtures written with the code | in-sample | 46/46, FP 0/33 | 24/24, FP 0/12 |
| **Review 1** on version 1 | **held-out** | **22/74, FP 18/34** | **11/69, FP 8/13, 1 crash** |
| **Review 2** on `6da1fa53` | **held-out** | **171/182 (94%), FP 4/66** | **119/134 (89%), FP 6/42** |
| **Review 2**, blind grading of history 301-480 | **held-out** | n/a | **84 TP / 20 FP (81%); 19 of the 20 from the result-document rule** |
| **Review 3** on `ca7a85af` | **held-out** | **25/25 + 23/23 supplementary; FP 0/15 + 0/7; 0 crashes** | **12/12, FP 1/8** |
| **Review 3**, blind grading of history 481-660 | **held-out** | n/a | **78 TP / 6 FP (92.9%); 1 false negative in 27 sampled unflagged commits** |
| Review 3 coverage finding | held-out | n/a | 18 collected modules (292 test functions) check through an `ok()` helper the guard did not recognise: their checks were uncounted |
| All three reviews' fixtures on the final code | in-sample | 73/74, 182/182, 25/25; FP 1/34 (by design), 0/66, 0/15 | 67/69 + 1 renamed rule, 134/134, 12/12; FP 0/13, 0/42, 0/8 |
| Reviews' graded history on the final code | in-sample | n/a | 481-660: TP 78/78 kept, FP 6 -> 4. 301-480: TP 80/84 kept, FP 20 -> 2. Of the 4 TPs no longer reported, 1 was a strengthening and 3 were prose result edits. |
| Real tool calls of this session | real work | 2,314 calls; 37 protected flags, all true (36 safeguard edits, 1 workflow dispatch); 0 false | n/a |

## Comparison with the tooling that existed before

| Defect class | Before Phase 1 | After (report-only) |
|---|---|---|
| Force push, delete or mirror of `main`, `capture-prod` or the shared branch | Not detected anywhere; GitHub unprotected | Recorded as PROTECTED_PUSH |
| Merge, auto-merge, agent approval | Not detected | Recorded |
| Hook skips (`--no-verify`, `core.hooksPath`, hooks dir edits) | Not detected | Recorded |
| Safeguard or approval-file writes | mode_guard denies 2/46 escapes in BUILD, 10/46 in OPERATE, 0/46 with no mode | Recorded in every mode |
| Test weakening, 7 seeded kinds | Runner catches 3/7 | Floor guard reports 7/7 |
| Checks routed through an unrecognised helper | Counted by the runner, invisible to any change review | Helpers found by what they do (`ok()`, `check()`, any name) |
| Missing git-ignored test inputs | Tests raised or silently dropped checks | Named by `test_env_check`; tests report BLOCKED with a cause |
| Cost | n/a | 0.8 ms per tool call; 0 interruptions |

## False positives and false negatives

**git_guard.**
- Held-out false-positive rate: 6% in review 2, 0% in review 3.
- 0 false positives in 2,314 real calls.
- The remaining by-design flag: any file whose name contains *APPROV* counts as approval evidence (D-5).

**floor_guard.**
- Held-out precision on untouched history was 92.9%. Review 3 notes that only 12 of the 78 true positives actually
  made a bar easier to pass. The rest are corrections, rewrites into stronger tests, or matches on a path or code
  pattern.
- That supports a REPORT, not a gate.
- No rule proposed for promotion is a soft rule: SUPPRESSION_ADDED, BROAD_EXCEPT_PASS_ADDED and
  RESULT_STATUS_FLIPPED_TO_PASS all stay out.

**Known false negatives, open:**
- An exact equality replaced by a subset check, masked when the same test gains new `==` checks (P2-10).
- Allowlist or exclusion-set widening (P2-9; outside the Phase 1 spec).
- A local-variable tolerance.
- A semantically identical rewrite (`assertEqual(30, 20 + 10)`).

**Known false negatives by construction:**
- A script that writes or pushes by itself. This was observed in this session: patch scripts run from files edited
  the guards unflagged.
- Paths computed at run time.
- History-dependent git effects.
- Sessions rooted elsewhere, Actions, other agents and humans.

## Defects found in my own evidence (and corrected)

1. **The first real-call replay's identity claim was vacuous.**
   - The base mode_guard was loaded with the wrong `ROOT`, so it could never deny anything.
   - The harness was fixed and now also reports how many calls each guard denies.
2. **A crash on redirect-only commands** in the first git_guard-2 replay. Fixed.
3. **Review 3's Task 2 raw results were overwritten by my re-run.**
   - The held-out numbers survive in `REVIEW3_REPORT.md`.
   - The files are relabelled as in-sample (`coverage_review_3/PROVENANCE.md`).
4. **A test-environment claim about the main checkout was first checked on the wrong root.**
   - It was re-checked explicitly: `TEST_ENV_CHECK_MAIN_CHECKOUT.json`.

## Residual risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Nothing is enforced and GitHub has no protection | high | D-1 |
| R2 | The by-construction blind spots above | high | D-1; floor guard after the fact |
| R3 | The guard files are not in PROTECTED_PATHS (D2) | medium | D-2 |
| R4 | Everything after review 3's fixes is in-sample | medium | P2-11 before any enforcement |
| R5 | A Python heredoc over about 400 KB takes over 1 s to classify (inside the 20 s hook timeout); a Write with a numeric `file_path` leaves no record | low | Phase 2 |
| R6 | Pre-existing: mode_guard fails open (D1); a heredoc `>` is misread (D3); `test_detectors_have_controls::test_05` passes a constant True when its artifact is absent (D5b) | medium | Phase 2, owner-gated |

## Rollback

Nothing is merged, so rollback is not merging. After a merge: `git revert <merge>`.

The components are independent:
- Deleting `coordination/git_guard.py` leaves mode_guard deciding as before and recording GUARD_IMPORT_FAILED
  (`test_09`).
- `nfl/tools/floor_guard.py` and `nfl/tools/test_env_check.py` have no callers.
- Restoring `.claude/settings.json` and `coordination/mode_guard.py` from `0c5bf600` restores the original hook.

## Owner decisions (batched)

| ID | Decision | Agent recommendation |
|---|---|---|
| D-1 | GitHub rulesets on `main` and `capture-prod` (block force push and deletion, require a PR); block force push and deletion on the shared branch | **Yes.** The only control that holds for every actor. |
| D-2 | Add the guard files and `.claude/settings.json` to PROTECTED_PATHS / always_denied | Yes, together with D-3. |
| D-3 | Arm any git_guard rule | Not yet. First candidates are PROTECTED_PUSH to `main`/`capture-prod` and UNAUTHORIZED_MERGE (0 false positives in real calls and in review 3), after two weeks of logs and P2-11. |
| D-4 | Merge Phase 1 to the shared branch as report-only | Merge: it changes no decision, adds 0.8 ms per call, and starts the real-call log D-3 needs. |
| D-5 | Keep direct edits to `OWNER_APPROVAL_QUEUE.jsonl` and *APPROV*-named files as SELF_APPROVAL | Keep. |
| D-6 | NBA repository: name and access | Provide. |
| D-7 | Carried over: Classic S1-S7, W5-G24, OD-1/OD-4, DST mean, CHI QB verification (OUT-047), the 5 DK identities | Unchanged. |

## Next actions

1. Owner: D-1, about ten minutes on GitHub. Then D-4.
2. Agent, already authorized and with no production impact: let the report log accumulate for D-3.
3. Phase 2 only on approval: `PHASE2_PROPOSAL.md` (P2-1 to P2-11, each citing its observed defect).

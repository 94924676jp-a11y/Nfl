# Review 3: coverage and precision of floor_guard and git_guard

Reviewed worktree: `/home/user/nfl-phase1` at `ca7a85af`, read-only. Python 3.12. Neither repository was changed. The repository's test suite was not run. I did not open the excluded paths (`/tmp/claude-0/review2/`, `/tmp/claude-0/-home-user-mlb-prop-system-v7/`, `coordination/EVIDENCE/`, `nfl/tests/test_git_guard.py`, `nfl/tests/test_floor_guard.py`). The Task 2 cases come only from the two module docstrings, plus the constants and function signatures I needed in order to call `run()` and `classify()`.

## Task 1: blind grading on untouched history

**Population.** `git rev-list --first-parent --max-count=180 0c5bf600~480`. That is positions 481 to 660, from `7311a0df` (481) to `54c782f2` (660). I ran `FG.run(repo, f'{sha}~1', sha)` on each one.

- 180 commits ran.
- None crashed and none returned COULD NOT RUN.
- 46 commits were flagged.
- They produced 84 high or medium findings.
- I graded every finding by reading the diff.

| rule | TP | FP | AMBIGUOUS |
|---|---|---|---|
| TEST_COMPARISON_NUMBER_CHANGED | 16 | 4 | 0 |
| TEST_FUNCTION_REMOVED | 18 | 0 | 0 |
| RESULT_STATUS_FLIPPED_TO_PASS | 14 | 1 | 0 |
| BROAD_EXCEPT_PASS_ADDED | 12 | 0 | 0 |
| SUPPRESSION_ADDED | 10 | 0 | 0 |
| GOVERNANCE_OR_SAFEGUARD_CHANGED | 4 | 0 | 0 |
| SKIP_ADDED | 1 | 1 | 0 |
| VERIFICATION_MACHINERY_CHANGED | 1 | 0 | 0 |
| APPEND_ONLY_LOG_REWRITTEN | 1 | 0 | 0 |
| TEST_EARLY_RETURN | 1 | 0 | 0 |
| **total** | **78** | **6** | **0** |

**Overall precision: 78 of 84 = 92.9%.**

"TP" means the change really did what the rule names. It does not mean the bar actually became easier to pass. I also tagged each TP on that second question:

- **12 TPs made a bar easier**, most of them justified. These are a62d8b82 ×3, da8dc4dc, 01566246, 7d46f395, 54c782f2 (early return), 2fece8a0 (an import failure is skipped silently), and 0b558b03 ×4.
- **40 TPs did not make a bar easier.** They are corrections, reversals or rewrites into stronger tests.
- **26 TPs come from path or pattern rules**, where "easier" does not apply.

Two rules stand out:

- **0b558b03 is the most consequential true finding.** `POSTGAME_REVIEW.md` lost its NOT_EXECUTED rows for phases 3, 8, 9 and 11, and the new document never mentions those phases.
- **SUPPRESSION_ADDED is pure noise here.** All 10 findings are `# noqa: BLE001` on handlers that record the error.

Of the 14 RESULT_STATUS TPs, 10 are regenerated state snapshots: `SYSTEM_STATE.json` and `AGENT_STATE.json` showing `is_clean` or `source_scope_clean` going from false to true, and the run_status of a new run that git paired with an old one as a rename. They are literally true, but they are benign.

**The 6 false positives:**

1. `4bf829c3` `run_status.json` `accounting_verdicts[6].state` FAIL to PASS (RESULT). This is an index shift. A new PASS invariant `draw_contract` was inserted, and `nonqb_layer_availability` is still FAIL at index 7. JSON lists are compared by position. Reproduced as probe X5.
2. `34de39af` `test_current_season_opportunity.py` (SKIP_ADDED). `Outcome.blocked(...)` here is a fixture passed into a negative test, not a skip.
3. `f9148b0f` `test_t90_workflow.py::test_F` (TCN). The test did not change. The module constants `SEASON, WEEK = 2026, 1` became computed, so the constant-folded call arguments dropped out of the comparison signature.
4. `98d2f61a` `test_publication_semantics.py::test_D` (TCN). The removed `'K' not in got` guarded a `not_executed()` skip, and it became a real check (`'K' in got`). This is a tightening.
5. and 6. `54c782f2` `test_participant_class.py::test_c` and `::test_d` (TCN). `x > 0.5` became `(x or 0) > 0.5` with an extra conjunct. The operator and bound are unchanged and the test is stricter, but the `or 0` adds a 0 to the signature. Reproduced as probe X6.

Per-finding grades with notes are in `task1_grades.json`. The raw guard output is in `task1_raw.json`.

### False negatives: every 5th unflagged commit

134 commits were unflagged. I took indices 0, 5, …, 130 of them in list order, which gives 27 commits, and read every diff:

482:7dadfeef 490:fe25d988 500:c182e684 507:b2fadfdd 514:df36d7fd 521:fd3a5495 526:3c682cae 531:d67243ac 539:1cbe36d2 546:5ea58c55 558:e6eeed53 572:7090e591 577:7d5c23a5 583:1ad9d57e 588:b60bcf7d 595:638af4f6 601:340d581b 606:14a52572 611:5368f783 618:43bb6737 623:30e963ba 628:47188546 634:caca59f4 639:9d3b9b2f 645:af9ef9e1 650:d350b7ba 655:8efd8bbf

**1 false negative in 27:**

- `638af4f6`, `nfl/tests/test_support_kinds.py::test_D`, rule TEST_COMPARISON_NUMBER_CHANGED. Inside the loop, `check(..., EMITTED_KINDS[k].get('defect') == 'QB_YARDS_CONTINUOUS_SHARE')` became `check(..., bool(names) and set(names) <= KNOWN)`. That turns an exact equality into a subset test, which is looser. The same function also gained new `== 'QB_YARDS_CONTINUOUS_SHARE'` checks. Because signatures are compared as a multiset of (operator, numbers), the lost `('cmp', ('Eq',), ())` is cancelled by the added ones. Reproduced as probe X3.

The other 26 commits are additions only, production refactors, tightenings, or bars written in Markdown, which the spec does not judge. I verified that `1ad9d57e` only appended to `nfl/vintage_manifest.jsonl`.

**Out of spec, not counted as false negatives:**

- `5ea58c55` adds a `DISPOSITIONS` entry to `nfl/production/ownership_audit.py`. That entry clears an `OWNERSHIP_AUDIT_UNREVIEWED_SITE` finding, so it is an allowlist entry that silences an audit.
- I noticed this one while grading a flagged commit: `a62d8b82` `test_dossier_migration.py` widened the equivalence test's `declared = {'spec_version'}` set and excluded the `official_availability` axis from the hash comparison. Neither change was reported. Reproduced as probe X4.

### Coverage gap measured at the HEAD commit (`helper_coverage.py`)

`CHECK_CALLS` and `_helpers()` recognise only `check`, `observe`, `_check` and `expect` as a module's own check helper. 18 collected modules route every check through `ok()`: 292 test functions and 868 `ok(...)` calls, and every one of those functions counts 0 checks. In those modules:

- CHECKS_REDUCED cannot fire.
- TEST_BODY_EMPTIED is blind for any check that contains no comparison.
- Weakening the `ok()` helper itself is never reported.

All three are confirmed by probes X1 and X2 below. This is why all 18 TEST_FUNCTION_REMOVED findings in those files show `n_checks_before: 0`.

## Task 2: held-out fixtures

### git_guard: 40 cases (`task2_git.py`, `task2_git_results.json`)

For the push cases I made three throwaway repos: `repos/on_main`, `repos/on_shared` (on the shared branch) and `repos/on_feature` (on `feature/x`).

| | result |
|---|---|
| Should be protected | **25 of 25 detected** under the expected rule |
| Ordinary commands | **0 of 15 false positives** |
| Crashes | 0 |

The ordinary set included text-only mentions that could trip a naive matcher: a commit message containing `--no-verify`, a `grep` for `core.hooksPath`, `gh pr review --comment`, a non-force push to the shared branch, and `git config user.email`.

I then ran 30 supplementary probes (`task2_git_supplement.py`): refspecs, `+` force refspecs, `HEAD` on main, `-C`, `sh -c`, `--mirror`, `cd … &&`, `gh pr merge --auto` with no PR number, `gh run rerun`, the MCP review and actions tools, `--no-veri`, `SKIP=`, `python -c` and `tee <<<` writes, `MultiEdit`, `git restore --source`, `--skip-worktree`, plus 7 ordinary commands. **23 of 23 were detected and 0 of 7 were false positives.** The report log was never written, which is consistent with `classify()` being pure.

### floor_guard: 20 cases, each in its own repo under `fg/` (`task2_floor.py`, `task2_floor_results.json`)

| | result |
|---|---|
| Should report | **12 of 12 detected** |
| Ordinary changes | **1 of 8 false positives** |
| Crashes | 0 |

The 12 should-report cases were: an assert removed, `abs_tol` loosened, `@pytest.mark.skip`, `MAX_ERROR` loosened, `passed` false to true, a test file deleted, a test body emptied, pyproject `addopts --deselect`, `check()` no longer counting failures, a Markdown row FAIL to PASS, `x == x`, and a ledger row rewritten.

- **False positive: N08.** A test moved verbatim from `test_other.py` into `test_math.py`, with the old file deleted, is reported as `TEST_FILE_DELETED/high`. The docstring says a test moved to another module is not a removal. The function-level rule respects that, but the file-level rule does not.
- The correctly quiet ordinary cases were: a new test, a production refactor, a rename with an identical body, a tightened tolerance (reported as info), a README edit, a ledger append, and a `WORKERS` change.

Supplementary probes (`task2_floor_supplement.py`) reproduced every Task 1 pattern exactly:

- X1: the `ok()` helper stops counting failures. Missed.
- X2: an `ok(flag, msg)` call deleted. Missed.
- X3: an Eq check loosened to a subset test, masked by an added Eq check. Missed.
- X4: the declared-difference exclusion set widened. Missed (out of spec).
- X5: a PASS entry inserted ahead of an unchanged FAIL in a JSON list. False positive, high.
- X6: `x > 0.5` changed to `(x or 0) > 0.5`. False positive, medium.

## Files (all under `/tmp/claude-0/review3/`)

- **Scripts:** `task1_run.py`, `task1_grade.py`, `helper_coverage.py`, `task2_git.py`, `task2_git_supplement.py`, `task2_floor.py`, `task2_floor_supplement.py`
- **Raw results:** `task1_raw.json`, `task1_grades.json`, `task1_fn_sample.json`, `helper_coverage.json`, `task2_git_results.json`, `task2_git_supplement_results.json`, `task2_floor_results.json`, `task2_floor_supplement_results.json`
- **Throwaway repos:** `repos/` and `fg/`

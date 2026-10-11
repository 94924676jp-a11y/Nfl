# Phase 2 proposal (prepared, NOT implemented, NOT authorized)

Owner rule for this list: each item must cite an **observed defect**, a **measurable benefit**, and its
**governance compatibility**. Anything that touches an owner-only file is marked OWNER-GATED and stays a proposal
until the owner says so. Ordered by expected value per unit of risk.

| # | Item | Observed defect it fixes (evidence) | Measurable benefit (how it will be scored) | Governance | Size |
|---|---|---|---|---|---|
| P2-1 | **Server-side protection for `main` and `capture-prod`** (owner action on GitHub; agent writes the checklist only) | No branch protection and no rulesets on any branch, measured 2026-10-11 (`ENFORCEMENT_BOUNDARY.md`). Phase 1 guards are advisory and see only hooked sessions. | Converts PROTECTED_PUSH / UNAUTHORIZED_MERGE from "recorded" to "impossible" for every actor. Verified by `gh api .../branches/main` returning `protected: true` and a refused test force-push to a scratch protected branch. | OWNER-GATED (GitHub settings) | owner, 10 min |
| P2-2 | **Protect the guards themselves** | D2: `coordination/git_guard.py`, `mode_guard.py`, `floor_guard.py` and `.claude/settings.json` are not in `PROTECTED_PATHS` / `always_denied`; the real-call replay shows 19 safeguard edits by this agent, all recorded, none stoppable. | Safeguard edits move from "recorded" to "denied in OPERATE and VERIFY". Scored by the mode-boundary tests. | OWNER-GATED (`MODE_POLICY.json`) | small |
| P2-3 | **Promote the structural git_guard rules to ENFORCE, one rule at a time** | Prior tooling denies 2 of 46 escapes in BUILD and 0 git-level operations (`PRIOR_TOOLING_ON_ESCAPES.json`). | Per rule: a precision floor measured on a NEW held-out sample (the second independent review plus 2 weeks of real-call logs) before arming; interruptions per 1,000 real calls stays below a predeclared margin (proposal: 1). Start with PROTECTED_PUSH to `main`/`capture-prod` and UNAUTHORIZED_MERGE (0 false positives in 2,203 real calls). | OWNER-GATED (promotion) | small code, owner decision |
| P2-4 | **Floor guard as a pre-push report for structural rules only** | The runner misses 4 of 7 test weakenings (`PRIOR_TOOLING_RUNNER_ON_WEAKENED_TESTS.json`). History: the structural rules found real frozen-seal writes (82a049c4) and detector removals. | Soft rules (SUPPRESSION, BROAD_EXCEPT, RESULT_FLIP on living boards) stay info; structural rules reported on every push. Scored by TP/FP on the independent blind history grading. | compatible (report-only); a blocking gate is OWNER-GATED | small |
| P2-5 | **Fail-closed mode guard** (D1) | `mode_guard.decide()` returns no decision when no mode is set, on unreadable state or on a crash. | A missing mode becomes DENY for protected paths only (not all writes). Scored by mode-boundary tests and interruptions per 1,000 real calls. | OWNER-GATED (changes what blocks work) | small |
| P2-6 | **Heredoc-aware redirect parser in mode_guard** (D3) | `mode_guard._BASH_WRITE` reads `>` inside heredoc bodies as a redirect; git_guard-2's lexer already does this correctly. | Fewer false mode denies; scored by replaying real calls (base vs candidate denies, each diff hand-checked). | changes a decision path: OWNER-GATED | small |
| P2-ENV | **Cached test inputs keyed by manifest hash** | D5: a fresh checkout lacks git-ignored `nfl/derived/` and `nfl_vintage/raw/`; tests raised or silently dropped checks until Phase 1 made them BLOCKED. | `test_env_check` COMPLETE in a fresh checkout with no manual copy; scored on a new worktree. | compatible | medium |
| P2-7 | **Defect-cycle ledger with an independent verifier** | This phase: two harness defects found only by re-measurement (the base mode_guard ROOT defect that made an identity claim vacuous; the replay crash on redirect-only commands). | Every claimed fix carries reproduce -> root cause -> test -> independent verify rows; scored by the fraction of claims with all four. | compatible | medium |
| P2-8 | **Continuous historical evaluation** (owner's future priority) | No standing job measures projection calibration, ownership error, field assumptions or realised portfolio results week over week. | Weekly CRPS / calibration / ownership MAE with predeclared margins, graded on locked pregame artifacts only. | compatible (research, read-only on production) | large |

## Not proposed, and why

- **Marketplace skills or plugins**: the tooling evaluation found no capability that the repository lacks and
  that justifies third-party code execution; nothing observed in Phase 1 changes that.
- **Tuning the soft floor-guard rules on the held-out windows**: they have now been inspected, so they cannot be
  used both to tune and to measure. Any recalibration needs a new untouched window.

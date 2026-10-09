# Owner rulings relayed in session, 2026-10-09 (Week 5 Classic)

**Source.** The owner's message in the Claude Code session, after the Week 5 decision board (`a3929144`). The rulings
are recorded here because `OWNER_DECISIONS.md` is a protected file. The proposed entry for it is at the end, and only
the owner applies it.

## Decision 1: depth-rank tie-order repair is PROVISIONALLY RETAINED

- Keep `39340321` (evidence order) and `a8efedae` (tight ends usage-first).
- **Rollback path:** revert those two commits. Nothing else depends on them.
- **Status of the evidence:** the predictive effect is provisional. The statistical validation is exploratory (the
  tie-break was chosen on the same 2026 weeks it was replayed on), not conclusive.
- **Owner requirement:** a player-level review of CIN, WAS and PIT before Sunday. Done:
  `nfl/dfs/salaries/classic_early_2026W5/WEEK5_ROLE_CHANGE_REVIEW.md`.
- The WR2 ceiling stays a separate prospective candidate, RC-1 (`nfl/research/role_ceiling/PREREGISTRATION_ROLE_CEILING_AND_APPEARANCE.md`).

## Decision 2: accounting repair is NOT PROMOTED

- The event-consistent worlds arm stays research (`nfl/research/accounting_repair/`).
- **Separately:** investigate the incumbent's non-integer DST scoring. Design bounded scoring corrections that do not
  adopt the failed event simulator. Require exact world-level statistical and fantasy-scoring reconciliation and
  history-based distribution checks.
- Nothing is promoted until downstream tests and distributional checks pass.

## Decision 3: opponent adjustment is REOPENED FOR RESEARCH ONLY

- This supersedes the earlier exclusion (item 9; `nfl/sim/football_points.py` docstring;
  `docs/FOOTBALL_INTELLIGENCE_AUDIT_2026-10-08.md` G15) **for investigation only**.
- Production behaviour is unchanged until a candidate earns promotion.
- **Scope:** defensive quality, coverage, pressure, offensive-line matchups, defensive absences and other defensible
  contextual variables. Arbitrary defence-vs-position multipliers are out.
- **Required:** a preregistered, point-in-time historical evaluation with stable-game controls, QB-change groups,
  position-specific calibration and uncertainty estimates.

## Sunday priorities (as given)

1. Availability and starting QBs from authoritative sources, with scenario projections where uncertain.
2. Complete player research: actionable / represented / speculative / research-dependent; the major FC disagreements
   explained.
3. Correctness and distributions: conditional means vs simulated realisations; name every unrepaired defect's effect.
4. DFS construction research, with no tuning on Thursday's winners and Stokastic as context only.

## Proposed entry for OWNER_DECISIONS.md (owner applies; not applied by the agent)

> 2026-10-09: (1) W5-G13 tie-order repair retained provisionally; rollback = revert 39340321, a8efedae. (2) The accounting
> repair (event-consistent worlds) is not promoted; bounded DST/K scoring correction to be researched separately.
> (3) Opponent adjustment reopened for research only, superseding item 9 for investigation; production unchanged pending
> a preregistered point-in-time evaluation.

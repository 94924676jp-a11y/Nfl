# NFL DFS engine: post-lock roadmap (owner, 2026-10-04, after Week-4 Early Only lock)

Status of every item: PROPOSED. Nothing here is promoted to production without a pre-registered,
forward-chained A/B against the accepted baseline (owner item 16; CLAUDE.md rules 2-5).

## Order (owner)

1. **True role / route / usage allocation** -- first post-slate task (task #120).
   Replace the generic depth-rank target curve. Inputs per player: route share, snap share, target share,
   carry share, third-down, two-minute, red-zone and goal-line roles, alignment, personnel usage.
   *Acceptance target from today's audit* (`nfl/dfs/salaries/DK_2026W4_EARLY_FINAL_DISAGREEMENT_AUDIT.json`,
   `DK_2026W4_EARLY_FINAL_DEPTH_REVIEW.csv`): the successor must reduce the within-club concentration error
   (WR3/depth under-allocation, e.g. Raymond 3.6 vs 7.0, Flournoy 3.1 vs 6.0, Boutte 0.7 vs 3.0 targets/game;
   WR1/TE1 over-allocation, e.g. Lamb +1.8, Washington +2.5, Wilson +2.8) on held-out weeks, with team
   volume unchanged.
2. **Calibrated field, ownership and duplication simulation**, then an objective of expected tournament
   value under the real payout structure (owner items 8-10). Today: OWNERSHIP_STATE = UNAVAILABLE.
3. **Prospective validation of every component** (owner items 4, 16): freeze before lock (the forecast
   seal already does this), grade after, report calibration of median/P75/P90/P95, TD probability,
   targets, carries, yards, catches, QB attempts.

## Also queued (owner items)

- Absence redistribution learned from history, conditional on position, staff, archetype, lineup (2).
- Volume uncertainty separated from efficiency uncertainty, carried into the simulator (3).
- Defence and offensive line modelled structurally, applied by archetype (6).
- Backup-QB priors with wider uncertainty propagated to receivers and the opposing DST (7).
- Automatic "why" decomposition and disagreement triage before the optimizer sees a projection
  (11, 12) -- today's one-off audit scripts are the starting point.
- Every-player completeness as a hard gate with reason codes (13).
- Automated Sunday news ingestion with localized reruns of only the affected teams (14, 15).

## Dependencies outside this machine

Items 1, 5, 14 need data this checkout does not hold: route participation, alignment, personnel and
snap context, and live news feeds. Routes/alignment are `UNAVAILABLE_NO_CAPTURE` in every research-book
card today. They are requested in `docs/AGENT_OUTBOX.md`; this machine has no network.

# OPP-ADJUST-1 — Amendment A1 (spec opp-adjust-1-prereg-v1.1)

Declared 2026-10-09T19:34:28Z. **Before any outcome-based result was computed** (only the frame build
and its truncation self-test, which passed with 0 mismatches, had run). The original file
PREREGISTRATION_OPP_ADJUST_1.md (sha256 88b4c9df...) is unchanged.

**Change.** Position labels. ROLE_HISTORY (the declared source) labels only players that held a
measured role: 30.2% of PLAYER_GAME rows and 22% of DK points had no label, including QBs
(358 club-games had no labelled QB). That would make position groups wrong by construction.

**New rule.** Position = nflverse players table, reduced crosswalk
`nfl/postgame/raw/role_audit_history/players_crosswalk.bea61fc25c863150.csv.gz` (column
`position`); FB counted as RB; any other position (OL, defence, specialists) excluded; players
absent from the crosswalk fall back to the ROLE_HISTORY modal label; still unknown -> excluded.
The label is the player's current nflverse position (not season-specific) — disclosed; position
changes across 2021-2025 are rare for QB/RB/WR/TE and the label is not an outcome.

Nothing else changes.

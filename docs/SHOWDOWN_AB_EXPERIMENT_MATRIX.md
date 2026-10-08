# Showdown A/B experiment matrix (deliverable C), 2026-10-08

Each experiment compares **the incumbent against exactly one change**, with:
- matched inputs;
- matched seeds: 20261005 for ATL@NO, the slate's own seeds for TB@DAL;
- 2,000 simulations;
- the same contest rules and entry counts.

**The incumbent is `66990085`.** Its reproduction of the historical production portfolio is in
`SHOWDOWN_BASELINE_REPRODUCTION.md`, run R-C4.

The comparison tool is `nfl/tools/showdown_regression_compare.py`. It checks 26 items:
- projection rows, and points by position;
- all player draws, world points, club worlds, DST components, interceptions, kickers and per-world stat lines;
- correlations from the draws, and the correlation board;
- the projections CSV, simulation summary, stack, game-script, CPT and candidate boards;
- lineups, exposures, CPT exposures and every upload;
- legality and uniqueness;
- the binding-stripped slate state.

**Tool controls:** R3 vs R4 identical; Daniels vs Mayfield different.

## Experiments

| Id | Change | Class | Slate / environment | Result | Evidence |
|---|---|---|---|---|---|
| A1 | Replay exit code blocks; current-run receipt required (`69fceb0d`) | A validation | TB@DAL Daniels R5 → R6 | **26/26 byte-identical** | `REGRESSION_DANIELS_R5_vs_R6.json` |
| A2 | Starter-state guard before projection; scenario and evidence binding (`69fceb0d`) | A validation | same pair | identical; the state differs only in binding metadata, which is excluded and declared | same |
| A3 | Explicit environment, inherited `SHOWDOWN_*` dropped (`69fceb0d`) | B execution | same pair | identical | same |
| A4 | Certificate refuses added arrays (`69fceb0d`) | A validation | not on the Showdown path (classic `run_forecast` only) | n/a | `test_coherence_certificate` 27/27 |
| B1 | Per-scenario work directories, global lock, tree-diff guard (`66990085`) | B execution | TB@DAL Daniels R3 → R4 | 26/26 identical | `REGRESSION` via the comparator control |
| B2 | Content-bound measurement / kicking cache keys; role state bound to its own state (`0ea3bc21`) | B execution + A validation | TB@DAL Daniels R5 → R7; Mayfield R3 → R4 | **both 26/26 identical** | `REGRESSION_DANIELS_R5_vs_R7.json`, `REGRESSION_MAYFIELD_R3_vs_R4.json` |
| A1–B2 combined | all P0 commits (`0ea3bc21`) | A + B | **ATL@NO, point-in-time environment** | **all checks identical; uploads equal production `8f4d9a77…`** | `ab/AB_PIT_P0_0ea3bc21_vs_incumbent.json` |
| A1–B2 combined | all P0 commits | A + B | ATL@NO, drifted data environment | identical to the incumbent in the same environment | `ab/AB_P0_0ea3bc21_vs_66990085.json` |
| C1 | Conditional pass keeps `_chart_rank` (one line, `proj_v1.py:1328`) | **C model** | ATL@NO point-in-time; TB@DAL | `dk_points_if_plays` and conditional volume move (13 ATL players; e.g. Delp up, Welch down). `dk_points` unchanged. Draws differ only by floating-point rounding (at most 7e-15; means identical). **Lineups, exposures and uploads identical** on both slates. | `ab/AB_PIT_C1_CHART_RANK_vs_incumbent.json` |
| C2 | Appearance / `p_plays` successor | C model | not rerun | already registered: the gate alone fails its pre-declared bar; rates and gate must be fixed together | `CANDIDATE_STATUS_REGISTER.json` |
| C3 | Event-linked world coherence repair | C model | not runnable as a portfolio today (research harness) | SC-COH-1 clean evaluation: energy and variogram fail superiority; team-points CRPS fails non-inferiority | `docs/NFL_GAP_AUDIT_RECONCILIATION_2026-10-07.md` |
| C4 | De-duplicate repeated 2026 PBP captures in `kicking.fit` / `gadget_rush` / `rushing_conversion` | C model (classic) | **Showdown-neutral by construction**: no Showdown module imports them; the Showdown readers select one capture per season | classic fit: 619 counted vs 259 distinct 2026 FG attempts | `NFL_P0_CLOSURE_2026-10-08.md` |
| C5 | Cohort-cache panel binding | B execution | deferred | re-stamping `player_prior.py` would stale the global role artifact's lineage tonight | `test_lineage` 8/8 → 7/8, measured |
| F1 | Game resolution checks the export's kickoff date | A validation (proposed) | not implemented | TB@DAL unaffected | `SHOWDOWN_BASELINE_REPRODUCTION.md` |
| F2/F3 | Roster and PBP capture selected by capture time at the cutoff | B execution (proposed) | not implemented | TB@DAL: 0 slate players affected by roster order; PBP newest is legitimately pre-lock | same |

## Not combined

Every row above is one change against the incumbent. The single combined row (all P0 commits) is reported only
because each P0 commit was also shown identical on its own on TB@DAL.

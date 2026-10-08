# Showdown baseline reproduction (deliverable B), 2026-10-08

**Slate:** ATL@NO 2026 W4, the only FULL_REPLAY_ELIGIBLE slate (see `HISTORICAL_REPLAY_FEASIBILITY.md`).

**Production incumbent:** scenario `RW_INACTIVES_CHARTFIX`, commit `9736516d` (2026-10-05 23:47Z, 28 minutes
before kickoff). Uploads:

| File | sha256 |
|---|---|
| `SHOWDOWN_ATL_NO_DK_UPLOAD.csv` | `8f4d9a77…` |
| contest 196285137 | `4047a189…` |
| contest 196285160 | `17e397b4…` |
| contest 196285161 | `a30f529f…` |

**Run parameters:** seed 20261005, 2,000 simulations.

**Inputs** (all committed before kickoff):
- DKEntries `fd0c1faa…`;
- designations V4 (RW_INACTIVES_CHARTFIX);
- RotoWire inactives, identical to the owner-verified official list;
- starters `STARTERS_ATL_NO_2026W4.json`, tier PUBLIC_DEPTH_CHART_AND_SNAPS_CITED;
- depth chart `1e6aa643…`.

Every run below used exactly those arguments (`atl_replay.sh`), with every inherited `SHOWDOWN_*` variable unset.

## Runs

| # | Code | Data environment | Upload | vs production |
|---|---|---|---|---|
| R-H | `b0a2b57b`, the code of the recorded 2026-10-07 reproduction | generation-1 cache rebuilt there (6/6 pinned hashes match); the commit's own tracked data | `8f4d9a77…` and all three per-contest files | **numeric output byte-identical on every check.** The only difference is the slate state's `specialist_safety` header, the owner-approved specialist detector added after lock. It is already documented in `REPRO_POSTRESTART_2026-10-07.json`. |
| R-C1 | `66990085`, today's incumbent before P0 | generation 1; **today's** `TEAM_GAME` | refused: `SLATE_STATE_NO_IMPLIED_TOTAL` for `2026_17_NO_ATL` | resolved to the wrong game (finding F1) |
| R-C2 | `66990085` | generation 1; lock-time `TEAM_GAME` (from `9736516d`); today's rosters and PBP | `9686b815…` | **DIFFERENT**: projections, draws, worlds and 123 of 150 lineups (finding F2) |
| R-C3 | `66990085` | the above plus lock-time rosters (the 2 post-lock roster captures removed) | `426f529d…` | DIFFERENT, only in the K and DST projections and draws (finding F3) |
| R-C4 | `66990085` | the above plus lock-time PBP (the post-lock capture `2b3e9f2c` removed) | **`8f4d9a77…`, all four files** | **ALL checks byte-identical, the slate state included** |

## Conclusion

**Today's incumbent code reproduces the historical production portfolio exactly when given the information
available at lock.** No forecasting code change entered between the historical run and today. Every difference seen
in R-C1 to R-C3 is data vintage.

## Findings

**F1. Game resolution uses the current schedule** (`showdown_slate_state.build`).
- It picks any unplayed same-season game between the two clubs and never checks the export's kickoff date.
- Effect: a historical slate maps to the next meeting.
- **TB@DAL:** not affected. That game is unplayed and the clubs' only remaining meeting.
- **Proposal (class A, validation-only):** refuse `SLATE_STATE_GAME_DATE_MISMATCH` when the game's date differs from
  the export's kickoff date.

**F2. Roster positions come from every capture ever taken** (`player_prior.position_index` / `name_index`).
- They glob all `weekly_rosters.*raw.csv.gz` files. Last-wins, in hash-name order.
- So post-lock captures changed positions, which changed group shares, depth shares and bonus rates.
- **TB@DAL:** measured. Only 2 players in all of history get a different position under hash order versus capture-time
  order, and **none is on the TB@DAL slate**.
- **Proposal (class B):** select captures by capture time, at or before the slate's information cutoff.

**F3. The DST and kicker projections recompute from the largest PBP capture per season at projection time**
(`dst_model._capture`).
- A post-lock capture that contains the game itself changed the ATL@NO DSTs (12.16 → 11.49) and kickers.
- **TB@DAL:** not a leak. The newest capture (weeks 1-4) is pre-lock information for week 5.
- **Proposal (class B):** select by capture time at or before the cutoff, and record the selected vintage in the
  projection.

**Consequence.** Today's code is not replay-safe without a point-in-time data environment. The environment built here
is generation-1 cache, lock-time `TEAM_GAME`, and lock-time rosters and PBP. A permanent replay harness has to
construct it from the vintage manifest, not by hand.

## Preserved evidence

- `nfl/postgame/showdown_atl_no_2026W4/ab/`:
  - `BASELINE_REPRO_PROD_vs_b0a2b57b.json`
  - `DRIFT_b0a2b57b_vs_66990085.json`
  - `DRIFT_b0a2b57b_vs_66990085_PIT_ROSTERS.json`
  - `REPRO_b0a2b57b_vs_66990085_POINT_IN_TIME.json`
- The replay worktrees are under `/home/user/p0work/`. They are scratch, outside the repository, and reproducible from
  the commands above.
- No production artifact, prelock record or prospective record was modified.

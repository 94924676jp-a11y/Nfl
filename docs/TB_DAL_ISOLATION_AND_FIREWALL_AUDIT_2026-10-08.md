# TB@DAL: scenario isolation and market firewall audit, 2026-10-08

Requested by the owner after two concurrently run TB QB precomputes produced one byte-identical upload. Two
defects are audited. Each has its own verdict.

## 1. Market firewall: PASS

**Verdict: PASS_MARKET_BLIND.** No sportsbook value enters the football forecast on the production Showdown path.
`MARKET_INPUT_CONTAMINATION` does not apply.

### Call graph, read from the code

`showdown_next_slate.run` → `showdown_tonight.run` → `showdown_slate_state.build` → `showdown_slate_run.run`, which
then calls `role_state`, `proj_v1` and `showdown_draws` / `sim.game`.

1. `showdown_slate_state.environment_for` (`nfl/tools/showdown_slate_state.py:81-113`) copies the `TEAM_GAME` market
   fields into `state.environment.games`: `home_implied`, `away_implied`, `total_line` and `home_spread`.
2. `showdown_slate_run.run` (`nfl/tools/showdown_slate_run.py`) sets `proj_v1.MARKET_ARM = 'FOOTBALL_ONLY'`.
   - This is the owner production contract of 2026-10-03 (`nfl/tools/classic_slate_run.py:11-19`).
   - The run refuses with `SHOWDOWN_RUN_ARM_NOT_APPLIED` if the projection does not echo the arm back.
3. `proj_v1.main`, `FOOTBALL_ONLY` branch (`nfl/tools/proj_v1.py:1127-1172`).
   - It replaces all four environment scoring fields with `football_points.centre_for_game`, an own-offence blend
     of each club's realised points: the current season through week W−1, plus the prior season at 4 pseudo-games.
   - **Team volume.** `team_volume(..., market_response_enabled=False)` records `NOT_APPLIED_FOOTBALL_ONLY_ARM` and
     `implied_total: None`.
   - **DST.** Points-allowed residuals are measured around the opponent's football centre.
   - **Touchdown pool.** `td_fit` comes from `FOOTBALL_POINTS.json`.
   - **Kicker.** `kicker_model.project` accepts implied-total arguments and never reads them.
   - **Captured market.** It is kept only under `market_environment_DOWNSTREAM_COMPARISON_ONLY`.
4. `showdown_draws.build` (`nfl/tools/showdown_draws.py:221-236`). Under the football arm it draws the game total and
   the margin around the football centre. It also replaces the simulator's market-centred residual sets with the
   `FOOTBALL_POINTS.json` empirical residuals.
5. The simulator's volume coefficients (`nfl/sim/shared_state.py:138-190`) regress realised attempts on **realised**
   points and margin.
   - Their fitting sample is filtered to games that carry a line. That is a sample filter: line coverage is 100% for
     1999-2025, and no line value enters a coefficient.
   - `volume_response_to_market` is fitted but not read by the simulator.
6. `nfl/sim/football_points.py` reads `TEAM_GAME` for realised points only. Its `FIELDS_FORBIDDEN` list is asserted
   by an AST test.

### Measured proof: `nfl/tools/market_firewall_check.py`

On the Daniels scenario's frozen state:

- **Inputs.** State `30b98bac…`; `TEAM_GAME` `4307db1f…`; 300 simulations; seed 20261008.
- **Method.** `role_state` → `proj_v1` → `showdown_draws` re-run three ways, entirely in a git-ignored scratch
  directory:
  - **CAPTURED:** the inputs as captured.
  - **PERTURBED:** this game's total −15, spread flipped −10, implied totals swapped ±9, and every market field on
    every `TEAM_GAME` row moved.
  - **REMOVED:** every market field set to None.

| Run | Projection rows sha256 | Draws sha256 |
|---|---|---|
| CAPTURED | `7e3065d0…` | `f7e0be87…` |
| PERTURBED | `7e3065d0…` | `f7e0be87…` |
| REMOVED | `7e3065d0…` | `f7e0be87…` |
| P1 control: MARKET arm, captured | `661d1b82…` | `fce68c66…` |
| P1 control: MARKET arm, perturbed | `8434f5c6…` | `f2d420fe…` |
| P2 control: football arm, home club's 2026 points +14 | `9cea1a83…` | `c6f88dc3…` |

- **Result.** The three runs are byte-identical.
- **Controls.** Both moved: the harness reaches the market consumers (P1) and the football inputs (P2).
- **Artifact.** `nfl/dfs/salaries/showdown_tb_dal/MARKET_FIREWALL_PRECOMPUTE_TBQB_DANIELS_R3.json`.

**Football centre for this game.** DAL 29.10, TB 20.68, total 49.78, home margin +8.43. Both clubs are
`BLENDED`: 4 current games plus 17 prior.

### What the TEAM_GAME rebuild did, and did not do

- **The refusal.** `SLATE_STATE_NO_IMPLIED_TOTAL` was a presence check: the state builder refuses when the market
  row is absent, although the football arm then discards it. The rebuild satisfied that check.
- **The football input.** The rebuild also added the week-4 realised points that the football centre needs. It now
  shows `n_cur 4` for both clubs.
- **Market totals.** They remain only as a downstream comparison.

**Open item, a proposal and not a change.** A football-only run should not be blocked by a missing market line,
because that couples availability of the forecast to availability of a book. Changing the gate is a gate change. I
have not made it.

### Existing tests on this path

| Test | Result |
|---|---|
| `test_market_in_projection` | 7/7 |
| `test_volume_centre_arm` | 7/7 |
| `test_fc_firewall_and_projection_source` | 10/10 |
| `test_football_only_arm` | 2/6: the backlog item `BLOCKED[V1_INPUT_ABSENT]`, fixture role file missing |

`market_firewall_check.py` is the end-to-end measurement that test was meant to provide.

**Test hygiene.** `test_fc_firewall_and_projection_source` rewrites two tracked week-3 files:
`DK_WEEK3_PROJECTION_SOURCE_LEDGER.json` and `DK_WEEK3_PLACEHOLDER_PORTFOLIO_AUDIT.json`. The change is a timestamp
and a key reordering. I restored both from git. It belongs in the suite backlog. `run_suite.py` catches it through
its working-tree diff; a hand run does not.

## 2. Scenario isolation

### Architecture: FAIL as found, fixed in this commit

**Shared mutable paths on the production Showdown path, as found:**

| Path | Written by | Shared across | Copied into the scenario? |
|---|---|---|---|
| `nfl/dfs/salaries/showdown_<tag>/SHOWDOWN_<TAG>_STATE.json` | `showdown_slate_state` (`SSS.OUT`) | every scenario of a slate | yes, after the run |
| `…_PROJ.json` | `proj_v1` (`PV.OUT`) | every scenario of a slate | yes, after the run |
| `…_DRAWS.json`, `…_WORLDS.npz` | `showdown_slate_run` | every scenario of a slate | yes, after the run |
| `nfl/derived/ROLE_STATE.json` | `role_state.OUT`, read by `proj_v1.ROLE` | **every slate** | **no** |
| `nfl/derived/DST_RATES.json` (hash-pinned in the derived manifest) | `dst_model.OUT`, rewritten on every projection | **every slate** | no |

**How the 2026-10-08 contamination happened.** The two precomputes ran concurrently. The Daniels run's state was
overwritten by the Mayfield run's before projection. Both scenarios were then built from the Mayfield world, so their
uploads are byte-identical: `75756698…`, which equals the Mayfield R2 rerun's upload.

- **What caught it.** The draws' state and projection hashes still matched their copies, because the copy was
  internally coherent. Only the designation and starter checks caught it.
- **Evidence kept.** `INVALIDATED_RUNS_TB_DAL_2026W5.json`.

**Fixes:**

1. **Per-scenario work directory.**
   - `showdown_slate_run.paths(tag, work=...)` and `run(..., work=...)` write state, projection, role state, DST rates,
     draws and worlds directly into the scenario's directory.
   - `showdown_tonight.run` uses it, and raises if any intermediate's parent is not the scenario.
   - Nothing is copied from a shared path any more. The global `ROLE_STATE.json` and `DST_RATES.json` are no longer
     written by a Showdown run.
2. **Tree-diff guard.** `showdown_next_slate` snapshots the top-level files of `nfl/derived`, `nfl/dfs/salaries`,
   `nfl/sim`, `nfl/warehouse` and the slate directory around the build. It refuses with
   `SCENARIO_ISOLATION_BREACH` if any of them changed.
3. **Global run lock.** `nfl/dfs/salaries/.SHOWDOWN_RUN_LOCK` is taken for all Showdown runs, not per tag. A second
   run refuses with `CONCURRENT_RUN`.
4. **State-consistency check.** `SCENARIO_STATE_MISMATCH` refuses unless the built state carries the scenario's own
   designations and names only the scenario's starters.

**Equivalence proof of the fix.** Daniels R4, run under the new architecture, must reproduce R3's upload
byte-for-byte without touching a shared path. The result is in section 4.

### Run level: PASS for Daniels R3 and Mayfield R2

Tool: `nfl/tools/showdown_scenario_compare.py`. Artifact:
`nfl/dfs/salaries/showdown_tb_dal/SCENARIO_COMPARISON_DANIELS_R3_vs_MAYFIELD_R2.json`.

- **Negative control.** On the invalidated pair the tool returns `ISOLATION_FAIL`.
- **Chain, both scenarios PASS.**
  - The draws' `state_sha256` and `projection_sha256` equal the scenario's own files.
  - The state's designations equal the scenario's.
  - The state's named starters equal the scenario's.

| Stage | Daniels R3 | Mayfield R2 | Moved? |
|---|---|---|---|
| Designations | Mayfield OUT (formal, relayed) | Mayfield's formal Out removed counterfactually | yes |
| Slate state | Mayfield REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED; Daniels QB rank 1 | Mayfield UNKNOWN_ACTIVE_STATE rank 1; Daniels rank 2 | yes |
| Starter identification | Daniels | Mayfield | yes |
| QB opportunity | Daniels 34.9 att, 173 yds, 3.4 car, 14.6 pts; Mayfield not projected | Mayfield 35.2 att, 214 yds, 4.0 car, 17.8 pts; Daniels 0.1 att | **yes** |
| TB team pass volume (projection) | 35.28 att, 31.04 targets | 35.28 att, 31.04 targets | **no** |
| TB scoring centre | 20.68 | 20.68 | **no** |
| TB receiver targets | Egbuka 7.75, Otton 7.01, Godwin 4.61 | identical | **no** |
| TB receiver receiving yards (projection) | Egbuka 51.68, Otton 47.66 | 51.67, 47.65 | ~no |
| Joint simulation, TB | pass yds 172.3 (4.96/att); receivers' yds 202.2; TB points 19.70 | pass yds 217.6 (6.09/att); receivers' yds 207.5; TB points 19.50 | QB yes; receivers ~no; points no |
| Player projections | 33 of 52 players moved; the TB QBs by 14 points, everyone else by under 1 | | |
| Portfolio | upload `bba17b23…`; 162 distinct lineups | upload `75756698…`; 155 distinct | 14 shared lineups |

### Response verdict: FAIL as "appropriate"

The scenario inputs reach every stage that the model lets depend on the quarterback. They do **not** reach team
scoring, team volume or receiver targets, because no term there depends on who starts:

- `proj_v1.team_volume` and `football_points` are club-level blends of club history.
- Receiver yards respond about 2% to a 21% drop in the QB's yards. This is registered defect R1:
  `classic_slate_run.efficiency_worlds` scales each player's yards by his own factor independently.
- In the Daniels worlds the receivers are credited with 30 more yards per game than the QB throws. The worst
  single world is 113 yards apart.

**Even the registered repair would not close this.** That is the event-linked world, EL_S1 in
`docs/NFL_COHERENCE_REPAIR_PREREGISTRATION.md`. It makes passer yards the sum of receiver yards and drops the QB's
own yards-per-attempt row. TB's passing would then be QB-invariant. The model has no pathway from QB identity to
team efficiency or scoring.

**Readiness.** Under the owner's rule ("if scenario-specific inputs differ but the resulting football distributions
do not change appropriately, refuse READY"), neither scenario may be READY on this basis. Fixing it is a model
change, and no model change is authorized. **This is an owner decision.**

## 3. Finality

Neither scenario is READY. Gates outstanding:

1. **Official TB QB evidence:** `STARTERS_TB_DAL_2026W5.json` + `.PROVENANCE.json` with `CONFIRMED: true`.
2. **Official inactives:** `OFFICIAL_INACTIVES_TB_DAL_2026W5.json` + `.PROVENANCE.json` with `OFFICIALLY_VERIFIED`.
3. **Market firewall:** PASS.
4. **Scenario isolation, architecture:** fixed, pending the R4 equivalence result below.
5. **Scenario response:** FAIL as appropriate. Owner decision.

## 4. R4 equivalence result

(filled in below when the run completes)

# TB@DAL repair program: sections F to I (2026-10-09)

Each item is one bounded change with a predeclared acceptance test, and every item runs shadow-first against the
preserved incumbent. **Nothing is promoted on the strength of this game.** Defect IDs refer to `TB_DAL_DEFECT_REGISTER.json`.

## F. Simulation integrity repair plan (D-05)

**The defect.** The raw simulator (`nfl/sim/game.py`) holds its accounting identities exactly. The *published* worlds
break them, because two steps run after it:
- `classic_slate_run.efficiency_worlds` applies independent per-player yard factors and draws interceptions per attempt
  from a projection-level rate;
- the defense anchor step adjusts the defenses separately.

The result, from `WORLD_ACCOUNTING_OFFICIAL.json`:
- receiving yards without a catch in 1,496 of 2,000 worlds;
- a receiving TD without a catch in 558;
- QB passing yards ≠ receiving yards (TB about 30 yards per game short);
- interceptions not credited as takeaways to the opposing defense (~470 worlds per club);
- club points ≠ 6 × TDs (~65 per club).

**The repair.** An isolated arm, `nfl/sim/event_consistent_worlds.py`, under construction in a separate worktree:
1. Efficiency is anchored at the **club** passing level and allocated to **completed catches**. A target that isn't
   caught carries 0 yards and 0 TDs.
2. QB passing yards and TDs are **derived** from his receivers' events, never drawn separately.
3. Every interception thrown is a takeaway credited to the opposing defense in the same world. The defense's DK points
   come from those events.
4. Club points are the sum of scoring events (TDs + tries + FGs + safeties). Any component the simulator doesn't
   represent is **named**, never imputed.
5. Exceptions: laterals, non-QB passes and penalties are **not represented**, so no world may claim one as an excuse.

**Invariants and tests**, in `nfl/tests`, counted by `run_suite.py`:
- one check per law, matching the `world_accounting_check.py` checks;
- a negative control: the incumbent-style independent factors must FAIL;
- determinism under a fixed seed;
- the drift in each player's average against the projection is reported, never hidden;
- DK points recomputed from the published stat line equal the published DK points (one scorer).

**Acceptance:**
- zero violations of every ordinary-event law on TB@DAL OFFICIAL inputs;
- any player's average drifting more than 0.5 DK points from its projection anchor is listed and explained;
- the full harness shows no regression;
- shadow only: production keeps reporting `SIMULATION_ACCOUNTING_VALID = FAIL` until this arm is promoted by owner
  decision.

**Status:** IN PROGRESS. Results will be added to this section with harness counts before and after.

## G. QB-conditioned forecasting plan (D-02, D-03), updated with Daniels' second start

**What the two starts show** (play-by-play; descriptive, not estimates):

| | Mayfield wk 1–3 | Daniels wk 4 | Daniels wk 5 | Our wk 5 projection | FC |
|---|---|---|---|---|---|
| TB pass attempts | 28 / 34 / 37 | 27 | 25 | 34.6 | — |
| TB pass rate | 0.63 / 0.60 / 0.67 | 0.49 | 0.41 | not computed | — |
| TB QB carries | — | 8 (6 scrambles) | 7 (5 scrambles) | 3.3 | — |
| TB team rush attempts | 21–31 | 31 | 39 | — | — |
| TB points | 27 / 19 / 16 | 14 | 24 | 19.7 | 19.75 (Vegas) |
| Daniels DK points | — | — | 13.9 | 14.0 | 12.1 |

His DK total came out right through two offsetting errors: passing volume was over-projected and rushing
under-projected. That is not evidence the mechanism works.

**Method** (unchanged from `docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md` §4, now with two starts):
1. **Role-aware evidence windows.** Starts and relief appearances enter as separately weighted evidence.
2. **QB rushing by identity.** Designed runs and scrambles per dropback, partially pooled toward a mobility-aware prior.
   The prior is a hierarchical model: QB → QB cohort by measured college/NFL rush rate → league. Shrinkage comes from
   sample size: Daniels has 2 starts and 56 dropbacks on which he threw, so his own rate carries a small but real weight.
3. **QB-split team history.** Pass rate and plays per game get a QB effect, shrunk toward the club using the measured
   historical QB-change effects (the 719 cases already measured). Two starts at 0.49 and 0.41 against the club's 0.63
   are evidence of a regime effect. They are not its size.
4. **Teammate shares by QB regime**, with shrinkage. In Daniels' two starts the leading share swapped: Godwin 0.27 then
   0.12, Egbuka 0.15 then 0.36. That is the noise any per-game estimate must absorb, and it is why share volatility
   (D-04) belongs in this model.

**Data:** 2021–2025 nflverse play-by-play (available), pregame starter identity per game (from the depth charts and
the injury-report vintage, joined point-in-time), and dropback-level scramble and designed-run flags (available in
the play-by-play).

**Controlled experiment** (predeclared, before any 2026 week-6 evaluation):
- **Unit:** team-games with a starter different from the club's dominant starter of the prior window, 2021–2025.
  Forward-chained by season.
- **Metrics:** CRPS and log score for team pass attempts and QB carries, plus calibration of the 80% interval.
- **Clustering:** by game and by team.
- **Arms:** incumbent against steps 1–3, each one alone, then combined.
- **Acceptance:** a CRPS improvement whose cluster-bootstrap 95% interval excludes 0, with no degradation on games
  without a QB change (non-inferiority margin 1% CRPS).
- **2026 from week 6 is prospective**, graded by the postgame system.

## H. NFL engine improvement board

| Item | Priority | Status | Evidence |
|---|---|---|---|
| Roster-eligibility gate in release (D-08) | P0 | **DONE (release gate)**; selection not yet consuming it | `upload_roster_eligibility`, `test_release_roster_eligibility` 12/12 |
| Eligibility feeding selection | P0 | NEXT; needs a matched regression equal to R1 | — |
| Unavailable players get zero participation | P0 | PARTIAL: the release gate blocks them, but the projection still carries their volume (DAL 1.26 / TB 0.65 DK) | eligibility analysis 2026-10-08 |
| Pregame freeze manifest before grading | P0 | **DONE** | `PREGAME_FREEZE_MANIFEST.json` (97 hashes, re-verified by the grader) |
| Accepted-entry reconciliation | P0 | **BUILT**; waits on the DK export | `contest_financials` (172/172 on ATL@NO) |
| Simulation accounting (D-05) | P0 | IN PROGRESS (isolated arm) | section F |
| Disclose relaxation level in every portfolio summary (D-09) | P0 | NEXT | — |
| QB-conditioned volume, QB rushing, shares (D-02, D-03) | P1 | PLAN + predeclared experiment | section G |
| Lower-tail volatility (D-01, D-04) | P2 | MEASURED; repair next | `STAR_DUD_RATE_2021_2025.json` |
| Ownership and field simulation (D-06) | P2 | BLOCKED on standings exports | outbox |
| Separate 20-max portfolios (D-07) | P2 | NEXT | — |
| Postgame grading, automated | P3 | **DONE** | `showdown_postgame.py`, `auto_postgame.py`, ledger |
| Our-vs-FC disagreement as a predictor of our error (D-12) | P3 | LEDGER STARTED (2 slates) | `SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl` |
| Promotion of any forecasting candidate | — | **NONE**: nothing promoted | — |

## I. Automated postgame evaluation specification

**Entry point:** `python3.12 nfl/postgame/auto_postgame.py`, run after each slate and on a schedule.

1. **Find work.** It looks for every `nfl/postgame/*/POSTGAME_CONFIG.json` without a `<tag>_POSTGAME.json`. Each config
   names the game, the frozen scenario directory, the FC export, the freeze manifest, the contests, the eligible pool
   and every portfolio with its status.
2. **Get results.** It downloads nflverse play-by-play from the `nflverse-data` GitHub release (reachable from this
   environment) and content-addresses it into `raw_dir`. If the game is absent or has no END GAME row, it records
   **PENDING** with the reason in `POSTGAME_STATUS.json`. An absent game is never graded against absence.
3. **Freeze check.** Every hash in the freeze manifest is re-verified. A changed prelock file refuses with
   `FROZEN_ARTIFACT_CHANGED`.
4. **DK points.** These come from one scorer (`nfl.product.dk_scoring`), with the kicker rule settled empirically. A
   FanDuel scorer is **not yet implemented**; the slot is named, not faked.
5. **Forecast grading.** For each player: our average and 10th–90th percentile range, FC's projection, the actual,
   both errors, and where the actual fell in our simulated range. Also the stat-level errors from the published worlds,
   team totals and margin, and this game's calibration summary with the one-game caveat.
6. **Portfolio grading.** Every named portfolio, scored separately: distribution, captains, exposure, team splits,
   QB stacks, salary, the exact hindsight optimum (labelled HINDSIGHT) and captain attribution.
7. **Contest financials** only from a DK entry-history export, which also identifies which file DraftKings held.
   Otherwise every financial field is UNKNOWN.
8. **Provider comparison.** One row per player per slate is appended to `SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl`
   (idempotent by tag). Longitudinal questions are answered from the ledger, clustered by game.
9. **Cross-check** against nflverse `stats_player_week` once it carries the game. Disagreement is listed by player and
   field.
10. **Issue reports.** For now the report and defect register are written per slate. Automatic task generation is
    **not built**; that is the next step.
11. **No leakage.** Outputs sit in the POSTGAME_ACTUAL layer. `assert_no_postgame_inputs`
    (`guard_reachability.py`) is load-bearing, and nothing here is imported by a forecast path.
12. **No automatic retraining or promotion**, ever, on one game.

**Tests:** `nfl/tests/test_showdown_postgame.py` (13 checks):
- parity with the ATL@NO actuals;
- the ATL module delegating to the generic scorer;
- refusal of an absent game;
- accepted-portfolio identification against a decoy;
- financials UNKNOWN without an export;
- exact hindsight against brute force;
- the captain multiplier;
- the probability-transform handling of ties.

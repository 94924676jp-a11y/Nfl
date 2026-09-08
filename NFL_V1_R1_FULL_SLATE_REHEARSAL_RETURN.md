# NFL-V1-R1 — FULL-SLATE PRODUCTION REHEARSAL

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Freeze** `nfl/production/rehearsal/FREEZE_V1R1.json`, clean tree at
`91f018dfa45901eb655acc82d7db503748028a09`

## DECISION: `V1_FULL_SLATE_REHEARSAL_BLOCKED`

The orchestrator now runs all 16 games end-to-end, seals a deterministic
artifact per game, and refuses publication. But it forecasts **quarterbacks
only — 84 of 921 skill-position players, 9.1% coverage.** Four of the five
model layers have no production implementation, so **there is no shared draw
system and no cross-layer accounting to check.** §C could not be executed.

Four structural defects were found and repaired. **The most serious one is that
before this rehearsal the pipeline sealed 16 of 16 artifacts containing
`distributions: {}` and reported PASS on every one.**

G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. No research conclusion, T−90
component or ALIGN/FTN artifact was altered.

---

## 1. The headline

A rehearsal is supposed to find out whether the thing works. It found that the
production path could **report complete success for a run that forecast
nothing**:

    16 of 16 games      status SEALED
    every artifact      "distributions": {}
    every stage         PASS
    six stages          spec_version "...ACCEPTED", value {}

That is this project's Class A failure mode — absence read as success — sitting
in the production entrypoint, and it would have been invisible on any
single-game test because a single game seals just as cleanly.

---

## 2. Failure inventory (§D)

Every failure carries a category. No generic "error".

| # | category | defect | scope | status |
|---|---|---|---|---|
| 1 | `MODEL_INTERFACE` | QB layer could only name players already in its **historical** frame, so `QB_SLATE_EMPTY` on a season not yet played | 15 of 16 games | **repaired** |
| 2 | `ID_RECONCILIATION` | one roster row with no `gsis_id` refused an entire game | 1 of 16 | **repaired** |
| 3 | `PRODUCTION_ENTRYPOINT` | `player_draws` returned a fixture key nothing ever set, discarding the QB draws that had just been computed | all 16 | **repaired** |
| 4 | `PRODUCTION_ENTRYPOINT` | sealing accepted an artifact with zero distributions and reported PASS | all 16 | **repaired** |
| 5 | `MODEL_INTERFACE` | receiving, rushing, TD and team-volume layers have **no production implementation** | all 16 | **NOT repaired — out of scope, §E forbids new models** |

### Defect 1 — a forecaster that could only forecast the past

`qb_v1.slate()` filtered the historical frame by season, so for 2026 it
returned nothing. **A layer that sources its player set from history can only
ever forecast a season already played.**

Before repairing I checked whether the simulator itself was prospective-capable
by reading **every** outcome-field reference in `qb2_lib.simulate`. All of them
— `db`, `team_db`, `att`, `sacks`, `scr`, `cmp`, `pyds`, `rush_opp`, `drush`,
`ryds` — sit inside an oracle branch. The candidate path reads history only, so
a row with no realised outcomes simulates correctly.

`slate_prospective()` therefore takes the player set from the **2026 week-1
roster** and attaches history by appending the prospective rows to the
historical frame and re-running the frozen `attach`. **Chronology is not
reimplemented** — each row inherits the existing strictly-earlier prefix cut
rather than a second copy of that logic. It also refuses outright if the frame
already contains rows at or after the forecast ordinal, so a week cannot inform
its own prediction.

### Defect 2 — one player should not block a game

One NYJ running back has no `gsis_id`, in **all three** roster vintages — an
upstream nflverse condition, not a capture defect.

The guard's purpose is that we never forecast a player we cannot identify and
never fuzzy-match a name. **Excluding him satisfies both; refusing the game
does not.** He is now excluded, named in the artifact with reason `NO_GSIS_ID`,
and counted as a warning. The escape hatch is bounded: above **1%** of the
slate the run refuses, because that is a broken roster feed rather than an
incomplete one. Both directions are tested.

### Defects 3 and 4 — the empty artifact

`player_draws` returned `fx.get('draws', {})` — a fixture key nothing ever
sets. The QB layer's real draws were computed, checked for accounting
coherence, and then dropped on the floor. Sealing then accepted the empty
result.

`player_draws` now assembles every layer's draws into a player-keyed structure,
and sealing refuses with the new named code **`EMPTY_FORECAST_ARTIFACT`** if no
layer produced anything.

---

## 3. Defect 5 — the one that is not repaired, and why

Six stages reported `..._OK` while returning `{}`, carrying spec strings like
`P4C system C ACCEPTED` and `Stage2 ewma_hl2 ACCEPTED`. **The accepted research
baseline exists; a production implementation of it does not, and nothing in the
pipeline said so.**

They now return `STAGE_DECLARED_UNIMPLEMENTED` and the artifact reports:

    "completeness": "PARTIAL_PLAYER_COVERAGE"
    "absent_layers": ["appearance", "conversion", "feature_build",
                      "participation", "targets_carries", "td_layer",
                      "team_environment"]

Implementing them is a new predictive model, which §E forbids in this task. So
the pipeline is now **truthful about being partial** rather than being made
complete.

---

## 4. What §C could not test

§C asked for one shared draw system with per-draw accounting across team plays,
dropbacks, rush attempts, QB accounting, targets, receptions, receiving/rushing/
passing yards, TD accounting and residual mass.

**Only one layer produces draws, so there is nothing to reconcile against.** The
QB layer's own seven per-draw identities hold on every cell (unchanged from
P2), and `qb_accounting.reconcile_cross_layer` correctly returns **DEFERRED**
with the receiving layer named as owed — it does not report a pass it did not
earn. Cross-layer accounting becomes testable the moment a second layer
produces draws, and not before.

---

## 5. The rehearsal artifact (§F)

`nfl/production/rehearsal/slate_artifact.json` — sha256 `4a65ca604930423a…`

| | |
|---|---|
| games | 16 |
| player-layer distribution rows | 84 |
| layers present | `qb` only |
| fields per player | `db, att, cmp, sacks, scr, pyds, ptd, int, rush_opp, ryds, rtd` |
| summaries | mean, p10, p50, p90 |
| `dry_run` | **true** |
| `prospective_eligible` | **false** |
| publication | **`NFL1_NOT_AUTHORIZED`** on all 16 |
| completeness | `PARTIAL_PLAYER_COVERAGE` |

Determinism: run ids are stable across output directories, and the 16 ids are
distinct. Sample output (WAS@PHI): dropbacks mean 29.4 [p10 9.9, p90 43.0];
passing yards mean 180.0 [p10 51.0, p90 284.8].

**This is a rehearsal artifact, not a forecast anyone may act on.** G0A is
incomplete, so publication is refused by the gate, not by convention.

---

## 6. Coverage, stated plainly

| | count |
|---|---|
| roster, 2026 week 1 | 2,955 |
| skill positions (QB/RB/WR/TE) | 921 |
| **carrying any distribution** | **84** |
| **coverage** | **9.1%** |
| QBs on roster | 119 |
| QBs forecast | 84 (the rest have no prior appearance and are named, not dropped) |

WR 381, RB 214, TE 207 — **zero forecast**.

---

## 7. Tests (§G)

`nfl/tests/test_full_slate_rehearsal.py` — **24 checks**, one per defect:

- an artifact with no distributions refuses, with `EMPTY_FORECAST_ARTIFACT`;
- an unimplemented layer declares itself, while the implemented QB layer still
  reports OK;
- completeness is computed rather than asserted, and absent layers are named;
- the prospective slate refuses a week its history already contains;
- one unidentified player of 201 passes with a warning, ten of sixty refuses;
- the whole 16-game slate runs, seals, and refuses publication.

One pre-existing test broke and I repaired it properly rather than bumping a
number: it asserted `len(RF.REFUSALS) == 17`, a magic constant that fails the
moment a genuine refusal code is added. It now reads the production source and
asserts **every refusal code actually raised is declared** — the property that
matters for auditability.

**Canonical suite: 36 modules, 366 test functions, 2,155 checks, 0 failing,
0 raised — SUITE PASS.**

---

## 8. What this means for tomorrow

**Tomorrow's NE@SEA T−90 gate is unaffected by everything in this packet.** The
capture workflows, schedule identity and coverage logic were not touched, and
the diff over `nfl/capture`, `nfl/tools/gen_t90_schedule.py` and the T−90
workflow is empty.

The honest position on V1: **the production shell is real and now tells the
truth, but the forecast is quarterbacks only.** Whether that is "V1" is your
call, not mine — I would not describe a 9.1% slate as a full-slate forecast.

The blocker is not engineering plumbing any more. It is that receiving,
rushing, TD and team-volume have accepted *research* baselines with no
production implementation, and building those is model work that needs its own
packet and its own gates.

---

## 9. Changed files

| file | change |
|---|---|
| `nfl/production/qb_v1.py` | `slate_prospective()` — roster-sourced player set, frozen chronology reused, refuses a seen week |
| `nfl/production/run_forecast.py` | prospective QB path; exclude-and-name unidentified players with a 1% bound; `player_draws` assembles real draws; sealing refuses an empty artifact; completeness computed |
| `nfl/production/refusal.py` | `EMPTY_FORECAST_ARTIFACT` declared |
| `nfl/production/rehearsal/run_slate.py` | the slate driver and failure inventory |
| `nfl/production/rehearsal/{FREEZE_V1R1,slate_inventory,slate_artifact}.json` | freeze, inventory, artifact |
| `nfl/tests/test_full_slate_rehearsal.py` | 24 regression checks |
| `nfl/tests/test_production_pipeline.py` | magic-number assertion → the property it protects |

**Not touched:** `nfl/capture`, `gen_t90_schedule.py`, `nfl-t90.yml`,
`nfl-status.yml`, `nfl/research/alignb1`, `ftns1`, `ftns2`, `rbb1`,
`PATH_C_STATE.json`, `NFL_G0A_CHECKLIST.md`.

**No new model research. No feature search. No calibration tuning on upcoming
games. Nothing promoted. G0A remains 11/12; NFL-1 remains NOT AUTHORIZED.**

**THEN STOP.**

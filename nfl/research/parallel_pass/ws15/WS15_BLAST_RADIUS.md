# WS15 — BLAST RADIUS: every refusal in the production path, and what it destroys

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws15/` was
written. Every line number below is read from HEAD `57d38ad`.

---

## 1. The question, and the one distinction that makes it answerable

A refusal is *over-scoped* when the evidence that is missing is about one unit
and the refusal destroys many. That test only applies to a refusal whose
trigger is **an absent or unusable input**. It does not apply to a refusal
whose trigger is **an arithmetic identity that must hold by construction**.

* **EVIDENCE-GAP refusal.** "I do not know X about unit U." The right scope is
  the scope of U. Narrowing it recovers real forecasts that were never in
  doubt. All three known instances of this defect class — the two repaired at
  HEAD and the one at the evidence ceiling — are of this kind.
* **CONSTRUCTION-INVARIANT refusal.** "Attempts + sacks + scrambles did not
  equal dropbacks." One violated cell means the code that produced every other
  cell is wrong. Narrowing it to the offending row would hide the defect in the
  rows it did not narrow. These are scored CORRECT below even when a single
  player's row is what tripped them, and the reason is written into each.

Mixing the two is how a blast-radius audit turns into a request to loosen a
guard. This report never asks for that.

Two more refusal families are scored CORRECT without further argument, per the
task's standing instruction: **chronology** (`SOURCE_TOO_LATE`,
`INJURY_REPORT_CHRONOLOGY_FAILURE`, `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF`,
`INACTIVES_POST_KICKOFF`, `DEPTH_CHART_CHRONOLOGY_FAILURE`,
`WRITTEN_AT_*`, `SOURCE_AFTER_WRITTEN_AT`) and **authorization**
(`UNAUTHORIZED_INPUT`, `ARM_RULE_VIOLATION`, `COLD_START_VIOLATION`,
`NFL1_NOT_AUTHORIZED`, `TEST_ONLY_DATA_IN_PRODUCTION_PATH`). A capture that is
too late is too late for both clubs and every player in them: those are
correctly game-scoped or run-scoped *because the clock is a property of the
capture, not of a unit inside it*.

---

## 2. Two destruction sizes, measured, not assumed

The production entrypoint has exactly two blast sizes, and the sealed slate
shows both.

| Where the refusal lands | Mechanism | What survives |
|---|---|---|
| **non-QB chain** (`fx['_nonqb'] = {'fatal': o}`, `run_forecast.py:530-792`) | `_nonqb_stage` wraps it as `NOT_APPLICABLE` (`run_forecast.py:1115-1118`); five stages report blocked-upstream | the QB board seals; `completeness` reads `PARTIAL_PLAYER_COVERAGE` |
| **QB layer** (`RF.refuse(...)` at `run_forecast.py:393-419`, or any non-PASS returned from `_candidate_qb_compute`) | `Pipeline.run_stage` halts; every later stage records `STAGE_NOT_REACHED` | **nothing.** `status: REFUSED`, zero distributions sealed |

Measured on the 14 sealed games under `nfl/research/live/2026_01_*/`
(109 `run_status.json` files; 101 SEALED, 8 REFUSED). Player distributions
sealed per game, `post_inactives_V1_CANDIDATE_R8`:

| Game | Sealed dists | What fired | Blocking unit |
|---|--:|---|---|
| ARI@LAC | 32 | — | — |
| NO@DET | 34 | — | — |
| SF@LA | 36 | — | — |
| TB@CIN | 36 | — | — |
| BUF@HOU | **7** | `INJURY_REPORT_INCOMPLETE` | HOU only (BUF `READY_WITH_COMPLETE_INPUT`) |
| GB@MIN | **7** | `INJURY_REPORT_INCOMPLETE` | MIN only (GB `READY`) |
| MIA@LV | **8** | `INJURY_REPORT_INCOMPLETE` | MIA only (LV `READY`) |
| WAS@PHI | **8** | `INJURY_REPORT_INCOMPLETE` | WAS only (PHI `READY_WITH_COMPLETE_INPUT`) |
| NYJ@TEN | **7** | `NONQB_PLAYER_FRAME_INCOMPLETE` (pre-repair artifact) | 1 player of 190 |
| ATL@PIT | **0 REFUSED** | `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | ATL only |
| BAL@IND | **0 REFUSED** | `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | IND only |
| CHI@CAR | **0 REFUSED** | `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | CHI only |
| CLE@JAX | **0 REFUSED** | `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | CLE only |
| DAL@NYG | — | no post-inactives run in the tree | — |

A healthy R8 board carries **12–15 non-QB players per club** (ARI 13 / LAC 13;
NO 14 / DET 12; SF 13 / LA 15; TB 14 / CIN 14). A game that seals 7–8 sealed
quarterbacks only.

**The measured cost of one scope decision.** In all four
`INJURY_REPORT_INCOMPLETE` games exactly **one** club blocked and the other
club was READY — two of them `READY_WITH_COMPLETE_INPUT`, the strongest state
the contract defines. At 12–15 non-QB players per club that is roughly **52
player distributions destroyed on clubs whose evidence was complete**, in one
slate, from four one-club gaps.

---

## 3. Full refusal inventory

Scope vocabulary: PLAYER | MARKET | STAT | TEAM | GAME | RUN.
"Destroys" is what is actually lost at HEAD, not what the code says it is about.

### 3.1 `nfl/production/run_forecast.py` — the entrypoint

| Code | file:line | Trigger | Destroys | Justified scope | Verdict |
|---|---|---|---|---|---|
| `SOURCE_MISSING` | run_forecast.py:146 | no capture supplied | RUN | RUN | CORRECT |
| `UNAUTHORIZED_INPUT` | :150 | source not in `capture.registry` | RUN | RUN | CORRECT (authorization) |
| `RAW_HASH_MISMATCH` | :153, :157 | no sha256 / hash differs | RUN | RUN | CORRECT |
| `SOURCE_CHRONOLOGY_FAILURE` | :162, :173 | no `retrieved_at`; `written_at` not before kickoff | RUN | RUN | CORRECT (chronology) |
| `SOURCE_TOO_LATE` | :166 | capture after `written_at` | RUN | RUN | CORRECT (chronology) |
| `SCHEMA_DRIFT` | :170 | `schema_ok is False` | RUN | RUN | CORRECT |
| `ARM_RULE_VIOLATION` | :177 | arm A would consume a 2026 outcome | RUN | RUN | CORRECT (authorization) |
| `COLD_START_VIOLATION` | :181 | freeze identity mismatch | RUN | RUN | CORRECT |
| `APPEARANCE_SPEC_AMBIGUOUS` (raise) | :197 | config names r7 and r8 | RUN | RUN | CORRECT |
| `IDENTITY_UNRESOLVED` (no players) | :448 | empty player list | RUN | RUN | CORRECT |
| `IDENTITY_UNRESOLVED` (limit) | :462 | >1% of frame lacks `gsis_id` | RUN | see §4.6 | **TOO_BROAD (denominator)** |
| `IDENTITY_UNRESOLVED` (none resolved) | :469 | nobody carries a `gsis_id` | RUN | RUN | CORRECT |
| `REQUIRED_GAME_MISSING` | :477 | game absent from schedule | RUN | RUN | CORRECT |
| `NONQB_LAYER_IMPORT_FAILED` | :528 | engine import raises | non-QB board, both clubs | RUN | CORRECT |
| `NONQB_PLAYER_SET_EMPTY` | :540 | no player supplied | non-QB board | GAME | CORRECT |
| `NONQB_PLAYER_FRAME_INCOMPLETE` | :574 | >1% lack gsis_id/position/team | non-QB board | see §4.6 | **TOO_BROAD (denominator)** — *repaired at the player level; the limit's denominator was not* |
| `NONQB_TEAM_HAS_NO_PLACEABLE_PLAYER` | :594 | exclusions empty one club | non-QB board, **both** clubs | TEAM | **TOO_BROAD** (§4.3) |
| `MODEL_ARTIFACT_MISSING` | :616, :937, :966, :975 | derived artifacts / QB frame hash absent | non-QB board (:616) or RUN | RUN | CORRECT |
| `MODEL_HASH_MISMATCH` | :940 | artifact hash differs | RUN | RUN | CORRECT |
| `STAGE_NOT_IMPLEMENTED` | :943 | fixture flag | RUN | RUN | CORRECT |
| `SLATE_FITS_RAISED` / `SLATE_FITS_UNAVAILABLE` | :721 / football_engine.py:78 | any slate fit not PASS | non-QB board | GAME (slate fit is shared) | CORRECT, **except** the `participation_prior` path — §4.4 |
| `QB_SLATE_EMPTY` | :273/:280 | no QB on the roster | RUN | GAME | CORRECT |
| `A1_RB_BUDGET_INCOMPLETE` | :760 | A1 returned no `rb` budget for a club | non-QB board, both clubs | TEAM | **TOO_BROAD** (§4.5) |
| `NONQB_ENGINE_RAISED` | :789 | engine raised | non-QB board | GAME | CORRECT |
| `ENGINE_LAYER_NOT_REPORTED` | :864 | an engine layer no stage owns | non-QB board | GAME | CORRECT (a reporting guard; narrowing defeats it) |
| `INCOMPLETE_PLAYER_ACCOUNTING` (QB identity) | :393, :1019 | `qb_v1.identity_check` | **RUN** | construction invariant | CORRECT |
| `INCOMPLETE_PLAYER_ACCOUNTING` (per-draw) | :398, :1024 | `reconcile_draws` | **RUN** | construction invariant | CORRECT |
| `INCOMPLETE_PLAYER_ACCOUNTING` (inactive owns) | :410, :1044 | `assert_inactive_qbs_own_nothing` | **RUN** | TEAM-ish; see §4.7 | **TOO_BROAD (weak)** |
| `INCOMPLETE_PLAYER_ACCOUNTING` (team) | :416, :1050 | `reconcile_team` | **RUN** | construction invariant | CORRECT |
| `JOINT_RECONCILIATION_FAILURE` | :1134 | fixture flag | RUN | RUN | CORRECT |
| `TEAM_DRAW_ROWS_DISAGREE_WITH_TEAM_IDS` | :1266 | draw matrix teams ≠ declared teams | RUN | RUN | CORRECT |
| `EMPTY_FORECAST_ARTIFACT` | :1281/:1297, :1413/:1451 | no draw matrix / no distribution | RUN | RUN | CORRECT ("zeros are errors") |
| `ARTIFACT_SEALING_FAILURE` (hard gate) | :1523, :1530 | `assert_hard_invariants` | RUN | RUN | CORRECT |
| `ARTIFACT_SEALING_FAILURE` (contract) | :1601, :1605 | `assert_not_promoted`, `validate` | RUN | RUN | CORRECT |

### 3.2 `nfl/production/nonqb/football_engine.py` — the game engine

| Code / halt | file:line | Trigger | Destroys | Justified scope | Verdict |
|---|---|---|---|---|---|
| `SLATE_FITS_UNAVAILABLE` | :78 | any of 8 slate fits not PASS | non-QB board | GAME/slate | CORRECT (see §4.4 for the one exception) |
| `R2_NO_QB_SLATE` | :159 | R2 called with no QB slate | RUN (via qb_layer) | RUN | CORRECT |
| `R2_ALLOCATED_MASS_HAS_NO_MODELLED_QB` | :179 | one club's allocation names no forecast QB | **RUN** | TEAM | **TOO_BROAD** (§4.5) |
| halt `team_environment` | :304 | `TV.forecast` not PASS | non-QB board | GAME | CORRECT |
| halt `appearance` | :321 | `LY.appearance` not PASS — **carries `INJURY_REPORT_*`** | non-QB board, **both clubs** | TEAM (readiness is per club) | **TOO_BROAD** (§4.1) |
| `NONQB_TEAM_HAS_NO_APPEARING_PLAYER` | :356 | exclusions empty one club | non-QB board, **both clubs** | TEAM | **TOO_BROAD** (§4.3) |
| `C3_TEAM_HAS_NO_QUARTERBACK_ROW` | :432 | one club has no modelled passer | non-QB board, **both clubs** | TEAM | **TOO_BROAD** (§4.5) |
| `C3_TARGET_COUNT_DOES_NOT_CLOSE` | :489-493 | dealt + other ≠ targeted | non-QB board | construction invariant | CORRECT |
| `P4C_PARTITION_POOL_MISSING` | :541 | no `mass_pool_partition` in the fit | non-QB board | GAME/slate (fitted artifact) | CORRECT |
| `RUSHING_BUDGET_TEAM_MISSING` | :579 | A1 gave no budget for a club | non-QB board, **both clubs** | TEAM | **TOO_BROAD** (§4.5) |
| `RUSHING_BUDGET_DRAW_MISMATCH` | :593 | budget shape ≠ (teams, m) | non-QB board | construction invariant | CORRECT |
| `RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES` | :610 | partition > thing partitioned | non-QB board | construction invariant | CORRECT |
| halt `conversion_or_td` | :644 | `cv`/`td`/`rtd` not PASS | non-QB board | depends on cause — §4.2 | **TOO_BROAD** for `TD_RATE_*` |
| halt `qb_composition` | :739 | `conserve_allocated_mass` fails for **one pid on one team** | non-QB board, both clubs | PLAYER | **TOO_BROAD** (§4.8) |

### 3.3 `nfl/production/nonqb/layers.py` — the layer wiring

| Code | file:line | Trigger | Destroys | Justified scope | Verdict |
|---|---|---|---|---|---|
| readiness deferral (`INJURY_REPORT_*`) | layers.py:117-127 | **any** of the two named teams not READY | non-QB board, both clubs | TEAM | **TOO_BROAD** (§4.1) — this is the blast site; `readiness.py:433` is only where the state is named |
| `INJURIES_BLOB_MISSING` | :148 | ready but no row readable | non-QB board | GAME | CORRECT |
| `FIXTURE_NO_APPEARANCE` | :168 | test fixture supplies neither | non-QB board | GAME | CORRECT |
| `APPEARANCE_SPEC_UNKNOWN` | :213 | unrecognised mechanism name | non-QB board | RUN (config) | CORRECT |
| `P4C_PARAMS_NOT_A_MAPPING` / `P4C_PARAMS_INCOMPLETE` | :303, :310 | fitted params missing `add_pool` | non-QB board | GAME/slate | CORRECT |
| `ALLOCATION_PLAYER_WITHOUT_APPEARANCE` | :339 | a player has no appearance draw | non-QB board | PLAYER | CORRECT **as a backstop** — the narrowing now lives upstream at football_engine.py:340-397 |
| `CROSS_DRAW_INDEX_MISMATCH` | :351, :419, :555 | draw widths disagree | non-QB board | construction invariant | CORRECT |
| `CONVERSION_PRIOR_NOT_FROZEN` | :412 | RC1 prior block absent | non-QB board | GAME/slate | CORRECT |
| `TD_PRIOR_NOT_FROZEN` | :494, :548 | TD2 prior block absent / wrong estimand | non-QB board | GAME/slate | CORRECT |
| `TD_RATE_UNDEFINED` | :508 | **one position** has no `pos_catch_rate` | non-QB board, both clubs, all positions | STAT × POSITION | **TOO_BROAD** (§4.2) |
| `TD_RATE_ABOVE_ONE` | :514, :565 | **one position's** rate > 1 | non-QB board, both clubs, all positions | STAT × POSITION | **TOO_BROAD** (§4.2) |
| `RUSHING_PRIOR_NOT_OWNED_BY_CALLER` | :621 | caller supplies a rushing prior | that metric only | STAT | CORRECT |
| `RUSHING_CONVERSION_CONTROL_UNDEFINED` | :630 | no frozen control exists | `rushing_yards` only, emitted ABSENT | STAT | **CORRECT — and the model for every fix below** |
| `TEST_ONLY_DATA_IN_PRODUCTION_PATH` | :646 | a layer consumed a fixture | non-QB board | RUN | CORRECT (authorization) |

### 3.4 `nfl/production/nonqb/readiness.py`

| Code | file:line | Trigger | Destroys (via layers.py:121) | Justified scope | Verdict |
|---|---|---|---|---|---|
| `INJURY_REPORT_INCOMPLETE` | :433 | one club: rows exist, `report_status` blank on all | non-QB board, both clubs | TEAM | **TOO_BROAD in scope** — the *trigger* is at the evidence ceiling; the *scope* is not (§4.1) |
| `INJURY_REPORT_NOT_YET_FILED` | :396 | one club has no rows at all under the cut | non-QB board, both clubs | TEAM | **TOO_BROAD** (same shape) |
| `INJURY_REPORT_STALE` | :424 | one club's block older than `STALE_HOURS` | non-QB board, both clubs | TEAM | **TOO_BROAD** — fired on 6 games |
| `INJURY_REPORT_CHRONOLOGY_FAILURE` | :414 | capture at/after the bound | non-QB board | GAME | CORRECT (chronology) |
| `READINESS_CLOCK_UNRESOLVED` | :371 | no kickoff and no `written_at` | non-QB board | GAME | CORRECT (chronology) |

`game_readiness` at :449-500 is already correct and is worth naming as the
counter-example: it judges each game on its own two teams, keeps both team
verdicts in `teams`, and names `blocking_team`. **The per-team answer is
already computed and carried; only the consumer collapses it.**

### 3.5 `nfl/production/nonqb/qb_allocation.py` — the largest measured radius

| Code | file:line | Trigger | Destroys | Justified scope | Verdict |
|---|---|---|---|---|---|
| `QB_ALLOCATION_NOT_FITTED` | :437 | no cell fitted before `season` | RUN | RUN | CORRECT |
| `DEPTH_CHART_CHRONOLOGY_FAILURE` | :448 | depth chart at/after the bound | RUN | RUN | CORRECT (chronology) |
| `QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE` | :484 | **one club's** whole QB room inactive | **RUN** (0 distributions) | TEAM | **TOO_BROAD** (§4.5) |
| `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | :538 | **one club**, ≥1 draw with no share left | **RUN** (0 distributions) | TEAM | **TOO_BROAD** — *fired on 4 of 14 games* (§4.5) |
| `QB_ALLOCATION_EMPTY` | :552 | no team got an allocation | RUN | RUN | CORRECT |
| `QB_ALLOCATION_DOES_NOT_CLOSE` | :559 | shares do not sum to 1 | RUN | construction invariant | CORRECT |

### 3.6 Slate-fit and prior modules

| Code | file:line | Trigger | Destroys | Justified scope | Verdict |
|---|---|---|---|---|---|
| `PARTICIPATION_HISTORY_EMPTY` | participation_prior.py:110 | no prior pass-snap share anywhere | non-QB board | GAME/slate | CORRECT |
| `PARTICIPATION_HISTORY_STALE` | :122 | week ≥ 2 with no current-season history | non-QB board | GAME/slate | CORRECT |
| `PARTICIPATION_PRIOR_UNAVAILABLE` | :150 | **one player**: no history and no positional mean for his position | non-QB board, both clubs | PLAYER (or POSITION) | **TOO_BROAD** (§4.4) |
| `PARTICIPATION_IDENTITY_UNRESOLVED` | :156 | **one player** with no `gsis_id` | non-QB board, both clubs | PLAYER | **TOO_BROAD**, currently shadowed (§4.4) |
| `PARTICIPATION_PRIOR_EMPTY` | :161 | no WR/TE/RB at all | non-QB board | GAME | CORRECT |
| `ROSTER_STATUS_EMPTY` | roster_status.py:166 | no rows for these teams | non-QB board | GAME | CORRECT |
| `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF` | :185 | capture at/after kickoff | non-QB board | GAME | CORRECT (chronology; both clubs share one kickoff) |
| `ROSTER_STATUS_POSTHOC_CONTAMINATION` | :201 | INA/post-hoc statuses present | non-QB board | GAME | CORRECT (leakage; same reasoning) |
| `ROSTER_STATUS_NO_ACTIVE_PLAYERS` | :211 | no ACT row | non-QB board | GAME | CORRECT |
| `A1_NO_TEAMS` | rushing_a1.py:728 | empty slate | RUN | RUN | CORRECT |
| `A1_INPUT_TEAM_MISSING` | :750 | no carries/scrambles for a club | RUN | TEAM | **TOO_BROAD** (§4.5) |
| `A1_LEVEL_NOT_INTEGER` | :772 | non-integer level, rounding undeclared | RUN | construction invariant | CORRECT |
| `A1_DRAW_COUNT_MISMATCH` | :784 | wrong draw width | RUN | construction invariant | CORRECT |
| `A1_SCRAMBLES_EXCEED_TEAM_CARRIES` | :796 | negative rush-play budget | RUN | construction invariant | CORRECT |
| `THROW_BUDGET_*`, `TARGETED_THROWS_NEGATIVE` | shared_pass.py:102, 106, 113 | impossible throw budget | non-QB board | construction invariant | CORRECT |
| `QB_INACTIVE_STILL_OWNS_DROPBACKS` | qb_accounting.py:828 | **one inactive QB** holds mass | **RUN** | TEAM | **TOO_BROAD (weak)** (§4.7) |
| `QB_DROPBACK_IDENTITY_VIOLATED` | qb_v1.py:271 | identity fails in ≥1 cell | RUN | construction invariant | CORRECT |
| `QB_DRAW_ACCOUNTING_VIOLATED` | qb_accounting.py:113 | any per-draw identity fails | RUN | construction invariant | CORRECT |
| `APPORTION_NEGATIVE_SHARE` | :889 | negative share | RUN | construction invariant | CORRECT |
| `INACTIVES_IDENTITY_AMBIGUOUS` | inactives.py:505 | **one name** matches >1 player | the whole slate's inactive list | PLAYER | **TOO_BROAD** (§4.9) |
| `INACTIVES_SUPPLIED_NAME_NOT_IN_BYTES` | :438 | one supplied name absent | whole supplied list | PLAYER | **TOO_BROAD** (§4.9) |
| `INACTIVES_POST_KICKOFF` | :562 | list after kickoff | whole list | GAME | CORRECT (chronology) |
| `INACTIVES_EMPTY_BYTES` / `INACTIVES_EMPTY_DOCUMENT` | :104, :319, :421 | empty capture | whole list | RUN | CORRECT |

### 3.7 Product and tooling — clean

| Code | file:line | Trigger | Destroys | Verdict |
|---|---|---|---|---|
| `WEEK_PLAN_UNAVAILABLE` / `GAME_NOT_IN_WEEK_PLAN` | make_board.py:38, 44 | plan absent / game not in it | RUN | CORRECT |
| `WRITTEN_AT_NOT_BEFORE_KICKOFF` | :120 | post-kickoff clock | RUN | CORRECT (chronology) |
| `WRITTEN_AT_IN_THE_FUTURE` | :135 | clock ahead of wall | RUN | CORRECT (chronology) |
| `SOURCE_AFTER_WRITTEN_AT` | :147 | a source past the cut | RUN | CORRECT (chronology) |
| `ROSTER_EMPTY` | :155 | no roster rows for either club | RUN | CORRECT |
| `ARTIFACT_ABSENT` / `DRAWS_ABSENT` / `DRAW_SET_EMPTY` / `DRAW_INDEX_RAGGED` | distributions.py:41, 52, 63, 67 | unreadable sealed forecast | that game's board | CORRECT (the artifact *is* the game) |
| `MARKET_SNAPSHOT_ABSENT` | daily_board.py:116 | no snapshot | **nothing** — board still built, rows unrankable | CORRECT, and the pattern to copy |
| `MARKET_SNAPSHOT_EMPTY` | :122 | parsed to zero rows | that feed | CORRECT ("empty is an error") |
| `NO_LAWFUL_BOARD` | :217 | every board written at/after kickoff | that game's feed row | CORRECT (chronology) |
| row `eligibility` | :219+ | per-row reasons | one row, **stays visible** | CORRECT — the reference implementation |

`nfl/product/board.py` iterates players and `continue`s past a player it cannot
render (`:190`, `:198`, `:250-257`) while explicitly refusing to drop a player
the roster does not name (`:177-180`). The product layer has no blast-radius
defect. Everything found is upstream of the sealed artifact.

---

## 4. Ranked incorrect scopes, with proposed narrowings (NOT APPLIED)

Ranked by **measured** destruction on the sealed slate first, latent risk
second.

### 4.1 `INJURY_REPORT_INCOMPLETE` / `_NOT_YET_FILED` / `_STALE` — GAME where the evidence is TEAM
**Blast site: `nfl/production/nonqb/layers.py:117-127`** (not `readiness.py`).
**Measured: 4 games lost a ready club's entire non-QB board; ~52 player
distributions. `INJURY_REPORT_STALE` fired on 6 more.**

```
if teams:
    tr = [RD.team_readiness(...) for t in teams]
    bad = [t for t in tr if not t['state'].startswith('READY')]
    if bad:
        worst = bad[0]
        return Outcome.deferred(worst['state'], worst['reason'], owed={...})
```

`tr` already holds a per-club verdict and `owed` already carries
`blocking_team`. The refusal then throws the distinction away.

**This is NOT the withdrawn fix.** The withdrawn branch
(`nfl/research/slate_audit/EVIDENCE_CEILING_injury_report_publication.md`)
proposed changing **when** a club is judged unready — refuse only when
`report_status` *and* `practice_status` are both blank — and was withdrawn
because `both blank` is zero in all seven captures, so the condition would
never fire and the guard would be removed. That measurement stands and is not
revisited here. **The trigger is left exactly as it is.** What is proposed is
that the *consequence* of an unchanged trigger stop reaching a club the trigger
never named.

**Proposed narrowing (not applied).** `layers.appearance` returns
`Outcome.ok` over the players of the READY clubs only, with the unready clubs
named in evidence as `teams_deferred`, and returns the deferral unchanged when
**no** club is ready. Downstream, the engine runs the game with one club's
players.

**Honest obstacle, stated rather than hidden.** The engine currently cannot
produce a one-club game and says so on purpose:
`NONQB_TEAM_HAS_NO_APPEARING_PLAYER` (football_engine.py:356) and
`NONQB_TEAM_HAS_NO_PLACEABLE_PLAYER` (run_forecast.py:594) refuse exactly this
state, and `reconcile_nonqb` would receive a zero-count group. Several
downstream loops already tolerate it (`if not sel_t or not ri: continue` at
football_engine.py:887, :921). So this is **not** a two-line scope change like
the two repaired cases: it requires a declared single-club game mode, an
`absent_layers`-style statement that the unready club produced nothing, and a
pre-registration. **That is the decision, and it is the owner's, not mine.**
The cheaper half — §4.3 — is a prerequisite either way.

### 4.2 `TD_RATE_UNDEFINED` / `TD_RATE_ABOVE_ONE` — GAME where the evidence is one POSITION
`nfl/production/nonqb/layers.py:508, 514, 565`. Inside a per-player loop, a
single position lacking a `pos_catch_rate`, or carrying a per-reception rate
above 1, returns `Outcome.fail` for the whole layer. The engine then halts at
`conversion_or_td` (football_engine.py:644) and **every** receiving and rushing
projection for **both clubs, every position** is destroyed — including the
positions whose priors are perfectly fine.

Never fired on the sealed slate. Latent, and cheap to narrow.

**Proposed narrowing (not applied).** Emit `PR.absent(...)` for the touchdown
metric of players at the offending position, exactly as `rushing_yards` already
does at football_engine.py:981-987, name the position in evidence, and keep the
`Outcome.fail` for the case where **no** position has a usable rate. This is the
`RUSHING_CONVERSION_CONTROL_UNDEFINED` pattern applied one field over — a
pattern this repository already owns, so no new policy is introduced.

### 4.3 `NONQB_TEAM_HAS_NO_APPEARING_PLAYER` / `NONQB_TEAM_HAS_NO_PLACEABLE_PLAYER` — GAME where the evidence is TEAM
`football_engine.py:356` and `run_forecast.py:594`. Both are the *bounds* on
the two repairs already made. Both name `teams_emptied` — a list — and then
destroy the game. The reasoning in the comment is right for the emptied club
("a team with nobody left has no partition to make") and does not extend to
the other one.

**Proposed narrowing (not applied).** Refuse the **emptied club** and run the
other, under the same one-club mode §4.1 needs. Refuse the game only when
`teams_emptied` covers both. Doing this first makes §4.1 a scope change rather
than an architecture change.

### 4.4 `PARTICIPATION_PRIOR_UNAVAILABLE` / `PARTICIPATION_IDENTITY_UNRESOLVED` — GAME where the evidence is PLAYER
`participation_prior.py:150` and `:156`. These sit inside `slate_fits`, so a
non-PASS becomes `SLATE_FITS_UNAVAILABLE` (football_engine.py:78) and the whole
non-QB chain is fatal for the game. One player whose position has no positional
mean, or one player with no `gsis_id`, costs both clubs everything.

`:156` is currently **shadowed**: `run_forecast._nonqb_chain` filters
gsis-less players out at :573-604 before `slate_fits` is called, so production
cannot reach it. It is still a second, unbounded copy of the policy
`EXCLUSION_LIMIT` was created to bound, reachable from
`engine_rehearsal.py` / `slate_rehearsal.py`.

**Proposed narrowing (not applied).** Exclude the affected player by name and
return him in evidence (`n_excluded`, `excluded`), bounded by the *same*
`EXCLUSION_LIMIT` constant already declared at `run_forecast.py:51` — imported,
not re-declared, since a second copy of a bound is a second bound. Keep the
`Outcome.fail` for `PARTICIPATION_PRIOR_EMPTY`.

### 4.5 The team-loop family — RUN or GAME where the evidence is one TEAM
Six refusals share one shape: a `for t in teams:` loop that `return`s on the
first club it cannot serve.

| Code | file:line | Measured |
|---|---|---|
| `QB_ALLOCATION_ZERO_ACTIVE_SHARE` | qb_allocation.py:538 | **4 of 14 games REFUSED, 0 distributions each** |
| `QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE` | qb_allocation.py:484 | latent |
| `R2_ALLOCATED_MASS_HAS_NO_MODELLED_QB` | football_engine.py:179 | latent |
| `C3_TEAM_HAS_NO_QUARTERBACK_ROW` | football_engine.py:432 | latent (C3 is live in `V1_CANDIDATE`) |
| `RUSHING_BUDGET_TEAM_MISSING` / `A1_RB_BUDGET_INCOMPLETE` | football_engine.py:579 / run_forecast.py:760 | latent |
| `A1_INPUT_TEAM_MISSING` | rushing_a1.py:750 | latent |

`QB_ALLOCATION_ZERO_ACTIVE_SHARE` is the **largest measured blast radius in the
tree**: one club's quarterback room cost ATL@PIT, BAL@IND, CHI@CAR and CLE@JAX
their *entire* runs — QB board, non-QB board, draws, artifact, all of it — in
the post-inactives configuration operators actually ship.

Note for the record: at HEAD this specific guard has been made unreachable by
conditioning the draw on the eligible room *before* sampling
(`qb_allocation.py:522-524`), and the sealed artifacts carry the pre-repair
wording ("after removing officially inactive quarterbacks"). **The scope
structure was not changed** — the guard, its sibling at :484, and the four
others in the table still `return` out of a team loop.

**Proposed narrowing (not applied).** Accumulate per-club failures instead of
returning on the first: build `refused_teams = {team: Outcome}`, return
`Outcome.ok` with the served clubs plus an explicit `refused_teams` block when
at least one club is served, and `Outcome.fail` only when none is. Every
consumer then reads `refused_teams` and reports that club's markets as absent
rather than the run as refused. The reporting hook already exists —
`absent_layers` and `completeness: PARTIAL_PLAYER_COVERAGE` —
and would gain a `absent_teams` peer.

### 4.6 `EXCLUSION_LIMIT` has a GAME denominator for a per-TEAM feed defect
`run_forecast.py:51`, applied at `:461` and `:571`. `len(bad) / len(players)`
divides by the **whole game's** frame, so identical damage scores differently
depending on the other club's roster size, and a defect concentrated in one
club's feed is measured against a denominator half of which is the innocent
club. Two unplaceable players on one club is 1.05% of a 190-player game frame
and refuses; the same two players in a 210-player game do not.

**Proposed narrowing (not applied).** Evaluate the ratio **per club** against
the same constant and refuse only the club that breaches it — under the same
one-club mode. No new constant: `EXCLUSION_LIMIT` keeps its declared value and
gains a declared denominator.

### 4.7 `qb_inactive_owns_nothing` — RUN where the evidence is TEAM (weak)
`qb_accounting.py:828`, gating at `run_forecast.py:410/:1044` and again through
the HARD invariant gate at `:1523`. One inactive quarterback holding mass in one
draw refuses the run. The counter-argument is real and I record it: the
allocation is a closed simplex, so mass held by an inactive is mass taken from
his own teammates — the error is the *club's* allocation, not the player's row.
That makes the justified scope TEAM, not PLAYER, and the gap to RUN is one step
rather than two. **Verdict TOO_BROAD, ranked low, and I would not move it ahead
of §4.1–§4.5.** It is also a correctness guard with a live history (the SF@LA
board), so any narrowing must keep it refusing the offending club outright.

### 4.8 `qb_composition` halt — GAME where the evidence is one PLAYER
`football_engine.py:735-742`. `QBACC.conserve_allocated_mass` is called per
quarterback; a non-PASS for one `pid` on one team halts the game at
`qb_composition` and destroys both clubs' non-QB board. Reachable only on the
non-R2 composition path (R2 removes the division), so it is latent in the
shipped `V1_CANDIDATE`, which sets `r2: True` (`candidate_mode.py:121`).

**Proposed narrowing (not applied).** Refuse that quarterback's composition by
name, record him in a `qb_composition_refused` list, and halt only when a club
is left with no composable passer.

### 4.9 `INACTIVES_IDENTITY_AMBIGUOUS` / `INACTIVES_SUPPLIED_NAME_NOT_IN_BYTES` — SLATE where the evidence is one NAME
`inactives.py:505, 438`. One ambiguous name refuses the whole resolution, so
**no** club on the slate gets an official inactive list, and every game's
`qb_inactive_owns_nothing` then records DEFERRED. This is a capture-tool path
rather than the forecast path, and the "fuzzy resolution is forbidden" argument
is correct **for that name**. It is not an argument about the other 31 clubs.

**Proposed narrowing (not applied).** Return the resolved clubs, carry
`unresolved_names` per club, and refuse only the club carrying the ambiguity —
its games then run without an official list, which is the already-declared
DEFERRED state, instead of the whole slate losing one.

---

## 5. What I could not establish — evidence ceiling

1. **Whether a one-club non-QB board is scientifically admissible.** Every
   ranked narrowing in §4.1, §4.3, §4.5 and §4.6 depends on the engine
   producing a game in which one club has no modelled players. The engine
   refuses that state deliberately today. Whether the surviving club's
   allocation is still the accepted V1 allocation — its own simplex is
   within-club, and `reconcile_nonqb` groups per club, which argues yes — is a
   question for a pre-registration, and no artifact in this repository answers
   it. I did not run the engine to find out, because doing so would be
   measuring a configuration nobody has declared.

2. **Counterfactual recovery is bounded, not estimated.** "~52 player
   distributions" is `12–15 non-QB players per club` × `4 ready clubs`, read
   off four healthy R8 boards in the same slate. It is what a *healthy* club
   produces, not a measurement of what these four clubs would have produced.
   The true figure is unknown until the narrowing is run, and I have not run
   it.

3. **One slate, one week.** All empirical statements come from
   `nfl/research/live/2026_01_*/` — 14 games, 2026 week 1, 109 `run_status.json`
   files. Frequencies (4 of 14 refused; 4 of 14 lost a ready club's board) are
   counts from that slate and are not rates. Games are not independent
   observations of anything here; they are one week's operating record.

4. **Latent means latent.** §4.2, §4.5 (all but the first row), §4.8 and §4.9
   never fired in the sealed set. They are read from code, and the claim is
   about what the code would destroy, not about damage that has happened.

5. **I did not run the suite**, per the workstream constraint, so no statement
   here is backed by a test result. Every line number was read; every count was
   computed from the sealed artifacts on disk.

---

## 6. Summary

**Counts are of inventory ROWS, and a row is a refusal site.** Three defects
appear at two sites each, because the state is named in one module and applied
in another (readiness names `INJURY_REPORT_*`; `layers.appearance` and the
engine's `appearance` halt apply it). Deduplicated, the over-scoped sites
collapse into the **nine groups ranked in §4**.

* **106 refusal sites inventoried** across `nfl/production/run_forecast.py`,
  `nfl/production/nonqb/*.py`, `nfl/production/qb_*.py`, `nfl/product/*.py` and
  `nfl/tools/make_board.py`.
* **CORRECT: 79 sites.** Chronology (10), authorization (3) and construction
  invariants dominate. None of them should be narrowed, and this report asks
  for no change to any of them.
* **TOO_BROAD: 26 sites in 9 groups** (§4.1–§4.9). Two groups are measured on
  the sealed slate; seven are latent.
* **TOO_NARROW: 1.** `p4c_lib.allocate` returns a degenerate group — a club
  whose whole modelled position group is unavailable — as the integer
  `n_groups_with_no_modelled_weight` (`nfl/research/p4c/p4c_lib.py:136-139`,
  surfaced at `layers.py:374`), and **nothing gates on it**. A club that loses
  its entire running-back room to the player-level exclusion path therefore
  seals a PASS with zero rushing projections and the whole carry budget
  absorbed into `other`. That is a genuinely team-wide absence handled as a
  per-player exclusion and reported as a number nobody reads. Measured: the
  value is 0 in every sealed artifact in the tree, so it is latent. Proposed
  (not applied): a named `NONQB_TEAM_GROUP_UNMODELLED` outcome scoped to that
  club and that position group, carried into `absent_layers`.

**The single highest-value change** is §4.3 — narrow the two
`TEAM_HAS_NO_*_PLAYER` refusals to the emptied club — because it is the
prerequisite for §4.1 and §4.6 and is the smallest step that makes a one-club
game a real engine state rather than a refused one.

**The single largest measured loss** is §4.5
`QB_ALLOCATION_ZERO_ACTIVE_SHARE`: four whole runs, zero distributions sealed,
from one club's quarterback room each time.

**The most consequential correction to an earlier framing**: the injury-report
case is TWO separable questions. The *trigger* is at the evidence ceiling and
the withdrawn fix stays withdrawn. The *scope* is not at any ceiling — the
per-club verdict is already computed and carried in `owed['teams']` and
`blocking_team`, and is thrown away one line later.

**CODE CHANGED: NO.**

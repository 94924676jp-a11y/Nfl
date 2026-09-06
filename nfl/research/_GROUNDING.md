# Shared grounding brief for NFL greenfield research workers

**Status:** input to research workers. Not a finding. Every fact below was
measured in this container on 2026-09-06 by the lead, with the command shown.
Nothing here is recalled.

## Rule for every worker: label every claim

Each worker output must mark every substantive claim with exactly one of:

- `VERIFIED` — the worker ran a command or opened a file, and cites it.
  Include the command or `path:line`.
- `DERIVED` — follows by arithmetic or logic from something VERIFIED, and the
  derivation is shown.
- `UNVERIFIED-RECALL` — believed from training, **not** checked here. Permitted,
  but must be labelled, and must never be used as the basis of a design
  commitment without being flagged as needing confirmation.

An unlabelled claim is a defect in the worker output. This project has already
paid twice for recalled numbers presented as measured ones (see `CLAUDE.md`,
"Claims you may encounter that are FALSE").

## Network reality in this container — measured

General web egress is **blocked**. Verified 403/000:
`site.api.espn.com`, `www.pro-football-reference.com`, `api.sleeper.app`,
`api.github.com/repos/<other-owner>`.

**But `raw.githubusercontent.com` and `github.com/<owner>/<repo>/releases/download/...`
return 200.** This is the single most important operational fact for NFL-0. It
means the **nflverse** public data stack is fully readable from here.

Verified reachable (HTTP 200, byte counts as returned):

| Release path | 2024 bytes | Notes |
|---|---|---|
| `pbp/play_by_play_2024.csv` | 99,483,794 | 49,493 rows, **372 columns** |
| `pbp_participation/pbp_participation_2024.csv` | 49,688,308 | 45,920 rows |
| `ftn_charting/ftn_charting_2024.csv` | 8,254,908 | 29 columns |
| `snap_counts/snap_counts_2024.csv` | 2,402,841 | 16 columns |
| `injuries/injuries_2024.csv` | 816,989 | 6,215 rows, 16 columns |
| `depth_charts/depth_charts_2024.csv` | 3,391,616 | |
| `player_stats/player_stats_2024.csv` | 1,674,023 | |
| `weekly_rosters/roster_weekly_2024.csv` | 14,926,918 | |
| `rosters/roster_2024.csv` | 1,005,701 | |
| `players/players.csv` | 7,289,018 | |
| `pfr_advstats/advstats_week_pass_2024.csv` | 73,095 | |
| `espn_data/qbr_week_level.csv` | 2,443,597 | |
| `officials/officials.csv` | 1,293,787 | |
| `combine/combine.csv` | 893,875 | |
| `contracts/historical_contracts.csv.gz` | 1,186,370 | |

**2025 is fully present**: `play_by_play_2025.csv` (97,951,481),
`pbp_participation_2025.csv` (49,094,943), `ftn_charting_2025.csv` (8,128,926),
`snap_counts_2025.csv` (2,401,193), `injuries_2025.csv` (695,623).

**Historical depth, measured by probing each year:**
- `pbp_participation`: 200 for 2016, 2018, 2020, 2021, 2022, 2023, 2024, 2025.
- `ftn_charting`: **404 for 2016/2018/2020/2021**, 200 for 2022, 2023, 2024, 2025.
  FTN charting therefore begins in 2022 — four seasons.

404 (name is wrong or the set does not exist under that name; do not assume
absence without trying variants): `rosters_weekly/roster_weekly_2024.csv`,
`nextgen_stats/ngs_2024_receiving.csv`, `nextgen_stats/ngs_receiving.csv`,
`contracts/historical_contracts.csv`.

Download command that works:
```
curl -sS -L -o OUT.csv "https://github.com/nflverse/nflverse-data/releases/download/<path>"
```

## Verified schemas

### `pbp_participation` — 26 columns, the opportunity substrate
```
nflverse_game_id, old_game_id, play_id, possession_team, offense_formation,
offense_personnel, defenders_in_box, defense_personnel, number_of_pass_rushers,
players_on_play, offense_players, defense_players, n_offense, n_defense,
ngs_air_yards, time_to_throw, was_pressure, route, defense_man_zone_type,
defense_coverage_type, offense_names, defense_names, offense_positions,
defense_positions, offense_numbers, defense_numbers
```
`offense_players` is a `;`-delimited list of gsis IDs. Together with `route`
this is what makes **route participation** and **targets per route run**
computable. `was_pressure`, `time_to_throw`, `defense_man_zone_type` and
`defense_coverage_type` are present on the same row.

### `injuries` — 16 columns
```
season, game_type, team, week, gsis_id, position, full_name, first_name,
last_name, report_primary_injury, report_secondary_injury, report_status,
practice_primary_injury, practice_secondary_injury, practice_status,
date_modified
```
`date_modified` is a full ISO-8601 UTC timestamp, e.g. `2024-09-06T19:05:30Z`.

### `snap_counts` — 16 columns
```
game_id, pfr_game_id, season, game_type, week, player, pfr_player_id, position,
team, opponent, offense_snaps, offense_pct, defense_snaps, defense_pct,
st_snaps, st_pct
```

### `ftn_charting` — 29 columns
```
ftn_game_id, nflverse_game_id, season, week, ftn_play_id, nflverse_play_id,
starting_hash, qb_location, n_offense_backfield, n_defense_box, is_no_huddle,
is_motion, is_play_action, is_screen_pass, is_rpo, is_trick_play,
is_qb_out_of_pocket, is_interception_worthy, is_throw_away, read_thrown,
is_catchable_ball, is_contested_ball, is_created_reception, is_drop,
is_qb_sneak, n_blitzers, n_pass_rushers, is_qb_fault_sack, date_pulled
```

## The finding that drives NFL-0 — injury history is a terminal snapshot

Measured on `injuries_2024.csv`:

- 6,215 rows, **6,213 distinct `(season, week, gsis_id)`** — only 2 player-weeks
  carry more than one row.
- Week-1 `date_modified` by day: 2024-09-04 → 18, 2024-09-05 → 12,
  **2024-09-06 → 154**, 2024-09-07 → 22.

So the file holds **one row per player-week, stamped near the final (Friday)
report**. The Wednesday practice status is *overwritten* by the Friday one. The
user's requirement — "Never overwrite Tuesday with Sunday" — is already violated
by the historical archive, and **the weekly information cascade cannot be
reconstructed from it retroactively.**

Consequence every worker should reason from: if the project wants to answer
"how much did knowing Player X was inactive improve the projection?", the
Tuesday/Wednesday/Thursday vintages have to be **captured live, week by week,
starting from the next unplayed week**. Every week not captured is permanently
unavailable. Today is 2026-09-06.

## A leakage hazard already present in the data

`play_by_play` carries market-derived columns — `spread_line`, `total_line`,
`vegas_wp`, `vegas_wpa`, `vegas_home_wp` among its 372. A "neutral" data source
therefore ships sportsbook information inside it. Under `CLAUDE.md` rule 1
(never optimise toward the book) and the platform's market/forecast separation,
these columns must be **quarantined at ingest**, not merely "not selected".

## Governance the NFL work inherits — real, named, existing

Read these before proposing anything; do not invent parallel vocabulary.

- `v8/V8_SYSTEM_CONSTITUTION.md` — Rule 001 five-state vocabulary
  (`PASS` / `FAIL` / `BLOCKED` / `DEFERRED` / `NOT_APPLICABLE`), Rule 002 five
  clocks, Rule 003 leakage, Rule 004 baseline comparison, Rule 004a metrics
  frozen before scoring, Rule 005 no cherry-picking (r, SD ratio and calibration
  slope are algebraically one fact), Rule 006 no promotion from development data.
- `v8/V8_FAILURE_TAXONOMY.md` — Class A "absence read as success" is the
  dominant class; also B missing state vocabulary, C declaration drift,
  D environment-dependent behaviour.
- `v8/FEATURE_REGISTRY.md` — lifecycle statuses CORE / SECONDARY / EXPERIMENTAL
  / DESCRIPTIVE / REJECTED, and the rule that a status above EXPERIMENTAL must
  cite the experiment that earned it.
- `sportsplatform/governance/` — working code: `outcome.py`, `provenance.py`, `scorecard.py`,
  `stopping.py`, `environment.py`, plus their replay tests.
- `docs/AGENT_PROTOCOL.md` — escalation bar, and DEC-029 "not blocked — assigned".
- `CLAUDE.md` — the governing rules, the M0 four-state status, and the finish line.

## MLB lessons that are load-bearing here

- MLB's baseline discriminates barely at all: **r = 0.1101**, SD ratio 0.1804 on
  n=251. Calibration was near nominal while discrimination was ~zero. Those are
  different properties; passing one says nothing about the other.
- MLB stored **nine percentiles**, which cannot support exact CRPS, log score or
  tail calibration. The NFL design must store full joint draws from day one.
- MLB's M0 is **not reproducible** because the consumed corpus was never
  committed, and the fingerprint did not catch it because `SIM_FORMULA` excluded
  the corpus. Input manifests with content hashes are the fix.
- Power: detecting r 0.11 → 0.25 needed ~377 games independent, **~1,131 with
  the threefold clustering measured on MLB**. NFL has ~272 regular-season games
  per season (`UNVERIFIED-RECALL` — worker 1 should confirm from the schedule
  file). Sample size is the binding constraint on NFL confirmatory claims and
  every worker should treat it as such.
- Clustered standard errors: naive binomial SEs understated uncertainty roughly
  threefold on MLB props. NFL player-games within a team-game are more strongly
  coupled, not less.

## Hard scope limit for this pass

**Research and architecture only. No predictive production code.** Do not write
a model, a simulator, or a feature builder. Small throwaway measurement scripts
run in the scratchpad to establish a fact are expected and encouraged — that is
how you produce VERIFIED claims — but they are evidence, not deliverables, and
must not be committed to `nfl/` as modules.

---

## Corrections to this brief, recorded rather than edited away

This section exists because `CLAUDE.md` requires withdrawn claims to stay
visible, so a reader of an earlier copy can tell what changed.

**C1 — the power figure above is wrong, and the error is mine (lead).**
This brief said "~377 games independent, ~1,131 with the threefold clustering
measured on MLB". Worker 1 showed the second half treats a **standard-error**
ratio as if it were a sample-size multiplier. MLB's measured 1.653pp against
0.587pp is a design effect of **7.93**, not 3.

The corrected reading, which the integration document adopts:
- **Game-level** correlation: ~377 games ≈ 1.4 NFL seasons at 272 REG games.
- **Player-prop** analyses, where the clustering actually applies:
  ~2,000–3,000 game-equivalents, i.e. **7–11 seasons**.

The Fisher-z 377 reproduces exactly. It is only the clustering multiplier that
was misapplied. **Do not quote the 1,131.**

**C2 — `injuries` lost its timestamp in 2025, and the column count hides it.**
This brief documented `date_modified` from the 2024 file. Verified 2026-09-06:
`injuries_2025.csv` has **16 columns, same as 2024**, but `date_modified` is
**gone** and `season_type` has been added in its place. A column-count check
passes through this change unchanged — Failure Taxonomy Class A and C in one
schema revision. `injuries_2026.csv` is a **404** today.

Consequence, and it strengthens rather than weakens the finding above: the 2026
injury data will publish with **no timestamp at all**. Weekly vintages for 2026
are obtainable *only* by our own dated capture. There is no later recovery path.

**C3 — "route makes targets per route run computable" is WITHDRAWN. Mine.**
This brief asserted that `participation.route` together with `offense_players`
makes route participation and TPRR computable. Worker 4 refuted it and the lead
reproduced the refutation independently on `pbp_participation_2024.csv`:

- `route` is **one scalar per play**, not a per-player list.
- **14 distinct values**, all route *names* (`GO`, `SLANT`, `SCREEN`,
  `HITCH/CURL`, …), blank on 26,809 of 45,919 rows.
- **Zero rows contain a `;`**, so it is not a parallel list to `offense_players`.

It is the **targeted receiver's** route. Per-player routes-run is **not derivable
from this feed**. Any NFL feature named "routes run" or "TPRR" built on it is a
different quantity wearing that name — precisely the defect class that produced
MLB's blank-column export.

What survives, and it is verified rather than assumed: `offense_players`
restricted to dropbacks yields **pass-play participation**, which reconciles
*exactly* against official `player_stats_2024` (11,629 = 11,629 receptions
across 4,263/4,263 player-weeks). That is a sound denominator. It must be named
for what it is.

**C4 — NGS receiving is NOT 404. Mine.** This brief listed
`nextgen_stats/ngs_receiving.csv` and `ngs_2024_receiving.csv` as absent. The
extension was wrong, not the dataset: **`nextgen_stats/ngs_receiving.csv.gz`
returns 200** (981,431 bytes, 2016–2025), carrying `avg_cushion`,
`avg_separation`, `avg_intended_air_yards` and `avg_yac_above_expectation` —
the only separation and cushion data in the stack. `nfl/tools/probe_nfl_sources.py`
has been corrected to probe the real path.

Carry the caveat with it: Worker 4 measured coverage at **29.4% of player-weeks
with a target**, and availability correlates with volume, so it is a selection
hazard, not a free feature.

**Rule this reinforces:** a 404 means *this path 404ed*. It never means the
dataset does not exist. Two of the four "absent" datasets in the original list
were live under a different name.

**C5 — `participation.ngs_air_yards` is present in the header and EMPTY. Mine.**
This brief listed `ngs_air_yards` among the fields that make participation the
opportunity substrate. Worker 2 found it empty; the lead reproduced it:
**0 non-null of 45,919 rows** in `pbp_participation_2024.csv`. `time_to_throw`
on the same rows is populated (19,733), so this is not a parsing artefact.

Disposition: **REJECTED — SOURCE EMPTY**, the same disposition MLB gave the
`umpire` column. Air yards must come from `pbp.air_yards`, not from here.

This is the exact shape of the defect that produced MLB's 7,926-row export with
every meaningful column blank: **a column existing is not a column carrying
values.** Any NFL ingest must assert non-null fractions per column and refuse a
field that arrives empty, rather than reading the header as availability.

**C6 — denominator defects in `pbp` that a reasonable reader would walk into.**
Measured by Worker 2 and recorded here because they are the highest-cost kind of
error this project makes:
- `pass_attempt` **includes sacks** — 19,153 flagged, 1,314 of them sacks, 17,839
  true throws. Using it as the completion-percentage denominator returns 0.6072
  instead of 0.6555, a 4.8-point error **larger than the entire between-QB
  spread** (sd 0.0343).
- `passer_player_id` is **null on 100% of scrambles** (5.25% of dropbacks).
- `n_blitzers` counts *extra* rushers, not total; `n_pass_rushers == 0`,
  `defenders_in_box == 0` and `read_thrown == '0'` are **not-applicable
  sentinels**, not measured zeros.

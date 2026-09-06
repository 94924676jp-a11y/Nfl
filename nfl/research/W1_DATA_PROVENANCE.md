# W1 — NFL-0 Data, Provenance and Identity

**Worker:** 1 (NFL data, provenance, identity)
**Date measured:** 2026-09-06, in this container.
**Inputs:** nflverse-data GitHub releases; `nfl/research/_GROUNDING.md`;
`v8/V8_SYSTEM_CONSTITUTION.md`; `v8/V8_FAILURE_TAXONOMY.md`;
`docs/AGENT_PROTOCOL.md`; `CLAUDE.md`.
**Scope limit honoured:** research only. No predictive code written. All
measurement scripts were throwaway, run in the session scratchpad, and are not
committed. This file is the only file created or modified.

Every substantive claim below is labelled `VERIFIED`, `DERIVED`, or
`UNVERIFIED-RECALL` per the grounding brief's rule.

---

## 0. Method and reproduction

All measurements used the stdlib `csv` module under `python3.12`, so nothing
below depends on a third-party library.

**An environment fact, and it changed under me mid-session — Failure Taxonomy
Class D, observed live.** `VERIFIED` at 18:30 UTC:
`python3.12 -c "import pandas"` → `ModuleNotFoundError`. `VERIFIED` at 18:44
UTC, same container, same command: `pandas 3.0.5`. Another worker installed it
between the two checks. `VERIFIED` at 18:44: `python3`, `python3.11` and
`python3.13` all still raise `ModuleNotFoundError`.

`DERIVED`: pandas availability in this container is **not a stable fact**, it is
interpreter-specific, and it is mutated by concurrent sessions. Any NFL-0
tooling must either pin the interpreter and assert the import at start-up with a
named `BLOCKED` code, or use the stdlib. I have left this paragraph in rather
than silently updating the earlier claim, because the correction *is* the
finding.

Download shape that works (`VERIFIED`, all 200s reported inline below):

```
curl -sS -L -o OUT.csv "https://github.com/nflverse/nflverse-data/releases/download/<path>"
```

Files measured, with SHA-256 as retrieved on 2026-09-06 (`VERIFIED`,
`sha256sum`). These hashes are the point of §4: without them nothing below is
re-checkable.

| file | release path | bytes | sha256 (first 16) |
|---|---|---|---|
| schedules | `schedules/games.csv` | 2,177,171 | `5fd04e27b065aff1` |
| players | `players/players.csv` | 7,289,018 | `fb6a961ca631ab92` |
| pbp 2024 | `pbp/play_by_play_2024.csv` | 99,483,794 | `6ae564c2c49378ec` |
| participation 2024 | `pbp_participation/pbp_participation_2024.csv` | 49,688,308 | `b1f436a98b2a7759` |
| ftn 2024 | `ftn_charting/ftn_charting_2024.csv` | 8,254,908 | `6faae8118cc13ce6` |
| snap_counts 2024 | `snap_counts/snap_counts_2024.csv` | 2,402,841 | `a2aa58efe093f8aa` |
| injuries 2024 | `injuries/injuries_2024.csv` | 816,989 | `498bce8e13cb64b2` |
| depth_charts 2024 | `depth_charts/depth_charts_2024.csv` | 3,391,616 | `f210a33774611f7f` |
| player_stats 2024 | `player_stats/player_stats_2024.csv` | 1,674,023 | `4f1598c9a6ba396a` |
| rosters 2024 | `rosters/roster_2024.csv` | 1,005,701 | `97721aa9092edb15` |
| weekly_rosters 2024 | `weekly_rosters/roster_weekly_2024.csv` | 14,926,918 | `074ecaeb9325de94` |

---

## 1. Game and player identity — the join graph, measured

### 1.1 Which key each dataset actually carries

`VERIFIED` — headers read from the files listed in §0.

| dataset | game key | player key | team key | week key | notes |
|---|---|---|---|---|---|
| `schedules` | `game_id` (+`old_game_id`,`gsis`,`pfr`,`espn`,`ftn`,`pff`,`nfl_detail_id`) | `away_qb_id`,`home_qb_id` only | `home_team`/`away_team` | `season`+`week`+`game_type` | the hub |
| `pbp` | `game_id`, `old_game_id` | gsis (`passer_player_id`, …, ~40 role columns) | `home_team`,`away_team`,`posteam`,`defteam` | `season`,`week`,`season_type` | 372 cols |
| `pbp_participation` | `nflverse_game_id`, `old_game_id`, `play_id` | gsis, `;`-delimited in `offense_players`/`defense_players` | `possession_team` | none | 26 cols |
| `ftn_charting` | `nflverse_game_id`, `ftn_game_id`, `nflverse_play_id`, `ftn_play_id` | **none** | none | `season`,`week` | 29 cols |
| `snap_counts` | `game_id`, `pfr_game_id` | **`pfr_player_id` — PFR namespace, not gsis** | `team`,`opponent` | `season`,`week`,`game_type` | 16 cols |
| `injuries` (2024) | **none** | `gsis_id` | `team` | `season`,`week`,`game_type` | 16 cols |
| `depth_charts` (2024) | **none** | `gsis_id`, `elias_id` | `club_code` | `season`,`week`,`game_type` | 15 cols |
| `depth_charts` (2025+) | **none** | `gsis_id`, `espn_id` | `team` | **none — `dt` timestamp instead** | 12 cols |
| `player_stats` (2024) | **none** | `player_id` (gsis) | `recent_team`,`opponent_team` | `season`,`week`,`season_type` | 53 cols |
| `stats_player_week` (2025+) | **`game_id` present** | `player_id` (gsis) | `team`,`opponent_team` | `season`,`week`,`season_type` | 150 cols |
| `weekly_rosters` | none | `gsis_id` (+9 vendor ids) | `team` | `season`,`week`,`game_type` | 36 cols |
| `players` | n/a | `gsis_id` + `esb_id`+`nfl_id`+`pfr_id`+`pff_id`+`otc_id`+`espn_id`+`smart_id` | `latest_team` | n/a | **the crosswalk** |

**The grounding's hypothesis is confirmed exactly.** `snap_counts` is the only
per-game player dataset keyed on `pfr_player_id`; every other player dataset is
keyed on gsis. `players/players.csv` is the crosswalk (`VERIFIED`, below).

### 1.2 `players.csv` as a crosswalk — measured coverage

`VERIFIED` — 24,828 rows.

| id column | non-empty | % |
|---|---|---|
| `gsis_id` | 24,828 | 100.0 |
| `esb_id` | 24,828 | 100.0 |
| `smart_id` | 24,828 | 100.0 |
| `pfr_id` | 22,653 | 91.2 |
| `espn_id` | 16,561 | 66.7 |
| `nfl_id` | 11,899 | 47.9 |
| `pff_id` | 11,616 | 46.8 |
| `otc_id` | 9,794 | 39.4 |

`gsis_id` has 24,828 distinct values and 0 duplicates; `pfr_id` has 22,653
distinct and **0 duplicates** (`VERIFIED`). The `pfr_id → gsis_id` map is
therefore injective with 22,653 entries — a clean crosswalk, not a fuzzy one.

**Do not use `rosters/roster_2024.csv` as the crosswalk.** `VERIFIED`: 3,216
rows, `pfr_id` empty on **1,445 (44.9%)**. `weekly_rosters` is no better —
46,579 rows with `pfr_id` empty on **18,080 (38.8%)**. Only `players.csv`
carries a near-complete PFR mapping.

### 1.3 The join success rates — measured, not assumed

`VERIFIED`, 2024 season.

| join | denominator | matched | rate | failure mode |
|---|---|---|---|---|
| `snap_counts.game_id` → `schedules.game_id` | 26,615 rows | 26,615 | **100.000%** | none |
| `snap_counts.pfr_player_id` → `players.pfr_id` | 26,615 rows | 26,573 | **99.8422%** | 42 rows, 6 distinct players |
| `pbp_participation` → `pbp` on `(game_id, play_id)` | 45,919 rows | 45,919 | **100.000%** | none |
| `ftn_charting` → `pbp` on `(game_id, play_id)` | 48,031 rows | 48,031 | **100.000%** | none |
| `injuries.gsis_id` → `players.gsis_id` | 6,215 rows | 6,215 | **100.000%** | none |
| `depth_charts.gsis_id` → `players.gsis_id` | 37,312 rows | 37,312 | **100.000%** | none |
| `player_stats.player_id` → `players.gsis_id` | 5,597 rows | 5,597 | **100.000%** | none |
| `injuries (week, team)` → `schedules` | 6,215 rows | 6,215 | **100.000%** | none |
| `player_stats (week, team)` → `schedules` | 5,597 rows | 5,597 | **100.000%** | none |
| `depth_charts (week, club_code)` → `schedules` | 37,312 rows | 33,542 | **89.90%** | 3,770 rows — see §1.5 |

`(week, team)` resolves to **exactly one** 2024 game in every case — 0 keys map
to more than one game (`VERIFIED`). So a game-level join for the datasets that
lack `game_id` is safe *within a season*, provided bye weeks and postseason
week numbering are handled (§1.5).

### 1.4 The 42 unmapped snap rows — and why a name fallback is a trap

This is the Class A defect the task brief anticipated, caught in the small.
`VERIFIED`, all six unmapped `pfr_player_id`s, with a name lookup against
`players.display_name`:

| snap_counts `player` | pos | rows | name matches in `players.csv` | their `pfr_id` | verdict |
|---|---|---|---|---|---|
| Alec Anderson | G | 20 | 1 (`00-0037428`) | *empty* | recoverable — gap is in `players.csv` |
| Bill Murray | G | 3 | 1 (`00-0036093`) | *empty* | recoverable — same |
| John Samuel Shenker | TE | 8 | 0 | — | not recoverable here |
| Bump Cooper | CB | 1 | 0 | — | not recoverable here |
| Cody White | WR | 4 | **2** (`00-0029522`, `00-0035891`) | `WhitCo02`, empty | **ambiguous — name fallback would guess** |
| Rodney Williams | TE | 6 | 1 (`00-0017923`) | `WillRo23` | **wrong era — a 2001-vintage player. Name fallback joins the wrong man.** |

`DERIVED` from the table: a "fall back to name matching" rule recovers 2 of 6
correctly, silently mis-joins 2 of 6, and fails on 2 of 6. **A name fallback is
not a repair; it converts a visible 0.158% loss into an invisible 0.158%
corruption.** The right behaviour under Rule 001 is a per-row `FAIL` with code
`PFR_ID_UNMAPPED` carrying the offending id, plus a run-level count, never a
silent inner join and never a name guess.

All 42 rows are at G/TE/WR/CB (`VERIFIED`: G 23, TE 14, WR 4, CB 1) — fringe
linemen and practice-squad elevations, i.e. exactly the population that will be
non-fringe the moment the project models offensive line or blocking.

### 1.5 Identity hazards found, each a concrete Class A trap

All `VERIFIED` on 2024 data unless marked.

1. **Postseason week collision.** `schedules` numbers postseason as week 19 WC /
   20 DIV / 21 CON / 22 SB, continuing the same `week` integer as REG 1–18. But
   `depth_charts` carries rows labelled `game_type='REG'` **at week 19** for the
   same club-week as a `game_type='WC'` row. Joining on `(season, week, club)`
   alone therefore double-counts. `game_type` must be part of every key.
2. **Blank week.** `depth_charts` has 234 rows with `week=''` and
   `game_type='SBBYE'` (4 clubs). A loader that coerces `week` to int dies; one
   that coerces to 0 silently invents a week 0. Neither is a state.
3. **Exact duplicate rows.** 840 `depth_charts` rows are byte-identical
   duplicates on the full key `(season, week, club_code, gsis_id, formation,
   depth_position, depth_team)` — verified by printing both rows of a duplicate
   pair (Dee Alford, ATL, week 1, Defense/NB/1: two identical rows). Any
   `count()` or `mean()` over depth charts is wrong by ~2.3% unless deduplicated
   first.
4. **Team-code drift across seasons.** Within 2024, all eight team-code columns
   across all seven datasets carry **exactly the same 32 codes** (`VERIFIED`:
   zero extras, zero missing, in `schedules`, `snap_counts.team`,
   `snap_counts.opponent`, `injuries.team`, `depth_charts.club_code`,
   `rosters.team`, `player_stats.recent_team`, `player_stats.opponent_team`).
   Across seasons they do drift (`VERIFIED` from `schedules` 1999–2026):
   `OAK`→`LV` at 2020, `SD`→`LAC` at 2017, `STL`→`LA` at 2016, and `HOU` absent
   before 2002 (31 clubs in 1999–2001). A franchise-continuity table is required
   for any multi-season join and does not ship with nflverse.
5. **`injuries` duplicate player-weeks.** 6,215 rows, 6,213 distinct
   `(season, week, gsis_id)` — 2 player-weeks carry two rows. Small, but a
   `dict[key] = row` load loses one silently.
6. **`player_stats` (2024) is offence-only.** 612 distinct players; positions
   are WR 2,238 / RB 1,408 / TE 1,137 / QB 697 / FB 72 and a handful of
   miscoded others. There is no defensive weekly stat file under that name for
   2024. (Resolved for 2025+, see §1.6.)
7. **`snap_counts` is clean on its own key.** 0 duplicates on
   `(game_id, pfr_player_id)`; `weekly_rosters` 0 duplicates on
   `(week, team, gsis_id)`; `player_stats` 0 duplicates on `(week, player_id)`;
   0 player-weeks appear on two teams. These are the datasets that will not bite.

### 1.6 Schema drift 2024 → 2025 — Failure Taxonomy Class C, live

`VERIFIED` by HTTP range request on each release asset's first 4 KB.

| dataset | 2024 | 2025 | verdict |
|---|---|---|---|
| `injuries` | 16 cols, **has `date_modified`** | 16 cols, **`date_modified` GONE**, `season_type` added | **same column count, different columns.** A ncol check passes. |
| `depth_charts` | 15 cols, `season/club_code/week/game_type/depth_team/formation/depth_position` | 12 cols, `dt/team/player_name/espn_id/gsis_id/pos_grp_id/pos_grp/pos_id/pos_name/pos_abb/pos_slot/pos_rank` | **total redesign.** No `week`, no `game_type`, no `depth_team`; new `dt` timestamp. |
| `player_stats` | `player_stats/player_stats_2024.csv` → 200 | `player_stats/player_stats_2025.csv` → **404** | **release path renamed** to `stats_player/stats_player_week_2025.csv` (200, 8,656,387 bytes, **150 columns**, now including `game_id`, full defensive, kicking and punting blocks). |
| `snap_counts` | 16 cols | 16 cols, identical | stable |
| `pbp_participation` | 26 cols | 26 cols, identical | stable |
| `ftn_charting` | 29 cols | 29 cols, identical | stable |

`DERIVED`: a naive loop `for season in range(2016, 2026)` over
`player_stats/player_stats_{s}.csv` returns 200 for 2024 and 404 for 2025. Under
Rule 001 the 404 must be `FAIL: RELEASE_PATH_404`, not an empty frame. Under
Rule 002 the injuries change must be `FAIL: SCHEMA_VERSION_CHANGED` naming the
dropped column, because the count is unchanged and only a column-set comparison
catches it. **NFL-0 must pin a schema fingerprint per dataset-season — the
sorted column list hashed — not a column count.**

---

## 2. The four clocks

### 2.1 Vocabulary — mapping the task's four onto the constitution's five

`VERIFIED` — `sportsplatform/governance/provenance.py:13-17` defines five clocks:
`source_timestamp` (when the source says the data describes), `retrieved_at`
(when we obtained the bytes), `cache_timestamp`, `generated_at` (wrapper
assembly), `effective_for_date` (the game date it may lawfully be used for).
`_REQUIRED` at `provenance.py:31-32` makes all but `cache_timestamp` mandatory.

Mapping, `DERIVED`:

| task clock | constitution field | status |
|---|---|---|
| `event_time` | `source_timestamp` | direct |
| `ingested_time` | `retrieved_at` | direct |
| `prediction_time` | `effective_for_date` (+ the cutoff enforced by `assert_usable_for`, `provenance.py:125`) | direct |
| **`available_time`** | **no field exists** | **gap** |

`available_time` — the earliest instant at which a fact was knowable to a
forecaster — has no slot in `Provenance`. That is precisely the clock nflverse
destroys, and it is the clock every leakage question turns on. **Recommendation
for the lead:** NFL-0's input manifest carries `available_time` explicitly, and
whether `Provenance` gains a sixth field is a constitution amendment (Rule 013)
for the lead to route, not for a worker to make.

### 2.2 Per-dataset clock recoverability

| dataset | event_time | available_time | ingested_time | verdict |
|---|---|---|---|---|
| `schedules` | `gameday`+`gametime` (`VERIFIED`, 100% populated for 2024 and 2026) | **absent** — market columns are overwritten in place | HTTP `Last-Modified` only | **mutable file, no history** |
| `pbp` | `game_date`, `start_time`, `time_of_day` (per-play ISO-8601 UTC, `VERIFIED`) | **post-game by construction** | HTTP `Last-Modified` | fine — it is outcome data |
| `pbp_participation` | via `pbp` join | post-game | HTTP `Last-Modified` | fine |
| `ftn_charting` | via `pbp` join | **post-game, measured** — see §2.3 | `date_pulled` (present, but see §2.3) | **not usable pre-kickoff** |
| `snap_counts` | game date via `game_id` | post-game | HTTP `Last-Modified` | fine — outcome data |
| `injuries` **2024** | week+team → kickoff | **`date_modified`, but terminal** — see §2.4 | none | **one vintage only** |
| `injuries` **2025+** | week+team → kickoff | **PERMANENTLY ABSENT** — `date_modified` removed | none | **no clock at all** |
| `depth_charts` **2024** | week+team → kickoff | **absent** | none | **one vintage only** |
| `depth_charts` **2025+** | via `dt` | **`dt` — a real daily snapshot series** — see §2.5 | `dt` | **the one good case** |
| `weekly_rosters` | week+team → kickoff | **absent — and `INA` is ~90 min pre-kickoff** | none | **leaky, see §5** |
| `player_stats` / `stats_player_week` | week+team → kickoff (2025+ has `game_id`) | post-game | HTTP `Last-Modified` | fine — outcome data |
| `players` | `last_season`, `latest_team` are current-state | **absent** | HTTP `Last-Modified` | **mutable, no history** |

`VERIFIED` HTTP header evidence (`curl -sSI -L`), 2026-09-06:

| asset | `Last-Modified` | `Etag` |
|---|---|---|
| `schedules/games.csv` | Sun, 06 Sep 2026 18:16:21 GMT | `0x8DF0C42F3F4546D` |
| `players/players.csv` | Sun, 06 Sep 2026 11:54:34 GMT | `0x8DF0C0D9E937451` |
| `injuries/injuries_2025.csv` | Wed, 18 Mar 2026 12:45:31 GMT | `0x8DE84EC3DEC74F2` |
| `snap_counts/snap_counts_2025.csv` | Mon, 09 Feb 2026 13:39:50 GMT | `0x8DE67E0B31ED57B` |
| `depth_charts/depth_charts_2025.csv` | Sat, 14 Mar 2026 07:32:30 GMT | `0x8DE819BD9967446` |
| `depth_charts/depth_charts_2026.csv` | Sun, 06 Sep 2026 11:29:39 GMT | — |

`DERIVED`: `schedules/games.csv` and `players/players.csv` were rewritten
**today**. They are living files. Everything computed from them is stamped with
a version that no longer exists tomorrow unless we hash and keep it. That is the
M0 failure mode, one HTTP request away.

### 2.3 `ftn_charting.date_pulled` is an ingest clock, and it has been overwritten

`VERIFIED` — 48,031 rows joined to `schedules.gameday`, lag = `date_pulled` date
minus kickoff date, in days:

| statistic | value |
|---|---|
| min | **+2** |
| p25 | +3 |
| median | +7 |
| p75 | +330 |
| max | +361 |

| bucket | rows |
|---|---|
| before kickoff | **0** |
| 0–7 days after | 24,098 |
| 8–30 days after | 526 |
| 31–180 days after | 5,112 |
| **>180 days after** | **18,295** |

18 distinct `date_pulled` values; the single largest is
`2025-09-01T01:29:30.123782Z` carrying **18,295 rows (38.1%)** — a bulk re-pull
seven months after the Super Bowl. `DERIVED`: `date_pulled` is *our vendor's
last ETL touch*, not availability, and a later backfill **overwrote the original
pull timestamp for 38% of the season**. FTN is post-hoc charting; no FTN column
is available pre-kickoff, ever. It belongs in the outcome/analysis layer, never
in a pre-kickoff feature set.

### 2.4 `injuries` — independent confirmation and extension of the grounding finding

`VERIFIED`, `injuries_2024.csv`:

- 6,215 rows; **6,213 distinct `(season, week, gsis_id)`**; 6,213 distinct
  `(season, week, team, gsis_id)`. Confirms the grounding exactly.
- Week-1 `date_modified` by day: 2024-09-04 → 18, 2024-09-05 → 12,
  **2024-09-06 → 154**, 2024-09-07 → 22. Reproduces the grounding's figures
  cell for cell.

**Extension — `date_modified` relative to that team's kickoff, all 6,215 rows:**

| lag (days) | rows | share |
|---|---|---|
| −4 | 106 | 1.7% |
| −3 | 116 | 1.9% |
| **−2** | **5,475** | **88.1%** |
| −1 | 504 | 8.1% |
| 0 | 13 | 0.2% |
| +1 | 1 | 0.02% |

`date_modified` weekday (UTC): Fri 4,818 · Sat 509 · Wed 461 · Thu 351 · Tue 51
· Sun 22 · Mon 3.

`DERIVED`: the archive is a **final-report snapshot**, stamped Friday for a
Sunday game. The 222 rows at lag ≤ −3 are not early vintages of Sunday games;
they are the *final* reports for Thursday and Saturday games. There is no week
in which more than one vintage of a player's report survives. **The Wednesday
and Thursday practice-report cascade is not present in the historical archive
for any season.**

Per-week distinct `date_modified` days runs 3–7 per week — but those are
different *teams* reporting on their own schedules, not the same team reported
twice.

Two further Class A traps in this file (`VERIFIED`):

- `report_status` is **empty on 3,386 of 6,215 rows (54.5%)**. Values present:
  Questionable 1,513, Out 1,116, Doubtful 194, Note 6. An empty
  `report_status` means *on the practice report, no game-status designation* —
  a `NOT_APPLICABLE` with a reason, not a missing value and certainly not
  "healthy unknown". Coercing it to null or dropping the row throws away 54.5%
  of the file.
- `practice_status` contains the literal junk value `"\n    "` on **36 rows**,
  plus `"Note"` on 1. A naive categorical encoder produces a phantom level.
- There is **no `report_status` value for Injured Reserve and no inactive
  list**. Inactives live in `weekly_rosters.status` (§5), which is post-hoc.

### 2.5 `depth_charts` 2025+ is a genuine daily vintage series — the one good news

This overturns the pessimistic reading. `VERIFIED` by streaming the full
`depth_charts/depth_charts_2025.csv` (52,917,870 bytes) and counting:

| measure | value |
|---|---|
| rows | 554,215 |
| distinct `dt` snapshots | **221** |
| distinct snapshot **days** | **219** |
| first `dt` | `2025-08-03T10:09:07Z` |
| last `dt` | `2026-03-14T07:32:09Z` |
| rows per snapshot | min 2,095 · median 2,350 · max 3,264 |
| teams | 32 |
| distinct `gsis_id` | 2,986 |
| snapshot day-of-week | Sun 31 · Thu 32 · Fri 32 · Sat 31 · Mon 31 · Tue 31 · Wed 31 |

`DERIVED`: a snapshot on essentially **every calendar day**, at roughly 07:30
UTC, evenly spread across all seven weekdays. For 2025 onward, the *Tuesday
depth chart* and the *Friday depth chart* are both recoverable, retroactively,
for the whole season. The requirement "never overwrite Tuesday with Sunday" is
already satisfied by this one dataset and by no other.

**And it is already running for 2026.** `VERIFIED`:
`depth_charts/depth_charts_2026.csv` returns 200, 47,641,094 bytes,
`Last-Modified: Sun, 06 Sep 2026 11:29:39 GMT`; its newest row is
`dt = 2026-09-06T11:29:30Z` and its oldest visible row is
`dt = 2026-03-22T06:38:42Z` (file is sorted `dt` descending). So ~168 days of
2026 pre-season depth-chart vintages already exist, before Week 1 kicks off on
**2026-09-09**.

`VERIFIED`: `injuries/injuries_2026.csv` returns **404**. The 2026 injury file
does not exist yet, and when it does it will carry the 2025 schema — i.e. **no
`date_modified`**. Combined with §2.4, that means:

> For the 2026 season, injury-report vintages are recoverable **only by live
> capture**, starting now. Nothing in the archive will ever supply them, and
> unlike 2024 there will not even be a terminal timestamp.

That is the single most time-critical item in this report. See §6.

### 2.6 Kickoff instant precision

`VERIFIED`: `schedules.gametime` is populated on 285/285 games in 2024 and
272/272 in 2026, but there is **no timezone column**. `DERIVED` from a
cross-check: game `2024_01_ARI_BUF` has `schedules.gameday = 2024-09-08`,
`pbp.start_time = "9/8/24, 13:03:02"` and `pbp.time_of_day =
2024-09-08T17:03:02.957Z` — 13:03 local against 17:03 UTC, i.e. UTC−4, and the
2024 `gametime` distribution (13:00 ×136, 16:25 ×41, 16:05 ×26, 20:15 ×33,
09:30 ×4 for the London games) is consistent with **all times being US Eastern**,
not stadium-local. `UNVERIFIED-RECALL` that nflverse documents this as Eastern.
Consequence: an information cutoff expressed in hours-before-kickoff needs an
Eastern→UTC conversion including DST, and NFL-0 should store a derived
`kickoff_utc` in the schedule vintage rather than recompute it per use.

---

## 3. Schedule, sample size and the power ceiling

### 3.1 Games and weeks per season — measured, replacing the grounding's recall

`VERIFIED` from `schedules/games.csv`, 7,548 rows, seasons 1999–2026.
`game_type` counts across the whole file: REG 7,239 · WC 120 · DIV 108 · CON 54
· SB 27.

| season | REG games | REG weeks | POST games | total | clubs |
|---|---|---|---|---|---|
| 2015–2019 | 256 | 17 | 11 | 267 | 32 |
| 2020 | 256 | 17 | 13 | 269 | 32 |
| 2021 | **272** | **18** | 13 | 285 | 32 |
| 2022 | 271 *(one game cancelled)* | 18 | 13 | 284 | 32 |
| 2023 | 272 | 18 | 13 | 285 | 32 |
| 2024 | 272 | 18 | 13 | 285 | 32 |
| 2025 | 272 | 18 | 13 | 285 | 32 |
| 2026 | 272 (scheduled, 0 played) | 18 | 0 | 272 | 32 |

The grounding's `UNVERIFIED-RECALL` of "~272 regular-season games per season" is
**confirmed for 2021 onward**, and is wrong for 2020 and earlier (256).

Games per REG week, 2024 (`VERIFIED`): 13–16, with bye weeks compressing weeks
5–14. Full 2024 vector: 16,16,16,16,14,14,15,16,15,14,14,13,16,13,16,16,16,16.

2026 status (`VERIFIED`): 272 rows, **0 with a score**, gameday range
2026-09-09 → 2027-01-10; Week 1 dates 2026-09-09, 09-10, 09-13, 09-14; Week 2
dates 2026-09-17, 09-20, 09-21.

### 3.2 Player-games per week

`VERIFIED`, 2024 REG only (272 games, 25,398 `snap_counts` rows):

| population | total | per REG week | per game |
|---|---|---|---|
| any offensive snap | 10,056 | 559 | 37.0 |
| skill positions (QB/RB/WR/TE/FB) with ≥1 offensive snap | 6,624 | mean 368 (min 316, median 384, max 400) | mean 24.4 (min 20, median 24, max 29) |
| skill positions with ≥10 offensive snaps | 5,414 | 301 | 19.9 |

From `player_stats` 2024 REG (5,340 rows): ≥1 target 4,255 · **≥3 targets
2,509 (139 per week)** · ≥1 carry 2,254 · ≥1 pass attempt 664.

`DERIVED`: a realistic weekly NFL prop universe is on the order of **130–300
player-games**, clustered into **13–16 games**. The cluster count per week is
therefore in the low teens — exactly the regime `CLAUDE.md`'s pending
methodology fix #1 says to suppress precision beyond two significant figures.

### 3.3 Power — computed here, with a correction to the grounding

Fisher-z two-sided test, α = 0.05, power = 0.80,
n = ((z₀.₉₇₅ + z₀.₈₀)/(z(r₂) − z(r₁)))² + 3. `DERIVED`, arithmetic shown:

| effect | z(r₁) | z(r₂) | n independent | NFL REG seasons @272 |
|---|---|---|---|---|
| r 0.11 → 0.30 | 0.1104 | 0.3095 | **202** | 0.74 |
| r 0.11 → **0.25** | 0.1104 | 0.2554 | **377** | **1.39** |
| r 0.11 → 0.20 | 0.1104 | 0.2027 | **925** | 3.40 |
| r 0.11 → 0.15 | 0.1104 | 0.1511 | **4,743** | 17.44 |

This reproduces the grounding's 377 exactly.

**Correction the lead should adopt.** The grounding writes "~1,131 with the
threefold clustering measured on MLB", i.e. 377 × 3. The MLB figures in
`CLAUDE.md` are **standard errors**: naive 0.587pp, clustered by player-game
1.359pp, clustered by game 1.653pp. Those are SE ratios of 2.315 and 2.816.
Required sample scales with the **design effect**, which is the *variance*
ratio — the SE ratio **squared**:

| assumption | design effect | n required | NFL REG seasons | NFL REG weeks |
|---|---|---|---|---|
| independent | 1.00 | 377 | 1.39 | 25 |
| grounding's "threefold" read as an n-multiplier | 3.00 | 1,131 | 4.16 | 75 |
| DEFF from MLB player-game SE ratio (2.315²) | 5.36 | 2,021 | 7.43 | 134 |
| DEFF from MLB game SE ratio (2.816²) | **7.93** | **2,990** | **10.99** | 198 |

`DERIVED`, and the distinction that resolves it: **the design effect applies to
player-prop-level analyses, not to a game-level correlation.** For a game-level
metric there is one prediction per game, so clustering by game is the identity
and DEFF = 1; the binding number for a game-total r is **377 games ≈ 1.4 NFL
seasons**. For a player-prop hit-rate, where dozens of markets share a
player-game and a game, the DEFF is real and the honest planning number is
**2,000–3,000 game-equivalents, i.e. 7–11 NFL seasons**, not 1,131.

`DERIVED` conclusion, and it should be stated plainly in any NFL work order:

> A confirmatory NFL game-level claim at the r 0.11 → 0.25 effect size needs
> roughly **one and a half seasons of untouched games**. A confirmatory
> player-prop claim at the same effect size needs **most of a decade**, or a
> materially larger effect, or a metric with lower variance than a hit rate.
> Forward-chained live capture beginning 2026 Week 1 accumulates 272 games per
> year. There is no configuration of NFL data in which a player-prop
> confirmatory result arrives quickly.

`DERIVED` corollary: the 2016–2025 archive holds roughly
256×5 + 256 + 272 + 271 + 272 + 272 + 272 = **2,895 REG games** (2016–2025,
`VERIFIED` per-season counts above). That is enough for a game-level
confirmatory design *if and only if* the holdout is genuinely untouched — which
is a governance problem (Rule 006), not a data problem.

---

## 4. Immutable vintages — proposed storage design

The requirement this design exists to satisfy: `CLAUDE.md` records that M0
became irreproducible because the consumed corpus was never hashed or
committed, and that `SIM_FORMULA` excluded `corpus.py`, so the fingerprint
`FP-ab18309e17e7e16e` stayed identical while the inputs changed. §2.2 above
shows the same trap is already live for NFL: `schedules/games.csv` and
`players/players.csv` were both rewritten today.

### 4.1 What must be snapshotted, and at what cadence

| tier | datasets | cadence | why |
|---|---|---|---|
| **T0 — live-only, unrecoverable if missed** | `injuries/injuries_YYYY.csv`; any live injury/practice-report feed; any pre-kickoff inactive list | **daily, Tue–Sun, in season** | §2.4/§2.5: 2025+ carries no timestamp at all. Every uncaptured day is permanently gone. |
| **T1 — mutable current-state files** | `schedules/games.csv`, `players/players.csv`, `rosters/roster_YYYY.csv`, `weekly_rosters/roster_weekly_YYYY.csv` | **daily** in season, weekly out | Rewritten in place with no history; `schedules` accumulates market lines (§5). |
| **T2 — vendor-timestamped, self-vintaging** | `depth_charts/depth_charts_YYYY.csv` (2025+) | **weekly is sufficient** | The file carries `dt`; late capture still yields all past snapshots. |
| **T3 — post-game outcome data** | `pbp`, `pbp_participation`, `snap_counts`, `ftn_charting`, `stats_player_week`, `pfr_advstats` | **weekly, Tue morning** | Immutable in substance once a game is played; still re-issued (backfills, §2.3), so hash each capture. |
| **T4 — static reference** | `combine`, `officials`, `contracts`, franchise-continuity table (**hand-built, see §1.5**) | **on change** | small |

### 4.2 Storage layout

```
nfl/vintages/
  <dataset>/<capture_utc:YYYY-MM-DDTHHMMSSZ>/
      payload.csv.gz          # bytes exactly as received, gzip only
      manifest.json           # see 4.3
  _index/
      <dataset>.jsonl         # one line per capture, append-only, never rewritten
      content/<sha256>.json   # content-addressed: dedupes an unchanged re-fetch
```

Keyed by `(dataset, capture_utc)`. Content-addressed by `sha256` of the raw
bytes, so a daily re-fetch of an unchanged `players.csv` costs one index line
and zero payload bytes — `VERIFIED` that this dedupes in practice: two workers
in this session independently downloaded `schedules/games.csv` under different
filenames and both hashed to `5fd04e27b065aff16d62ddcd6b69334bd73fc34db8ca186b47dc2ba6515c51de`.

### 4.3 `manifest.json` — the content-addressed input manifest

Every field below is either measured at capture or is a `FAIL`. No field is
optional and no field defaults.

```
{
  "dataset":          "injuries_2026",
  "release_path":     "injuries/injuries_2026.csv",
  "url":              "https://github.com/nflverse/nflverse-data/releases/download/...",
  "sha256":           "<of raw bytes>",
  "bytes":            816989,
  "http_status":      200,
  "http_last_modified": "Wed, 18 Mar 2026 12:45:31 GMT",
  "http_etag":        "0x8DE84EC3DEC74F2",

  "source_timestamp":   "<from http_last_modified>",
  "retrieved_at":       "<clock at first byte>",
  "available_time":     "<earliest instant this content was knowable, or FAIL>",
  "generated_at":       "<manifest write time>",
  "effective_for_date": "<the slate date this may be used for>",

  "schema_version":   "sha256(sorted(column_names))",
  "n_columns":        16,
  "column_names":     [...],
  "n_rows":           6215,
  "row_key":          ["season","week","team","gsis_id"],
  "n_distinct_row_key": 6213,
  "duplicate_row_keys": 2,

  "capture_state":    "PASS | FAIL | BLOCKED | DEFERRED | NOT_APPLICABLE",
  "capture_code":     "OK | RELEASE_PATH_404 | SCHEMA_VERSION_CHANGED | ZERO_ROWS | ...",
  "prior_capture_sha256": "<or null>",
  "changed_vs_prior": true
}
```

Five design commitments, each traceable to a measured defect above:

1. **`schema_version` is a hash of the sorted column list, never a count.**
   §1.6: `injuries` 2024 and 2025 both have 16 columns and different columns.
2. **`n_rows == 0` is `FAIL: ZERO_ROWS`, never `PASS` with an empty frame.**
   Rule 001; `CLAUDE.md` rule 7.
3. **A 404 is `FAIL: RELEASE_PATH_404` naming the path**, never a skipped
   season. §1.6: `player_stats/player_stats_2025.csv` is a live 404.
4. **`available_time` is mandatory and is allowed to be `FAIL`.** For every
   nflverse file it *is* a `FAIL` unless we captured it ourselves — that is the
   honest record, and it is what makes an archive-derived backtest declarable as
   what it is.
5. **The model fingerprint must include the manifest sha256 set**, not just
   code. This is the direct fix for `SIM_FORMULA` excluding `corpus.py`. Define
   `NFL_INPUT_FINGERPRINT = sha256(sorted(manifest.sha256 for every input
   consumed))` and make it a required component of any run identity. A run that
   consumed a different `players.csv` must not be able to produce the same
   fingerprint.

### 4.4 The weekly information cascade — what a capture week looks like

For a Sunday slate at kickoff K, capture at each of these and store as separate
vintages, never overwriting:

| vintage | when | what changes |
|---|---|---|
| `T-5 Tue` | Tue ~12:00 UTC | first depth chart of the week; transactions |
| `T-4 Wed` | Wed ~12:00 UTC | **first practice report** — the vintage the archive destroys |
| `T-3 Thu` | Thu ~12:00 UTC | second practice report |
| `T-2 Fri` | Fri ~20:00 UTC | **final game-status report** — the only vintage the 2024 archive kept (88.1% of rows, §2.4) |
| `T-1 Sat` | Sat ~18:00 UTC | Saturday elevations, weather |
| `T-90m` | K − 90 min | **inactives** — the first moment `weekly_rosters.status = INA` is knowable |
| `T+` | Tue after | outcome tier (T3) |

`DERIVED`: any prediction declared at the Friday vintage must be scored against
outcomes without ever reading the `T-90m` vintage, and the `T-90m` vintage is
what `weekly_rosters` retroactively encodes (§5). Keeping them as separate,
separately-hashed vintages is what makes that enforceable rather than aspirational.

---

## 5. Leakage inventory

Relative to a prediction declared **before kickoff** of game G.

### 5.1 Market-derived — quarantine at ingest, per grounding and `CLAUDE.md` rule 1

| dataset | columns | measured facts |
|---|---|---|
| `pbp` | `spread_line`, `total_line`, `vegas_wp`, `vegas_home_wp`, `vegas_wpa`, `vegas_home_wpa` | `VERIFIED`: 6 of 372. `spread_line`/`total_line` are **constant within every one of the 285 games** and **identical to the `schedules` values for all 285 games** (0 mismatches). |
| `schedules` | `away_moneyline`, `home_moneyline`, `spread_line`, `away_spread_odds`, `home_spread_odds`, `total_line`, `under_odds`, `over_odds` | `VERIFIED`: 8 columns, 285/285 populated for 2024 — **and 112/272 already populated for the unplayed 2026 season.** |

`DERIVED` and important: quarantining `schedules` alone is insufficient. The
same market numbers are stamped onto **every one of the 49,492 `pbp` rows**. A
feature builder that "only reads pbp" ingests the closing line 49,492 times.
Quarantine must be a column-level deny-list applied at ingest to *both* files,
enforced by a test that fails if a quarantined name appears in any feature
frame.

`DERIVED`: the 2026 market columns being live *now* also means the `schedules`
file is a **market feed with a schedule attached**. It is T1 (daily capture) for
exactly that reason, and if the project ever wants a genuine opening-vs-closing
line comparison, capturing `schedules` daily from today is how it gets one —
subject to Rule 1, as a *comparison*, never as an input.

### 5.2 Outcome-derived: future information about game G itself

`VERIFIED` unless noted.

| dataset | field(s) | why it leaks |
|---|---|---|
| `schedules` | `away_score`, `home_score`, `result`, `total`, `overtime` | the outcome |
| `schedules` | `away_qb_id`, `home_qb_id`, `away_qb_name`, `home_qb_name` | **285/285 populated for 2024, 0/272 for 2026.** These are the QBs who *did* start. Post-hoc. The single most seductive leak in the file: it looks like a matchup field. |
| `schedules` | `referee` | 285/285 for 2024, **0/272 for 2026** — assigned/published late. Post-hoc in the archive. |
| `schedules` | `temp`, `wind` | 182/285 for 2024, **0/272 for 2026** — these are *observed* game-time conditions, not a forecast. |
| `schedules` | `gsis`, `nfl_detail_id`, `pff`, `ftn` id columns | 2024: `gsis` 285/285, `ftn` 272/285; 2026: all 0. Their mere presence discloses that the game was played. |
| `pbp` | `away_score`, `home_score`, `result`, `total` | game-final, **constant on every row** — `VERIFIED`, 0 of 285 games vary within pbp |
| `pbp` | 28 `total_home_*` / `total_away_*` columns | within-game cumulative; fine for in-game work, leakage for pre-game |
| `weekly_rosters` | **`status`** | `VERIFIED`: ACT 27,369 · DEV 8,722 · RES 5,426 · **INA 3,611** · CUT 1,028 · RET 398 · EXE 13 · TRC 6 · TRD 5 · E01 1. `INA` = inactive, which is knowable only ~90 minutes before kickoff (`UNVERIFIED-RECALL` for the exact 90-minute rule; the *direction* — after any Friday prediction — is certain). The file carries **no timestamp column at all**, so nothing distinguishes a Tuesday `RES` from a Sunday `INA`. |
| `snap_counts` | every numeric column | the game was played |
| `ftn_charting` | every column | §2.3: min lag +2 days after kickoff, 0 rows pre-kickoff |
| `player_stats` / `stats_player_week` | every stat column | the game was played |

### 5.3 Model-derived columns — leakage by model fit

`VERIFIED`: 31 columns in `pbp` are outputs of fitted models —
`no_score_prob`, `opp_fg_prob`, `opp_safety_prob`, `opp_td_prob`, `fg_prob`,
`safety_prob`, `td_prob`, `extra_point_prob`, `two_point_conversion_prob`,
`ep`, `epa`, `air_epa`, `yac_epa`, `comp_air_epa`, `comp_yac_epa`, `wp`,
`def_wp`, `home_wp`, `away_wp`, `wpa`, `cp`, `cpoe`, `success`, `qb_epa`,
`xyac_epa`, `xyac_mean_yardage`, `xyac_median_yardage`, `xyac_success`,
`xyac_fd`, `xpass`, `pass_oe`. Downstream, `player_stats` carries
`passing_epa`, `rushing_epa`, `receiving_epa`, `dakota`, `pacr`, `racr`.

`UNVERIFIED-RECALL`: nflverse fits these EP/WP/CP/xYAC/xPass models on
multi-season data and applies them to all seasons, including seasons in the
training range. **Needs confirmation** — but the design consequence does not
depend on resolving it: a feature whose *fitting data* includes the future is a
Rule 003 violation even when its *input row* does not. `DERIVED` treatment: all
31 are `EXPERIMENTAL` at best, and none may be promoted above that without an
experiment that either establishes the fit window or refits within the
forward-chained fold.

Note that `vegas_wp` / `vegas_wpa` / `vegas_home_wp` are **both** market-derived
and model-derived — they are win-probability models with the closing spread as
an input. They fail two rules at once.

### 5.4 Season-to-date and aggregate hazards

- `players.csv`: `last_season`, `latest_team`, `status`, `ngs_status`,
  `years_of_experience` are **current-state as of the file's `Last-Modified`**
  (today, §2.2), not as-of any historical week. `DERIVED`: joining
  `players.latest_team` into a 2024 feature frame imports 2026 knowledge. Only
  the immutable identity columns (`gsis_id`, `pfr_id`, `birth_date`,
  `draft_year`, `draft_round`, `draft_pick`, `college_name`) are safe as
  time-invariant; everything else must come from the week's roster vintage.
- `player_stats` / `stats_player_week`: `target_share`, `air_yards_share`,
  `wopr`, `pacr`, `racr` are within-week ratios (`DERIVED` from the file being
  one row per player-week — `VERIFIED`: 0 duplicates on `(week, player_id)`),
  so they are not themselves season-to-date. But **any rolling aggregate the
  project builds from them is a Rule 003 surface**, and Rule 003's text is
  explicit that season-to-date leaderboards have no date bound.
- `depth_charts` 2024: no timestamp, so a week-W depth chart cannot be shown to
  predate week W's games. `DERIVED`: 2024-and-earlier depth charts are
  **unusable as pre-kickoff features** and usable only as descriptive context.
  2025+ is fine because `dt` bounds it (§2.5).

### 5.5 The `NOT_APPLICABLE` vs missing distinction, measured

`VERIFIED`, `schedules` 2024, cross-tabulating `roof` against blank `temp`:

| roof | temp blank | temp present |
|---|---|---|
| `dome` | **53** | 0 |
| `closed` | **45** | 0 |
| `outdoors` | **5** | 182 |

`DERIVED`: 98 blanks are `NOT_APPLICABLE` with the reason "indoor venue"; **5
are genuinely `FAIL: MISSING`**. Any imputation that fills all 103 with a league
mean has invented weather for 98 domes and hidden 5 real gaps. This is the
smallest clean example in the whole dataset of why Rule 001 needs five states
and not a null.

---

## 6. Assigned to the networked agent (DEC-029 — *not blocked, assigned*)

`docs/AGENT_PROTOCOL.md:72-75` — "not blocked because one agent cannot do it. If
the other agent can, it is assigned, and the request goes in
`docs/AGENT_OUTBOX.md` with exact dates, identifiers, or endpoints."

**Nothing in nflverse is blocked for me.** `raw.githubusercontent.com` and
`github.com/<owner>/<repo>/releases/download/...` return 200 from this
container, and I read every file in §0 directly. The items below are genuinely
outside my reach, and each names the exact endpoint, date and identifier.

I have **not** written to `docs/AGENT_OUTBOX.md` — that is a shared file and my
brief says modify no other file. **Lead: these need to be transcribed into
`docs/AGENT_OUTBOX.md`, and A1 needs to be started before 2026-09-09.**

| # | request | exact specification | why it cannot be done here | urgency |
|---|---|---|---|---|
| **A1** | **Daily NFL injury-report capture, starting immediately** | Capture the league injury/practice report **every day Tue–Sun** from **2026-09-08** onward, stamping each capture with `retrieved_at` and keeping every vintage. Minimum: the NFL's official weekly injury report per club. If a live endpoint is unavailable, capture `https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv` daily (currently **404**, first publication expected on or after 2026-09-09) and keep every distinct sha256 as a separate vintage. | Requires a persistent daily scheduler and, for the official feed, general web egress — both outside this container. | **CRITICAL — every day not captured from 2026-09-08 is permanently lost (§2.4, §2.5).** |
| **A2** | Sunday inactives capture | For each 2026 game, capture the official inactive list at kickoff − 90 min, keyed `(game_id, gsis_id)`, stamped `retrieved_at`. Starting Week 1, 2026-09-09. | Same as A1; also needs a per-game timer, not a daily one. | High — this is the only honest `available_time` for `weekly_rosters.status = INA` (§5.2). |
| **A3** | Confirm nflverse model fit windows | Determine, from nflverse-pbp / nfl4th / nflfastR source or maintainer documentation, the **training seasons** used for `ep`, `wp`, `cp`, `xyac_*`, `xpass`. Cite the source. | Requires reading repos outside `nflverse/nflverse-data` releases; general web egress is 403 here. | Medium — resolves whether the 31 columns in §5.3 are usable at all. |
| **A4** | Confirm `schedules.gametime` timezone | Confirm from nflverse documentation that `gametime` is US Eastern for all games including international ones. | Documentation is outside the release assets. | Medium — §2.6; affects every cutoff computation. |
| **A5** | Franchise-continuity table | Provide or confirm an authoritative mapping for `OAK→LV` (2020), `SD→LAC` (2017), `STL→LA` (2016), and confirm `LA` vs `LAR` usage across nflverse datasets. | Needs a source of record beyond what the release CSVs assert. | Medium — §1.5; blocks any multi-season join. |
| **A6** | Six unmapped PFR ids | Resolve `pfr_player_id` → `gsis_id` for the 6 players in §1.4 (Alec Anderson, Bill Murray, John Samuel Shenker, Bump Cooper, Cody White, Rodney Williams — 2024 snap counts, teams BUF/CHI/LV/BAL/SEA/PIT). Note **Cody White is ambiguous** (two `players.csv` rows) and **Rodney Williams name-collides with a 2001 player**; a name match is not an answer. | Needs pro-football-reference.com, which returns 403 here. | Low — 42 of 26,615 rows, but it is the template for the recurring case. |
| **A7** | Hard Rock Bet NFL market inventory | Which NFL markets Hard Rock Bet offers, and at what times they open relative to kickoff. No prices needed for this pass. | Live odds connector is theirs by `docs/AGENT_PROTOCOL.md:79-82`. | Low for NFL-0 — but it bounds what §3.3's power calculation is ever *for*. |

---

## 7. Summary of what a lead can act on

1. **Identity is in better shape than MLB's was.** One crosswalk file
   (`players.csv`) resolves the single namespace split (`snap_counts` uses
   `pfr_player_id`); the join measures **99.84%**, team codes are perfectly
   consistent within a season, and the two play-level joins are **100.000%**.
   The residual 0.16% must be a named `FAIL`, not a name-match fallback (§1.4).
2. **The clocks are the real problem, and they are worse in 2025+ than 2024.**
   `injuries` lost `date_modified` entirely. `depth_charts` gained a genuine
   daily snapshot series. `ftn_charting`'s `date_pulled` was overwritten for 38%
   of 2024 by a post-season backfill. `weekly_rosters` has no clock and encodes
   inactives.
3. **The clock capture window opens on 2026-09-08 and never reopens.** Week 1 is
   2026-09-09. `injuries_2026.csv` is a 404 today and will carry no timestamp
   when it appears. Item A1 is the only irreversible item in this report.
4. **Schema drift is live, not hypothetical.** Three datasets changed between
   2024 and 2025, one of them with an unchanged column *count*. Pin a hashed
   column set, not a count.
5. **Market data is inside a "neutral" source, twice.** `schedules` carries 8
   market columns (already populated for 112 unplayed 2026 games) and `pbp`
   restamps 2 of them on all 49,492 rows.
6. **Power is the binding constraint and the grounding understates it for
   props.** Game-level: 377 games ≈ 1.4 seasons. Player-prop-level, using the
   MLB-measured SE ratios as *variance* inflation: 2,000–3,000 game-equivalents
   ≈ 7–11 seasons.

# Integration feasibility audit: DraftKings, Fantasy Cruncher, NFL data providers (2026-10-09)

**Question.** For each service, is there an authorised API, an official export, scheduled delivery, or a permitted
authenticated integration? Then: build the parts that are allowed, so the weekly copy-and-paste goes away without
weakening account security, data rights or reproducibility.

**Scope.** This system does read-only research and reads the owner's own exported files. Logging in, entering or
editing contests, uploading lineups, wagering, deposits and withdrawals are the owner's, by hand, on the platform.
None of them is built, and the matrix marks each one `NOT_TO_BE_BUILT`. No credential is stored, requested or used.

**Evidence quality.** The terms research is in `nfl/research/integrations/PLATFORM_TERMS_AND_APIS.{json,md}`.
- 29 items are **PRIMARY**: read directly, mostly the nflverse repositories and GitHub pages.
- 77 items are **SNIPPET_ONLY**. DraftKings, NFL.com, ESPN and the other vendor pages could not be opened from this
  executor, so their terms were seen only as search-result text.
- A SNIPPET_ONLY clause is a lead, not a finding. Check it against the live page before relying on it.
- This is not legal advice.

## The answer, per service

| Service | Authorised API | Official export | Scheduled delivery | Permitted authenticated integration | Verdict |
|---|---|---|---|---|---|
| **DraftKings** | None. The draftables and contest JSON endpoints are undocumented. | Yes, manual: salary CSV, entries CSV, contest standings CSV | No | No (partners only) | **Manual export only.** The terms bar "automated means (including ... scripts and third-party tools)". |
| **Fantasy Cruncher** | None | Yes, manual CSV | No | No | **Manual export only.** The terms bar robots and scrapers; personal, non-commercial use. |
| **nflverse** (schedules, rosters, depth charts, injuries, pbp, stats, snap counts) | Yes: public GitHub release files | Yes | Yes. The publisher refreshes on a cron (injuries, rosters and depth charts daily at 07:00 UTC; schedules every 5 min; pbp nightly). | Not needed | **Fully automatable.** The data stay governed by their upstream owners' terms (NFL, ESPN, PFR), so use them for personal research and do not redistribute. |
| **NFL.com** (injury report, inactives pages) | No public API. Official data are licensed exclusively through Genius Sports. | Web pages only | Licensed only | Licensed only | **Automated retrieval appears prohibited** (snippet: "systematic retrieval ... database ... prohibited absent express prior written consent"). This is **running today**: see OD-1. |
| **ESPN** | Undocumented only | No | No | No | **Prohibited** under Disney's terms. **Running today**: see OD-2. |
| **Sportradar / SportsDataIO / Genius Sports** | Yes, paid | Paid | Paid | Paid | **Approved provider connection.** SportsDataIO is the only source found that sells DK slate salaries. |

## The integration matrix

Generated from `nfl/integrations/matrix.py`, which the status page and the tests also read, so this table cannot drift
from the code.

### Fully Automated (8)

| Id | Capability | Provider and route | Action | Built | Terms evidence | Notes |
|---|---|---|---|---|---|---|
| I01 | Schedule and kickoff times | nflverse: GitHub release schedules file | READ_ONLY_RESEARCH | RUNNING | PRIMARY | Captured by .github/workflows/nfl-capture.yml to branch capture-prod. |
| I02 | Weekly rosters (status ACT/RES/DEV) | nflverse: GitHub release weekly roster file | READ_ONLY_RESEARCH | PARTIAL | PRIMARY | Captured, but the committed blob is REDUCED to season/week/team/gsis_id/position: it drops `status` and names, which the research universe needs. The universe is still built from a manual full-file slice. Gap INT-G1. |
| I03 | Depth charts | nflverse (ESPN-sourced since 2025): GitHub release depth chart file | READ_ONLY_RESEARCH | RUNNING | PRIMARY | nflverse changed source from NFL Data Exchange to ESPN in 2025. nflverse states the data belong to their owners and are governed by their terms: fine for personal research, not for redistribution. |
| I04 | Injury report (practice participation, game designation) | nflverse: GitHub release injuries file | READ_ONLY_RESEARCH | RUNNING | PRIMARY | LATENCY: the Friday afternoon designations (about 20:00 UTC) reach nflverse no earlier than the Saturday 07:00 UTC refresh. |
| I08 | Transactions (signings, IR, elevations) | nflverse rosters (derived): difference between consecutive weekly-roster captures | READ_ONLY_RESEARCH | NOT_BUILT | PRIMARY | The registered official_transactions endpoint is BLOCKED (ENDPOINT_NOT_YET_VERIFIED). Practice-squad elevations are not in any free feed before kickoff. Needs I02 to keep `status` (INT-G1). |
| I09 | Play-by-play and player game stats | nflverse (NFL GSIS): GitHub release pbp and player-stats | READ_ONLY_RESEARCH | PARTIAL | PRIMARY | Not on the capture schedule: the manifest's last pbp capture is 2026-09-17; the W5 files were fetched by hand on 2026-10-07. Gap INT-G2. |
| I10 | Snap counts | nflverse (Pro Football Reference-sourced): GitHub release snap counts | READ_ONLY_RESEARCH | PARTIAL | PRIMARY | Watch-only in the capture (NOT_APPLICABLE). PFR's own terms restrict tools built on scraped data; reading nflverse's published file for personal research is the supported route. |
| H02 | Postgame player grading | nflverse: player stats file (I09) | READ_ONLY_RESEARCH | PARTIAL | PRIMARY | Grading code exists; scheduled capture of the stats file is gap INT-G2. |

### Approved Provider Connection (4)

| Id | Capability | Provider and route | Action | Built | Terms evidence | Notes |
|---|---|---|---|---|---|---|
| D02 | DK player ids and salaries (licensed) | SportsDataIO: DFS slates API (DK, FD, Yahoo salaries) | READ_ONLY_RESEARCH | NOT_BUILT | SNIPPET_ONLY | The only licensed source found that sells DK slate salaries. Paid; trial data are scrambled and cannot be used for analysis. **Owner decision OD-3.** |
| I20 | Official real-time data | Genius Sports (NFL exclusive distributor): B2B licence | READ_ONLY_RESEARCH | NOT_BUILT | SNIPPET_ONLY | Exclusive distributor of official NFL data through 2029; media and betting operators only. **Owner decision OD-3.** |
| I21 | Injuries, depth charts, rosters (licensed) | Sportradar: NFL API v7 | READ_ONLY_RESEARCH | NOT_BUILT | SNIPPET_ONLY | Paid. The 30-day trial is "for internal testing and evaluation purposes only". **Owner decision OD-3.** |
| I22 | Injuries, depth charts, inactives (licensed) | SportsDataIO: NFL API | READ_ONLY_RESEARCH | NOT_BUILT | SNIPPET_ONLY | Paid; redistribution prohibited without consent. **Owner decision OD-3.** |

### Manual Export (4)

| Id | Capability | Provider and route | Action | Built | Terms evidence | Notes |
|---|---|---|---|---|---|---|
| D01 | DK player ids and salaries | DraftKings: DKSalaries.csv downloaded from the contest lobby | READ_ONLY_RESEARCH | BUILT | SNIPPET_ONLY | Drop the file in nfl/dfs/inbox/drop/; it is recognised by its header, hashed and stored. The football projection does not wait for it (research universe). |
| D04 | Owner's entries (entry ids, contests, fees) | DraftKings: DKEntries.csv download | ACCOUNT_DATA_READ | BUILT | SNIPPET_ONLY | ACCOUNT_PRIVATE. Read only. This system never edits, uploads or submits entries. |
| F01 | FC projections (benchmark only) | Fantasy Cruncher: players CSV export from the FC UI | READ_ONLY_RESEARCH | BUILT | SNIPPET_ONLY | Context only, NEVER a model input. FC terms: personal non-commercial use; no scraping. No API. |
| H01 | Contest standings and realised ownership | DraftKings: contest standings CSV export after the contest is final | READ_ONLY_RESEARCH | BUILT | SNIPPET_ONLY | POSTLOCK ONLY. Contains other users' names (stored, never published). Realised ownership is never treated as available before lock. Loader: nfl/field/contest_ownership.py. |

### Prohibited Or Unsupported (11)

| Id | Capability | Provider and route | Action | Built | Terms evidence | Notes |
|---|---|---|---|---|---|---|
| I05 | Official injury report page | NFL.com: scheduled fetch of nfl.com/injuries/ | READ_ONLY_RESEARCH | RUNNING | SNIPPET_ONLY | CURRENTLY AUTOMATED and terms-risky: NFL.com terms (search text only) bar "systematic retrieval of data ... to create or compile a collection ... database" without written consent. Lawful alternatives: nflverse injuries (I04, slower), a licensed feed (I20-I22), or the owner relaying what he reads (sunday_paste.py). **Owner decision OD-1.** |
| I06 | Official game-day inactives | NFL.com: scheduled fetch of nfl.com/inactives/ | READ_ONLY_RESEARCH | RUNNING | SNIPPET_ONLY | Same terms as I05. Has never yielded rows in the W5 week (SOURCE_HAS_NO_ROWS_YET). nflverse carries no pregame inactives. Lawful alternatives: licensed feed, or owner relay through sunday_paste.py (tier OWNER_RELAYED, never relabelled OFFICIAL_CAPTURED). **Owner decision OD-1.** |
| I07 | ESPN injuries JSON | ESPN (undocumented API): scheduled fetch of site.api.espn.com | READ_ONLY_RESEARCH | RUNNING | SNIPPET_ONLY | Undocumented API under Disney terms that bar automated retrieval and scraping. It discharges NO target in the registry (serves_kinds empty), so stopping it loses nothing the forecast uses. **Owner decision OD-2.** |
| I11 | Route participation / charting | nflverse (FTN, CC-BY-SA): participation file | READ_ONLY_RESEARCH | NOT_BUILT | PRIMARY | UNSUPPORTED IN SEASON at no cost: free participation data arrives only after the season. In-season routes need a licensed provider (FTN, PFF). Route participation stays UNKNOWN, never inferred. |
| D03 | DK draftables / contest JSON endpoints | DraftKings (undocumented): scripted HTTP | READ_ONLY_RESEARCH | NOT_TO_BE_BUILT | SNIPPET_ONLY | DK terms bar "automated means (including ... scripts and third-party tools) to interact with the Website in any way". Not built. |
| D05 | Lineup upload, edit, late swap | DraftKings: CSV upload or editing in the DK client | CONTEST_ENTRY | NOT_TO_BE_BUILT | SNIPPET_ONLY | Owner only, by hand. Automation is prohibited by DK terms and by the owner's standing rule. |
| D06 | Contest entry, deposits, withdrawals | DraftKings: account | FINANCIAL | NOT_TO_BE_BUILT | SNIPPET_ONLY | Never automated; out of this system's scope. |
| D07 | Login, session, credentials | DraftKings / Fantasy Cruncher: any | ACCOUNT_ACTION | NOT_TO_BE_BUILT | SNIPPET_ONLY | No credential is stored, requested or used. Credentials pasted into a conversation are never used. |
| F02 | FC automated pull | Fantasy Cruncher: scripted login or scraping | ACCOUNT_ACTION | NOT_TO_BE_BUILT | SNIPPET_ONLY | FC terms bar "any robot, spider, scraper or other automated means". Not built. |
| I23 | News | RotoWire: free RSS feeds | READ_ONLY_RESEARCH | NOT_BUILT | UNKNOWN | Terms for automated reading of the RSS feeds were not found. Until they are, news stays a discovery signal gathered by the network-holding agent, never confirmation. |
| W01 | Sportsbook prices and bets | Hard Rock Bet: any | WAGERING | NOT_TO_BE_BUILT | UNKNOWN | No sportsbook price enters an NFL prediction, and this system never places or recommends a wager. |

## What was built today (read-only; 40 checks in `nfl/tests/test_integrations.py`)

**1. Drop folder: `nfl/integrations/inbox.py` (priorities 2, 3, 6)**
- **What you do.** Download DKSalaries.csv, DKEntries.csv, a contest-standings CSV or a Fantasy Cruncher export, and
  drop it in `nfl/dfs/inbox/drop/` under any name.
- **What happens.** Each file is recognised by its own columns, never its name:
  - stored by content hash in `nfl/dfs/inbox/store/`;
  - recorded in `nfl/dfs/inbox/INBOX_LEDGER.jsonl` with role, privacy and prelock labels.
- **The labels:**
  - Fantasy Cruncher: `never_model_input`.
  - Contest standings: `available_prelock: false`. Realised ownership is never treated as known before lock.
  - Entries: `ACCOUNT_PRIVATE`.
- **Refusals are named and stay visible on the status page:**
  - `INBOX_UNRECOGNISED_HEADER`, `INBOX_EMPTY_FILE`, `INBOX_NOT_UTF8`;
  - `INBOX_DUPLICATE_DK_ID`, `INBOX_DK_POOL_EMPTY`;
  - `INBOX_STANDINGS_OWNERSHIP_UNPARSEABLE`, refused whole, because a player who drops out would read as zero-owned.
- **What it never does.** It never edits or deletes the dropped file. Re-dropping the same bytes changes nothing.

**2. Monitor: `nfl/integrations/monitor.py` (priorities 4, 7)**
- **Reads:** the capture manifest, the inbox ledger and the reference build.
- **Writes:** `nfl/integrations/status/INTEGRATION_STATUS_<slate>.{json,html}`.
- **Connection status.** Read from the newest success. A no-network attempt from this executor does not mark a source
  disconnected, but it is still shown.
- **Freshness.** Measured against each publisher's refresh interval.
- **Missing information**, for example the Friday designations not yet in the captured file.
- **Missing players.** UNKNOWN until a DK salary file arrives, then a name-plus-club comparison.
- **QB watch, per club:**
  - the projected QB1;
  - the newest chart's QB1 and QB2;
  - the QB injury lines;
  - flags.

**3. Rebuild on verified change: `nfl/integrations/rebuild.py` (priority 5)**
- **Plan.** Compares what a build made now would consume against what the reference build actually consumed:
  - depth chart bytes;
  - lawful injury captures;
  - inactives;
  - raw files;
  - the DK pool.
- **What counts as a change.** A recapture with unchanged content is not a change. Anything that cannot be compared is
  `UNCOMPARABLE`, never "unchanged".
- **Execute.** Builds into a new, empty directory only, and records the build in `nfl/integrations/REBUILD_LEDGER.jsonl`.
  It never overwrites a frozen board.

**Status page.** Published as a private dashboard at https://claude.ai/artifact/FRgTsJCueVYrqmB3oBoAKd, built from the
monitor's exported tables (`nfl/integrations/status/datasets/`). It is a snapshot: it changes when the monitor is re-run
and the tables are re-uploaded.

**4. Projections do not wait for DraftKings or Fantasy Cruncher.** The research universe (`nfl/tools/research_universe.py`)
builds the player list from the roster capture. With DK disconnected, pricing stops; with FC disconnected,
benchmarking stops. The football projection runs either way.

## Measured today: what the missing sync did to the Friday board

The rebuild planner, run against the Friday board (`research_projection/final_2026-10-09/`, as of 17:03Z), found two
consumed inputs newer than the ones the board used:
- the depth chart captured 2026-10-09 19:21Z (the board used 2026-10-08 22:51Z);
- the Thursday practice report (`injuries.21e35d2a84353248`), captured 08:16Z but only synced in at about 20:10Z.

The rebuild ran as of 20:13:49Z: `research_projection/rebuild_2026-10-09/`, 266 players × 2,000 worlds, football sanity
PASS. The comparison is in `COMPARE_TO_FRIDAY_BOARD.json` there.

- **Practice participation changed for 26 slate players, and no projection moved because of it.** Examples:
  - Ja'Marr Chase, Chris Olave, Alvin Kamara, Malik Nabers and D'Andre Swift went from DNP to Limited;
  - Michael Pittman went from Limited to DNP.

  The engine consumes game designations and inactives, not practice lines, so Thursday's report changed nothing it
  reads. The Friday designations will be the first input that can move these numbers.
- **The newer depth chart moved one backfield.** Washington's RB order changed:

  | Player | Depth | Role | DK points |
  |---|---|---|---|
  | Austin Ekeler | 4 → 3 | FRINGE → ROTATIONAL | 0.35 → 2.65 |
  | Kaytron Allen | 3 (unchanged) | ROTATIONAL → FRINGE | 1.15 → 0.12 |

  Allen is the player whose waiver status the 2026-10-09 outbox entry asked the networked agent to verify.
- Across all 266 players the summed absolute change is 4.31 DK points. No other player moved by 0.25 points or more,
  and none changed role band, depth or availability state.

The Friday board's numbers therefore stand, except for the two WAS backs. The defect it exposes, a board built on
captures that were not yet synced, is now detected automatically rather than by luck.

## Gaps found (each is a fact about this repository, measured today)

| Id | Gap | Effect | Fix |
|---|---|---|---|
| INT-G1 | The automated roster capture stores a reduced file without `status` or names | The research universe still needs a hand-made full roster slice; transactions cannot be derived | Keep `status` and `full_name` in the reduction (capture code change; validation separate) |
| INT-G2 | Play-by-play and player stats are not on the capture schedule (last capture 2026-09-17) | Usage history and postgame grading depend on hand fetches | Add pbp and player-stats to the capture schedule (nflverse publishes nightly) |
| INT-G3 | The capture-prod branch reaches this working tree only by a manual sync | **The Friday board's projection was built on Wednesday's injury file and an older depth chart.** Thursday's practice report was captured at 08:16Z but not synced in until 20:1xZ. The research notes cited Thursday correctly; the projection inputs did not. | The rebuild planner now detects exactly this. A scheduled sync needs OD-4. |
| INT-G4 | The workflow is cron `*/30` but runs about every 6–7 h | Intraday news reaches the manifest hours late | GitHub throttles scheduled runs; dispatch before a deadline, which needs OD-4 |
| INT-G5 | No lawful free automated source for pregame inactives or practice-squad elevations | Inactives stay an owner relay (`sunday_paste.py`, tier OWNER_RELAYED) unless a provider is licensed | OD-1, OD-3 |
| INT-G6 | No in-season route participation at no cost | Route participation stays UNKNOWN | Licensed charting (OD-3) |

## Decisions only the owner can make

- **OD-1. Keep, stop, or replace the scheduled fetch of the NFL.com injury and inactives pages (I05, I06)?** NFL.com terms, seen as search text only, bar systematic retrieval to compile a database without consent. The fetch runs today in .github/workflows/nfl-capture.yml. *Agent view:* Check the live NFL.com terms page first. If the clause is confirmed, stop the page fetch and use nflverse injuries for designations and the owner relay for inactives. The agent does not change the workflow until the owner decides.
- **OD-2. Stop the scheduled ESPN injuries JSON fetch (I07)?** Undocumented API under terms that bar automated retrieval; it discharges no forecast target. *Agent view:* Stop it: the forecast reads nothing from it.
- **OD-3. License a provider (SportsDataIO, Sportradar) for DK salaries, inactives or in-season charting?** It is the only automated route to DK salaries and official inactives that fits the terms. It costs money, which is the owner's decision alone. *Agent view:* No change needed for Sunday; the manual drop folder removes the copy-and-paste.
- **OD-4. May the agent dispatch the capture workflow and commit capture syncs into this branch without asking each time?** An attempt to dispatch nfl-capture.yml was refused by this session's permission classifier as an unrequested action in a connected app. The sync into the working tree ran; the dispatch did not. *Agent view:* Leave it on its schedule; ask for a dispatch only when a deadline needs it.

## The weekly flow after this change

1. **Automatic.** The scheduled capture brings in schedule, rosters, depth charts and injuries. The sync brings them into
   the tree. The monitor flags stale sources, QB changes and missing designations, and the rebuild planner says whether
   the projection is out of date.
2. **You, once per slate.** Drop DKSalaries.csv in `nfl/dfs/inbox/drop/`. Optionally drop the FC export, and
   DKEntries.csv after entering. No renaming, no pasting.
3. **Automatic.** The inbox ingests the files, the DK pool replaces the research universe for contest mapping, the
   rebuild runs into a new directory, and the status page updates.
4. **You, after the contest.** Drop the contest-standings CSV for postgame grading and ownership history.
5. **Never automated.** Entering, editing, uploading, late swap, wagering, deposits.

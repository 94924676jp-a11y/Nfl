# Handoff: how the IND @ KC baseline data was acquired (for Claude Code)

Scope: every data source, exact URL or command pattern, and every gotcha hit while building `IND_KC_baseline_projections_2026-09-20.csv` on 2026-09-20 between 23:00Z and 23:20Z. Written so a coding agent can reproduce the pipeline inside the `94924676jp-a11y/Nfl` repo without re-discovering anything. Nothing here uses sportsbook prices or commercial projections as model inputs; the Hard Rock capture is described only because it was part of the same session and the identifiers are reusable.

## 1. Repo state check (GitHub REST API)

Purpose: confirm whether a promoted model or an IND_KC board existed before producing any numbers.

Commands (authenticated `gh` CLI; any GitHub token with repo read works):

```
gh api repos/94924676jp-a11y/Nfl/contents
gh api repos/94924676jp-a11y/Nfl/contents/nfl/product/boards
gh api repos/94924676jp-a11y/Nfl/contents/CURRENT_STATE.md -H "Accept: application/vnd.github.raw"
gh api repos/94924676jp-a11y/Nfl/contents/NFL_BOARD_AUTOMATION.md -H "Accept: application/vnd.github.raw"
gh api "repos/94924676jp-a11y/Nfl/commits?per_page=8"
```

Findings: `nfl/product/boards/` contains only `2026_01_SF_LA/` and `INDEX.jsonl`. `CURRENT_STATE.md` states "NFL-0 evidence system built. No predictive model. NFL-1 not authorised." Latest commit at check time was a4c5cadb (2026-09-20T18:29:46Z, "NFL availability watch"). Boards are written as `nfl/product/boards/<dir>/BOARD.md`, `board.json`, `forecast_artifact.json` and scored with `nfl/tools/score_game.py --forecast-dir`. Consequence: anything produced is an external baseline, not repo output.

## 2. Play-by-play (nflverse public releases on GitHub)

Source: nflverse-data GitHub release assets. Download pattern:

```
https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet
https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet
```

Plain `curl -L -o` works; no auth. Archive hashes of what was used:

- play_by_play_2025.parquet: 20,337,029 bytes, sha256 c6ecedd6d678cc37ed316b23ef84ee1ec6abb69c514bb11868a7ebd5a367df29
- play_by_play_2026.parquet: 1,937,045 bytes, sha256 c5806887b70425c96d2f4492a5588ed8ff3420e47bf3efc3ea7bc0aafe7254ba (contained Week 1: 16 games, Week 2: 8 games at 23:07Z)

What did NOT work: the pre-aggregated `player_stats` release assets for 2025 and 2026 returned 404 at the same URL pattern (`.../releases/download/player_stats/<file>`). Do not assume they exist; aggregate from pbp instead. Verify each asset with a HEAD request before relying on it.

Columns read (pandas + pyarrow, `pd.read_parquet(path, columns=[...])`):
`game_id, season, week, posteam, defteam, home_team, away_team, play_type, pass, rush, qb_dropback, qb_scramble, passer_player_id, passer_player_name, receiver_player_id, receiver_player_name, rusher_player_id, rusher_player_name, complete_pass, yards_gained, passing_yards, receiving_yards, rushing_yards, pass_touchdown, rush_touchdown, touchdown, interception, sack, air_yards, two_point_attempt, field_goal_result, kicker_player_name, extra_point_result, season_type, game_seconds_remaining, wp, qtr`

### Gotchas that changed the numbers

1. Filter `season_type == "REG"` first; 2025 contains postseason rows.
2. Filter `play_type.isin(["pass","run"])`; `no_play` rows (penalties) carry player names and inflate counts.
3. The nflverse `pass` flag is 1 on sacks AND on QB scrambles (it is a dropback flag). The `rush` flag is 0 on scrambles. Result before the fix: Mahomes showed 3 carries for 2025 and Daniel Jones 16, while `rusher_player_name` on `play_type == "run"` rows showed 64 and 45. Fix applied in `build_proj.py` input prep:
   - `pass := (pass == 1) & (qb_scramble != 1)` (still includes sacks, which is intended for a "pass play" volume count)
   - `rush := (play_type == "run")` (includes scrambles)
   Confirmed on 2025 data: 1,160 scramble rows, 1,089 with `play_type == "run"`, `rush.sum() == 0`, all with `rusher_player_name` populated.
4. Player names are abbreviated (`P.Mahomes`, `K.Allen`); two different players can collide on abbreviation across teams. Use `*_player_id` (GSIS ids) for joins; names were used here only because the roster was small and every id mapped one to one.
5. Team codes are `KC`, `IND`, `SEA`, `LAC` etc. A player's 2025 team is whatever `posteam` shows on his plays, which is how Kenneth Walker (SEA) and Keenan Allen (LAC) priors were found without a roster file.
6. Games played was derived as distinct `game_id` where the player had any target, carry, or attempt. That undercounts games for low-usage players and is not a snap-count substitute.

### Aggregation used

`usage(df)` groups targets by `receiver_player_name`, carries by `rusher_player_name`, attempts by `passer_player_name`, then outer joins. Team volume: 2025 plays/game and pass rate per team, blended 0.75/0.25 with 2026 Week 1. Full code: `build_proj.py` in this directory; run `python3 build_proj.py` after producing `pbp_reg_fixed.parquet` with the two flag fixes above.

## 3. Official inactives (governing evidence)

Priority order used: official NFL page, then team sites, secondary only for discovery.

Fetched at 2026-09-20T23:08Z:

- https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026 (Around the NFL Staff, dated 2026-09-20). Contained the IND @ KC section with full inactive lists for both teams. This is the governing source for the projections.
- https://www.colts.com/news/inactives/ (index page). Showed the headline "Colts announce 6 inactive players for Week 2 game vs. Kansas City Chiefs" but the list itself was not on the index page; the article URL was not resolved.
- https://www.chiefs.com/news/ (index page). Showed "Week 2 Inactive Players | Colts vs. Chiefs" dated Sep 20, 2026; article URL not resolved.
- Friday injury report (for context only, not inactive status): https://www.chiefs.com/news/2026-week-2-injury-report-colts-vs-chiefs

Method: a fetch-plus-extraction call with the instruction to return names and positions exactly as listed and to answer NOT_PRESENT when a page lacked the list. For Claude Code, replace this with: `requests.get` the raw HTML, write bytes to `raw/<host>_<utc>.html`, record sha256 and `retrieved_at_utc`, then parse the inactives block. Team article slugs on these sites are usually derivable from the headline (lowercase, hyphens), but verify with a HEAD request rather than guessing.

Result: NFL.com list matched the owner screenshot exactly. Evidence status recorded as COMPLETE membership, INCOMPLETE raw archive (team-site bytes not captured). No SOURCE_CONFLICT observed because only one governing source was read.

## 4. Hard Rock market snapshots (OpticOdds connector, NOT a model input)

Recorded for identifier reuse only. Endpoints used through the internal OpticOdds connector: `/fixtures/active` (sport=football, league=nfl) to find fixtures; `/players?team_id=` to build a player id map; `/fixtures/odds` with `fixture_id`, `sportsbook=Hard Rock Bet`, at most five id values per call. Reusable ids: fixture `202609217572D919` (IND @ KC, 2026-09-21T00:20Z), KC team_id `2D71E5BA64A5`, IND team_id `28ABEAB98C11`. Gotcha: the fixture object exposes teams under `home_competitors[0].id` and `away_competitors[0].id`, not `home_team_id`. Snapshot files live under `market-snapshots/nfl-wk2-snf-ind-kc-hardrock-2026-09-20T2252Z/`.

## 5. Suggested next steps for the repo (unverified items marked)

- Pin nflverse asset versions by sha256 in a manifest and re-download on mismatch; the pbp files are rewritten in place as games finish.
- Add roster and depth-chart inputs so the RB2 question (IND without Giddens) is answered from data instead of left UNKNOWN. nflverse publishes `rosters` and `depth_charts` release assets in the same repo; availability for 2026 is UNVERIFIED and must be checked with a HEAD request, not assumed.
- Replace name-keyed joins with `gsis_id` joins.
- Replace the hand-set weights (0.75/0.25 volume blend; 2.5-game Week 1 weight; k = 60/150/200/300 shrinkage) with weights selected in a forward chain on 2025 weeks, per the standing "no random train/test split" rule.
- Archive every official inactives page as raw bytes with hash before parsing, matching the standard already used in `inactives/nfl-wk2-1pm-official-inactives-2026-09-20/`.

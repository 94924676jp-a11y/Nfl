# Week 5 Classic (Sunday early slate): postgame evaluation plan

**Freeze before kickoff (13:00 ET, 2026-10-11).** A `PREGAME_FREEZE_MANIFEST.json` will hash every prelock file:
- the FC export;
- the research boards;
- our STATE / PROJ / DRAWS / WORLDS, once built;
- every portfolio and upload;
- the inactives evidence;
- the commit.

Grading verifies the manifest first and refuses on any changed file. The TB@DAL tool already does this
(`showdown_postgame.verify_freeze`).

**Results.**
- **Source:** nflverse play-by-play for the 8 game ids, retrieved automatically. For TB@DAL it was available about
  4 hours after the final whistle.
- **Scoring:** DK points from the project's single scorer, with join provenance on every player (no anonymous zeros).
- **Cross-check:** against nflverse `stats_player_week`, the same check that caught the two-point-try bug.

**Grading.**
- **Players:** each player's actual score against our frozen projection, FC and his 2026 average, with the
  probability-transform position of the actual and the 10th–90th percentile coverage of our range. The results are
  added to `SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl`, which gets a Classic sibling.
- **Teams:** points, plays and pass rate against our worlds, flagged for CHI, MIN and WAS (the QB-regime clubs).
- **Portfolios:** every frozen portfolio scored on actuals, plus the hindsight optimum, labelled HINDSIGHT.
- **Contests:** from the DK standings export, via `showdown_standings.py` generalised to Classic. That covers which
  lineups DK held, scorer parity, finish, field ownership and duplication. Winnings require a payout source.

**Not done automatically, ever:** retraining, re-projection or promotion on one week's results.

**Code status.**
- `auto_postgame.py` grades Showdown configs today.
- A Classic `POSTGAME_CONFIG` and the Classic branch of the scorer are the remaining work (BOARD item P3).

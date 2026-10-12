# Data notice: PM-1 historical inputs and the tables derived from them

## Inputs

- `nfl/vintage/hist_participation_<season>.*.csv.gz`, 2016-2025.
  - nflverse `pbp_participation` release files. Participation data is FTN Data, distributed by nflverse under
    **CC-BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/).
  - Attribution: FTN Data via nflverse (https://github.com/nflverse/nflverse-data).
  - Stored as gzip of the original bytes, unmodified, and redistributed here under the same licence.
- `nfl/vintage/hist_injuries_<season>.*.csv.gz`, 2016-2025.
  - nflverse `injuries` release files. The upstream source's terms are **UNKNOWN**
    (`nfl/research/integrations/PLATFORM_TERMS_AND_APIS.md`).
  - **Not redistributed** (owner decision 2026-10-12). Removed from the branch tip at that date; earlier commits
    still contain them, and no history was rewritten.
  - They are git-ignored. To reproduce PM-1, re-fetch them with `acquire.py`, which checks each file against the
    SHA-256 recorded in `ACQUISITION.json`.

Downloaded 2026-10-11 under owner decision E1. URL, retrieval time and SHA-256 of every file are in `ACQUISITION.json`.

Pro Football Reference snap counts were deliberately **not** downloaded: PFR's terms prohibit building tools on that data.

## Derived tables: CC-BY-SA 4.0 (share-alike)

The following files are adaptations of the FTN participation data. They are licensed under **CC-BY-SA 4.0**, with
attribution "FTN Data via nflverse; derived by this project", and any further adaptation must carry the same licence:

- `PM1_TABLE.json`, `PM1_EVALUATION.json`, `PM1_UNITS_SUMMARY.json`, `PM1_CONTROL.json`
- `PM2_TABLE.json`, `PM2_REUSED_CHECK.json`
- `PM3_PHI.json`
- the participation summaries inside `nfl/tests/fixtures/contract45_w5_2026-10-11/*/DK_2026W5_EARLY_DRAWS.json.gz`
  (key `participation`)

**Open point.** These tables also condition on injury-report designations and practice status from the nflverse
`injuries` files, whose terms are unknown. They are aggregated cell rates and contain no copied rows. Whether that use
is permitted is recorded as **UNRESOLVED, owner/legal review**; it is not assumed.

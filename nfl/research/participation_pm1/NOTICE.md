# Data notice: PM-1 historical inputs

- `nfl/vintage/hist_participation_<season>.*.csv.gz`, 2016-2025.
  - nflverse `pbp_participation` release files. Participation data is FTN Data, distributed by nflverse under
    **CC-BY-SA 4.0**. Attribution: FTN Data via nflverse (https://github.com/nflverse/nflverse-data).
  - Stored as gzip of the original bytes.
- `nfl/vintage/hist_injuries_<season>.*.csv.gz`, 2016-2025.
  - nflverse `injuries` release files.
  - The upstream source's terms apply. They are recorded as UNKNOWN in
    `nfl/research/integrations/PLATFORM_TERMS_AND_APIS.md`.

Downloaded 2026-10-11 under owner decision E1. URL, retrieval time and SHA-256 of every file are in `ACQUISITION.json`.

Pro Football Reference snap counts were deliberately **not** downloaded: PFR's terms prohibit building tools on that data.

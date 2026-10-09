# Platform terms and API audit: NFL DFS workflow

Retrieved 2026-10-09. Full evidence is in `PLATFORM_TERMS_AND_APIS.json`.

**How sources were read.** Only github.com could be read directly. That covers the nflverse repos, cloned at nflreadr@23f915a and nflverse-data@a78da18, plus the third-party GitHub pages that document DraftKings and ESPN endpoints. Every other vendor page failed. WebFetch could not resolve the host names (ENOTFOUND), and the egress proxy returned 403 for DraftKings, NFL.com and site.api.espn.com. Those vendor pages were therefore seen only as search-result text and are tagged **SNIPPET_ONLY**. Before anyone relies on one of those quotes, check it against the live page. The file holds 29 PRIMARY and 77 SNIPPET_ONLY evidence items. Nothing here is legal advice.

| Service | API | Official export | Scheduled delivery | Authenticated integration | Automated-access terms | Redistribution |
|---|---|---|---|---|---|---|
| DraftKings DFS | UNOFFICIAL_UNDOCUMENTED (draftables and getcontests endpoints are reverse-engineered, with no DraftKings sanction) | OFFICIAL_MANUAL_EXPORT (GameCenter "Export Lineups to CSV", DKSalaries.csv, DKEntries.csv, CSV upload) | NOT_OFFERED | NOT_OFFERED (partners only) | **PROHIBITED_BY_TERMS** (scripts, third-party tools, scrapers) | UNKNOWN |
| Fantasy Cruncher | NOT_OFFERED | OFFICIAL_MANUAL_EXPORT (lineup CSV; Rewind CSV/XLSX) | NOT_OFFERED | NOT_OFFERED | **PROHIBITED_BY_TERMS** | PROHIBITED_BY_TERMS (except your own lineups) |
| nflverse | OFFICIALLY_SUPPORTED (GitHub release files) | OFFICIALLY_SUPPORTED | OFFICIALLY_SUPPORTED (pull on a cron schedule; see below) | NOT_OFFERED (not needed) | OFFICIALLY_SUPPORTED (but the upstream sources' terms still apply) | UNKNOWN (repo is CC BY 4.0, but NFL data "governed by their terms of use"; FTN data is CC-BY-SA) |
| NFL official | LICENSED_PAID (Genius Sports, exclusive) | OFFICIAL_MANUAL_EXPORT (NFL.com injury pages only, no file download) | LICENSED_PAID | LICENSED_PAID | **PROHIBITED_BY_TERMS** (no systematic retrieval without consent) | PROHIBITED_BY_TERMS |
| Sportradar | LICENSED_PAID (v7: injuries, depth charts, rosters) | NOT_OFFERED | LICENSED_PAID | LICENSED_PAID (30-day trial, 1,000 requests) | LICENSED_PAID (trial is for evaluation only) | PROHIBITED_BY_TERMS (trial) |
| SportsDataIO | LICENSED_PAID (injuries, depth charts, **DFS slates with DK/FD/Yahoo salaries**) | LICENSED_PAID | LICENSED_PAID (polling) | LICENSED_PAID (trial data is scrambled; Discovery Lab is one day delayed) | LICENSED_PAID | PROHIBITED_BY_TERMS |
| Genius Sports | LICENSED_PAID (B2B only) | UNKNOWN | LICENSED_PAID | LICENSED_PAID | UNKNOWN | UNKNOWN |
| ESPN hidden API | UNOFFICIAL_UNDOCUMENTED | NOT_OFFERED | NOT_OFFERED | NOT_OFFERED | **PROHIBITED_BY_TERMS** (Disney Terms of Use) | PROHIBITED_BY_TERMS |
| Pro Football Reference | NOT_OFFERED (custom data requests start at $5,000) | OFFICIAL_MANUAL_EXPORT (share individual tables with credit) | NOT_OFFERED | NOT_OFFERED | PROHIBITED_BY_TERMS (20 requests per minute) | PROHIBITED_BY_TERMS (no tools built on scraped data, no AI training) |
| RotoWire | LICENSED_PAID (B2B syndication; free RSS feeds) | UNKNOWN | LICENSED_PAID | LICENSED_PAID | UNKNOWN | UNKNOWN |

## nflverse refresh schedule (PRIMARY, from the repository source)

| Data | Refresh | Source |
|---|---|---|
| Injuries | Daily at 07:00 UTC, September to February | upstream "API" not named |
| Rosters | Daily at 07:00 UTC | not stated |
| Depth charts | Daily at 07:00 UTC, all year | ESPN since 2025 (previously NFL Data Exchange) |
| Schedules | Every 5 minutes in season | Lee Sharpe |
| Play-by-play and player stats | Nightly at 09:00 UTC, plus runs during game windows; stat corrections Wednesday night | NFL GSIS |
| Snap counts and PFR advanced stats | Every 6 hours in season | Pro Football Reference |
| FTN charting | Every 6 hours in season | FTN, CC-BY-SA 4.0 |
| Participation | After the postseason only | FTN, CC-BY-SA 4.0 |

## What this means for the workflow

1. The DraftKings steps that fit its terms are: a person downloads DKSalaries.csv or DKEntries.csv by hand, the files are processed offline, and a person uploads the CSV by hand. Scripted login, scraping, or automated entry and editing is prohibited.
2. nflverse is the only zero-cost source with an officially supported programmatic route. Its depth charts now come from ESPN and its snap counts from PFR, so passing that data on to others still depends on those upstream terms.
3. SportsDataIO is the one licensed source found that sells DFS slate salaries. The trial cannot be used for analysis, because its data is scrambled.

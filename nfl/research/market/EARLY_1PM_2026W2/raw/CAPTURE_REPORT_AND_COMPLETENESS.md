# NFL Week 2, 1 PM ET Early Only Slate: Hard Rock Bet Market Capture

Capture date: 2026-09-20. Retrieval window (UTC): start 2026-09-20T04:51:45Z, end 2026-09-20T04:54:07Z for the primary Hard Rock Bet board; secondary DraftKings touchdown probe 2026-09-20T04:54:59Z to 2026-09-20T04:55:02Z.

Purpose: external comparator layer only. Nothing in these files is a football model input, projection, or recommendation. Lines are preserved exactly as returned (247.5 stays 247.5; 4.5 stays 4.5).

## Files

| File | Contents |
|---|---|
| `NFL_wk2_1pm_hardrock_markets_2026-09-20T0452Z.csv` / `.json` | 7,081 Hard Rock Bet market rows across all eight games: 4,560 player-prop rows (main and alternate lines), 2,521 game/team rows (moneyline, point spread ladders, total ladders, team totals). One row per (market, selection, line); Over and Under prices are paired on the same row where both exist. |
| `SECONDARY_draftkings_player_touchdowns_2026-09-20T0458Z.csv` | 615 DraftKings `Player Touchdowns` rows (0.5, 1.5, 2.5 lines) for the same eight games. Book column is labeled `DraftKings (SECONDARY, comparison only)`. Never merge with the Hard Rock file as if from one source. |
| `NFL_wk2_1pm_hardrock_raw_evidence_2026-09-20.zip` | Raw structured API response bytes for every call (40 primary calls in `raw/`, 8 secondary calls in `raw_secondary/`), fixture and market discovery responses, player registry lookups, per-call request timestamps (`fetchlog.json`), the fetch and build scripts, and `SHA256SUMS.txt` over all evidence files. |

Evidence type for every row: `structured_json_api_response` (Hard Rock Bet prices delivered through the OpticOdds v3 `/fixtures/odds` feed with `sportsbook=Hard Rock`). No screenshots were needed because structured bytes were obtained. `source_url` carries the Hard Rock betslip deep link for the selection where the feed supplied one.

## Column notes

- `retrieved_at_utc`: request timestamp of the API call that returned the row (to the second).
- `book_line_timestamp_utc`: the feed's own last-change timestamp for that price; the range across the board is 2026-09-17T14:25:06Z to 2026-09-20T04:51:51Z.
- `line`: exact sportsbook number. For point spreads the line is signed from the perspective of `displayed_selection` (e.g. `Baltimore Ravens -9`).
- `over_price` / `under_price`: American odds. For moneyline and point spread rows, which are single-selection markets, the price is in `selection_price` and `market_status` is `open_single_selection`.
- `market_status`: `open_two_sided`, `open_one_sided_over`, `open_one_sided_under`, or `open_single_selection`. No suspended rows were returned; a market that the book does not list is simply absent (see gaps below).
- `is_main_line`: `True` for the book's primary line; `False` for alternates. Filter on `is_main_line == True` for the 591 primary player markets.
- `player`: exact displayed sportsbook name. All 133 Hard Rock player identities resolved to feed player records with team and position; zero `IDENTITY_UNRESOLVED` rows in the primary file. In the secondary DraftKings file the 48 `IDENTITY_UNRESOLVED` rows are team D/ST selections (e.g. `Baltimore Ravens D/ST`), not players; original displayed names are preserved.
- Team abbreviations: PHI TEN PIT NE MIN CHI CAR ATL GB NYJ NO BAL CIN HOU CLE TB.

## Main game lines (Hard Rock Bet, retrieved 2026-09-20T04:52:00Z to 04:52:03Z)

| Game | Spread (price) | Moneyline | Total (price) |
|---|---|---|---|
| PHI @ TEN | PHI -7.5 (-105) / TEN +7.5 (-115) | PHI -375 / TEN +300 | 39.5 (-110 / -110) |
| PIT @ NE | NE -5.5 (-110) / PIT +5.5 (-110) | NE -250 / PIT +200 | 41.5 (-110 / -110) |
| MIN @ CHI | CHI -5 (-110) / MIN +5 (-110) | CHI -230 / MIN +190 | 48 (-110 / -110) |
| CAR @ ATL | CAR -3 (-105) / ATL +3 (-115) | CAR -155 / ATL +130 | 43.5 (-110 / -110) |
| GB @ NYJ | GB -3.5 (-105) / NYJ +3.5 (-115) | GB -185 / NYJ +155 | 44.5 (-110 / -110) |
| NO @ BAL | BAL -9 (-110) / NO +9 (-110) | BAL -475 / NO +350 | 46 (-110 / -110) |
| CIN @ HOU | HOU -2.5 (-115) / CIN +2.5 (-105) | HOU -140 / CIN +120 | 45.5 (-110 / -110) |
| CLE @ TB | TB -8.5 (-110) / CLE +8.5 (-110) | TB -475 / CLE +350 | 41 (-110 / -110) |

## QB passing yards main lines (Hard Rock Bet)

| Game | Player | Line | Over / Under |
|---|---|---|---|
| PHI @ TEN | Jalen Hurts | 206.5 | -115 / -115 |
| PHI @ TEN | Cam Ward | 186.5 | -115 / -115 |
| PIT @ NE | Aaron Rodgers | 209.5 | -115 / -115 |
| PIT @ NE | Drake Maye | 225.5 | -115 / -115 |
| MIN @ CHI | Carson Wentz | 217.5 | -115 / -115 |
| MIN @ CHI | Caleb Williams | 229.5 | -115 / -115 |
| CAR @ ATL | Bryce Young | 222.5 | -115 / -115 |
| CAR @ ATL | Cooper Rush | 182.5 | -115 / -115 |
| GB @ NYJ | Jordan Love | 251.5 | -115 / -115 |
| GB @ NYJ | Geno Smith | 208.5 | -115 / -115 |
| NO @ BAL | Tyler Shough | 230.5 | -115 / -115 |
| NO @ BAL | Lamar Jackson | 211.5 | -115 / -115 |
| CIN @ HOU | Joe Burrow | 245.5 | -115 / -115 |
| CIN @ HOU | C.J. Stroud | 219.5 | -115 / -115 |
| CLE @ TB | Deshaun Watson | 174.5 | -115 / -115 |
| CLE @ TB | Baker Mayfield | 216.5 | -115 / -115 |

## Completeness report

- Total games captured: 8 of 8 (PHI@TEN, PIT@NE, MIN@CHI, CAR@ATL, GB@NYJ, NO@BAL, CIN@HOU, CLE@TB). Missing games: none.
- Total unique player markets (player x market x game, main line): 591. Unique players: 133.
- Total player-prop rows including alternates: 4,560 (main 591, alternate 3,969).
- Paired Over/Under player rows: 3,598 of 4,560 (main lines: 505 of 591).
- Player rows with only one side available: 962 (main lines: 86). Of the 86 one-sided main rows, 70 are `Player Touchdowns` (Over 1.5 only, priced as a yes-style market) and 16 are `Player Kicking Points` (Over only).
- Game/team rows: 2,521 (moneyline 16, point spread 1,411 including alternates, total points 1,499 including alternates, team total 680).
- Unresolved player identities: 0 in the Hard Rock file.
- Hard Rock access failures: none. All 40 primary calls returned HTTP 200 with data.
- Retrieval start: 2026-09-20T04:51:45Z. Retrieval end: 2026-09-20T04:54:07Z.
- Line movement: the entire primary board was pulled in one pass of 17 seconds; no market was observed at two different values, so there are no duplicate chronology rows. The feed's `book_line_timestamp_utc` shows when the book last changed each price.

## Explicit gaps (Hard Rock Bet did not list these; nothing was substituted or estimated)

1. Anytime touchdown (Over 0.5) is NOT present in the Hard Rock feed for any player in any of the eight games. Hard Rock's `Player Touchdowns` market appears only at 1.5, 2.5, and 3.5 (2+, 3+, 4+ touchdowns), Over side only. Whether the Hard Rock app shows an anytime TD market under a different heading that the feed does not map is UNKNOWN. For comparison only, the secondary DraftKings file carries 231 Over 0.5 rows across the eight games; it is labeled as a different book and must not be treated as Hard Rock pricing.
2. Receiving targets: not offered by Hard Rock (absent from the book's active market list for these fixtures).
3. Rushing attempts and longest rush: offered only for a subset of backs (28 and 36 main rows respectively), not every RB.
4. GB @ NYJ, Geno Smith: `Player Interceptions`, `Player Passing Completions`, and `Player Longest Passing Completion` were not listed (Jordan Love had all six QB markets).
5. CLE @ TB: no `Player Field Goals Made` market for either kicker (kicking points were listed).
6. Player passing rating, tackles, and all 1st-half/quarter derivatives were listed by the book but were out of scope and not captured.

## Provenance and constraints

- Primary source: Hard Rock Bet prices as carried by the OpticOdds v3 feed (`/fixtures/odds`, `sportsbook=Hard Rock`). This is a structured redistribution of the book's board, not a direct scrape of app.hardrockbet.com; each row keeps the feed odds ID and the book's betslip deep link.
- No consensus odds were used. No price or line was interpolated, rounded, or inferred from another market or book.
- These prices are for later comparison of independently generated model CDFs at the exact sportsbook line and must not enter the football forecast.

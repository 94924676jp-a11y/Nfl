# Hard Rock Early Only market board — ingest and validation

**Sound. Registered as delivered external-comparator evidence. Compared
against nothing, because there is nothing valid to compare it against.**

Every count the delivered capture report claims was **recomputed from the
bytes**, and every row was reconciled back to the raw API responses. Nothing
below is quoted from the report.

## Source qualification — this must not be flattened

These are **Hard Rock Bet prices carried by the OpticOdds v3
`/fixtures/odds` feed** with `sportsbook=Hard Rock`. That names the book whose
prices these are. It does **not** name who served the bytes.

It is a structured **redistribution**, not a direct scrape of
`app.hardrockbet.com`. Every artifact this ingest writes carries both facts
together. Relabelling a redistribution feed as first-party raw bytes is the
provenance defect this project audits itself for, and a single collapsed
sentence is how it would happen.

## Raw hashes and preservation paths

The owner's three files are preserved byte-for-byte, mode `444`, under
`nfl/research/market/EARLY_1PM_2026W2/raw/`. Each hash was recomputed **after**
the copy and pinned in `nfl/market/early_1pm_hardrock.py`, so a file whose
hash moves is refused rather than silently revalidated.

| file | sha256 | bytes |
|---|---|---|
| `NFL_wk2_1pm_hardrock_markets_2026-09-20T0452Z.csv` | `1c097f532fbd81bc0b82bc2c4aa43453b021252a555610dd479d3cd0fb684ec6` | 4,288,033 |
| `CAPTURE_REPORT_AND_COMPLETENESS.md` | `506ead2892b1d8aa30d563ccbfedbd3c02bdb82a5872567abb1df81eedcf2bfe` | 8,153 |
| `NFL_wk2_1pm_hardrock_raw_evidence_2026-09-20.zip` | `bed4b4d9b5845d9bd8cd054996760dbe53cd25f0ea607c8f5b450ae4017ed669` | 932,115 |

Nothing was modified in place. All derivatives are separate files.

## Bundle integrity

**74 of 74 evidence files verify** against the bundle's own `SHA256SUMS.txt`.
Nothing listed is missing; nothing present is unlisted.

The manifest holds **75** entries, and the 75th is `SHA256SUMS.txt` naming
itself — which no file can satisfy, since a file cannot contain its own hash.
Reporting "74 of 75 verified" would read as one corrupt file. Reporting 74 of
74 silently would hide a line that is there. So it is separated and named.

**What is not explained:** the hash the manifest lists for itself
(`7c8a80ef…`) matches neither the file as delivered (`2bc81143…`), nor the file
with its own line removed, nor that sorted. Neither `build.py` nor `fetch.py`
generates the manifest, so how it was produced is not established by this
bundle. Recorded as unverifiable rather than guessed at. It bears on no
evidence file.

## Every call returned data, with its provenance

- **40 of 40** primary calls: HTTP **200**, and **40 fixtures returned**. A
  200 carrying no rows is the empty-success defect this project pays for most
  often, so "returned data" is counted separately from "returned 200".
- **40 of 40** preserved the connector provenance block after the `<<STDERR>>`
  separator. It is kept, not stripped.

## Book separation — checked at the bytes

| | |
|---|---|
| primary raw odds records | **11,764**, every one `sportsbook = "Hard Rock"` |
| secondary raw odds records | **615**, every one `sportsbook = "DraftKings"` |
| overlap | **none** |

Read out of the `sportsbook` field of every record in all 48 raw responses,
not out of the CSV's `book` column. A column can be mislabelled; 12,379
records cannot be mislabelled quietly.

The DraftKings rows exist **only** because Hard Rock lists no anytime-TD
Over 0.5 anywhere in these eight games. They are a different book, not a fill
for that gap, and they are not merged.

## Slate membership

Exactly the eight 1PM ET games — CAR@ATL, CIN@HOU, CLE@TB, GB@NYJ, MIN@CHI,
NO@BAL, PHI@TEN, PIT@NE. **None missing, none extra**, and all 7,081 rows
carry `kickoff_utc = 2026-09-20T17:00:00Z`.

## Normalized row counts — every claim recomputed

| quantity | recomputed | report claims |
|---|---|---|
| total rows | **7,081** | 7,081 |
| player-prop rows | **4,560** | 4,560 |
| game / team rows | **2,521** | 2,521 |
| main-line player markets | **591** | 591 |
| alternate player lines | **3,969** | 3,969 |
| unique players (main) | **133** | 133 |
| two-sided main markets | **505** | 505 |
| one-sided main markets | **86** | 86 |

All eight agree.

## Conservation against the raw bytes — the check a row count cannot make

Two files can agree on a total and disagree on every row. So each CSV row was
resolved back to the raw response by `odds_id`:

| | |
|---|---|
| raw odds records | **11,764** |
| CSV odds references | **11,764** |
| referenced but absent from the raw | **0** |
| in the raw but never referenced | **0** |
| price / line / `is_main` mismatches | **0** |

The board is the raw bytes, reshaped, and nothing else.

## Duplicates, exact lines, prices, clocks

- **0** duplicate `(game, market, selection, line, is_main)` keys.
- Lines are exact. Checked as **strings**, not floats: every fractional part
  is `.5` (5,987) or absent (1,078), and `0` malformed. A 4.5 rounded to 5
  upstream parses as cleanly as an exact one, so only the string can show it.
- **0** malformed prices; all American integer odds.
- `market_status` **determines** which price columns are populated, with no
  exceptions: `open_two_sided` → over+under (4,683), `open_one_sided_over` →
  over (932), `open_one_sided_under` → under (39), `open_single_selection` →
  selection (1,427). A status column that did not would be decoration.
- **0** rows retrieved before the book last changed that price. Retrieval
  clock and feed clock are consistent on all 7,081 rows.

**One qualification on the retrieval window.** The report gives
04:51:45Z–04:54:07Z; the board *rows* span **04:52:00Z–04:52:16Z**. Not a
contradiction — the wider window covers fixture and market discovery calls as
well. The priced board was pulled in 16 seconds, which is why no market appears
at two values. Feed last-change stamps range 2026-09-17T14:25:06Z to
2026-09-20T04:51:51Z.

## Identity reconciliation

133 distinct priced players, joined to our canonical 2026 week-2 roster by the
same deterministic three passes the DK universe uses — exact `(name, team)`,
normalised `(name, team)`, normalised name with the team disagreement
**recorded**. **No edit distance anywhere.**

| | |
|---|---|
| `MATCHED_CANONICAL` | **130** |
| `AMBIGUOUS` | **0** |
| `UNMATCHED` | **3** |

The three are named, carry **no guessed id**, and say why:

| player | team | pos | game |
|---|---|---|---|
| Andres Borregales | NE | PK | PIT@NE |
| Kenneth Gainwell | TB | RB | CLE@TB |
| Kevin Concepcion | CLE | WR | CLE@TB |

Each is absent from our roster vintage **under that name on any team**, so
this is a coverage gap in *our* roster, not a reason to guess. It also means
the board's team attribution for them is unverified here — which is stated
rather than resolved by recall.

## Overlap with the DraftKings Early Only universe

115 of the 133 priced players are on the 256-player DK board. Of the 18 who are
not, **16 are kickers** — DraftKings Classic rosters no kicker at all, so that
is two products selecting two populations, not a gap in either. The remaining
two are Gainwell and Concepcion, the same UNMATCHED names above.

## Explicit gaps — measured, not quoted

Nothing was substituted from another book, another market or another line.

1. **No anytime touchdown (Over 0.5)** for any player in any of the eight
   games. Hard Rock's `Player Touchdowns` appears only at **1.5, 2.5, 3.5**,
   Over side only. Whether the app shows it under another heading the feed does
   not map is **UNKNOWN** and is left that way.
2. **No receiving-targets market** at all.
3. Rushing attempts (**28** main rows) and longest rush (**36**) cover a subset
   of backs, not all of them.
4. Per the delivered report: GB@NYJ Geno Smith has no interceptions,
   completions or longest-completion market; CLE@TB has no field-goals-made
   market for either kicker; passing rating, tackles and half/quarter
   derivatives were out of scope and not captured.

## Registration

Declared in `registry.DELIVERED` as `hardrock_early_1pm_market_board`,
`acquisition=OWNER_SUPPLIED_DELIVERY`, `role=DOWNSTREAM_COMPARATOR_ONLY`,
`forecast_eligible=False`.

**It is deliberately NOT in `registry.REGISTRY`.** Owner-delivered bytes create
**no recurring capture obligation** — this project holds no endpoint, no
credential and no schedule for them, and inventing an obligation because files
arrived once would make a freshness check start failing against a source nobody
agreed to fetch.

## The wall

No module under `nfl/production`, `nfl/product` or `nfl/prospective` imports
`nfl.market.early_1pm_hardrock`. That is **walked through the import graph**,
not asserted in a docstring. Its only importer today is its own test.

No sportsbook price, line, implied probability or derived market quantity
reaches player projections, team volume, role, efficiency, appearance, game
simulation or touchdown probability.

## Compared against nothing, and why

`CURRENT_PROJECTION_AVAILABLE = 0` for all 256 Early Only players. There is no
sealed forecast to hold this board against.

The 229 rehearsal distributions are **not** one: `dry_run=true`,
`prospective_eligible=false`, unsealed, and their `capture_validation` passed
on a placeholder source hash. Comparing a real market to those would be
comparing it to numbers whose inputs were never validated, and would
manufacture an apparent edge out of a provenance hole.

So this board waits. The order is unchanged: **DK-3**, then **DK-4**, then
rerun the eight games through the production path, then let the system name the
next blocker — expected to be SUN-5 — and **do not weaken sealing**. Only after
a legitimate sealed board exists does this file get joined to anything.

## What the eventual comparison will need, and what it already has

Nothing new has to be built for the model-vs-market step. Two modules that
predate this ingest already carry it, and this file is shaped to feed them:

- `nfl/market/odds.py` — American price to probability, and de-vig. It returns
  `NO_TWO_SIDED_DEVIG` rather than a number on a one-sided market, which
  matters here: **86 of the 591** main player markets are one-sided (70
  `Player Touchdowns` Over-only, 16 `Player Kicking Points` Over-only), and
  reporting their raw implied probability as no-vig would overstate the book's
  opinion by the entire hold.
- `nfl/market/evaluate.py` — `P(over)` counted from sealed draws at the exact
  line, with no distributional assumption and no interpolation from stored
  percentiles.

One measured detail worth carrying forward: **every whole-number line on this
board is a game or team line (1,078 of them); all 4,560 player-prop lines are
half points.** So push mass is zero by construction on the player side and
real on the game side — which is exactly the split `evaluate.py` already
handles in one code path rather than two.

None of this runs today. It is recorded so the next step is an assembly, not a
design.

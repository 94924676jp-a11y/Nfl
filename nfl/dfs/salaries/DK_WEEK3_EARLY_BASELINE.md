# DraftKings Week-3 Early Only (1 PM ET) — frozen pre-inactives baseline

Built 2026-09-27T01:26Z from two owner-supplied files. Every figure below was
produced by reading the preserved bytes through repository code, not read off the
delivered files by eye. Machine-readable twin: `DK_WEEK3_EARLY_BASELINE.json`.

**What this artifact is.** A record of what was known *before* Sunday news, so
that tomorrow every change can be measured against it. It is deliberately not a
projection, not a lineup, and not a recommendation.

**What it is not.** It is not final. It predates official inactives by roughly 15
hours (kickoff 2026-09-27T17:00Z), and the model cannot currently produce a
lawful board for this slate at all — see §5.

## 1. Provenance of the two supplied files

| | DK entries export | FantasyCruncher export |
|---|---|---|
| preserved as | `nfl/vintage/dk_entries.2c82fe5560677f56.csv.gz` | `nfl/vintage/dk_salaries_early.35f38b43e29d0e89.csv.gz` |
| sha256 | `2c82fe5560677f56fa16bf978671701f98f77291297581b0b4c2b7bfd91d357e` | `35f38b43e29d0e890d31bd7401898c043eff3a3ef888034878043fb76befcffd` |
| bytes | 53,827 | 39,727 |
| raw copy | `raw/DKEntries_EARLY_ONLY_2026W3_59.csv` | `raw/THIRDPARTY_players_EARLY_ONLY_2026W3_CONTEXT_ONLY.csv` |
| acquisition | `OWNER_SUPPLIED_DELIVERY` | `OWNER_SUPPLIED_DELIVERY` |
| role | **AUTHORITATIVE** contest universe, salary, game set | **EXTERNAL COMPARISON ONLY** |
| predictive use | salary/universe only | **NOT_AUTHORIZED — see §6** |

Both gzip round trips were verified byte-identical before anything was recorded.
Digests are written in full: a first draft of this table abbreviated them and got
the FantasyCruncher tail wrong from memory, which is the exact defect class this
project keeps paying for. Abbreviating a hash saves a line and costs an audit.
The raw files are preserved unedited; every derived object is a separate file.
The FC file's own name carries `THIRDPARTY_…_CONTEXT_ONLY` so that its status is
visible at the path, not only in a document.

## 2. The slate, resolved from DraftKings' own export

`PASS[DK_EARLY_SLATE_RESOLVED_FROM_EXPORT]` — 9 games, 18 clubs, **457 pool
rows**, all stamped `09/27/2026 01:00PM ET`.

CAR@CLE · CIN@PIT · HOU@IND · KC@MIA · LAC@BUF · NE@JAX · NYJ@DET · SEA@WAS ·
TEN@NYG

| position | rows |
|---|---|
| QB | 60 |
| RB | 107 |
| WR | 172 |
| TE | 100 |
| DST | 18 |

Salary band $2,000–$8,800. The window was resolved from the export rather than
assumed: `early_only.slate()` now separates a pool spanning more than one
kickoff window (`DK_POOL_SPANS_MORE_THAN_ONE_WINDOW`) from a single-window pool
that is not the *declared* window (`DK_POOL_WINDOW_IS_NOT_THE_DECLARED`). Those
are different faults and previously shared one code — filed as DEF-081.

## 3. Identity chain

DK PLAYER ID → canonical NFL/GSIS ID → model player. `n_in = n_out = 457`;
nothing was dropped.

| outcome | n |
|---|---|
| MATCHED_CANONICAL | 433 |
| — of which EXACT_NAME_TEAM | 420 |
| — of which NORMALIZED_NAME_TEAM | 12 |
| — of which NORMALIZED_NAME_ONLY (team disagrees) | 1 |
| DST (no player identity by construction) | 18 |
| **UNMATCHED** | **6** |
| ambiguous | 0 |
| duplicate gsis_id | 0 |

The six unmatched, named rather than counted:

| DK id | pos | name | team | salary |
|---|---|---|---|---|
| 44246968 | RB | Al-Jay Henderson | NYJ | $4,000 |
| 44246912 | RB | Nick Singleton | TEN | $4,000 |
| 44247126 | WR | Joshua Palmer | BUF | $3,500 |
| 44247216 | WR | Mitch Tinsley | HOU | $3,000 |
| 44247168 | WR | River Cracraft | WAS | $3,000 |
| 44247446 | TE | Drew Ogletree | IND | $2,500 |

**UNMATCHED is a state, not a zero and not an absence.** These six are on
DraftKings' own contest export, so they are rosterable. Our failure to resolve
them to a canonical id is our defect, not evidence they are not playing.

One club disagreement (Cal Adomitis, DK says MIA, canonical says NO) and six
position disagreements, mostly long snappers that DK lists at TE, are recorded
rather than silently overwritten.

## 4. Owner entries — recorded, never touched

`PASS[DK_ENTRIES_LOADED]` — **2 entries**, contest *NFL $1K Dime Package [Just
$0.10!] (Early Only)*, contest id 195955835, $0.10 each, $0.20 total.

Read once to establish what exists. Not modified, not submitted, not uploaded,
and structurally excluded from every projection input. No contest was entered
and no money was spent.

## 5. Model state — a refusal, preserved as a refusal

```
2026_03_CIN_PIT  REFUSED feature_build: STAGE_DECLARED_UNIMPLEMENTED
-- 0 board(s) written
```

This applies to all 9 slate games. It is corroborated by scheduled GitHub
Actions run `36257140735`, which refused all 15 Week-3 games with the identical
code — so the refusal is a property of the deployed system, not of my local
invocation.

The cause is declared debt, not a crash: `SYSTEM_STATE.json
.measured.work_queue.items[14]` records `feature_build` as
`DEFERRED[STAGE_DECLARED_UNIMPLEMENTED]` because the accepted research baseline
("prior-only, ordinal prefix cut") has no production implementation.

**Not produced tonight, and recorded as not produced:** mean, median, quantiles,
sd, cdf, carries, targets, routes, red-zone opportunity, team volume,
efficiency, participation, DK points.

No projection value is written anywhere in this artifact or its JSON twin. A
governed refusal is preserved instead of a fabricated number.

## 6. FantasyCruncher — universe overlap only

**The owner's rule, restated because this section is where it would be broken:**
FC projections, floor, ceiling and ownership may not be blended into our
projection, averaged against it, used to calibrate it, used to build our
distributions, or used to influence the football model. None of those values
appear in this artifact, not even as an unused column.

A projection comparison is impossible tonight anyway, because §5 means there is
nothing of ours to compare. So this is universe overlap and nothing else.

The FC file is a **broad Week-3 export**: 431 rows over **26 clubs**, eight of
which (ARI, BAL, DAL, LV, MIN, NO, SF, TB) are not on this contest. All 18 slate
clubs are present. 301 FC rows fall on slate clubs.

Overlap is reported at three join strengths, because a single overlap number is
a property of the join and not of the two files:

| join | overlap | FC-only | DK-only |
|---|---|---|---|
| raw lowercase name | 289 | 12 | 168 |
| normalized name | 297 | 4 | 160 |
| normalized name + team | 297 | 4 | 160 |

Normalization alone collapses 8 of the 12 apparent FC-only rows. Team
disagreements: **zero**.

The four residual FC-only rows — `andrew ogletree`, `josh palmer`, `nick
westbrook`, `ed williams` — are first-name and compound-surname variants the
normalizer cannot collapse, because it never measures distance. Two of them are
the same people as two of our six UNMATCHED rows (Drew Ogletree, Joshua Palmer):
one short-form/long-form problem broke both joins.

**Noting that is not permission to use it.** FC may not enter the identity chain
any more than it may enter a projection. Those six stay UNMATCHED until the
canonical roster resolves them.

### Completeness finding

FantasyCruncher carries **no row for 160 of the 457** DK-eligible players on
this slate — 14 QB, 40 RB, 32 TE, 74 WR — across the $2,500–$7,000 band. That is
35% of the rosterable pool, concentrated in exactly the depth tail that official
inactives promote into relevance on Sunday morning. Treating an FC export as the
contest universe would miss a third of it. The DK export is the authority and
this is the measured reason why.

**Withdrawn claim.** An earlier draft of this section said FC omits "all 18
DST". That is false — FC carries all 18 and every one matches at raw strength.
The figure was inferred from a by-position table that simply had no DST key,
rather than read. Corrected before commit.

## 7. What must be refreshed when Sunday news arrives

Frozen now: the contest universe, the identity chain, the owner entries, and the
model's refusal.

Still unknown tonight: official inactives, Sunday-morning injury and news
changes, and any projection at all.

To be refreshed on news: participation, role and depth, opportunity
redistribution to the players who inherit it, team-volume reconciliation,
simulation and the resulting distributions, DK point projections, and the
comparison layer.

**Redistribution must go through football logic.** An inactive player may not be
set to zero with everyone else left unchanged — the opportunity has to go
somewhere. The layer that would do this,
`nfl/production/nonqb/layers.py::participation()`, has since DEF-066 *refused*
with `PARTICIPATION_PRIOR_INCOMPLETE` rather than silently zeroing an absent
prior. A redistribution it cannot support will therefore be a refusal, not a
quiet wrong number.

**Vocabulary that has cost this project before:** QUESTIONABLE and DOUBTFUL are
**not** inactive. Only an official inactive-list entry marks a player inactive.
UNRESOLVED identity is not inactive either. UNKNOWN ≠ ZERO.
MISSING ≠ NOT PLAYING.

# DraftKings Week-2 salary universe — ingest and readiness

Ingested 2026-09-20T03:01:58Z. Every figure below was produced by
`nfl/dfs/salaries/build_artifacts.py` from the preserved bytes, not read off
the delivered file by eye.

## 1. Raw file provenance

| | |
|---|---|
| original filename | `draftkings_NFL_2026-week-2_players.csv` |
| sha256 | `c143c94f152a7d6bfb07ee84e5d88502c831fc672c0f7dc011984d85b28b2bec` |
| bytes | 48,936 |
| preserved as | `nfl/vintage/dk_salaries.c143c94f152a7d6b.csv.gz` |
| ingest time (UTC) | 2026-09-20T03:01:58Z |
| acquisition | `OWNER_SUPPLIED_DELIVERY` |
| role | `DOWNSTREAM_SALARY_AND_UNIVERSE_ONLY` |
| predictive use | `NOT_AUTHORIZED_BY_OWNER` |

Append-only. The gzip round trip was verified before anything was recorded —
decompressed bytes are identical and re-hash to the same digest. The raw bytes
are never edited; every derived object is a separate file.

**The ingest timestamp is not a publication time.** When DraftKings produced
these salaries is not observable from the file, and the record says so rather
than implying it.

## 2. Normalized shape

537 data rows, 24 columns, reproducing the owner's own inspection exactly:
32 teams, 16 matchups, 0 missing salaries, $2,000–$8,500, no duplicate names,
QB 86 / RB 116 / WR 184 / TE 119 / DST 32.

**One parsing hazard, worth naming.** The header is on **line 2**. Line 1 is
twenty-three commas. A `csv.DictReader` over the bytes as delivered takes that
line as the header and returns 537 rows keyed by the empty string, raising
nothing — the same shape as the 7,926-row export this project already had to
diagnose once. The loader locates the row whose first cell is `Player` and
raises `HeaderNotFound` if there is none.

### The column wall

**Kept** (salary / universe): `Player`, `Pos`, `Salary`, `Team`, `Opp`.

**Kept for reconciliation only**, never as truth: `Inj`, `pDepth`.

**Dropped at parse time — 17 columns**: `Def v Pos`, `VegasPts`, `STDV`,
`2025 Avg`, `2026 Avg`, `FC`, `My`, `Diff`, `Floor`, `Ceiling`, `FC Proj`,
`My Proj`, `Exp.`, `Used`, `Con.`, `Value`, `Likes`.

`Likes` was not on the owner's forbidden list; it is a third-party sentiment
count and is dropped on the same ground rather than carried because nobody
named it. `2025 Avg` and `2026 Avg` are dropped because the directive
authorises them only "unless separately justified" and nobody has justified
them.

This is **enforced, not documented**. `load()` never returns those columns, and
`column_disposition('VegasPts')` raises `ForbiddenColumn` — the test sets every
forbidden column to `99.9` and asserts the string `99.9` appears nowhere in the
returned rows.

### Team codes

DraftKings writes `JAC` and `LAR`; we write `JAX` and `LA`. Two entries,
declared in `DK_TO_CANONICAL`, not matched by similarity. All 32 normalised
codes land on ours, in both the `Team` and `Opp` directions.

## 3. Main-slate game universe — **UNRESOLVED**

`DEFERRED[DK_MAIN_SLATE_GAME_SET_NOT_SUPPLIED]`.

The file holds all 32 clubs and all 16 Week-2 games. Which of them a DK Classic
main slate covers is a fact about a **contest**, and no contest game list has
been supplied. It is not inferred from the file, and it is not inferred from
the usual shape of a main slate either — "Sunday 1pm and 4pm" is a convention,
not this contest.

So `RAW_DK_WEEK2_UNIVERSE` exists (537 rows) and
`DK_WEEK2_MAIN_SLATE_ELIGIBLE_UNIVERSE` does not.

**One exclusion is made without the contest**, because it needs no knowledge of
DraftKings at all:

| game | rows | reason |
|---|---|---|
| BUF–DET | **44** | kicked off 2026-09-18T00:15Z and is played. It cannot belong to a contest that has not locked. |

That is a clock fact. The other 15 games are **UNRESOLVED, not excluded**.

## 4. Identity reconciliation

Against 2,527 distinct canonical players from 8 roster vintages (2026 week 2).

| status | n |
|---|---|
| `MATCHED_CANONICAL` | **504** |
| `DST` | **32** |
| `UNMATCHED` | **1** |
| `AMBIGUOUS` | **0** |

Match methods: exact (name, team) 491, normalised (name, team) 12, declared
alias 1. **Zero duplicate `gsis_id`s. Zero team disagreements.**

**No edit distance anywhere.** Three deterministic passes; two names either
normalise to the same string or they do not. A fuzzy matcher would eventually
join Josh Allen the quarterback to Josh Allen the linebacker and would never
say it had — the test asserts that a one-character difference does **not**
match.

**The one alias.** `Hollywood Brown` (PHI) → `Marquise Brown`, gsis
`00-0035662`, PHI, WR, ACT. The roster holds exactly one Marquise Brown and no
player named Hollywood in any club: same club, same position, unique. Recorded
in `NAME_ALIASES` with that evidence, under its own match method so it never
hides inside "exact". An alias that stops resolving uniquely degrades to a
refusal rather than to a wrong join.

**The one unmatched.** `Ed Williams`, JAC, WR, $3,000. No `Ed Williams` in any
club in the roster capture; JAX carries `C.J. Williams` (WR) and
`Wesley Williams` (DL), neither of whom is Ed. **Not guessed.** Either DK lists
a player our roster vintage does not carry, or a name is wrong on one side.
Raised as OUT-030.

**One position disagreement**, recorded and not corrected: `Riley Nowakowski`
— DK `RB`, roster `TE`.

## 5. Injury-flag reconciliation

Governed source: `nfl/vintage/injuries.<hash>.csv.gz`, 246 rows for 2026 week 2
across all 32 clubs.

All eight DK-flagged players matched to a governed row. Seven carry
`Questionable`. **One does not:**

| DK name | team | DK | governed report | practice | injury |
|---|---|---|---|---|---|
| **Puka Nacua** | LA | `!` | **(none)** | **Did Not Participate In Practice** | Hip |
| Joe Burrow | CIN | `!` | Questionable | Full Participation | Back |
| Ladd McConkey | LAC | `!` | Questionable | Limited | Rib |
| Chris Olave | NO | `!` | Questionable | Limited | Hamstring |
| RJ Harvey | DEN | `!` | Questionable | Limited | Hamstring |
| Jalen McMillan | TB | `!` | Questionable | Full | Knee |
| Kaelon Black | SF | `!` | Questionable | Limited | Groin |
| DJ Giddens | IND | `!` | Questionable | Full | Knee |

Nacua is the one disagreement and the most consequential of the eight: DK flags
him, our governed report carries **no designation**, and he did not practise.
Recorded, not resolved — `!` is not authoritative and neither is a blank.

### The reverse check, which is the more interesting one

Our governed evidence carries **46 players Out or Doubtful**, 14 of them at
skill positions — Kyler Murray, Sam Darnold, Nico Collins, Brock Bowers, Zay
Flowers, Tua Tagovailoa among them. **Not one of the 46 appears in the DK
file**, verified by `gsis_id` and independently by normalised name.

Read carefully: this is consistent with DraftKings having withdrawn ruled-out
players before publishing, and therefore with the file being at least as recent
as those rulings. **Neither that convention nor the file's publication time is
established here**, so it is corroboration to note, not a fact to rely on.

## 6. Football coverage — and why there are no projections in this join

**There are no projections in the join, and that is not an omission.**

No board sealed for 2026 week 2. `artifact_sealing` BLOCKS every game of the
slate on `current_season_input_freshness`, under both the production baseline
and the candidate configuration (`nfl/SUNDAY_READINESS.md`). There is no
forecast to attach a salary to, so every distribution field —
mean, median, p05, p10, p25, p50, p75, p90, p95, P(zero), MCSE, draws ref —
is **null with a stated reason**, never backfilled from `FC Proj` or `My Proj`.

What *is* answerable is coverage: whether this system can project a player at
all. Read from the rehearsal runs' draw manifests, which carry `row_ids` on a
`gsis_id` axis. That is a statement about the model's reach, not a forecast —
those runs are REFUSED runs, and a number lifted out of one and printed beside
a salary would be the absence-read-as-success defect this project exists
downstream of.

| | n |
|---|---|
| DK rows matched to a canonical id | 504 |
| of those, the model reaches (`MODEL_COVERED_FORECAST_NOT_SEALED`) | **412** |
| `DK_ELIGIBLE_MODEL_UNSUPPORTED` — person | **92** |
| `DK_ELIGIBLE_MODEL_UNSUPPORTED` — DST | **32** |
| `DK_ELIGIBLE_IDENTITY_UNRESOLVED` | 1 |
| modelled players absent from the DK file | 54 |

**The 92 are not mysterious. They decompose exactly onto the games that refuse:**

| n | game | why |
|---|---|---|
| 42 | BUF–DET | refused at `capture_validation`; played Thursday, no draws exist |
| 27 | LA–NYG | appearance halted for the whole game — NYG `report_status` unfilled on every row |
| 9 | DEN–JAX | JAX deferred, `INJURY_REPORT_INCOMPLETE` |
| 6 | CHI–MIN | CHI deferred, `INJURY_REPORT_INCOMPLETE` |
| 8 | scattered | deep bench — QB3, WR5, WR6, TE3, RB4 — at or near minimum salary |

84 of 92 are the four known refusals already in the readiness report. Fixing
those three injury reports (OUT-027) would recover 42 of them.

## 7. Validation

| check | result |
|---|---|
| raw rows | 537 |
| main-slate-eligible rows | **UNRESOLVED** |
| matched / unmatched / ambiguous / DST | 504 / 1 / 0 / 32 |
| duplicate identities | **none** |
| team↔opponent inconsistencies | **none** |
| salaries missing or malformed | **none** |
| teams represented | 32 |
| salary range | $2,000 – $8,500 |
| **inactive/out players carrying modelled opportunity** | **0** |

That last row is the one worth dwelling on: no player our governed evidence
lists as Out or Doubtful carries a modelled opportunity in the DK join. It is
0 partly because the engine's own availability layer does its job, and partly
because DK had already withdrawn those players.

## 8. DK scoring and site contract — **BLOCKED for Classic**

The certified DK scoring adapter exists and runs: `dk_scoring/dk_points` is
produced for every covered player on every rehearsal run. **The site contract
is the blocker.**

`nfl/dfs/scoring/site_rules.py` holds two contracts — `DRAFTKINGS_SHOWDOWN`
and `FANDUEL_SINGLE_GAME`. **There is no DK Classic contract at all**: no
salary cap, no roster slots, no FLEX rule, no minimum-teams rule, no
eligible-game set. That is OUT-025's DK half and it is unchanged by this file.

And the harder one: **a Classic lineup must field a DST, and the engine
produces no team-defence outputs at all** (`statline.NOT_SIMULATED`:
"the engine produces no team-defence outputs at all"). All 32 DSTs in this file
are `DK_ELIGIBLE_MODEL_UNSUPPORTED`. A salary for a thing we cannot score is
not a step toward scoring it.

## 9. Does this dataset unblock any Sunday item?

**No existing blocker moves.** Precisely:

| Sunday item | moved by this file? |
|---|---|
| SUN-5 — no 2026 denominator panel, sealing refuses | **no** — unrelated, upstream |
| SUN-6 — `feature_build` unimplemented | **no** — unrelated, upstream |
| SUN-3 — three clubs' injury reports | **no** — but this file corroborates 46 Out/Doubtful |
| SUN-2 — T-90 windows on the default branch | **no** |
| DFS full-slate legality | **no** — no Classic contract, no DST model |

What it *does* supply, and it is real: the salary and player universe, joined
to canonical identity at 504 of 537 rows with zero ambiguity, and an
independent cross-check on our injury capture. That is the fourth arrow of the
chain. The first three are still blocked.

**A salary file is not permission to bypass an upstream football blocker**, and
nothing here was built toward a 150-max portfolio.

## 10. Classification

**READY** — raw preservation, normalized shape, the column wall, team
crosswalk, identity reconciliation (504/537, 0 ambiguous, 0 duplicates), the
injury cross-check, salary validation.

**PARTIAL** — model coverage: 412 of 504 matched players are reachable, and the
92 that are not are fully explained.

**BLOCKED** — main-slate eligibility (no contest game set), every projection
field (no sealed board), DK Classic legality (no contract, no DST model), and
therefore any lineup at all.

**WILL NOT BE USED** — every dropped column. No FantasyCruncher projection,
Vegas total, ownership estimate, floor, ceiling or optimizer metric enters a
football layer, now or behind a flag.

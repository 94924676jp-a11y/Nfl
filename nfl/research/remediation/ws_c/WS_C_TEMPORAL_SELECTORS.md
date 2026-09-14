# WS-C — one cutoff-aware selector per perishable source family

Branch `claude/nfl-greenfield-architecture-stsxmk`, baseline HEAD `837d52f`,
`python3.12`. Every number below was measured on this checkout, not recalled.
`nfl/production/nonqb/layers.py` was **not** edited and is byte-identical; it is
hashed by Q9's frozen candidate identity `481f005f682cd721`.

**No git command was run.** No commit, add, stash or push. The full suite was
not run.

---

## DEFECT

The chronology **gate** and the **feed the model actually eats** were two
different selectors and only the gate had a clock.

| | selector | bound applied |
|---|---|---|
| gate | `readiness.team_readiness` | `min(written_at, kickoff)` — but `layers.py:117` never passes `written_at` |
| feed | `layers.py:145` → `readiness.latest_injuries_rows` | **none at all** |

Reproduced at HEAD before any edit:

```
L1  latest_injuries_rows(2026) retrieved_at = 2026-09-13T23:12:09.422344+00:00
    rows returned                           = 182
    teams whose kickoff it is AT OR AFTER   = 28 of 32

L2  85 player-rows differ across the 20 teams of the 10 executable week-1
    games, at a written_at of kickoff minus 24 hours
    ARI 5  ATL 11  BAL 4  CAR 2  CHI 6  CIN 5  CLE 2  DAL 2  DET 3  IND 4
    JAX 2  LA  7   LAC 4  NO 5   NYG 2  NYJ 4  PIT 1  SF 11  TB 4   TEN 1

L3  board.depth_rank(2026, 1, ('DAL','NYG')) resolved to the chart stamped
    2026-09-08T11:56:57Z from depth_charts.f57ef0724d907160 — the LAST blob in
    filename order, neither the newest (2026-09-13T12:42:08Z) nor the
    point-in-time one. Five days stale for a Sunday-night forecast; 24 hours
    AFTER the cutoff of a forecast written 2026-09-07T12:00Z.
```

## ROOT CAUSE

Three causes, one class.

1. **Selection without a clock is spelled the same as selection with one.**
   Nothing in the tree made `latest_injuries_rows(season)` illegal, so the
   unbounded call compiled, ran, and looked like an answer.
2. **The rule lived in four copies.** `readiness.as_of_cut`,
   `depth_vintage.daily_point_in_time`, `roster_status.status_map` and
   `information_set.build` each held their own version of "what may I read".
   Three of them drifted; `roster_status` did not, which is why it was the
   only family WS12 scored PROVEN_CLEAN.
3. **The cut was applied AFTER selection instead of AT it.** `readiness`'s own
   docstring already records this for the gate — "The guard was right and the
   selector never looked" — and the same shape was still live in the feed, in
   `board.depth_rank`, and in `board.roster_identity`.

## REPAIR

New module `nfl/production/nonqb/vintage_selector.py`. One selector per
declared family; there is **no way to call it without a clock**.

* `resolve_as_of` takes an explicit `as_of`, else a declared
  `vintage_selector.clock(...)` context, else **raises**
  `VintageClockUnresolved`. An explicit `as_of=None` is refused too: None never
  means "no bound".
* Selection is `max(retrieved_at, content_sha256)` over the lawful candidates.
  Forbidden and stated in the evidence of every answer: filesystem mtime, glob
  order, filename order, file size, row count.
* One row per distinct **content**, at its **earliest** observation — the
  capture workflow re-fetches on a schedule and records a PASS row each time.
  Taking the latest `retrieved_at` for a content hash would have excluded bytes
  from a cut falling between the first sighting and a re-fetch, even though
  they demonstrably existed at the first.
* Every selection returns source identity, `retrieved_at`, publication time
  with its authority, content hash, a chronology verdict from a **closed**
  vocabulary, a fallback reason, and an **evidence ceiling**.
* Rejections are returned alongside, each with the reason. "There was nothing"
  and "there were six and all of them were late" are different answers.

Rewired on top of it:

| file | change |
|---|---|
| `readiness.py` | `as_of_cut` and `_parse_ts` delegate; `_all_injury_captures` delegates; NEW `lawful_injuries_rows`; `latest_injuries_rows` refuses without a clock; the gate picks `written_at` up from a declared context (L2) |
| `board.py` | NEW `depth_rank_outcome` / `roster_identity_outcome`, both cutoff-aware; the dict forms raise instead of returning a silently wrong or empty map; `build` derives its cut from the sealed artifact and records refusals on the board |
| `roster_status.py` | selection delegated to the shared selector; the ISO **string** comparison (WS12 E4) replaced with parsed instants; both guards unchanged |
| `depth_vintage.py` | RL-10 — `pos_slot` refuses instead of defaulting to 0; durability ceiling attached to every answer |

### THE FEED IS A COMPOSITION, NOT A FILTER — and that was not optional

Bounding the old "newest file on disk" to the cut is necessary and **not
sufficient**, because the injuries feed is **not monotone**. Measured over the
seven 2026 blobs, week 1 only:

```
2026-09-07T13:06Z   2 teams,  11 rows
2026-09-08T17:06Z   2 teams,  11 rows
2026-09-10T05:05Z   4 teams,  29 rows
2026-09-10T12:07Z  30 teams, 139 rows
2026-09-11T12:19Z  32 teams, 167 rows
2026-09-13T12:47Z  20 teams,  48 rows   <- SHRINKS
2026-09-13T15:45Z  32 teams, 182 rows
```

A team that filed on the 11th and is absent from the 12:47 capture on the 13th
is not a team with nobody injured. The **gate** has composed per-team since R4;
the **feed** took one file. So they could disagree even inside the lawful
window. `lawful_injuries_rows` composes exactly the gate's rule, generalised
over weeks so it needs no `week` argument, and records per-block provenance so
"gate and feed chose the same vintage" is checkable rather than argued.

### THE layers.py CONSTRAINT, AND HOW IT WAS MET WITHOUT EDITING IT

`layers.py:145` is `rows = RD.latest_injuries_rows(season)` — one argument, in
a frozen file. The clock is therefore declared **upstream** and honoured
downstream, which is the C1 pattern: `football_engine.run_game` wraps the layer
chain in `vintage_selector.clock(written_at=observed_before,
kickoff_utc=kickoff_utc)`. That patch is written, proven, and **handed over
un-applied** (P1 in `WS_C_CALL_SITE_PATCHES.md`) because `football_engine.py`
is WS-B's.

**I did not stop and escalate**, because layers.py is not the only correct
site: the corrected behaviour sits entirely in files WS-C owns, and the caller
only has to say what its cutoff is.

Until P1 lands there is a **transitional third path**, and it is marked as
such in the code, in the evidence of every answer, and here. The gate is
evaluated two lines above the feed, on the same season, week and kickoff, so it
**publishes the cut it used and the feed consumes it**:

* the handoff is **consumed once** — a second feed read without a fresh gate
  evaluation refuses, so a cut cannot be reused across games;
* where several gate evaluations are outstanding (the slate-wide branch), the
  **minimum** is taken, which is the earliest kickoff on the slate and is
  lawful for every game judged;
* an explicit `as_of` and a declared context both **beat** it and clear it, so
  P1 retires this path without anyone removing it;
* every answer carries `clock_basis` = `EXPLICIT` / `DECLARED_CONTEXT` /
  `GATE_HANDOFF`, so an un-rewired call site is visible in the artifact.

## WHY THIS REPAIR

The alternative was to bound the existing selector in place and leave four
copies of the rule. That is what produced the defect: the gate was bounded in
R4, the feed was not, and nothing could tell. A shared selector makes the
divergence impossible to express, and the closed chronology vocabulary means a
consumer cannot invent a fifth verdict.

Two things were deliberately **not** changed, because one repair should have
one effect:

* `board.depth_rank` still returns the vendor's **raw** `pos_abb` / `pos_rank`.
  `depth_vintage` re-ranks onto a common ordinal scale to bridge the vendor
  break; swapping that in here would move R6 tiers for a reason unrelated to
  chronology.
* RL-10 does not re-rank anything. Proven below.

## PRE-REPAIR FAILURE

Reproduced at HEAD, above: 28 of 32 teams fed a post-kickoff capture; 85
player-rows of `written_at` gap; a depth chart chosen by content-hash order.

## POST-REPAIR RESULT

**Gate and feed name the same blob, for every team, at every cut tested:**

```
cut 2026-09-13T16:59:59.999999Z  gate_teams 32  feed_blocks 32  mismatches 0
cut 2026-09-12T12:00:00Z         gate_teams 32  feed_blocks 32  mismatches 0
cut 2026-09-11T00:34:59.999999Z  gate_teams 30  feed_blocks 30  mismatches 0
cut 2026-09-10T00:19:59.999999Z  gate_teams  2  feed_blocks  2  mismatches 0
```

**Equivalence where the old selector happened to be right.** The old feed was
lawful only under a cut at or after the newest capture. There:

```
old newest capture 2026-09-13T23:12:09Z, 182 rows
new composed feed                        182 rows, from ONE blob
identical key sets           True
differing rows, shared keys  0
```

Byte-identical. So the diff isolates exactly the cases where the old selector
was wrong.

**Depth, point-in-time:**

```
as_of 2026-09-07T12:00:00Z -> dt 2026-09-06T11:29:30Z  (24.51h before the cut)
as_of 2026-09-13T20:00:00Z -> dt 2026-09-13T12:42:08Z  ( 7.30h before the cut)
as_of 2026-08-01T00:00:00Z -> BLOCKED[DEPTH_RANK_CAPTURE_ABSENT]
```

versus the single 2026-09-08 chart the old code returned for all three.

### THE HONEST SELECTOR REFUSES MORE GAMES, AND THAT IS THE CORRECT OUTCOME

This is the number that matters most and it is not a comfortable one.
`game_readiness` on 2026 week 1, executable games:

```
kickoff-bounded (the leaking gate)     10 of 16
written_at = kickoff - 0.5h            10 of 16
written_at = kickoff - 2h               8 of 16
written_at = kickoff - 6h               3 of 16
written_at = kickoff - 12h              1 of 16
written_at = kickoff - 18h              0 of 16
written_at = kickoff - 24h              0 of 16   (15 INCOMPLETE, 1 NOT_YET_FILED)
```

**Nothing was weakened to recover any of this.** The reading is not that the
model got worse. It is that with the captures currently retained, this system
cannot honestly forecast week 1 at any lead time beyond a few hours, because
the pre-kickoff game-status filings it needs were **not captured before those
cutoffs**. The 10-of-16 figure was only ever reachable by reading bytes
retrieved after the forecast's own cutoff.

That is a **capture-cadence finding, not a model finding**, and it is WS-K's
and the capture layer's to act on, not WS-C's. It is stated here because a
coverage drop of this size must not be discovered later and mistaken for a
regression.

### RL-10 — `pos_slot`

`depth_vintage._daily_rows` read `int(r.get('pos_slot') or 0)` against blobs
whose header is `dt,team,gsis_id,pos_abb,pos_rank`. Reproduced independently on
all six persisted reduced blobs: the column is absent from **every row of every
blob** (2,176–2,222 rows each).

The repair is **not** a blanket refusal, because two different ties were being
conflated and only one is `pos_slot`'s business:

* **Vendor tie** — two players at the same `(team, dt, RAW pos_abb, pos_rank)`.
  This is what `pos_slot` orders. Measured: **0 of 586** groups. It has never
  fired. Now a named `FAIL[DEPTH_DAILY_POS_SLOT_REQUIRED_AND_ABSENT]`.
* **Normalisation tie** — same `(team, dt, NORMALISED pos, pos_rank)` but
  different raw positions, because `_NORM` folds FB and HB into RB. Measured on
  `depth_charts.a14e8dfe865a4b03`: **14 of 572** groups, 13 of them `{FB, RB}`
  and one `{FB, KR, RB}`. `pos_slot` orders *within* one `pos_abb` and could
  not have resolved these even if present. This module's own normalisation
  created the collision, so the tiebreak is this module's to declare —
  `gsis_id`, which is what `or 0` produced by accident. It is now recorded.

**No depth rank in this repository moves.** The pre-repair algorithm was
reproduced inline and compared on all six blobs:

```
361f1c69443cba69  identical  575 ranked players
76d7bcb384ec11e3  identical  576
a14e8dfe865a4b03  identical  586
db0a09454965e6fc  identical  572
ecc4973e8715d866  identical  576
f57ef0724d907160  identical  575
```

Measured harm today is **zero**. It is recorded that way so this is not
mistaken for a bug fix with an outcome. What a silent 0 could never have told
anyone is what happened on the three lost vintages.

The check also exists at the selector, where it belongs:
`vintage_selector.column_check` and `select(..., require_columns=...)` turn
"lawful on the clock but missing a declared column" into
`FAIL[VINTAGE_DECLARED_COLUMN_ABSENT]`. **A lawful vintage whose bytes lack a
declared column is not a successful selection.**

### RL-11 — `ingest_inactives.consumed_slice`

Reproduced independently against every `CONSUMED` entry:

```
schedules:       declared 8, missing []
weekly_rosters:  declared 4, missing ['status']
injuries:        declared 4, missing []
depth_charts:    declared 5, missing []
```

`nfl/tools/ingest_inactives.py` is not WS-C's. Patch P5 is handed over
un-applied. It names the choice rather than making it: narrow `CONSUMED`, or
retain `status` in the capture reduction — **not both silently**.

### Evidence ceilings now travel with the answer

* **Depth durability.** 171 of 177 captured `dt` slices are persisted nowhere;
  6 reduced blobs survive, one `dt` each. `depth_vintage` attaches this to
  every answer, PASS and DEFERRED alike, because a successful selection does
  not close the ceiling. Point-in-time resolution is only as dense as what
  survives, and the correct answer for a cut with no stored slice is the
  ceiling, never the nearest chart.
* **Publication authority (WS12 E3).** For `official_inactives` and
  `official_injury_report` the "source-provided exact timestamp" is the HTTP
  `Date` header — retrieval time, lag 0.000h in 188 of 188 rows. The selector
  annotates the authority so `published_at` cannot be read as the league's
  clock.
* **Schedules (L4).** Declared as a family with a working clock-aware selector,
  and the ceiling still reads UNPROVABLE. **No leak is claimed and none was
  measured.** What is measured is that neither existing selector takes a clock.

---

## TEST

`nfl/tests/test_vintage_selector.py` — **24 test functions, 127 checks, 0
failing, 0 raised.** Run with `python3.12 nfl/tests/run_suite.py --only
test_vintage_selector`. Several checks build their own manifest and blobs in a
temp directory, so they do not go stale when the capture tree moves.

The six required cases, each its own function:

1. a capture retrieved after kickoff is **not selectable** — and is rejected
   **by name**, not merely absent;
2. with two lawful pregame captures, the **later** one is selected;
3. with no lawful capture, a named `BLOCKED[VINTAGE_NO_LAWFUL_CAPTURE]` that
   counts what it refused and carries the ceiling — never a silent empty;
4. **gate and feed resolve to the same vintage**, per team, at four cuts;
5. **filesystem ordering cannot change the selection** — 25 permutations of the
   manifest read order, plus touching a blob to the newest mtime on disk, plus
   a synthetic depth fixture whose filename order is the reverse of its `dt`
   order;
6. **replay at a historical `written_at`** picks the historically available
   vintage, is not the newest on disk, and is idempotent.

Plus: every selector refuses without a clock; the declared clock reaches a
selector it cannot be passed to (the layers.py constraint, executable); the L2
gate takes `written_at` from the declared clock and is *allowed to refuse a
game the leaking gate passed*; equivalence at an open cut; the non-monotone
feed; depth point-in-time; RL-10's two tie kinds; RL-10 changed no rank; the
declared-column check; and the durability ceiling.

The RL-10 equivalence check compares **one capture at a time** against the
pre-repair algorithm. It deliberately does not compare across captures: WS-L
measured upstream **restating `gsis_id`** in historical snapshots — 2,363 rows
across 133 of 170 slices, in both directions — so two captures of the same
slice can disagree on the join key without either being wrong.

## BLAST RADIUS

Suites run (never the full suite), after the repair:

```
test_vintage_selector        24 fn  127 checks  PASS
test_readiness_vintage_cut    9 fn   30 checks  PASS
test_r5_active_pool           8 fn   21 checks  PASS
test_inactives_propagation   19 fn   43 checks  PASS
test_football_engine_r4      17 fn  142 checks  PASS
test_nonqb_r3                28 fn  129 checks  PASS
test_non_g0a_isolation       12 fn   52 checks  PASS
test_r7_appearance_frame     20 fn   67 checks  PASS
test_r6_role_prior            8 fn   24 checks  PASS
```

`test_product_orchestration` reports 2 failing checks — *"every array that
moved since the stored board was a DECLARED change: undeclared
`qb__cmp`, `qb__ptd`, `qb__pyds`"*. **These are QB draw arrays.** WS-C touches
no QB layer; the non-QB arrays do not move. The working tree carries concurrent
edits from other workstreams to `run_forecast.py`, `pipeline.py`,
`prospective/artifact.py` and `capture/coverage.py`. Flagged to the
coordinator; **not attributed to WS-C and not claimed as clean either** — it
should be re-checked once the pass is serialised.

Behaviour changes a reviewer should expect:

* `latest_injuries_rows` / `depth_rank` / `roster_identity` **raise** rather
  than returning an unbounded or empty answer. Three call sites need the
  handed-over patches: `run_forecast.py:681` (WS-D), `score_game.py:83`, and
  optionally `slate_rehearsal.py:40`.
* `roster_status.status_map(observed_before=None, kickoff_utc=KO)` now applies
  the kickoff bound **at selection**, so a case that previously selected a
  post-kickoff capture and then FAILED
  `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF` now selects the lawful earlier one and
  PASSES. This is the same "the guard was right and the selector never looked"
  repair `readiness` already carries. The content guard is untouched.
* The `written_at` boundary moved by one microsecond, from `retrieved_at <
  written_at` to `retrieved_at <= written_at`, which is the contract
  `as_of_cut` states.
* `readiness.report` now says `clock_view: BOUNDED_REPLAY` or
  `UNBOUNDED_OPERATOR_DASHBOARD`. The unbounded dashboard is kept on purpose —
  it is the right answer to "what does the feed look like right now" — and is
  labelled so it cannot be mistaken for a bounded one.
* Boards carry a `vintage_selection` block with the cut, what was chosen, and
  any refusals.

## IDENTITY IMPACT

* `nfl/production/nonqb/layers.py` — **UNTOUCHED.** `481f005f682cd721` holds.
* No freeze file was read, written, or re-hashed.
* No QB module, allocator, coefficient, standardiser or prior was touched.
* No seed, draw count or RNG stream changed.
* `depth_vintage` ranks are byte-identical on all six persisted blobs.
* `readiness`, `roster_status`, `board` and `depth_vintage` carry new
  `spec_version` provenance in their evidence (`vintage-selector-1`); the
  frozen mechanism spec versions are unchanged.
* Injury rows consumed by the appearance mechanism **do** change whenever the
  old selector was unlawful — that is the repair, and it changes appearance
  probabilities for any run whose cut is earlier than the newest capture.
  Anything sealed before this lands was produced under the leaking selector and
  cannot be compared to anything produced after it as though the configuration
  were the same.

---

## STATUS PER SOURCE FAMILY

| family | before (WS12) | after |
|---|---|---|
| **Injury reports** | PROVEN_LEAKING (L1, L2) | **REPAIRED** — one composed selector, cut applied at selection, gate/feed identity proven at four cuts, 0 mismatches |
| **Depth charts** | PROVEN_LEAKING on the R6 path (L3) | **REPAIRED in the selector; the R6 CALL SITE IS UN-PATCHED** — `run_forecast.py:681` is WS-D's. Until P2 lands, the R6 tier fallback is a recorded refusal rather than a wrong chart |
| **Rosters** | PROVEN_CLEAN | **PROVEN_CLEAN, preserved** — routed through the shared selector, both guards intact, E4 string comparison fixed |
| **Schedules** | UNPROVABLE | **UNPROVABLE** — declared family, working clock-aware selector, no leak claimed, no verdict upgraded. Both existing call sites un-patched (P6, design only) |
| **`pos_slot` tiebreak (RL-10)** | not scored | **REPAIRED** — refuses where it would decide, declared where it would not, measured harm zero, no rank moved |
| **`consumed_slice` columns (RL-11)** | not scored | **PATCH HANDED OVER** — reproduced (`weekly_rosters` missing `status`), `ingest_inactives.py` is not WS-C's |
| Transactions / weather / snap counts / play-by-play | PROVEN_CLEAN by non-consumption | unchanged, not touched |
| Historical panels | UNPROVABLE | unchanged, not touched |

**Nothing is BLOCKED-ON-FREEZE.** The frozen module never needed editing.

## FILES CHANGED

```
nfl/production/nonqb/vintage_selector.py   NEW
nfl/tests/test_vintage_selector.py         NEW
nfl/production/nonqb/readiness.py          modified
nfl/production/nonqb/depth_vintage.py      modified
nfl/production/nonqb/roster_status.py      modified
nfl/product/board.py                       modified
nfl/research/remediation/ws_c/WS_C_TEMPORAL_SELECTORS.md    NEW (this file)
nfl/research/remediation/ws_c/WS_C_CALL_SITE_PATCHES.md     NEW (un-applied)
```

Every one is inside WS-C's exclusive ownership. Nothing else in the tree was
written by this workstream.

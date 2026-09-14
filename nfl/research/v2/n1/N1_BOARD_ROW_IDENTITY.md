# N1 — the board row that renders a gsis_id where a person belongs

Measured 2026-09-14. Every number below was read out of a run in this checkout.
Nothing here is recalled.

## 1. The frozen-identity check, first and last

`nfl/production/nonqb/layers.py` is hashed into candidate identity
`481f005f682cd721` and was not to be touched.

| When | sha256 (first 16) |
|---|---|
| Before any edit | `481f005f682cd721` |
| After all edits  | `481f005f682cd721` |

Full digest both times:
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`.
The file is also absent from `git status --porcelain nfl/production/`
throughout. I did not open it for writing.

## 2. Before and after

Both numbers are from `quality_gates.evaluate()` run by me, output read.

| Board | `IDENTITY_DEPTH_ROLE_CONFLICT` FIRED | PASS | total findings |
|---|---|---|---|
| `research/live/.../V1_CANDIDATE_R9/d1e2727743c93990` (pre-repair) | **20** | 0 | 139 |
| `research/v2/n1/trial_after/5d7829c0be9ec550` (post-repair) | **0** | **19** | 138 |
| `research/v2/n1/trial_v3/b282c52f7976c682` (post-repair, later tree) | **0** | **33** | 203 |

The third row is a full end-to-end rebuild finished after the first two. It is
**not** a like-for-like comparison and section 8.3 says why — another agent's
DEN repair landed in between and the board grew from 19 rows to 33. It is
reported because it answers the one question the 19-row pair cannot: the name
join holds on rows that did not exist when I wrote it. 33 of 33 resolve, 0
unresolved, fallback still not consulted.

Every other gate is unmoved, which is the point — this was a display join and
it should have changed nothing else:

| Gate | pre | post |
|---|---|---|
| COUNT_SUPPORT_FAILURE | 99 PASS | 99 PASS |
| DEGENERATE_DISTRIBUTION_WIDTH (soft) | 5 FIRED | 5 FIRED |
| HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY | 2 PASS | 2 PASS |
| QB_ROOM_SPLIT_ANOMALY | 2 FIRED | 2 FIRED |
| ROLE_STATE_SOURCE_CONFLICT | 2 FIRED | 2 FIRED |
| RUSH_ACCOUNTING_FAILURE | 1 FIRED, 1 PASS | 1 FIRED, 1 PASS |
| UNATTRIBUTED_OPPORTUNITY_MASS | 2 FIRED, 4 PASS | 2 FIRED, 4 PASS |
| AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY | 1 INSUFFICIENT_EVIDENCE | 1 INSUFFICIENT_EVIDENCE |

139 → 138 because the 19 row findings flip FIRED → PASS and the 20th finding,
the board-scope escalation, stops being emitted at all.

The remaining hard FIRED count is 7 (2 + 2 + 1 + 2), consistent with the brief's
27 hard findings of which 20 were identity.

## 3. Three things in the brief, and in the gate's own text, that are wrong

### 3.1 "20 of 19 board rows (every row, some twice)"

No row fires twice. The 20 is **19 row-scope findings, one per row, plus one
board-scope finding**. The board-scope one is the escalation
`gate_identity_depth_role` emits when `n_nameless == n_rows`
(`quality_gates.py:831-840`), and it carries `action = WITHHOLD_BOARD` rather
than `WITHHOLD_ROW`. Measured subjects: 19 distinct `TEAM/gsis_id` strings and
one `BOARD`.

### 3.2 The gate's stated cause is right about the defect and wrong about this board

The gate says, verbatim:

> the reduced roster vintage the board DOES read drops `full_name` in its
> `reduce_cols`

Tonight's board did **not** read the reduced vintage. Its own
`board.json → vintage_selection.roster.blob` is
`nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz` — the **raw** form,
whose header carries `full_name` in position 7 of 36. I read the header.
`information_set.blob_for()` globs `weekly_rosters.<sha16>.*` and takes
`hits[0]`, and `.raw.csv.gz` sorts before `.reduced.csv.gz`, so the raw blob is
what `make_board` handed to `board.build`.

So the name was in the bytes the board already had open. The actual cause is
one line narrower than the gate's account: `board.roster_identity_outcome`
extracted `position` and `team` from each row and nothing else. The
`reduce_cols` sentence is a true statement about a path this board did not
take — it would have been the cause had the selector returned the reduced blob,
and it still is for any board that does, which is why the repair handles that
case explicitly rather than assuming the raw blob is always there.

### 3.3 "the board does not call `names.py`" — true only of `board.json`

`nfl/tools/make_board.py:252-253` already does

```
NM.cache_clear()
md = R.render(bd, names=NM.lookup(written_at))
```

so `BOARD.md` in the pre-repair R9 directory **already reads**
`| Patrick Mahomes (KC QB1) | Pass attempts | 35 | ...`. The human-readable
render has carried real names all along. What had no name was the
machine-readable `board.json`, which is what the gate evaluates. Worth saying
plainly because it changes the severity: the product was not shipping gsis_ids
to a reader, it was shipping a board artifact that could not prove it knew who
its rows were.

## 4. Was dropping `full_name` deliberate? Yes. It is not reversed.

`nfl/capture/registry.py:185` declares, for `weekly_rosters`:

```
required=False, durability="reduce",
reduce_cols=("season", "week", "team", "gsis_id", "position"),
```

and `nfl/tools/capture_vintage.py:839 _reduce_frame` states in its own
docstring that **its output bytes are the artifact's identity** and that any
change to the column set "needs a TRANSFORM_VERSION bump". The reduction is a
retention decision with a hashed transform behind it.

Two reasons not to touch it, either of which is sufficient:

1. Widening `reduce_cols` changes the identity of every blob written
   afterwards, and `registry.py` is outside the files I own.
2. It would do nothing for any blob **already stored** — the bytes on disk do
   not grow a column retroactively. The 2026-09-14 board needs a name from a
   capture that already exists.

So the repair adds no column to any capture and changes no stored byte. It
reads a column that is already present where it is present, and selects a
second lawful capture where it is not.

## 5. What was changed

Two files, both on my owned list.

### `nfl/product/board.py`

- `roster_identity_outcome` now also reads a name column from the blob it is
  already reading, and reports in its evidence which name columns the blob
  carried (`name_columns_present`), whether it carried none at all
  (`name_column_absent` — a different state from carrying one and finding
  nothing), and how many players it named (`n_named`).
- `build()` puts `name` and `name_provenance` on every row, and a
  `name_resolution` block on the board.
- `_name_fallback()` is consulted **only** when the primary left a row unnamed.
  A board whose own roster blob names everyone opens no second file.

### `nfl/product/names.py`

- Reads the **committed** `nfl/vintage/weekly_rosters.*.raw.csv.gz` as well as
  the ephemeral store. This matters more than it looks: `nfl_vintage/` is
  gitignored (`.gitignore:7`), so before this change `names.lookup()` resolved
  2,962 ids in this working copy and would have resolved **182** in a fresh
  clone — the injuries blobs only. Measured both ways.
- Precedence is chronological. The old form merged blobs in `sorted(glob(...))`
  order with `setdefault`, so a disagreement between two lawful captures was
  settled by a content hash in a filename — the same defect
  `board.depth_rank_outcome` documents as L3. Captures are now ordered by the
  observation time the manifest bounds them with and the newest lawful one
  wins.
- `resolve()` returns per-id provenance: blob, column, observation time.

**The one observable consequence of the precedence change, stated so nobody
finds it later and calls it a regression.** Of 2,962 ids, exactly **4** change
spelling, because exactly 4 carry more than one spelling across captures:

| gsis_id | was (filename order) | now (newest lawful capture) |
|---|---|---|
| 00-0038411 | Anthony Johnson Jr. | Anthony Johnson |
| 00-0038603 | Robert Beal Jr. | Rob Beal Jr. |
| 00-0039454 | Beanie Bishop Jr. | Beanie Bishop |
| 00-0040093 | Melvin Smith Jr. | Melvin Smith |

None of the four is on the DEN@KC board. The new value is the vendor's own
spelling in the 2026-09-14T16:16:25Z capture. I did not pick between them and
nothing here prefers the longer or the shorter form; the rule is "newest lawful
capture", applied blind.

## 6. Where the names came from, and their provenance

For the DEN@KC rebuild, all 19 came from the **primary** path — the board's own
selected roster vintage, read for a column it already had open.

```
name_resolution.primary = {
  "source": "weekly_rosters",
  "blob": "nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz",
  "basis": "CALLER_SUPPLIED_BLOB",
  "name_columns_present": ["full_name"],
  "name_column_absent": false,
  "n_named": 180
}
name_resolution.fallback.consulted = false
  ("the roster vintage this board selected named every row;
    no second source was opened")
```

That blob is observed at **2026-09-14T16:16:25Z**, which is 4h42m before the
board's cut of 2026-09-14T20:58:33Z and 7.98h before kickoff. It is the same
blob `board.json → vintage_selection.roster` already named, and it is tracked
in git. **Nothing post-cut is read**: `names._candidates()` drops any capture
whose manifest-bounded observation is after the cut, and drops any capture the
manifest cannot date at all rather than using it unclocked. A cut of
2020-01-01 resolves zero names, which is asserted in the test.

Per row, `name_provenance` carries source, blob, column and basis. Example:

```
{"source": "weekly_rosters",
 "blob": "nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz",
 "column": "full_name",
 "basis": "CALLER_SUPPLIED_BLOB",
 "selected_for": "the roster vintage this board already selected,
                  read for its own name column"}
```

### The 19 rows

| team | gsis_id | pos | depth | name |
|---|---|---|---|---|
| KC | 00-0033873 | QB | QB1 | Patrick Mahomes |
| DEN | 00-0039732 | QB | QB1 | Bo Nix |
| KC | 00-0036945 | QB | QB2 | Justin Fields |
| KC | 00-0040906 | QB | QB3 | Garrett Nussmeier |
| DEN | 00-0035264 | QB | QB2 | Jarrett Stidham |
| DEN | 00-0036879 | QB | QB3 | Sam Ehlinger |
| KC | 00-0041013 | RB | RB2 | Emmett Johnson |
| KC | 00-0038134 | RB | RB1 | Kenneth Walker III |
| KC | 00-0040078 | RB | RB3 | Brashard Smith |
| KC | 00-0039067 | WR | WR1 | Rashee Rice |
| KC | 00-0040890 | WR | WR4 | Cyrus Allen |
| KC | 00-0039894 | WR | WR2 | Xavier Worthy |
| KC | 00-0038519 | WR | WR6 | Nikko Remigio |
| KC | 00-0038104 | WR | WR3 | Tyquan Thornton |
| KC | 00-0040646 | WR | WR5 | Jalen Royals |
| KC | 00-0030506 | TE | TE1 | Travis Kelce |
| KC | 00-0036637 | TE | TE2 | Noah Gray |
| KC | 00-0040081 | TE | TE4 | Jake Briningstool |
| KC | 00-0039824 | TE | TE3 | Jared Wiley |

**19 of 19 resolve. 0 unresolved.** `name_resolution.unresolved` is `[]`.

All six of the brief's spot-check names match. So do all 19 against an
independently built artifact:
`nfl/research/v2/r2/R2_ELIGIBILITY_SNAPSHOT_2026_01_DEN_KC.json`, whose
`full_roster_snapshot.rows` map was assembled by a different tool.
**19 agree, 0 disagree, 0 absent.** That is a cross-check on the join, not a
source — nothing in `nfl/product` reads that file.

### The unresolved case is still reachable and still honest

I did not get to observe it on this board, so it is exercised on a blob built
inside the test. A row no lawful capture names keeps `name: None` and gets

```
{"source": null, "code": "NAME_UNRESOLVED_AT_CUT",
 "detail": "no capture lawful at <cut> carries a name for <gsis_id>.
            The row renders the gsis_id. This is a real state and is
            not repaired by guessing."}
```

and the board lists him in `name_resolution.unresolved`. The gate will still
withhold that row, correctly. That is the intended behaviour: the repair makes
the board able to name people, not able to claim it named them.

### The reduced-vintage path, exercised

Built the same board against
`nfl/vintage/weekly_rosters.bdab6ecee12d44a4.reduced.csv.gz`:
`name_column_absent: true`, `n_named: 0`, fallback `consulted: true`,
`n_filled: 19`, `n_unresolved: 0`, and every row's provenance switches to
`basis: NAME_FALLBACK_LAWFUL_CAPTURE` naming the capture that answered. So a
board selecting the reduced blob still resolves, still says where from, and
still does not invent.

## 7. Tests

New module `nfl/tests/test_board_row_identity.py`, 9 test functions, **38
checks, 0 failing, 0 blocked, 0 zero-check functions**.

It asserts, in order of what matters: no fuzzy matcher is imported and no
gsis_id string literal exists in either module (so a hardcoded name table
fails here rather than in a board); every resolved id names its blob and
column; no capture after the cut is read and an undatable capture is refused;
precedence is chronological; the reduced vintage reports "no name column"
rather than "no names"; the raw vintage names every player it identifies; an
empty name cell resolves to `None` and not to `''` or to the id; and the gate's
own condition flips both ways on a named / unnamed row.

**It can fail.** Mutation-tested: setting `'name': None` in
`roster_identity_outcome` turns 9 of the 38 checks red, including all six
spot-check names and `n_named == len(o.value)`. Restored immediately after.

| Suite | result |
|---|---|
| `--only test_board_row_identity` | 9 fn, 38 checks, **SUITE PASS** |
| `--only test_quality_gates` | 24 fn, 253 checks, **SUITE PASS** |
| `--only test_vintage_selector` | 24 fn, 131 checks, **SUITE PASS** |
| `--only test_product_orchestration` | 14 fn, 51 checks, **SUITE PASS** |
| `--only test_persisted_provenance` | 14 fn, 94 checks, **SUITE PASS** |
| `--only test_harness_audit` | 5 fn, 20 checks, **SUITE PASS** |
| `--only test_qb_pyds_market_eligibility` | 5 fn, 41 checks, **SUITE PASS** |
| `--only test_daily_board` | 9 fn, 69 checks, **SUITE PASS** |

There is no `test_board` module in this repository; `run_suite.py --only
test_board` would match the new module and nothing else. The suites above are
the ones that import `nfl.product.board`, import `nfl.product.names`, or assert
on `reduce_cols`.

`test_quality_gates` deserves a note. It asserts, on the **sealed R8 board**
(`.../V1_CANDIDATE_R8/f91342d6787a66a1`), that "every row fails the name
condition, so the board escalates to board scope". That still passes and should:
the sealed board is an immutable artifact, it genuinely has no names, and
nothing I did rewrote it. The module re-hashes every file under the seal at the
end of its run and reports byte-identity; it passed.

## 8. Caveats

- **8.1** The headline post-repair measurement is
  `nfl/research/v2/n1/trial_after/5d7829c0be9ec550`, whose `board.json` was
  re-rendered from its own sealed forecast with the final `board.py` and then
  evaluated. That is the pair to read: same engine, same cut, same 19 rows,
  only the name join different.
- **8.2 I did not write into `nfl/research/live/`.** Trial builds are under
  `nfl/research/v2/n1/`. The final live build is yours.
- **8.3 The tree moved under me, and the third build proves it.** A full
  rebuild finished after the others and produced **33 rows, not 19** — DEN
  gained RB, WR and TE rows it did not have, and
  `UNATTRIBUTED_OPPORTUNITY_MASS` went from 2 FIRED / 4 PASS to **0 FIRED /
  6 PASS**. That is not my change and I claim no credit for it: another agent
  was running `.../v2/d1/DEN_NODESIG_REPAIR` against the same cut at the same
  time, and `git status` showed `nfl/production/nonqb/readiness.py` become
  modified between my first and last check. **Do not read the 139 → 203 finding
  count as an effect of this repair.** What is attributable is the identity
  gate: 0 FIRED in both post-repair builds, and every one of the 17 new DEN
  rows named — J.K. Dobbins, RJ Harvey, Courtland Sutton, Marvin Mims Jr.,
  Lil'Jordan Humphrey and the rest resolve from the same blob with the same
  provenance, and the fallback was still never opened.
- `nfl/product/render.py` was **not** touched. It reads `names.get(gsis_id)`
  from the map `make_board` passes it and already produced correct names. It is
  outside my owned files. There is now a second place a name can come from —
  `row['name']` on the board — and the two agree by construction here because
  both resolve at the same cut. Making `render._name` prefer `row['name']` is a
  one-line follow-up for whoever owns that file; it is not required by the gate.

## 9. Files changed

| File | Change |
|---|---|
| `nfl/product/board.py` | name join, provenance, lazy fallback, `name_resolution` block |
| `nfl/product/names.py` | committed raw blobs as a source, chronological precedence, per-id provenance |
| `nfl/tests/test_board_row_identity.py` | new, 38 checks |
| `nfl/research/v2/n1/` | trial builds and this report |

Nothing under `nfl/production/` was written. Every repo write went through
`nfl/tools/nflwrite.py`.

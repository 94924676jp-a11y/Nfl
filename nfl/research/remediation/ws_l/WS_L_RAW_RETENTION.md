# WS-L — RAW RETENTION INVENTORY

**CODE CHANGED: NO.** Research only. Repo `/home/user/nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `837d52f`. Everything below was
read out of the bytes on 2026-09-14 with `python3.12` — gzip blobs through
`csv.DictReader`, JSON through `json.load`, the manifest line by line. Where a
document and the bytes disagree, the bytes are quoted and the document is named.
No suite was run. No file outside `nfl/research/remediation/ws_l/` was written.

**What this document is.** It is the requirement side of the retention repair.
WS-K's manifest schema and WS-J's retention guard are the implementation side.
Every rule in §5 is stated so that it can be turned into an assertion and so that
its result today is known in advance — a rule whose current answer I cannot state
is a rule I have not made testable.

---

## 0. THE FINDING IN ONE PARAGRAPH

Four fields that production, governance and the product board read every run —
`weekly_rosters.status`, `weekly_rosters.full_name`, `weekly_rosters.football_name`
and `depth_charts.pos_slot` — exist in **no durable store**. Three of them are read
out of `nfl_vintage/raw/`, which `.gitignore:7` excludes from the repository, and
the fourth is not read at all any more: `depth_vintage._daily_rows` asks the
reduced blob for `pos_slot`, does not get it, and silently substitutes `0`. The
retention policy the project actually holds, RET-001, governs
`pbp_participation` and `snap_counts` — **two sources with zero captured bytes** —
and returns `NOT_APPLICABLE / NOT_A_WATCHED_SOURCE` for all eight sources that do
have bytes, including both reduce sources. The assumption that makes the
reduction lawful, `reduce_recoverability_assumption: "upstream retains full dt
history for this source"`, is asserted on 366 rows, has never been checked
(`reduce_recoverability_checked: false` on all 368), is **false as written for
`weekly_rosters`, which has no `dt` column and is a rolling current-state file**,
and is **false as a byte claim for `depth_charts`, where 2,363 historical rows
across 133 of 170 shared `dt` slices have had their `gsis_id` restated upstream
between two captures seven days apart.** Six raw captures are already lost
outright, a seventh (`schedules.c563178ace7c6637`, the first schedules vintage,
2,177,171 bytes) exists nowhere at all, and 171 of 177 depth-chart `dt` slices
have never been durable.

---

## 1. METHOD

- Sources enumerated from `nfl/capture/registry.py` — **10 `SourceSpec` entries**,
  plus two delivery pseudo-sources (`official_status_evidence`,
  `hardrock_market_snapshot`) and one delivery evidence blob
  (`delivered_injury_evidence`) that appear in the manifest without a spec.
- Cross-checked against `nfl/vintage_manifest.jsonl` (**1,672 rows**, 0 unparseable)
  and the **490** blobs in `nfl/vintage/`.
- Every PASS row that names a blob was re-hashed from the bytes on disk
  (gunzip, then `sha256`) and compared to the row's `sha256`.
- Field lists read from the files. Roster and depth headers taken from the
  surviving raw `.csv` under `nfl_vintage/raw/`; reduced headers from the
  `.reduced.csv.gz` under `nfl/vintage/`; `schedules` and `injuries` headers from
  the durable blobs; ESPN structure from
  `nfl/vintage/espn_injuries_json.ffcc75fa28cbb8e3.json.gz`.
- Consumers found by grep over `nfl/production`, `nfl/product`, `nfl/tools`,
  `nfl/capture`, `nfl/ingest`, then read.

---

## 2. STORE TOPOLOGY AND WHO GUARDS WHAT

| Store | Contents | Tracked? | Guarded by |
|---|---|---|---|
| `nfl/vintage/` | **490 blobs, 134 MB** | **YES** — `git ls-files nfl/vintage` = 490 | **nothing.** `git log --all --diff-filter=D -- nfl/vintage` is empty, so nothing has been deleted; that is an observation, not a guard |
| `nfl/vintage_manifest.jsonl` | 1,672 rows | YES | nothing programmatic |
| `nfl_vintage/raw/` | **7 full-byte `.csv`, 4 `.incoming.*`, 7 `.headers.*`, 192 MB** | **NO** — `.gitignore:7` `nfl_vintage/` | nothing. `capture_vintage._persist` labels it `full_bytes_ephemeral_at` |
| `nfl/availability_raw/` | **2 blobs** | YES | **RET-001, R1–R8** |
| `nfl/availability_manifest.jsonl` | **6 rows** | YES | RET-001 R5 |

`nfl/tools/check_retention.py` defaults to `--blob-root AV.BLOB_ROOT` and
`--manifest AV.MANIFEST`, i.e. the **2-blob / 6-row** store. Measured by calling
`availability.assert_retention_policy` on every registered source:

```
pbp_participation          PASS            RETENTION_POLICY_OK
snap_counts                PASS            RETENTION_POLICY_OK
weekly_rosters             NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
depth_charts               NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
injuries                   NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
schedules                  NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
official_inactives         NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
official_injury_report     NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
espn_injuries_json         NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
official_transactions      NOT_APPLICABLE  NOT_A_WATCHED_SOURCE
```

The two sources a retention decision covers have **98 `NOT_APPLICABLE` manifest
rows each and zero captured bytes** (404 for 2026). The eight that have bytes
have no retention decision. That inversion is the structural cause of everything
in §4.

Note also `NFL_PARTICIPATION_RETENTION_DECISION.json` requirement **R7**: *"no
reduction / newest-N retention policy"*. `depth_charts` and `weekly_rosters` are
`durability="reduce"`, and the depth reducer's recorded strategy is literally
`"newest_dt_slice"`. **If RET-001's scope were widened as written, both reduce
sources would fail R7 immediately.** Widening the scope is therefore an owner
decision, not a guard-scope edit, and WS-J should not make it silently either
way. §5 RL-7 states the narrow version that can be enforced now.

### 2a. Blob integrity, re-derived independently of WS13

1,061 PASS rows carrying a blob and a sha256:

| verdict | rows | which |
|---|---|---|
| `SHA_OK` | **687** | schedules 184, espn_injuries_json 148, injuries 147, official_inactives 94+18, official_injury_report 94, 2 delivery rows |
| `SHA_MISMATCH` | **368** | **depth_charts 184 + weekly_rosters 184 — every `durability: reduce` row, without exception** |
| blob absent | **6** | the two earliest runs, §4b |

48 blobs on disk are named by no manifest row, all `schedules.*.csv.gz`. Reading
`value.delivery.raw_evidence_blobs` as well as `value.blob` is required to avoid a
49th false positive (`delivered_injury_evidence.df1dd90380b8d720.html.gz`).

`reduce_recoverability_assumption` appears on exactly the 368:

```
183  depth_charts    "upstream retains full dt history for this source"   checked=False
  1  depth_charts    "upstream retains full history for this source"      checked=False
183  weekly_rosters  "upstream retains full dt history for this source"   checked=False
  1  weekly_rosters  "upstream retains full history for this source"      checked=False
```

---

## 3. THE INVENTORY

Four columns as specified, one block per source. **RAW-REQUIRED** means a
consumer reads it and the persisted artifact does not carry it, or the reduced
form cannot reconstruct it. **REDUCED-SUFFICIENT** means the persisted artifact
carries it and a named consumer reads it from there. **NOT-CONSUMED** means no
module under `nfl/production`, `nfl/product`, `nfl/tools`, `nfl/capture` or
`nfl/ingest` reads it today — which is a statement about consumption, never about
whether the bytes are worth keeping.

### 3.1 `weekly_rosters` — `durability="reduce"`, 36 upstream columns, 5 persisted

Upstream header measured on `nfl_vintage/raw/weekly_rosters.cef497eaeddef07b.csv`
(2,963 rows, week 1 only, 939,000 bytes). Persisted header measured on all seven
`weekly_rosters.*.reduced.csv.gz`: identical 5 columns, 2,946–2,963 rows.

| field | class | who reads it | fill rate | note |
|---|---|---|---|---|
| `season` | REDUCED-SUFFICIENT | `roster_status.status_map`, `ingest_inactives`, `delivered_injuries.roster_index` | 100% | |
| `week` | REDUCED-SUFFICIENT | same | 100% | |
| `team` | REDUCED-SUFFICIENT | same, + `daily_board.roster_names` | 100%, 32 distinct | |
| `gsis_id` | REDUCED-SUFFICIENT | every consumer; the join key | 2,962/2,963 | |
| `position` | REDUCED-SUFFICIENT | `ingest_inactives` roster dict, `delivered_injuries.roster_index` | 100%, 11 distinct | |
| **`status`** | **RAW-REQUIRED** | **`nfl/production/nonqb/roster_status.py:72,155` (R5 active pool)**; declared in `ingest_inactives.CONSUMED['weekly_rosters']` | 100%, 7 distinct: ACT/DEV/RES/CUT/EXE/RET/INA | quarantined POSTHOC in `allowlist.py:129` with one named exemption for `roster_status.py`. **Not in `reduce_cols`.** Read only from the gitignored raw store |
| **`full_name`** | **RAW-REQUIRED** | `product/names.py:78`, `product/daily_board.py:470`, `tools/ingest_inactives.py:280`, `capture/delivered_injuries.py:273` | 100%, 2,956 distinct | the **only** path from an official inactives list (which prints names) to a `gsis_id`. `ingest_inactives` says so at its own line 254: the first rehearsal resolved 0 of 6 without it |
| **`football_name`** | **RAW-REQUIRED** | `daily_board.py:470`, `ingest_inactives.py:281`, `delivered_injuries.py:273` | 100%, 1,371 distinct | fallback for `full_name` |
| **`first_name`** | **RAW-REQUIRED (declared, not read)** | listed in `delivered_injuries.ROSTER_IDENTITY_COLUMNS` (line 110) and reported as `columns_read` in that function's evidence | 100% | **the evidence block names a column the function body never reads.** Either read it or drop it from the declaration |
| **`last_name`** | **RAW-REQUIRED (declared, not read)** | same | 100% | same |
| **`status_description_abbr`** | **RAW-REQUIRED (governance)** | named in `delivered_injuries.ROSTER_FORBIDDEN_COLUMNS` (line 113) — i.e. governance knows it exists and forbids it | 100%, **16 distinct**: A01 1,735 · P01 334 · P07 123 · P06 61 · P03 24 · P02 3 · R01 175 · R02 23 · R04 30 · R05 6 · R27 1 · R40 6 · R48 50 · R49 1 · W03 386 · E02 5 | the only field separating practice-squad types, IR variants and elevations. **No decoder exists in the repository** (WS05 E3). Unreconstructible from anything else we hold |
| **`espn_id`** | **RAW-REQUIRED (bridge)** | no current consumer; WS05 measured the ESPN→gsis bridge at **691 of 800 rows** using it | 68.0% | it is the **only** join from the 148 retained `espn_injuries_json` captures — the largest unconsumed eligibility corpus in the tree — to our identity space. Dropping it makes those 148 blobs unjoinable |
| `depth_chart_position` | NOT-CONSUMED | — | 100%, 23 distinct | |
| `jersey_number` | NOT-CONSUMED | — | 99.9% | |
| `birth_date` | NOT-CONSUMED | — | 92.6% | |
| `height` | NOT-CONSUMED | — | 92.6% | |
| `weight` | NOT-CONSUMED | — | 100% | |
| `college` | NOT-CONSUMED | — | 91.9% | |
| `sportradar_id` | NOT-CONSUMED | — | 63.9% | |
| `yahoo_id` | NOT-CONSUMED | — | 38.7% | |
| `rotowire_id` | NOT-CONSUMED | — | 68.0% | |
| `pff_id` | NOT-CONSUMED | — | 66.1% | |
| `pfr_id` | NOT-CONSUMED | — | 67.0% | `ingest/identifiers.Crosswalk` is `pfr_id→gsis_id` but is built from `players.csv`, not from this file |
| `fantasy_data_id` | NOT-CONSUMED | — | 63.8% | |
| `sleeper_id` | NOT-CONSUMED | — | 63.9% | |
| `years_exp` | NOT-CONSUMED | — | 100% | |
| `headshot_url` | NOT-CONSUMED | — | 96.8% | |
| `ngs_position` | NOT-CONSUMED | — | **5.0%** | |
| `game_type` | NOT-CONSUMED | — | 100%, 1 distinct | |
| `esb_id` | NOT-CONSUMED | — | 99.9% | |
| `gsis_it_id` | NOT-CONSUMED | — | 100% | |
| `smart_id` | NOT-CONSUMED | — | 99.8% | |
| `entry_year` | NOT-CONSUMED | — | 100% | |
| `rookie_year` | NOT-CONSUMED | — | 100% | |
| `draft_club` | NOT-CONSUMED | — | 58.9% | |
| `draft_number` | NOT-CONSUMED | — | 58.9% | |

**Row dimension:** none. The reduction keeps every row (2,963 → 2,963). The loss
is purely columnar: 31 of 36 columns.

**Sufficiency proof for the 5 reduced columns.** `ingest_inactives` builds its
pool from `nfl/vintage/weekly_rosters.<sha>.reduced.csv.gz` (line 268), filtering
on `season`, `week`, `team`, `gsis_id` and reading `position` — and then has to
open the **raw** file separately for the name. That split is the sufficiency
proof and the insufficiency proof in one function.

### 3.2 `depth_charts` — `durability="reduce"`, 12 upstream columns, 5 persisted, **and 171 of 177 row-slices dropped**

Upstream header measured on `nfl_vintage/raw/depth_charts.a14e8dfe865a4b03.csv`
(516,349 rows, 49,097,593 bytes, **177 distinct `dt` values from 2026-03-22T06:38:42Z
to 2026-09-13T12:42:08Z**). Persisted: 5 columns, **one `dt` slice**, 2,222 rows.

| field | class | who reads it | note |
|---|---|---|---|
| `dt` | REDUCED-SUFFICIENT | `depth_vintage._daily_rows:156`, `daily_point_in_time`; `ingest_inactives.CONSUMED` | the only source-provided effective instant in the registry (`ScopeKind.EXACT_TIMESTAMP`) |
| `team` | REDUCED-SUFFICIENT | same | |
| `gsis_id` | REDUCED-SUFFICIENT | same | **but see the mutation finding below** |
| `pos_abb` | REDUCED-SUFFICIENT | `_daily_rows:149`, filtered to `SKILL` = {QB,RB,HB,FB,WR,TE} | |
| `pos_rank` | REDUCED-SUFFICIENT | `_daily_rows:153`; `board.depth_rank` feeds R6 tiering | |
| **`pos_slot`** | **RAW-REQUIRED, and currently failing silently** | **`depth_vintage._daily_rows:157` — `int(r.get('pos_slot') or 0)`**, used as the tie-break in `daily()` (`(rk, slot) < (cur[0], cur[2])`) and as the second sort key in `_ordinal` (`(v[0], v[2], pid)`) | **not in `reduce_cols`.** The module's own docstring line 19 names it as part of the schema it reads. Against the reduced blob it is `0` for every row, on every run, with no refusal. Measured harm: **zero** — across all three surviving raw captures there are **0 `(team, pos_abb, pos_rank)` tie groups**, over 170/174/177 `dt` slices, so the tie-break never fires. Inert today, unverifiable on the three lost vintages, and a silent default rather than a named refusal either way |
| `player_name` | NOT-CONSUMED | — | |
| `espn_id` | NOT-CONSUMED | — | |
| `pos_grp_id`, `pos_grp`, `pos_id`, `pos_name` | NOT-CONSUMED | — | |

**Row dimension, and this is the larger loss.** The reducer keeps only the
newest `dt` slice (`strategy: "newest_dt_slice"`). Measured `dt` content of each
durable blob:

```
depth_charts.76d7bcb384ec11e3.reduced.csv.gz   ->  2026-09-06T11:29:30Z
depth_charts.ecc4973e8715d866.reduced.csv.gz   ->  2026-09-07T13:13:25Z
depth_charts.f57ef0724d907160.reduced.csv.gz   ->  2026-09-08T11:56:57Z
depth_charts.361f1c69443cba69.reduced.csv.gz   ->  2026-09-09T12:06:21Z
depth_charts.db0a09454965e6fc.reduced.csv.gz   ->  2026-09-10T12:01:46Z
depth_charts.a14e8dfe865a4b03.reduced.csv.gz   ->  2026-09-13T12:42:08Z
```

Six slices. The 09-13 raw file contains **177**. So **171 of 177 daily depth
snapshots are durable nowhere** — 169 of them from 2026-03-22 to 2026-09-05, plus
**`2026-09-11T12:21:50Z` and `2026-09-12T11:36:06Z`**, which fall inside week 1's
build-up and are the reason production's point-in-time depth series jumps from
09-10T12:01 straight to 09-13T12:42.

Those two are **still recoverable today without any fetch**: both are inside the
retained `nfl_vintage/raw/depth_charts.a14e8dfe865a4b03.csv`. That is a
time-limited recovery — the file is gitignored and one clean checkout removes it.

### 3.3 The eight sources where retention is not in question

| source | durability | bytes durable? | verified | field-loss risk |
|---|---|---|---|---|
| `injuries` | `commit_raw` | yes, 7 blobs | 147/147 `SHA_OK` | **none.** All columns retained. Schema moves across captures — 4 distinct headers, 13/14/15/16 columns — but every version is stored whole. Consumed: `report_status`, `practice_status`, `report_primary_injury`, `practice_primary_injury`, `practice_secondary_injury`, `season_type` by `appearance_model`, `appearance_r7`, `appearance_r8`, `readiness`, `inputs`, `confidence`, `delivered_injuries` |
| `schedules` | `commit_raw` | yes, 132 blobs (86 content vintages) | 184/184 `SHA_OK` | none for retained blobs. 46 columns; `away_qb_id`/`home_qb_id` quarantined POSTHOC in `allowlist._SCH_POSTHOC`. **One vintage lost outright — §4b** |
| `official_injury_report` | `commit_raw` | yes, 92 html blobs | 94/94 `SHA_OK` | none. Parser `nfl/parse/injury_report.py` exists; **no production module imports it** (WS05 F14). That is a consumption gap, not a retention gap |
| `official_inactives` | `commit_raw` | yes, 95 html blobs | 112/112 `SHA_OK` | none. 92 of 95 are the empty placeholder (WS05 §2) — again consumption/source, not retention |
| `espn_injuries_json` | `commit_raw` | yes, 148 json blobs | 148/148 `SHA_OK` | **none for the bytes, total for the join.** Structure read from the blob: `injuries[].injuries[]` with `id`, `status`, `date`, `longComment`, `shortComment`, `athlete{firstName,lastName,displayName,links[]}`, `type`. It carries **no direct athlete id** — the ESPN id must be regexed from `athlete.links[0].href`. So these 148 fully-retained captures are joinable **only** through `weekly_rosters.espn_id`, which the reduction drops. Retaining a corpus you cannot join is not retention |
| `official_transactions` | `commit_raw` | **zero bytes, 177 BLOCKED** | — | nothing to retain. `url_template=None` |
| `pbp_participation` | `commit_raw` | zero bytes, 98 `NOT_APPLICABLE` | — | **the only source RET-001 covers, alongside `snap_counts`** |
| `snap_counts` | `commit_raw` | zero bytes, 98 `NOT_APPLICABLE` | — | same |

Plus three delivery artifacts (`official_status_evidence`,
`hardrock_market_snapshot`, `delivered_injury_evidence`): 1 blob each, all
`SHA_OK`, all full bytes.

### 3.4 Classification totals

Over the **48 fields of the two `reduce` sources** — the only sources where the
persisted form differs from the captured form:

| class | count | fields |
|---|---|---|
| **REDUCED-SUFFICIENT** | **10** | roster: `season`, `week`, `team`, `gsis_id`, `position` · depth: `dt`, `team`, `gsis_id`, `pos_abb`, `pos_rank` |
| **RAW-REQUIRED — read today by a consumer, absent from the persisted artifact** | **4** | `weekly_rosters.status`, `.full_name`, `.football_name`, `depth_charts.pos_slot` |
| **RAW-REQUIRED — named by governance or by a declared consumer, absent from the persisted artifact** | **4** | `weekly_rosters.status_description_abbr`, `.espn_id`, `.first_name`, `.last_name` |
| **NOT-CONSUMED** | **30** | 24 roster + 6 depth |

Plus one row-dimension entry: **`depth_charts`, 171 of 177 `dt` slices — RAW-REQUIRED and not retained.**

Across the other eight registered sources plus three delivery artifacts:
**every field of every captured byte is inside a durable git-tracked blob.**
`durability="commit_raw"` is doing its job; `durability="reduce"` is where the
whole problem lives.

---

## 4. WHAT IS ALREADY LOST

Named, not softened. Nothing below is reconstructed, interpolated or inferred.

### 4a. Six raw captures, gone

Each is a `sha256` the manifest attests to, for bytes that exist nowhere.

| # | source | digest (sha16) | upstream `source_timestamp` | first captured | upstream bytes | upstream lines | manifest PASS rows citing it | what went with it |
|---|---|---|---|---|---|---|---|---|
| L1 | `depth_charts` | `ecc4973e8715d866` | 2026-09-07T13:13:35Z | 20260907T133903Z | 47,849,272 | 503,246 | 44 | `pos_slot` + 6 unconsumed cols, and ~172 `dt` slices |
| L2 | `depth_charts` | `f57ef0724d907160` | 2026-09-08T11:57:06Z | 20260908T120739Z | 48,057,446 | 505,423 | 11 | same |
| L3 | `depth_charts` | `361f1c69443cba69` | 2026-09-09T12:06:29Z | 20260910T050518Z | 48,262,563 | 507,606 | 21 | same |
| L4 | `weekly_rosters` | `e157129706145664` | 2026-09-07T13:10:26Z | 20260907T133903Z | 935,135 | 2,955 | 44 | **`status`, `status_description_abbr`, `espn_id`, `full_name`, `football_name` + 26 others** |
| L5 | `weekly_rosters` | `125c300ff066d314` | 2026-09-08T11:56:44Z | 20260908T120739Z | 935,535 | 2,956 | 11 | same |
| L6 | `weekly_rosters` | `0b005c45d924a541` | 2026-09-09T12:05:51Z | 20260910T050518Z | 935,441 | 2,956 | 21 | same |

What survives of each is the 5-column reduced blob, which carries **no eligibility
fact and no name at all**. For L4–L6 that means: for 2026-09-07, 09-08 and 09-09
the project cannot say who was on an active roster, and cannot resolve any name
on any document to a `gsis_id` using a vintage from those days.

**The mechanism, and it separates perfectly.** For each of the 13 distinct
`depth_charts`/`weekly_rosters` digests, I took the set of `execution.basis`
values across all its manifest rows:

```
digest              raw on disk   observation bases
ecc4973e8715d866    False         PERIODIC_SWEEP
f57ef0724d907160    False         PERIODIC_SWEEP
361f1c69443cba69    False         PERIODIC_SWEEP, SCHEDULED_WINDOW_ANCHORED_NON_G0A
e157129706145664    False         PERIODIC_SWEEP
125c300ff066d314    False         PERIODIC_SWEEP
0b005c45d924a541    False         PERIODIC_SWEEP, SCHEDULED_WINDOW_ANCHORED_NON_G0A
76d7bcb384ec11e3    True          NONE, OPERATOR_TARGETED, PERIODIC_SWEEP
5ec59c5228198f57    True          NONE, OPERATOR_TARGETED, PERIODIC_SWEEP
db0a09454965e6fc    True          LOCAL_INVOCATION, PERIODIC_SWEEP, SCHEDULED_WINDOW_ANCHORED(+_NON_G0A)
3b0d5d40dc7816f7    True          LOCAL_INVOCATION, PERIODIC_SWEEP, SCHEDULED_WINDOW_ANCHORED(+_NON_G0A)
fb79560b5c4738a2    True          LOCAL_INVOCATION
cef497eaeddef07b    True          LOCAL_INVOCATION
a14e8dfe865a4b03    True          LOCAL_INVOCATION
```

**6 of 6 digests observed only from GitHub Actions lost their raw bytes; 7 of 7
digests observed at least once from a run on the persistent local filesystem kept
them.** `nfl_vintage/` is gitignored and an Actions runner's workspace is
discarded, so a raw file survives if and only if a non-Actions run happened to
see that digest. Retention is currently a property of **which machine looked**,
not of any policy — and the executor that can reach the official sources is
exactly the one that retains nothing.

### 4b. `schedules.c563178ace7c6637` — the first schedules vintage, gone entirely

Six PASS rows (`20260906T185049Z` and `20260906T185100Z`) cite repo-root-relative
`raw/…` paths written before the path convention changed at `20260906T201020Z`:

```
raw/depth_charts.76d7bcb384ec11e3.csv     -> recoverable at nfl_vintage/raw/, re-hashed: 76d7bcb384ec11e3  MATCH
raw/weekly_rosters.5ec59c5228198f57.csv   -> recoverable at nfl_vintage/raw/, re-hashed: 5ec59c5228198f57  MATCH
raw/schedules.c563178ace7c6637.csv        -> NOWHERE
```

This sharpens WS13 §3b, which files all six as "low, historical". Two of the
three artifacts are a **path defect** and their bytes verify at the corrected
location. The third is a **loss**: `schedules.c563178ace7c6637`, 2,177,171 bytes,
is not in `nfl/vintage/`, not in `nfl_vintage/raw/`, and
`git log --all -- 'nfl/vintage/schedules.c563178ace7c6637*'` is empty. It is the
first schedules capture of the season and the only lost artifact from a
`commit_raw` source.

### 4c. 171 of 177 depth-chart `dt` slices, never durable

§3.2. Two of them — `2026-09-11T12:21:50Z` and `2026-09-12T11:36:06Z` — are still
inside a retained raw file today and can be made durable without a fetch. The
other 169 exist only in `nfl_vintage/raw/depth_charts.{76d7…,db0a…,a14e…}.csv`
and are as gitignored as everything else in that directory.

### 4d. Not mine, but it bounds what §5 can promise

2026-09-09: **31 capture runs executed, zero manifest rows survive**, 30 orphan
`schedules` blobs the only residue (WS13 §3d). No retention rule recovers that;
the guard in `nfl-capture.yml` prevents recurrence only.

### 4e. What is NOT lost, and should stop being described as at risk

All 148 `espn_injuries_json` captures, all 95 `official_inactives`, all 92
`official_injury_report` and all 7 `injuries` blobs are byte-complete,
git-tracked and re-hash correctly against their manifest rows. Of the 132
`schedules` blobs on disk, 84 are cited by a manifest row and all 84 verify;
the 48 orphans self-verify against the digest embedded in their own filename
(0 of 48 fail) but are named by no row, so they are bytes without an
observation — RL-8's problem, not a retention loss. Their problem is that **nothing
reads them**, which is WS05's finding and a different repair.

---

## 5. RETENTION RULES — the testable requirements

Each rule states the assertion, the store it runs against, and **its answer
today**, so that an implementation can be checked rather than believed. A rule
whose current answer is unknown is not on this list.

### For WS-K — manifest schema and the capture/reduce path

**RL-1 — Two hashes, and the persisted one is the one that verifies.**
Every manifest row naming a `blob` carries `persisted_content_sha256`, equal to
`sha256` of the bytes obtained by fully decompressing that blob, and
`upstream_content_sha256`, equal to `sha256` of the bytes as fetched. For
`commit_raw` they are equal; for `reduce` they are not, and neither may be
omitted.
*Test:* for every PASS row with a blob, recompute and compare against
`persisted_content_sha256`.
*Today:* 687 of 1,061 verify against the single `sha256` field; the rule requires
**1,061 of 1,061**.
*Corollary:* `sha256_is_of: "uncompressed_bytes"` must be removed or made
explicit about which hash it describes. On **366 rows it names bytes that were
never stored** and is false as written.

**RL-2 — A reduced artifact may not be the sole home of a field any consumer reads.**
Let `CONSUMED(src)` be the union of field names read from `src` by any module
under `nfl/production`, `nfl/product`, `nfl/tools`, `nfl/capture`, `nfl/ingest`.
Assert `CONSUMED(src) ⊆ set(reduce_cols(src))` for every `durability="reduce"`
source.
*Today it fails on exactly four fields:* `weekly_rosters.status`, `.full_name`,
`.football_name`, `depth_charts.pos_slot`.
*Two lawful discharges, and only two:* add the field to `reduce_cols`, or move the
source to `durability="commit_raw"`. **Retaining it in `nfl_vintage/raw/` is not
a discharge** — see RL-9.
*Recommended `reduce_cols` if the first discharge is taken:*
`weekly_rosters` → `("season","week","team","gsis_id","position","status","full_name","football_name","status_description_abbr","espn_id")` (10 of 36);
`depth_charts` → `("dt","team","gsis_id","pos_abb","pos_rank","pos_slot")` (6 of 12).
Measured cost of the roster change: the 5-column reduced blobs are ~2,960 rows
each; adding five short columns is a small multiple of a file that already
compresses to well under the 939 KB raw. I have not measured the compressed
delta and do not assert one.

**RL-3 — Every `dt` slice reaches the durable store, not only the newest.**
For a source whose payload carries a per-row effective clock, the reducer
persists every slice not already durable.
*Test:* for every retained raw capture, `set(dt in raw) ⊆ union(dt across all
durable reduced blobs for that source)`.
*Today:* **6 of 177 satisfied, 171 fail.**
*Immediate partial discharge with no fetch:* `2026-09-11T12:21:50Z` and
`2026-09-12T11:36:06Z` are inside
`nfl_vintage/raw/depth_charts.a14e8dfe865a4b03.csv` and can be persisted now.

**RL-4 — `reduce_recoverability_assumption` is a measurement or it is absent.**
No row may carry the assumption string while `reduce_recoverability_checked` is
`false`. If the claim cannot be tested, the field is omitted and the row says the
reduction is irreversible.
*Today:* 368 rows assert it, 0 have checked it.
*What I measured, and it is the reason this rule matters:*

- **`weekly_rosters` — the assumption is false, categorically.** The file has **no
  `dt` column**, so "upstream retains full dt history for this source" names a
  column that does not exist. It is a rolling current-state file overwritten in
  place. Week-1 rows across the four surviving raw captures:

  | capture | rows | ACT | DEV | RES | CUT | EXE | RET | INA |
  |---|---|---|---|---|---|---|---|---|
  | 5ec5 (src_ts 09-06T11:29) | 2,946 | 1,693 | 528 | 277 | 421 | 4 | 23 | 0 |
  | 3b0d (09-10T12:01) | 2,963 | 1,684 | 559 | 264 | 414 | 5 | 23 | 14 |
  | fb79 (09-11T12:16) | 2,963 | 1,675 | 557 | 263 | 415 | 5 | 23 | 25 |
  | cef4 (09-13T12:43) | 2,963 | 1,709 | 520 | 266 | 415 | 5 | 23 | 25 |

  A re-fetch returns today's partition of week 1, not the one captured. **L4, L5
  and L6 are unrecoverable by any means, at any price.**

- **`depth_charts` — the assumption holds for coverage and fails for bytes.**
  Comparing the 09-06 raw against the 09-13 raw: **0 of 170 shared `dt` slices
  disappeared, 0 changed row count**, and 7 new slices accreted (170 → 177). So
  slice *coverage* is retained upstream. But **2,363 rows across 133 of the 170
  shared slices differ**, and of the 12 columns **exactly one moved: `gsis_id`,
  2,363 of 2,363 changes.** Both directions occur — blank→id (`Nadame Tucker`,
  `2026-04-26T08:14:47Z`, `'' → 00-0041385`) and id→blank (`Marcus Allen`, same
  slice, `00-0041340 → ''`). Upstream restates identity in historical snapshots.
  Consequence: the manifest `sha256` of a `depth_charts` capture **can never be
  reproduced by re-fetching**, and the join key production uses is not stable
  point-in-time. Measured over one 7-day interval and two captures; I make no
  claim about the rate.

**RL-5 — Retention is declared per field, not per source.**
Each `SourceSpec` carries the set of fields whose presence in the **persisted**
artifact is required, and the capture asserts they are present before the row is
written — a named failure otherwise, never a row with a missing column.
*Test:* `required_retained_fields(src) ⊆ header(persisted artifact)` at write
time.
*Today:* no such declaration exists; `_persist` records `missing_columns` in the
`reduced` block and continues.

**RL-6 — The transformation must be reproducible from the row alone.**
For each reduced artifact the row records the input digest, the output digest,
the selected columns, the row-selection rule, and the identity of the
transformation code. Re-running that transformation on the input must reproduce
the output digest byte for byte.
*Test:* given a retained raw file and its row, re-reduce and compare to
`persisted_content_sha256`.
*Today:* possible for 7 of 13 digests (those whose raw survives) and impossible
for the other 6. Note the trap this closes: `strategy: "newest_dt_slice"` is
recorded as a string, so a change to the reducer's column list or slice rule
would leave every existing row's declaration unchanged.

### For WS-J — the retention guard

**RL-7 — Retention scope equals capture scope.**
*Test:* for every `spec` in `registry.REGISTRY`,
`availability.assert_retention_policy(spec.name).state is not State.NOT_APPLICABLE`.
*Today:* **2 of 10 pass; 8 return `NOT_A_WATCHED_SOURCE`.**
*And the thing not to do quietly:* RET-001 R7 forbids "reduction / newest-N
retention". Widening scope without changing R7 makes `depth_charts` and
`weekly_rosters` fail immediately, which is the honest signal — but **the fix for
that failure is an owner decision on RET-001, not a relaxation of R7 and not a
carve-out.** If a narrower step is wanted now: assert that every registered
source is *named* by some retention decision, with `reduce` sources named as
`POLICY_UNDECIDED` rather than `NOT_APPLICABLE`. Silence and a decision must not
look the same.

**RL-8 — The deletion and orphan guards run against the vintage store.**
`check_retention.py` must additionally run `assert_no_vintage_deleted`,
`assert_manifest_append_only` and `assert_no_orphan_blobs` against
`nfl/vintage` + `nfl/vintage_manifest.jsonl`.
*Today:* it runs against `nfl/availability_raw` (**2 blobs**) and
`nfl/availability_manifest.jsonl` (**6 rows**), which is why `R8 NO_ORPHAN_BLOBS`
was green while 48 orphans accumulated.
*Expected first result when pointed at the vintage store:*
**FAIL — `ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION`, 48 orphans, all `schedules.*.csv.gz`.**
That FAIL is the correct answer and is not a reason to soften the check.
*Required alongside it:* `assert_no_orphan_blobs` currently reads only the `blob`
and `blob_sidecar` keys. It must also read `value.delivery.raw_evidence_blobs`,
or `delivered_injury_evidence.df1dd90380b8d720.html.gz` becomes a 49th false
positive (WS13 §3e).

**RL-9 — No gitignored path may be the sole home of anything a consumer reads.**
*Test:* grep for the literal `nfl_vintage` under `nfl/production`, `nfl/product`
and `nfl/capture`; assert zero hits once RL-2 is discharged.
*Today:* `nfl/production/nonqb/roster_status.py:72`, `nfl/product/names.py:65`,
`nfl/product/daily_board.py:464`, plus `nfl/tools/ingest_inactives.py:274` and
`nfl/tools/ingest_delivered_injuries.py:150`. `nfl/research/own2/characterise_coldstart.py:39`
hardcodes `weekly_rosters.5ec59c5228198f57.csv` — a research script whose only
input is an untracked file that happens still to exist.
*Evidence this is not theoretical:* §4a. Perfect 6/6 versus 7/7 separation on
which executor observed the digest.

### For WS-C — two consumer-side requirements this inventory generates

I do not own these files. Relaying them.

**RL-10 — No consumer substitutes a default for a declared column it cannot find.**
`depth_vintage._daily_rows:157` reads `int(r.get('pos_slot') or 0)` against a
persisted artifact with no `pos_slot` column. It must raise a named refusal
(`DEPTH_COLUMN_ABSENT`) when the header lacks a column the module declares.
*Measured harm today: zero* — 0 tie groups over 170/174/177 `dt` slices in all
three surviving raws, so the tie-break never fires. *Measured harm on the three
lost vintages: unknowable.* This is the Phase-1 defect class exactly — a partial
input read as a complete one — and its current inertness is luck, not design.

**RL-11 — A consumed-slice hash may not declare a column the file it reads does not carry.**
`ingest_inactives.consumed_slice` globs `nfl/vintage/{src}.{sha16}.*`, which for
`weekly_rosters` resolves to the reduced blob, while `CONSUMED['weekly_rosters']`
declares `status`. Re-run here on `cef497eaeddef07b` for SF/LA, 2026 week 1:
**181 keep-strings, 181 of 181 ending in the literal `|None`**, slice hash
`2af2f65dff52303c`. The guard that exists to prove the consumed roster slice did
not move between the pre- and post-inactives seals **cannot see the column it
names**. It must assert `set(CONSUMED[src]) ⊆ fieldnames` and refuse otherwise.
(WS05 F10; reproduced independently here on a different vintage.)

---

## 6. EVIDENCE CEILING AND OUTBOX REQUESTS

**What this pass cannot establish from inside the checkout.**

**O1 — Whether nflverse serves prior versions of the two reduce-source files.**
This single answer decides whether L1–L3 are "lost" or "re-fetchable", and
whether RL-4's assumption can ever be checked rather than deleted. Exact request:
for `https://github.com/nflverse/nflverse-data`, release tags `weekly_rosters`
and `depth_charts` — list every asset with its name, size, `updated_at` and
whether any previously-published version of `roster_weekly_2026.csv` or
`depth_charts_2026.csv` remains downloadable (asset version history, or a dated
mirror). If only the current asset is served, L1–L6 are permanently lost and RL-4
resolves to "assumption deleted" for both sources.

**O2 — A single dated re-fetch, with its sha256, of
`.../weekly_rosters/roster_weekly_2026.csv` and
`.../depth_charts/depth_charts_2026.csv`.** Needed to state whether *any* of our
13 recorded digests is still the digest upstream serves. My in-place-mutation
findings rest on two captures seven days apart; one current hash converts that
from a two-point observation into a check anyone can repeat.

**O3 — A decode table for `weekly_rosters.status_description_abbr`.**
Restating WS05 E3 because it is load-bearing *here*: 16 codes observed, zero
decoders. Whether `P07` is a standard gameday elevation, and what separates
`R01/R04/R05/R27/R40/R48/R49`, decides whether that field is RAW-REQUIRED or
merely NOT-CONSUMED. A published nflverse or league reference is enough; a guess
is not. Until it lands I have classified it RAW-REQUIRED (governance) on the
ground that it is unreconstructible from anything else we hold — that is a
conservative call and it should be revisited when the table arrives.

**Not blocked, and not an outbox item:** the capture executor retains no raw
bytes because `nfl_vintage/` is gitignored and the runner is ephemeral. That is a
repository decision inside this checkout and it is WS-J's and WS-K's to make.

**What I did not establish.**
- Whether the 09-11 and 09-12 depth slices would change any forecast. They are a
  gap in the durable series; I have not scored anything with them.
- The rate of upstream `gsis_id` restatement. One 7-day interval, two captures.
- Whether `pos_slot` has ever mattered. Zero ties in three surviving vintages;
  the three lost ones cannot be checked and never will be.
- Any compressed-size cost of the `reduce_cols` in RL-2. Not measured, not asserted.

**CODE CHANGED: NO.**

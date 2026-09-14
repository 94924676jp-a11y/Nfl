# WS13 — DATA HEALTH MATRIX

**CODE CHANGED: NO.** No existing repository file was modified. Everything below was
read, hashed or recomputed from the tree at HEAD `57d38ad`. The only file written is
this one, via `nfl/tools/nflwrite.py`.

- Measured: **2026-09-14, UTC**, `python3.12`.
- Stores read: `nfl/vintage/` (490 blobs, 134 MB, all git-tracked, working tree clean),
  `nfl/vintage_manifest.jsonl` (1,672 rows, 0 unparseable lines),
  `nfl/availability_raw/` (2 files), `nfl/availability_manifest.jsonl` (6 rows),
  `nfl/research/postgame/`, `nfl/research/live/2026_01_*` (14 game dirs),
  `nfl_vintage/raw/` (untracked, gitignored, 192 MB).
- Coverage logic executed as written: `nfl.capture.coverage.coverage(2026, 1, ...)` and
  `performed_from_manifest`, with `verify_artifacts=True`.

---

## 0. Headline, in one paragraph

The vintage store is large and mostly honest, and three things in it are not. **(1)** Every
persisted `depth_charts` and `weekly_rosters` blob fails its own manifest hash — 368 of
1,061 PASS rows, 34.7% — because the recorded `sha256`, `n_bytes` and `n_lines` describe the
full upstream file while the file actually persisted is a column-reduced subset whose hash was
never recorded. **(2)** Fifty GitHub-Actions capture runs on 2026-09-08/09/10 committed a blob
and appended **zero** manifest rows; 2026-09-09 has 31 such runs and is therefore entirely
absent from the manifest, including the four runs inside the NE@SEA T-90 inactives window.
**(3)** The only executor with egress to nfl.com and ESPN stopped running after
**2026-09-11T00:44:04Z**, so every anchored cron the repo had scheduled for the 12-game Sunday
slate and for DEN@KC produced nothing; the 2026-09-13 rows in the manifest are all
`basis: LOCAL_INVOCATION`, `basis_can_discharge: false`, with `NO_EGRESS` on the three
official sources. Separately, real, hash-verified, game-anchored inactives evidence **does**
exist for 13 of 16 week-1 games — and `coverage.py` scores 12 of them as MISSED, because they
were written by a second writer whose rows carry no `discharge_eligibility` block.

---

## 1. Store inventory

| Store | Rows / files | Notes |
|---|---|---|
| `nfl/vintage_manifest.jsonl` | 1,672 rows, 191 distinct `capture_id` | append-only; 0 malformed JSON lines |
| states | PASS 1,061 · BLOCKED 267 · NOT_APPLICABLE 196 · FAIL 108 · DEFERRED 40 | |
| `nfl/vintage/` | 490 blobs, 134 MB | all tracked, `git status` clean |
| blobs cited by a PASS row | 447 distinct | 444 resolve on disk, 3 resolve only after appending `.gz` |
| **blobs on disk cited by nothing** | **48** | all `schedules.*.csv.gz`; see §3 |
| `nfl_vintage/raw/` | 7 full-byte files + 4 `.incoming.*` + 7 `.headers.*`, 192 MB | gitignored, ephemeral, **not** an audit store |
| `nfl/availability_manifest.jsonl` | 6 rows | watch-only store (`pbp_participation`, `snap_counts`) |
| `nfl/research/postgame/` | pbp 2021–2024 + 2 × 2026 snapshots | see §7 |

Manifest row-identity balances: `n_attributed_rows (12) + n_unattributed (1,049) = n_pass_rows (1,061)`.
Of 1,061 PASS rows, **12 rows** carry a declared eligible target, yielding **103 (game_id, kind)
dischargeable pairs**; 1,049 rows discharge nothing. 6 rows are pre-Directive-7 legacy
`discharge_claims` rows and discharge nothing by design.

---

## 2. Per-source data-health matrix

`req` = `registry.SourceSpec.required`. "stale" = PASS row with `content_unchanged: true`
(a re-observation of bytes already held — a measurement, not a duplicate artifact).
"dup cite" = PASS rows beyond the first that cite an already-stored blob. Hash columns are
per **distinct blob**, computed by re-hashing the bytes on disk exactly as
`coverage._blob_ok` does.

| source | req | rows | PASS | BLOCKED | FAIL | DEFER | N/A | distinct blobs | stale | dup cite | sha OK | sha MISMATCH | blob absent | unparseable | first PASS | last PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `injuries` | yes | 187 | 147 | 0 | 0 | 40 | 0 | 7 | 141 | 140 | 7 | 0 | 0 | **0** | 09-07T13:06Z | 09-13T23:12Z |
| `schedules` | yes | 186 | 186 | 0 | 0 | 0 | 0 | 86 | 97 | 100 | 85 | 0 | **1** | 0 | 09-06T18:50Z | 09-13T23:12Z |
| `depth_charts` | yes | 186 | 186 | 0 | 0 | 0 | 0 | 8 | 179 | 178 | **0** | **7** | **1** | 0 | 09-06T18:50Z | 09-13T23:12Z |
| `weekly_rosters` | no | 186 | 186 | 0 | 0 | 0 | 0 | 9 | 178 | 177 | **0** | **8** | **1** | 0 | 09-06T18:50Z | 09-13T23:12Z |
| `official_injury_report` | yes | 180 | 94 | 32 | **54** | 0 | 0 | 92 | 2 | 2 | 92 | 0 | 0 | 0 | 09-07T00:24Z | **09-11T00:44Z** |
| `official_inactives` | yes | 195 | 112 | 29 | **54** | 0 | 0 | 95 | 17 | 17 | 95 | 0 | 0 | 0 | 09-07T00:24Z | 09-13T19:14Z |
| `espn_injuries_json` | no | 177 | 148 | 29 | 0 | 0 | 0 | 148 | 0 | 0 | 148 | 0 | 0 | 0 | 09-07T00:24Z | **09-11T00:44Z** |
| `official_transactions` | no | 177 | 0 | 177 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | never | never |
| `pbp_participation` | no | 98 | 0 | 0 | 0 | 0 | 98 | 0 | — | — | — | — | — | — | watch-only | watch-only |
| `snap_counts` | no | 98 | 0 | 0 | 0 | 0 | 98 | 0 | — | — | — | — | — | — | watch-only | watch-only |
| `hardrock_market_snapshot` | n/r | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | delivery | delivery |
| `official_status_evidence` | n/r | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | delivery | delivery |

Totals across PASS rows: **687 verify (64.8%) · 368 hash-mismatch (34.7%) · 6 absent (0.6%)**.
Stale 614, new-content 445, `content_unchanged` absent 2.

**Malformed / unparseable: zero.** Every one of the 447 distinct stored blobs decoded as UTF-8
and parsed under its declared `content_kind` — 85 CSV, 148 JSON, 187 HTML (and every HTML blob
carries its registry `content_markers`: median 15 injury-word hits on `official_injury_report`,
median 21 `inactive` hits on `official_inactives`). There is no parse defect anywhere in the
store today.

### 2a. Per-source notes that matter

- **`injuries`** — 40 DEFERRED `SOURCE_NOT_YET_PUBLISHED` (404) from 2026-09-06T18:50Z to
  2026-09-07T12:42Z, then published. Seven content vintages: 12 → 12 → 30 → 140 → 168 → *49
  (delivered)* → 183 data rows. The 49-row vintage is `CAPTURED_BY_DELIVERY`
  (`EXTERNAL_AUTHORITATIVE_DELIVERY`, NFL final report, 2026-09-13T12:47Z) and is **smaller
  than both its neighbours** — it is a different document, not a regression. Do not read the
  row count as a trend.
- **`schedules`** — highest churn in the store: 86 content vintages in 186 captures, because
  nflverse restamps `games.csv` continuously. This is why the lost-manifest runs (§3) left
  *only* schedules blobs behind: on those runs nothing else had changed.
- **`depth_charts` / `weekly_rosters`** — see §3a. 100% hash failure; not a corruption.
- **`official_injury_report` / `espn_injuries_json`** — **no successful capture since
  2026-09-11T00:44:00Z.** At Sunday 1 p.m. kickoff the freshest injury-report page in the
  store was **64.3 hours old**; at 4:25 p.m. **67.7 h**; at SNF **71.6 h**.
- **`official_transactions`** — 177 consecutive `ENDPOINT_NOT_YET_VERIFIED`. Registered,
  wired, no URL, never captured. It is a declared open debt, not a failure.
- **`pbp_participation` / `snap_counts`** — 98 `NOT_APPLICABLE` each, correct: `watch_only=True`
  keeps them out of the vintage path by design.

---

## 3. Blob integrity findings

### 3a. 368 hash mismatches — a reduce-durability contract defect, not corruption

Every `durability: "reduce"` PASS row (368 of 368) fails `coverage._blob_ok` with
`RAW_SHA256_MISMATCH`. Worked example, first occurrence `20260906T201020Z`:

```
blob     nfl/vintage/depth_charts.76d7bcb384ec11e3.reduced.csv(.gz)
declared sha256 = 76d7bcb384ec11e3…  n_bytes = 47,641,094  n_lines = 501,069
stored   sha256 = b610bbc735f54c0c…  actual stored content = 2,177 lines, 5 columns
reduced.full_bytes_ephemeral_at = nfl_vintage/raw/depth_charts.76d7bcb384ec11e3.csv
```

The declared hash is **correct for a file that is not in the repository**. Proof: three
`depth_charts` and four `weekly_rosters` full-byte files survive by accident in the gitignored
`nfl_vintage/raw/`, and `sha256sum` on them reproduces the manifest digest exactly
(`depth_charts.a14e8dfe865a4b03.csv → a14e8dfe865a4b03…`,
`weekly_rosters.cef497eaeddef07b.csv → cef497eaeddef07b…`). So `sha256`, `n_bytes` and
`n_lines` in these rows all describe the upstream artifact; the artifact actually persisted
carries **no recorded hash of its own** and cannot be verified by anything.

Consequence, already live: `performed_from_manifest` excludes all 368 on artifact
verification. `reduce_recoverability_checked` is `false` on all 368 and
`reduce_recoverability_assumption` is the bare string *"upstream retains full history for this
source"* — untested.

Also note `sha256_is_of: "uncompressed_bytes"` is asserted on 366 of the 368. On these rows
that field is **false as written**: the bytes it names were never stored.

### 3b. 6 manifest rows whose blob is absent

Capture runs `20260906T185049Z` and `20260906T185100Z` cite repo-root-relative paths
`raw/depth_charts.76d7bcb384ec11e3.csv`, `raw/schedules.c563178ace7c6637.csv`,
`raw/weekly_rosters.5ec59c5228198f57.csv`. No `raw/` directory exists at the repo root.
Excluded as `RAW_ARTIFACT_MISSING_ON_DISK`. Earliest two runs only; the path convention changed
at `20260906T201020Z` and has been stable since.

### 3c. 3 rows whose blob resolves only with `.gz` appended

Run `20260906T201020Z` names `…reduced.csv`; only `…reduced.csv.gz` exists. Cosmetic relative
to 3a (those rows fail the hash anyway) but it means a naive path check overstates absence.

### 3d. 48 blobs on disk with no manifest row

All `schedules.*.csv.gz`, ~507 KB each, every one self-consistent (content hashes to the digest
embedded in its own filename) and **none** of their content hashes appears anywhere in the
manifest. Each was added by a separate commit; all 48 commits are authored
`nfl-capture[bot]`, titled `NFL … capture unknown`, and **none touched
`nfl/vintage_manifest.jsonl`**. Distribution: 2026-09-08 → 9, 2026-09-09 → 30, 2026-09-10 → 9.

Widening to all bot commits: **198 total — 148 titled with a real `capture_id`, all 148 wrote
manifest rows; 50 titled `unknown`, all 50 wrote zero manifest rows.** By day, `unknown` runs:
09-08 → 9, 09-09 → 31, 09-10 → 10.

The manifest therefore contains **no rows at all dated 2026-09-09**, against 31 capture runs
that demonstrably executed that day. It also holds none dated 2026-09-12.

This is already named in `.github/workflows/nfl-capture.yml` and guarded by the step
*"Assert the capture produced a manifest row"*, which fails the run if
`manifest rows appended: [1-9]` is not in the log. The guard postdates the loss; the 2026-09-09
evidence is not recoverable.

### 3e. A scanner trap worth recording

`nfl/vintage/delivered_injury_evidence.df1dd90380b8d720.html.gz` is **not** an orphan, but it is
invisible to any scan that reads only `value.blob`: it is referenced from
`value.delivery.raw_evidence_blobs` on row `20260913T124700Z`. Any future orphan check must read
both keys or it will report a false positive.

### 3f. `check_retention.py` does not cover this store

`nfl/tools/check_retention.py` runs green — `R4 NO_VINTAGE_DELETED`, `R5 MANIFEST_APPEND_ONLY`,
`R8 NO_ORPHAN_BLOBS`, plus retention policy PASS for both watched sources — but it is pointed at
`availability.BLOB_ROOT` / `availability.MANIFEST`, which is **2 blobs and 6 rows**. Its own
output says so: `blobs before 0 after 2 · rows before 0 after 6`. `R8 NO_ORPHAN_BLOBS` passed
while 48 orphan blobs sat in `nfl/vintage/`, because that directory is outside its scope. The
check is not wrong; its scope is narrower than its name reads.

---

## 4. Week-1 coverage against the declared plan

`coverage(2026, 1, manifest_path='nfl/vintage_manifest.jsonl')`, as of 2026-09-14T04:37Z:

```
State.FAIL  PERISHABLE_WINDOWS_MISSED
n_targets 63   covered 15   missed 47   not_yet_due 1
attributed_captures 103   unattributed_captures 1,049   total_pass_rows 1,061
artifacts_verified true   legacy_claim_rows 6
```

Plan = 79 targets over 16 games from `schedules.88d66eade90ab738.csv.gz`; 16 are `seal` /
`unschedulable` bookkeeping, leaving 63 obligations.

| kind | expected | covered | missed | not yet due | authorised source |
|---|---|---|---|---|---|
| `practice` | 31 | 14 | 17 | 0 | `official_injury_report` |
| `final_status` | 16 | 0 | 16 | 0 | `official_injury_report` |
| `inactives` | 16 | 1 | 14 | 1 (DEN@KC) | `official_inactives` |
| **total** | **63** | **15** | **47** | **1** | |

The 15 covered are `practice_thu` for 14 games plus `inactives` for SF@LA, and **all 15 were
discharged by two captures at 2026-09-10T23:28:38Z** — one `official_injury_report` and one
`official_inactives`, both from an anchored GitHub-Actions run that declared its targets before
fetching. Chronology-valid: **121 game-anchored (row, target) pairs checked, 0 captures at or
after their own kickoff.** No leakage of a post-kickoff capture into a pregame obligation.

### 4a. Twelve of the 47 "missed" are a schema divergence, not missing evidence

The manifest holds **18 rows with `spec_version: "official-inactives-1"`**, written by
`nfl/production/nonqb/inactives.py` (not by `capture_vintage.py`). They carry `game_id`,
`source_url`, `published_at`, `http_status: 200`, and a `sha256` that **verifies against the
blob on disk** — all 18 checked, all `SHA_OK`, all retrieved strictly before their kickoff.
They cover 13 distinct games:

```
20260910T234420Z  SF_LA  ×2     (blob sha 423d… / earlier vintage)
20260913T160017Z  BUF_HOU, CLE_JAX, NYJ_TEN, CHI_CAR, ATL_PIT, BAL_IND, NO_DET, TB_CIN
                  published_at 2026-09-13T15:46:51Z, retrieved 16:00:17Z (kickoff 17:00Z)
20260913T191400Z  ARI_LAC, GB_MIN, MIA_LV, WAS_PHI  (each twice)
                  published_at 2026-09-13T19:03:50Z, retrieved 19:14:00Z (kickoff 20:25Z)
```

`coverage.py` scores every one of the 12 Sunday games as `inactives: MISSED`, because
`execution.eligible_targets` reads **only** `value.discharge_eligibility`, and these rows have
no such block. That refusal is correct under Directive 7 §6 as the rule is written. The
reportable fact is the divergence itself: **two writers append to one manifest under two
schemas, and only one of them can ever discharge an obligation.** The evidence exists, is
hash-verified, is game-anchored and is chronologically valid; the coverage report cannot see it.

---

## 5. The 2026 week-1 live slate — what was available before each kickoff

Fourteen game directories under `nfl/research/live/2026_01_*`. "Last before KO" is the most
recent PASS capture with `retrieved_at` **strictly** before kickoff; `T-` is its lag.
`inactives evidence` is a hash-verified, game-anchored `official-inactives-1` or
discharge-eligible `official_inactives` row naming that game.

| game | kickoff (UTC) | injuries | schedules | depth_charts | weekly_rosters | official_injury_report | official_inactives (page) | espn_json | transactions | game-anchored inactives evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| SF@LA | 09-11 00:35 | T-0.19h | T-0.19h | T-0.19h | T-0.19h | **T-0.19h** | **T-0.19h** | T-0.19h | none | **YES** (discharged) |
| ATL@PIT | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| BAL@IND | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| BUF@HOU | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| CHI@CAR | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| CLE@JAX | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| NO@DET | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| NYJ@TEN | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| TB@CIN | 09-13 17:00 | T-0.72h | T-0.72h | T-0.72h | T-0.72h | T-64.3h | T-1.00h | T-64.3h | none | YES (not discharged) |
| ARI@LAC | 09-13 20:25 | T-0.65h | T-0.65h | T-0.65h | T-0.65h | T-67.7h | T-1.18h | T-67.7h | none | YES (not discharged) |
| GB@MIN | 09-13 20:25 | T-0.65h | T-0.65h | T-0.65h | T-0.65h | T-67.7h | T-1.18h | T-67.7h | none | YES (not discharged) |
| MIA@LV | 09-13 20:25 | T-0.65h | T-0.65h | T-0.65h | T-0.65h | T-67.7h | T-1.18h | T-67.7h | none | YES (not discharged) |
| WAS@PHI | 09-13 20:25 | T-0.65h | T-0.65h | T-0.65h | T-0.65h | T-67.7h | T-1.18h | T-67.7h | none | YES (not discharged) |
| **DAL@NYG** | 09-14 00:20 | T-1.13h | T-1.13h | T-1.13h | T-1.13h | T-71.6h | T-5.10h | T-71.6h | none | **NO** |

Read the `official_inactives` column carefully: for the twelve Sunday games it is the
**T-90 news-article capture** written by `inactives.py`, not the `nfl.com/inactives/` page —
the page itself has not been fetched successfully since 2026-09-11T00:44Z.

**DAL@NYG is the one live game with no inactives evidence of any kind in the capture store.**
The only inactives information for it is
`nfl/research/live/2026_01_DAL_NYG/INACTIVES_DISCOVERY_QUARANTINED.json` — an owner-observed
RotoWire screenshot, explicitly marked `governing: false` and third-party. That quarantine is
correct and should stay.

Counts: **14/14** games had `injuries`, `schedules`, `depth_charts`, `weekly_rosters` within
~1.2 h of kickoff. **1/14** had a `official_injury_report` fresher than 64 h. **13/14** had
game-anchored inactives evidence; **1/14** had it in a form `coverage.py` accepts.
**0/14** had `official_transactions` — it has never been captured at all.

---

## 6. Stale, duplicate, missing, malformed — consolidated

| category | definition used | count | where |
|---|---|---|---|
| stale capture | PASS with `content_unchanged: true` | **614** of 1,061 | mostly `depth_charts` 179, `weekly_rosters` 178, `injuries` 141, `schedules` 97 |
| duplicate citation | PASS row citing an already-stored blob | **614** | same rows; 447 distinct blobs behind 1,061 rows |
| duplicate blob | two distinct files with identical content | **0** | content-addressed naming makes this impossible |
| missing game | week-1 obligation with no in-window authorised attributed capture | **47** of 63 | §4 |
| missing pregame source | (game, required source) pair with nothing before kickoff | **14** | `official_transactions`, all 14 games |
| malformed / unparseable blob | stored bytes that fail their declared `content_kind` | **0** of 447 | — |
| blob fails its manifest hash | re-hash ≠ declared `sha256` | **368** rows / 15 distinct blobs | §3a |
| manifest row, blob absent | cited path resolves to nothing | **6** | §3b |
| blob present, no manifest row | on disk, cited by nothing | **48** | §3d |
| capture run, no manifest row | bot commit with zero appended rows | **50** | §3d |
| capture with unreadable clock | PASS with no `retrieved_at` anywhere | **0** | clock guard holds |
| chronology violation | attributed capture at or after its kickoff | **0** of 121 | §4 |

Note on stale vs duplicate: `test_capture_states.test_f_unchanged_content_is_a_measurement_not_a_duplicate`
is explicit that a re-observation of identical bytes is evidence the page has not moved. The 614
are counted here because they bear on *freshness*, not because they are waste.

---

## 7. nflverse play-by-play coverage of 2026 week 1 — confirmed, and it is a fact, not a defect

Verified independently by decompressing and parsing
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz` (retrieved 2026-09-14T00:25:56Z,
679,935 bytes): **exactly 10 distinct `game_id` values, 1,738 plays, all `season=2026, week=1`.**

```
ATL_PIT 175 · BAL_IND 167 · BUF_HOU 180 · CHI_CAR 196 · CLE_JAX 148
NE_SEA  166 · NO_DET  218 · NYJ_TEN 162 · SF_LA   157 · TB_CIN 169
```

The earlier snapshot `pbp_2026.d9e442ae17ba88e7.csv.gz` (2026-09-11T19:16Z) holds the two
openers only, NE@SEA and SF@LA. Both provenance files are internally consistent with the blobs.

**Not yet published: ARI@LAC, GB@MIN, MIA@LV, WAS@PHI (all 20:25Z / 4:25 p.m. ET) and
DAL@NYG (SNF).** DEN@KC had not kicked off at measurement time. Relative to the 14-game live
slate this is **9 of 14 present, 5 absent**; the 10th published game, NE@SEA, has no
`research/live/` directory. Quote it that way — "10 of 14" is wrong by one game in each
direction.

This is an upstream publication lag, expected within hours of the late window, and the
provenance files already record retrieval clocks rather than inventing publication clocks. It is
a **coverage fact**. It is not an outage and nothing should be repaired for it. The only thing
it constrains is analysis: any week-1 outcome computation run today is on 9 of 14 slate games
and must say so.

---

## 8. Outage classification

Different remedies; kept apart deliberately.

### SOURCE OUTAGE — the origin did not serve the bytes

| # | what | evidence | remedy |
|---|---|---|---|
| S1 | `injuries_2026.csv` 404 before publication | 40 DEFERRED `SOURCE_NOT_YET_PUBLISHED`, 2026-09-06T18:50Z → 09-07T12:42Z, then 200 | **none — worked as designed.** DEFERRED is the correct state and it self-cleared. |
| S2 | nflverse pbp late-window lag | §7 | none. Re-poll; do not backfill from another source. |
| S3 | `pbp_participation` / `snap_counts` 404 for 2026 | registry notes, 98 `NOT_APPLICABLE` rows each | none here; watch-only by decision. |

**There is no source outage on any official source.** nfl.com and ESPN are recorded
`VERIFIED_REACHABLE_EXTERNALLY`. Nothing in this store shows either origin failing to serve.

### PARSER OUTAGE — bytes arrived, code could not turn them into a result

| # | what | evidence | status |
|---|---|---|---|
| P1 | `AttributeError: 'Source' object has no attribute 'content_markers'` | **108 FAIL rows**, 54 runs, 54 × `official_injury_report` + 54 × `official_inactives`, 2026-09-10T05:05:18Z → 23:15:38Z (18.2 h) | **FIXED.** `capture_vintage.py:115-116` now forwards `content_markers` from the registry; `test_source_registry.py:529` locks it. The first successful attributed capture, 23:28:38Z, is 13 minutes after the last failure. |
| P2 | `SOURCE_RAISED` used for a client-side exception | same 108 rows | **open, cosmetic-but-not.** The code names the source for a defect in our own code. Every one of these was a parser outage filed as a source outage. |

Zero parser outages are live today: all 447 stored blobs parse.

### WORKFLOW OUTAGE — ours; the pipeline did not run, did not record, or recorded unusably

| # | what | evidence | severity |
|---|---|---|---|
| W1 | **Anchored capture stopped before the main slate.** Last GitHub-Actions capture commit `1034e27`, 2026-09-11T00:44:04Z. `nfl-t90.yml` has crons for 09-13 15:30–16:50Z, 18:55–20:15Z, 22:50–00:10Z and 09-14 22:45–00:05Z; `nfl-status.yml` through 09-12T16:00Z. None produced a manifest row. | **highest.** It is the sole cause of 47 missed targets. |
| W2 | **The surviving executor cannot reach the official sources.** All 2026-09-13 rows: `basis: LOCAL_INVOCATION`, `is_github_actions: false`, `basis_can_discharge: false`; 18 runs with `NO_EGRESS` on `official_injury_report`, `official_inactives`, `espn_injuries_json`. 90 such rows / 32 runs overall. | high. Two independent blocks at once: no egress, and a basis that cannot discharge even with egress. |
| W3 | **50 runs wrote a blob and no manifest row**, 48 orphan blobs, all of 2026-09-09 absent. §3d | high, partly mitigated — guard now in `nfl-capture.yml`; the lost evidence is gone. |
| W4 | **Reduce durability persists an unhashed artifact.** §3a. 368 rows, 34.7% of PASS, self-excluding from discharge. | high. Every `depth_charts` and `weekly_rosters` capture is unverifiable on its own bytes. |
| W5 | **Two manifest writers, two schemas.** §4a. 18 verified, game-anchored inactives rows invisible to `coverage.py`. | high. Causes 12 of the 47 "missed" to misstate what the store holds. |
| W6 | 6 rows citing a `raw/` path that does not exist. §3b | low, historical, first two runs only. |
| W7 | `check_retention.py` guards the availability store, not the vintage store. §3f | medium. `R8 NO_ORPHAN_BLOBS` was green throughout W3. |
| W8 | `official_transactions` never captured, 177 BLOCKED. | declared debt, not a regression. Needs a verified endpoint from the networked agent. |

**Do not conflate W1/W2 with a source outage.** Nothing here shows nfl.com or ESPN failing.
The remedy for W1 is a runner that fires; for W2, an executor with egress *and* an anchored
basis; for S1/S2, patience. Filing any of these as the other produces the wrong fix.

---

## 9. Evidence ceiling

What this pass **cannot** establish, and what would be needed:

1. **What happened on 2026-09-09.** Thirty-one runs executed, zero rows survive, and the only
   residue is 30 `schedules` blobs. Whether the NE@SEA inactives window (22:50Z–00:10Z, four
   runs inside it: 22:56, 23:07, 23:23, 23:46Z) captured the page, was blocked, or failed is
   **not recoverable from this repository.** Perishable pages are overwritten in place. No
   remedy exists; the guard prevents recurrence only.
2. **Whether the reduced blobs are faithful reductions.** Their content has no recorded hash
   and `reduce_recoverability_checked` is `false` on all 368. Three `depth_charts` and four
   `weekly_rosters` full-byte files happen to remain in gitignored `nfl_vintage/raw/`; every
   other vintage is unverifiable. Closing this needs a second hash field for the persisted
   artifact, and for the recoverability assumption to be tested rather than asserted.
3. **Whether any anchored cron actually fired on 09-13/09-14.** Absence of a commit is not
   proof a run did not start. GitHub Actions run history is outside this checkout.
4. **`injuries` row-count comparability.** The 49-row delivered vintage and the 183-row
   nflverse vintage are different documents. Nothing here establishes a mapping between them.
5. **`official_transactions` semantics.** Never captured; 177 BLOCKED rows say only that no
   endpoint is verified.
6. **Any statement about week-1 outcomes.** Play-by-play exists for 9 of the 14 live-slate
   games (§7). Anything computed today is on that subset.
7. **Sample size.** One week of one season, 191 capture runs over 8 days. No claim about
   capture reliability *rates* is supportable from this, and none is made above — the counts
   are census counts of this store, not estimates.

## 10. Reproduction

```bash
cd /home/user/nfl
python3.12 -c "
from nfl.capture.coverage import coverage, performed_from_manifest
print(performed_from_manifest('nfl/vintage_manifest.jsonl').evidence['n_pass_rows'])
print(coverage(2026,1,manifest_path='nfl/vintage_manifest.jsonl'))"
python3.12 nfl/tools/check_retention.py          # note its scope: §3f
git log --author=nfl-capture --format='%h|%ad|%s' --date=iso   # 198 commits, 50 'unknown'
```

Hash sweep, orphan scan and the per-game table were computed with throwaway scripts in the
session scratchpad; every number above is reproducible from the manifest and the blobs alone.

**CODE CHANGED: NO.**

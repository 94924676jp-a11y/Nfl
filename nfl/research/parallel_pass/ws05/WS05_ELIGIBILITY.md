# WS05 — ELIGIBILITY AS AN ARCHITECTURE LAYER

**CODE CHANGED: NO.** Research only. Repo `/home/user/nfl`, HEAD `57d38ad`.
Every number below was read out of the tree on 2026-09-14 with `python3.12`,
not recalled and not taken from a prose document. Where a document and the
bytes disagree, the bytes are quoted and the document is named.

---

## 0. THE ONE-SENTENCE FINDING

Eligibility is not a layer in this system. It is **four disconnected
half-implementations** — a quarantine (`allowlist`), a debt object that nothing
calls (`ingest/eligibility`), a pool filter that runs on an explicitly
**ephemeral** file and exempts quarterbacks (`nonqb/roster_status`), and a
gameday override that only fires when a human hand-delivers bytes
(`nonqb/inactives`) — and the one source that could unify them
(`official_transactions`) has **no URL at all**.

---

## 1. METHOD

- Every capture source enumerated from `nfl/capture/registry.py` (10 specs) and
  cross-checked against `nfl/vintage_manifest.jsonl` (1,672 rows) and the 490
  blobs in `nfl/vintage/`.
- **Column headers were read from the files**, not from documentation: gzip
  blobs opened with `csv.DictReader`, JSON blobs with `json.load`, HTML blobs
  scanned for their own content markers.
- Observation times taken from `nfl.research.shadow.information_set`
  (`first_observation()`), which bounds each blob by the earliest `capture_id`
  it appears in. Kickoffs from `schedules.135fcc9341866637`.
- Nothing was executed that writes. No suite was run.

---

## 2. WHAT THE MANIFEST AND THE DISK ACTUALLY SAY

Manifest rows by source and state (1,672 total):

| source | PASS | BLOCKED | FAIL | DEFERRED | N/A | blobs on disk |
|---|--:|--:|--:|--:|--:|--:|
| `official_inactives` | 112 | 29 | 54 | 0 | 0 | 95 |
| `injuries` | 147 | 0 | 0 | 40 | 0 | 7 |
| `depth_charts` | 186 | 0 | 0 | 0 | 0 | 6 (3 raw) |
| `schedules` | 186 | 0 | 0 | 0 | 0 | 132 |
| `weekly_rosters` | 186 | 0 | 0 | 0 | 0 | 7 (4 raw) |
| `official_injury_report` | 94 | 32 | 54 | 0 | 0 | 92 |
| `espn_injuries_json` | 148 | 29 | 0 | 0 | 0 | 148 |
| **`official_transactions`** | **0** | **177** | 0 | 0 | 0 | **0** |
| `pbp_participation` | 0 | 0 | 0 | 0 | 98 | 0 |
| `snap_counts` | 0 | 0 | 0 | 0 | 98 | 0 |
| `official_status_evidence` | 1 | 0 | 0 | 0 | 0 | 1 |
| `hardrock_market_snapshot` | 1 | 0 | 0 | 0 | 0 | 1 |

**The 112 `official_inactives` PASSes are not 112 inactive lists.** Of the 95
stored blobs, **92 carry an empty-state marker** (`check back soon` /
`not yet available`). Exactly **three** carry real content, and none of the
three came from the registered URL `https://www.nfl.com/inactives/`:

| sha16 | bytes | `source_url` | games served |
|---|--:|---|---|
| `91bdf335602a7475` | 70,098 | `/news/australia-game-inactives-san-francisco-49ers-at-los-angeles-rams` | SF@LA |
| `3fc8c4f13968d023` | 889,867 | `/news/inactive-reports-sunday-week-1-2026-nfl-season` | 9 Sunday games |
| `423d0c34811cd6d6` | 904,425 | same news article, later revision | 4 Sunday games |

The registry's declared inactives endpoint has **never once published a list**
into this tree. The only working path is a news article whose URL is not in
`registry.REGISTRY`.

---

## 3. EVIDENCE MATRIX

Columns exactly as specified. "USED BY MODEL?" means it reaches a projected
quantity; "USED BY BOARD?" means it reaches a product artifact a human reads.

| SOURCE | FIELD | OBSERVATION TIME | AUTHORITATIVE? | AVAILABLE BEFORE KICKOFF? | USED BY MODEL? | USED BY BOARD? | FAILURE MODE |
|---|---|---|---|---|---|---|---|
| `weekly_rosters` **raw** (`nfl_vintage/raw/*.csv`, 36 cols) | `status` ∈ {ACT, DEV, RES, CUT, EXE, RET, INA} | manifest `capture_id`; 7 vintages 2026-09-06T18:50Z → 2026-09-13T15:45Z | nflverse mirror, ARCHIVE authority (`registry.authority=ARCHIVE`) | **PARTLY.** 2026-09-13T15:45:56Z is 1h14m before the 17:00Z Sunday kickoffs — yes. But the file is a *rolling current-state* file, so pre-kickoff it is membership and post-kickoff it is the dress list | **YES** via `roster_status.active_pool`, but only under flag `active_roster_only` (R5–R8; the `V1_CANDIDATE` control has it off) and **only for non-QB** | Indirectly (`_r5` evidence block in the artifact) | (a) The column is **dropped by the vintage reduction** — durable file is 5 cols. R5 reads `nfl_vintage/raw/`, which `capture_vintage._persist` labels `full_bytes_ephemeral_at`. (b) `RET` is in neither `EXCLUDED` nor `POSTHOC`, so 23 retired players (9 of them QB/RB/WR/TE, incl. Adam Thielen, Teddy Bridgewater) are **kept in the pool** and counted as `kept_unrecognised_status`. (c) post-kickoff re-partition: ACT silently becomes "dressed" |
| `weekly_rosters` **raw** | `status_description_abbr` ∈ {A01, P01, P02, P03, P06, P07, R01, R02, R04, R05, R27, R40, R48, R49, W03, E02} | same | same | same | **NO** | **NO** | **No decoder exists anywhere in the repo.** Grepped: the string appears in exactly 3 places, one of which forbids it (`delivered_injuries.ROSTER_FORBIDDEN_COLUMNS`). This is the field that separates practice-squad types, IR variants and elevations. Measured: `ACT`+`P07` = 2 SF players (Okoronkwo, Hodge) and `ACT`+`P01` = 1 LA player — **the standard gameday elevation signature** — present in `fb79…` and `cef4…`, both observed *after* the SF@LA kickoff, so on this evidence the elevation flag is currently post-hoc |
| `weekly_rosters` **reduced** (`nfl/vintage/*.reduced.csv.gz`) | `season, week, team, gsis_id, position` — verified by `zcat`, 5 cols, ~2,950 rows | same | same | yes | Pool construction and identity | `board.roster_identity` reads it | Carries **no eligibility fact at all**. 3 of 7 roster vintages (`0b005c45d924a541`, `125c300ff066d314`, `e157129706145664`) have **no raw counterpart on disk**: their `status` is **irrecoverable** |
| `official_inactives` (95 html blobs) | free-text names segmented per club; parsed to `OFFICIAL_INACTIVE` gsis ids | SF@LA 2026-09-10T23:44:20Z = **T-50m**; Sunday article 2026-09-13T16:00:17Z and T19:14:00Z | **YES** — `SourceAuthority.OFFICIAL`, `authority_rank=1`, the only source that can discharge kind `inactives` | **YES when it arrives.** Arrived for 1 of 2 due games in the T-90 reconciliation (`t90_obligation_reconciliation.json`: inactives COVERED 1, MISSED 1, NOT_YET_DUE 14) | **YES** — `layers.appearance` zeroes appearance draws; after commit `622fdd5` also zeroes QB dropback share | **YES** — `daily_board` emits `official_inactive`, `POST_INACTIVES_COMPLETE`, `n_official_inactive`, `inactive_quarterbacks_still_owning_dropbacks` | **92 of 95 captures are the empty page.** D02 in `OPEN_DEFECTS.json` records that the empty page once parsed to 311 fake "names". The guard now exists, but D02's own `test_required` — "an assertion that a capture whose parse yields `INACTIVES_PAGE_EMPTY_STATE` cannot discharge the obligation" — is **still open**. Real bytes have only ever arrived by human hand-off |
| `official_injury_report` (92 html blobs) | season, week, team, player slug + display name, designation | 2026-09-07T00:24Z → 2026-09-11T00:43Z | **YES** — OFFICIAL, `authority_rank=1`, serves kinds `practice` + `final_status` | Yes in principle | **NO** | **NO** | Parser `nfl/parse/injury_report.py` exists and is tested, but **no production module imports it** (grep: only `nfl/tests/`). The page carries **zero `00-0NNNNNN` gsis ids** (measured by the parser's own docstring), so every row is `PLAYER_UNMAPPED`. 54 manifest rows are `FAIL[SOURCE_RAISED]`, 32 `BLOCKED[NO_EGRESS]` |
| `injuries` (nflverse, 7 blobs) | `report_status` ∈ {Out, Questionable, Doubtful, ''}, `practice_status` ∈ {Full/Limited/DNP}, `report_primary_injury`, `practice_*` | 2026-09-07T13:06Z → 2026-09-13T15:45Z | ARCHIVE / mirror. Registry note: "does NOT discharge a practice or final-status target" | Yes, but **terminal weekly snapshot** — `GAP-INJURY-VINTAGE` says the intraweek cascade cannot be reconstructed | **YES** — `appearance_r8` reads `report_status`/`practice_status` into `inj_status`/`inj_practice`; `readiness.NEEDS_REPORT_STATUS = True` gates the whole non-QB chain | Via readiness verdicts | **Schema is unstable across 7 captures: 4 distinct headers** (13/14/15/16 cols; `report_primary_injury`, `report_secondary_injury`, `practice_secondary_injury` appear and disappear). **Coverage is thin and mostly unfilled**: `cd7338473dd852d0` = 167 rows, 32 teams, **8** with `report_status` filled; `66e960ec81fccc6e` = 182 rows, 32 teams, **61** filled. This is D03, unrepaired, and is the direct cause of the QB-only Sunday board |
| `depth_charts` **raw** (3 blobs, 12 cols) | `dt, team, player_name, espn_id, gsis_id, pos_grp_id, pos_grp, pos_id, pos_name, pos_abb, pos_slot, pos_rank` | source-provided per-row `dt`; newest `2026-09-13T12:42:08Z` | ARCHIVE, but `ScopeKind.EXACT_TIMESTAMP` — the **only** source with a genuine per-row effective instant | **YES** — `GAP-DEPTH-CHART-PIT` measures 6.3–18.7h before kickoff, median 10.8 | **YES** — `depth_vintage` + `appearance_r7`; `board.depth_rank` feeds R6 tiering | **YES** | **It is not an eligibility signal and must not be read as one.** Measured against `cef497…`: the 1,963 charted players break down **ACT 1,689, RES 232, INA 25, EXE 4, CUT 3, DEV 1, not-on-roster 9**. A player on injured reserve still holds a depth rank. Reduction drops `espn_id`, `player_name`, `pos_slot`, `pos_grp` — and **3 of 6 depth vintages have no raw counterpart**, so those four columns are gone for them |
| `espn_injuries_json` (148 blobs) | `status` ∈ {Active 451, Questionable 147, **Injured Reserve 162**, Out 36, **Suspension 4**} per capture; `type.name` = `INJURY_STATUS_*`; `athlete.position`; 800 rows × 32 teams | 2026-09-07T00:24Z → 2026-09-11T00:43Z, at ~20-minute cadence | **NO** — `CANDIDATE_FALLBACK`, `authority_rank=9`, registry: "discharges NO target and does not inherit OFFICIAL authority by being easier to consume" | **YES** — 148 pre-kickoff captures exist | **NO** | **NO** | **This is the largest unconsumed eligibility corpus in the tree.** It is the only source carrying `Injured Reserve` and `Suspension` as first-class statuses. Grep for consumers returns only `registry.py` and `probe_nfl_sources.py`. It carries **no direct athlete id** — the ESPN id must be regexed out of `athlete.links[0].href`. I measured the bridge: joining that id to `weekly_rosters` raw `espn_id` resolves **691 of 800 rows (86.4%)** to a gsis id; the 109 unresolved are overwhelmingly IR and practice-squad players absent from the week-1 roster rows |
| **`official_transactions`** | *nothing* — signings, releases, IR placements, elevations | never observed | OFFICIAL, `authority_rank=1` | **NO** | **NO** | **NO** | `url_template = None`. 177 manifest rows, all `BLOCKED[ENDPOINT_NOT_YET_VERIFIED]`. Registry note: "Candidate for closing the prediction-time eligibility debt." **Zero bytes exist** |
| `official_status_evidence` (1 blob, delivered) | 19 rows, 3 clubs (MIA, MIN, WAS); `game_status` ∈ {BLANK 9, UNSPECIFIED 10}; `practice_status` ∈ {FP 13, LP 5, DNP 1} | 2026-09-13T18:12:01Z | delivered, `DELIVERED_EXPLICIT` | yes for those 3 clubs | **NO** | **NO** | Its own manifest row records `readiness_contract_verdict: "DOES_NOT_SATISFY"`. `BLANK`/`UNSPECIFIED` are explicitly **not** designations and **not** active statuses (`never_inferred_into_active: true`). A correct refusal, not a usable fact |
| `delivered_injury_evidence` (1 html blob) | `EXPLICIT_TEAM_NO_INJURY_DESIGNATIONS`, 20 clubs, 48 rows with `report_status` 48/48 filled | 2026-09-13T12:47Z | `EXTERNAL_AUTHORITATIVE_DELIVERY`, cites `nfl.com/news/nfl-week-1-injury-report-2026-season` | yes | via `injuries.0bc645a4b9aa6255` (the only injuries blob with 100% `report_status`) | Via readiness | Covers **20 of 32 clubs**. `clears_a_readiness_gate: false` on the no-designation rows — see `NO_DESIGNATION_CONTRACT_MISMATCH.json` |
| `schedules` (132 blobs) | `gameday`, `gametime`, `game_id` — the **kickoff clock** every eligibility guard is measured against | continuous | ARCHIVE | yes | yes | yes | `away_qb_id`/`home_qb_id` are quarantined POSTHOC (`_SCH_POSTHOC`, measured 285/285 populated for 2024 vs 0/272 for 2026). So the schedule names a starting QB **only after the fact** |
| `pbp_participation`, `snap_counts` | per-play / per-game participation | — | INDEPENDENT_MIRROR, `watch_only=True` | **NO — 404 for 2026** (measured 2026-09-08) | no | no | `GAP-2026-PARTICIPATION`. 98 `NOT_APPLICABLE` rows each. `snap_counts` carries no pass/run split |
| `rotowire` screenshot (DAL@NYG) | 12 transcribed inactive names | 2026-09-13 ~19:17 ET | **NO** — aggregator | yes | **NO** | **NO** — `governs_nothing: true` | Correctly quarantined in `INACTIVES_DISCOVERY_QUARANTINED.json`. It records that Najee Harris was listed inactive while the sealed board projected him 4.79 carries (15.2% of the NYG pool) — **the exact cost of the gap, priced** |

### The ten pregame facts, scored

| Pregame fact | Do bytes exist? | Where | Reaches a forecast? |
|---|---|---|---|
| **Active 53** | YES, 4 raw roster captures | `weekly_rosters.status == ACT` pre-kickoff | Yes, non-QB only, flagged |
| **Game-day inactive** | 3 of 16 week-1 games | `official_inactives` news blobs | Yes, when hand-delivered |
| **Practice squad** | YES | `status == DEV` (+ `P01/P03/P06/P07`) | Only as an exclusion |
| **Injured reserve** | YES, two independent sources | `status == RES` (264–277/capture); ESPN `Injured Reserve` (162/capture) | Only as an exclusion; ESPN never read |
| **Reserve lists (PUP/NFI/exempt/suspended)** | PARTIAL | `EXE` (4–5 rows); `R48/R40/R27/R49` undecoded; ESPN `Suspension` (4) | **NO** |
| **Elevations** | WEAK | `ACT`+`P07`/`P01`; and `DEV→ACT` diffs (5 on played clubs, 5 elsewhere, per `NFL_ROSTER_STATUS_GOVERNANCE.md` §3) | **NO** |
| **Transactions** | **NO** as a feed; **YES** as a derivable diff between roster vintages | `official_transactions` has no URL; the diff ledger exists in the governance doc | **NO** |
| **Signed / released** | YES | `status == CUT` (414–421/capture) | Only as an exclusion |
| **Emergency QB rules** | NAME ONLY | `inactives_segmentation.py` preserves "(emergency third QB)" as an annotation and refuses to read it as a position | **NO** — no third-QB rule is modelled |
| **Depth chart status** | YES, with a real timestamp | `depth_charts.pos_rank` | Yes (R6/R7) — **but it contains 232 IR players** |

---

## 4. FINDING TABLE

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| F1 | The roster vintage production reads carries only `season, week, team, gsis_id, position` | **CONFIRMED** | `zcat` on all 7 `weekly_rosters.*.reduced.csv.gz`: identical 5-col header, 2,947–2,964 rows. Upstream header has 36 cols incl. `status` |
| F2 | `weekly_rosters.status` is quarantined POSTHOC in `nfl/ingest/allowlist.py` | **CONFIRMED** | `allowlist.py:129`, with the R5 exemption stated in the comment at lines 121–128 |
| F3 | `delivered_injuries.py` has `ROSTER_FORBIDDEN_COLUMNS` | **CONFIRMED** | line 113: `('status', 'game_type_status', 'status_description_abbr')`. Note `game_type_status` **is not a column in any captured header** — it is a defensive name for a field that does not exist |
| F4 | `roster_status.py` implements R5 | **CONFIRMED** | 263 lines; two independent guards — clock (`ROSTER_STATUS_OBSERVED_AFTER_KICKOFF`) then content (`ROSTER_STATUS_POSTHOC_CONTAMINATION`) |
| F5 | `run_forecast.py`'s R5 block exempts the QB pool | **CONFIRMED** | `run_forecast.py:630–653`: `nonqb = [q for q in players if q.get('position') != 'QB']`; `players = qbs + pool.value`. Comment states the exemption and its reason |
| F6 | `ingest_inactives.py` handles official inactives | **CONFIRMED** | 454 lines, 7 ordered guards; `INACTIVES_INGESTION.json` for SF@LA shows all 7 passing at T-50m |
| F7 | R5 is on by default in production | **FALSIFIED** | `active_roster_only` is absent from `V1_CANDIDATE` and present in `R5/R6/R7/R8_FLAGS` only. `R5_REPAIR['governance'] == 'REHEARSAL_ONLY'` |
| F8 | The inactives capture pipeline is working | **FALSIFIED** | 92 of 95 blobs are the empty placeholder. All 3 real blobs came from a **news article URL not in the registry** |
| F9 | The prediction-time eligibility debt is enforced | **FALSIFIED** | `require_prediction_time_eligibility` is imported by **`nfl/tests/test_identifier_mapping.py` and nothing else**. No production module calls it. The debt is declared and unenforced |
| F10 | `ingest_inactives.consumed_slice` hashes `weekly_rosters.status` | **FALSIFIED — and this is a live Phase-1-class defect** | `CONSUMED['weekly_rosters']` lists `status`, but `consumed_slice` globs `nfl/vintage/{src}.{sha16}.*`, which resolves to the **reduced** file. I re-ran it: slice hash `fe00c25f08623c12`, 181 rows — **exactly the value recorded in `INACTIVES_INGESTION.json`** — and every one of the 181 keep-strings ends in the literal `\|None`. The guard that exists to prove the consumed roster slice did not move between the pre- and post-inactives seals is **blind to the status column it names**. A cut, an IR placement or an elevation between the two seals would not move that hash |
| F11 | `roster_status.EXCLUDED` covers the observed status vocabulary | **FALSIFIED** | Observed codes: ACT, CUT, DEV, EXE, **RET**, RES, INA. `RET` is in neither `EXCLUDED` nor `POSTHOC`, so `active_pool` **keeps** all 23 retired players. 9 are skill positions. The behaviour is deliberate and named (`kept_unrecognised_status`) — it is conservative, not silent — but the pool it is meant to restore to ~14.5 is inflated by them |
| F12 | Two agreeing sources establish that INA is the official list arriving late | **CONFIRMED** | `cef497…` gives SF INA=6, LA INA=5. `INACTIVES_INGESTION.json` gives SF 6, LA 5 from the official bytes at T-50m. Exact agreement — the vendor's post-hoc `INA` **is** the inactive list, ~13h late. It confirms the governance ruling and prices the latency |
| F13 | The depth chart can stand in for eligibility | **FALSIFIED** | 1,963 charted players in the 2026-09-13 vintage: 232 `RES`, 25 `INA`, 4 `EXE`, 3 `CUT`, 1 `DEV`, 9 not on the roster file. IR players hold ranks |
| F14 | `official_injury_report` reaches production | **FALSIFIED** | Parser exists and is adversarially tested; zero production importers; zero gsis ids on the page |
| F15 | `espn_injuries_json` is consumed anywhere | **FALSIFIED** | 148 captures × 800 rows, the only source of `Injured Reserve` and `Suspension`, read by nothing |
| F16 | The ESPN→gsis identity bridge is blocked | **FALSIFIED (it is 86.4% open)** | ESPN id regexed from `athlete.links[0].href`, joined to `weekly_rosters` raw `espn_id` (2,015 entries): **691/800 resolve**. Identity is not the blocker; **retention** is — `espn_id` is dropped by the reduction, so the bridge only exists for the 4 captures with raw bytes |
| F17 | `official_transactions` is a source | **PARTIAL** | It is a registered spec with `authority_rank=1` and `url_template=None`. 177 BLOCKED rows, zero bytes. It is an *assignment*, not a source |
| F18 | Elevations are observable pregame | **PARTIAL** | `ACT`+`P07` appears in `fb79…` (2026-09-11T12:19Z) and `cef4…` (2026-09-13T15:45Z) but not in the two earlier raw captures. Both carrying captures are **post-kickoff for SF**, so on present evidence the elevation signature is post-hoc. It would become pregame evidence with a Saturday-evening raw capture, which we do not have |
| F19 | Eligibility has a registered information gap | **FALSIFIED** | `INFORMATION_GAP_REGISTRY.json` holds 10 gaps; **none is about eligibility, inactives, transactions or roster status.** The debt lives only in an unconsumed module's docstring |
| F20 | `nonqb/eligibility.py` is about player eligibility | **FALSIFIED — name collision** | It is **layer** eligibility (`LAYER_SUBSYSTEM`, `PATH_C_STATE`, publishable-or-not). Two modules named `eligibility.py` mean two different things. `readiness.py` and `player_record.py` import the layer one |
| F21 | Elevation / IR detail is recoverable from what we hold | **UNRESOLVED** | `status_description_abbr` distinguishes P01/P03/P06/P07 and R01/R04/R05/R27/R40/R48/R49, and **no decoder exists in the repo**. Whether P07 means a standard elevation cannot be settled from these bytes |
| F22 | The vendor's re-partition window is ~12h | **UNRESOLVED at this sample** | The governance doc asserts ~12h from one pair of captures. With 4 raw captures and 2 played games I can confirm the direction (INA appears only for played clubs) but not the duration |

---

## 5. THE SMALLEST DETERMINISTIC STAGE-0 ELIGIBILITY GATE

**Placement.** Before `slate_fits`, before the engine, before the QB split —
i.e. **above** the current R5 block in `run_forecast.py`, not inside the non-QB
branch. R5's own comment already argues this ("a statement about who is
eligible to receive opportunity at all"); it simply does not apply to
quarterbacks. Stage-0 is R5's argument taken to its conclusion.

**One rule governs the whole design:** Stage-0 **emits a state per player and
refuses; it never infers, never promotes, and never fills a gap.** Absence from
an inactive list is not activity. An unknown code is not an exclusion.

### 5.1 What it consumes (all of it already on disk)

| Input | Role | Must be |
|---|---|---|
| `nfl_vintage/raw/weekly_rosters.<sha>.csv` → `status`, `status_description_abbr`, `gsis_id`, `team`, `espn_id` | roster membership | observed **strictly before** the team's kickoff, and carrying **no** post-hoc code for the teams in scope — both checks, per the 2026-09-10 ruling |
| `schedules.<sha>` → `gameday`, `gametime` per `game_id` | the kickoff clock every guard is measured against | the vintage the forecast itself consumed |
| `official_inactives` parsed sets (`inactives.sets()`) | the T-90 override | **both** clubs present, else `POST_INACTIVES_INCOMPLETE` |
| `injuries` → `report_status`, `practice_status` | designation, **not** status | `report_status` filled, else `INJURY_REPORT_INCOMPLETE` |
| *(new consumer, existing bytes)* `espn_injuries_json` → `status`, bridged via `espn_id` | **corroboration only**, `authority_rank=9` | may never change a state; may only raise `ELIGIBILITY_SOURCE_DISAGREEMENT` |

### 5.2 What it emits — six states, one per (player, game)

| State | Established by | May a projection be built on him? |
|---|---|---|
| `ROSTER_ACTIVE` | pre-kickoff `status == ACT` | **Yes** |
| `ROSTER_EXCLUDED` | pre-kickoff `status` ∈ {DEV, RES, CUT, EXE, **RET**} | No — excluded, with the code named |
| `OFFICIAL_INACTIVE` | on the official list for this game | No — appearance zeroed in every draw, **for QBs too** |
| `ELIGIBILITY_UNKNOWN` | on the frame, no roster row, or an unrecognised code | **Yes, and flagged** — kept, never silently dropped (this is R5's existing conservative direction, preserved) |
| `ELIGIBILITY_REFUSED` | the guards below fired | No — the whole game refuses |
| — | `GAME_ACTIVE` is **deliberately not emitted.** No source we hold establishes it. | — |

### 5.3 What it refuses, by name

| Code | Fires when |
|---|---|
| `ELIGIBILITY_VINTAGE_AFTER_KICKOFF` | the chosen roster capture is at or after this game's kickoff |
| `ELIGIBILITY_POSTHOC_CODE_PRESENT` | any `INA` row for a team in scope |
| `ELIGIBILITY_STATUS_COLUMN_ABSENT` | only a reduced roster vintage is available — **the common case today** |
| `ELIGIBILITY_CODE_UNDECODED` | a `status_description_abbr` with no entry in a declared decode table |
| `ELIGIBILITY_INACTIVES_ONE_CLUB` | one club's list only |
| `ELIGIBILITY_INACTIVES_EMPTY_STATE` | the parsed page hits an `_EMPTY_STATE` marker — **closes D02's open `test_required`** |
| `ELIGIBILITY_SOURCE_DISAGREEMENT` | ESPN says `Injured Reserve` where the roster says `ACT`, or vice versa |
| `ELIGIBILITY_CONSUMED_SLICE_BLIND` | the consumed-slice hash was computed over a file missing a column the slice declares — **closes F10** |

### 5.4 What it changes about today's behaviour

1. **QBs stop being exempt.** The exemption's stated reason is that QB shares
   are already correct and changing them would disturb a control. Stage-0 does
   not reweight anyone — it only marks the ineligible — so the reason does not
   extend to it. D04 (inactive QBs holding 0.90 dropback share) and D17
   (Darnold 24.48 forecast attempts, 2 thrown) are both eligibility failures
   reached through the QB path.
2. **`RET` becomes a declared exclusion** rather than an unrecognised keep.
3. **The consumed-slice guard stops being blind** (F10).
4. **ESPN's 148 captures become a corroborator** — never an authority.
5. **One module owns the vocabulary.** `ROSTER_ACTIVE` / `GAME_ACTIVE` /
   `OFFICIAL_INACTIVE` / `INJURY_QUESTIONABLE` / `UNKNOWN` already exist in
   `inactives.py:74–78`; they belong in Stage-0 and everyone else should import
   them. Rename one of the two `eligibility.py` modules (F20).

### 5.5 What Stage-0 explicitly does **not** do

It does not model elevations, does not implement the emergency-third-QB rule,
does not derive transactions from roster diffs, and does not promote anyone to
`GAME_ACTIVE`. Each needs bytes we do not have, listed next.

---

## 6. EVIDENCE CEILING — the bytes we do not have

Stated as an evidence request, per `docs/AGENT_OUTBOX.md` discipline. **None of
this is a code change and none of it is blocked for the project — it is
assigned.**

**E1 — `official_transactions`: a verified endpoint.** The single highest-value
item. It is the only source that makes elevations, IR placements/returns,
signings and releases observable *as events with their own effective time*
rather than inferred from a diff. `registry.py` has the spec, the authority and
the wiring; it lacks `url_template`. 177 BLOCKED rows are waiting on one URL.

**E2 — the real inactives endpoint.** `https://www.nfl.com/inactives/` has
published an empty placeholder 92 times out of 95. Every real list arrived from
`https://www.nfl.com/news/inactive-reports-<day>-week-<n>-<season>-nfl-season`
or a game-specific news article. Needed: the canonical per-game inactives URL
pattern, or confirmation that the news article **is** the canonical form — in
which case the registry should say so instead of pointing at a placeholder.

**E3 — a decode table for `status_description_abbr`.** 16 observed codes,
zero decoders. Specifically: does `P07` denote a standard gameday elevation?
What separates `R01` / `R04` / `R05` / `R27` / `R40` / `R48` / `R49` (PUP vs
NFI vs IR vs designated-to-return)? A published nflverse or league reference is
enough; a guess is not. **Without this, "elevations" and "reserve lists" cannot
be distinguished from "practice squad" and "IR" in bytes we already hold.**

**E4 — a Saturday-evening raw roster capture, weekly.** The elevation deadline
is Saturday ~4pm ET. Our raw captures are Sunday 12:07Z and 15:45Z. A capture
between the elevation deadline and the first kickoff would make `ACT`+`P0x`
a **pregame** fact (F18) instead of a post-hoc one.

**E5 — retention, which is ours to ask for and not a modelling problem.**
`weekly_rosters` and `depth_charts` are `durability='reduce'`; the full bytes
land in `nfl_vintage/raw/` under the key `full_bytes_ephemeral_at`. **3 of 7
roster vintages and 3 of 6 depth vintages have already lost their raw
counterpart**, taking `status`, `status_description_abbr` and `espn_id` with
them. R5 — a production repair — reads a directory the capture layer calls
ephemeral. Either the reduction should retain these columns or the raw files
should be declared durable. This is a capture-layer decision, flagged in
`roster_status.py`'s own docstring and **not made here**.

**E6 — the emergency-third-QB rule.** `inactives_segmentation.py` preserves the
annotation and refuses to read it. Needed: the league rule text stating when a
third QB may enter without counting against the 48. Until then the engine
cannot represent it, and D17's in-game QB substitution stays unmodelled.

**E7 — a registered gap.** There is no `GAP-ELIGIBILITY` in
`INFORMATION_GAP_REGISTRY.json` (F19). That is a bookkeeping absence, not a
data one, and it is why the debt has been invisible.

### What the ceiling costs, priced from the tree

`INACTIVES_DISCOVERY_QUARANTINED.json` for DAL@NYG, correctly refused as an
aggregator screenshot: Najee Harris listed inactive while the sealed board
carried him at **4.79 carries, 15.2% of the NYG pool**; Israel Abanikanda
listed inactive while projected **4.79 carries, above the charted RB2**. That
is one game. The T-90 reconciliation shows inactives **COVERED 1, MISSED 1** of
the two then-due obligations.

---

## 7. WHAT I DID NOT ESTABLISH

- Whether `P07` is an elevation (E3). Stated as UNRESOLVED, not asserted.
- The vendor's INA-population latency beyond direction (F22); n=2 played games.
- Whether Stage-0 would **improve** any forecast. It is a correctness and
  auditability change. Nothing here is evidence that it moves a score, and the
  251-game-style trap applies: R5/R6/R7/R8 were all selected on the same two
  live games in `OPEN_DEFECTS.json`, so a Stage-0 comparison on those games
  would be exploratory, not confirmatory.
- I did not run the suite, did not run a forecast, and did not touch
  governance.

**CODE CHANGED: NO.**

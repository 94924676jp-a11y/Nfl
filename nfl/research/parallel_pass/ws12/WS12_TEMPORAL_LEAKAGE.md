# WS12 — Future-leakage audit of the pregame forecast path

**CODE CHANGED: NO.** Nothing outside
`nfl/research/parallel_pass/ws12/` was written, and no repository file was
modified. Every number below was read out of the tree at HEAD `57d38ad` on
`python3.12`, not recalled. The reproductions are in
`nfl/research/parallel_pass/ws12/repro_ws12.py`, which imports repository
modules and writes nothing.

**The full suite was not run.** No chronology guard was weakened. No blocker is
discharged by inference: everything here was measured locally, and nothing in
this workstream needed bytes from outside the checkout.

---

## 0. The question, stated precisely

"No post-cutoff information enters a pregame forecast" is two claims, and this
repository already distinguishes them in one place and conflates them in
others.

* **Clock claim.** The bytes a forecast consumed were *retrieved* before the
  forecast's own declared cutoff. `readiness.as_of_cut`
  (`nfl/production/nonqb/readiness.py:217`) writes the contract down exactly:
  `retrieved_at <= written_at < kickoff`.
* **Content claim.** Those bytes do not *describe* anything that happened after
  that cutoff. `roster_status.py` is the one module in the tree that states
  this separately and guards it separately, and it is right to: the vendor
  re-partitions a team's roster after that team plays, so a capture can be
  pre-kickoff by the clock and post-game in content.

A family is **PROVEN_CLEAN** here only when both claims are enforced *at
selection* and a missing preferred vintage produces a named refusal rather than
a substitution. Passing the clock claim alone is not adequacy.

---

## 1. Per-family verdict

| Family | Source of record | Vintage chosen at forecast time | Fallback when the preferred vintage is absent | Verdict |
|---|---|---|---|---|
| **Injury reports** | `injuries` (nflverse mirror), `official_injury_report` (nfl.com HTML), delivered packages via `capture/delivered_injuries.py` | **Two selectors disagree.** The *gate* (`readiness.team_readiness`) cuts at `min(written_at, kickoff)`. The *feed the model eats* (`layers.py:145 → readiness.latest_injuries_rows`) applies **no bound at all** | gate: `INJURY_REPORT_NOT_YET_FILED` / `_INCOMPLETE`; feed: silently takes the newest capture on disk | **PROVEN_LEAKING** — L1, L2 |
| **Depth charts** | `depth_charts` (ESPN daily via nflverse), row-level `dt` | Two selectors again. `depth_vintage.captured()` (`:220`) is strict point-in-time on the vendor `dt`. `board.depth_rank` (`nfl/product/board.py:55`) takes **no clock** and resolves by glob order | `depth_vintage`: `DEPTH_CAPTURE_NOT_POINT_IN_TIME` (deferred). `depth_rank`: no refusal exists; the R6 call site wraps it in `except Exception: dr = {}` | **PROVEN_LEAKING** on the R6 path — L3. PROVEN_CLEAN on the R7/R8 path |
| **Rosters** | `weekly_rosters`; raw retained under `nfl_vintage/raw/` (7 files) | `information_set.build` by observation time; `roster_status.status_map` additionally requires `observed_at < written_at` **and** `observed_at < kickoff` **and** no `INA` row for the teams in scope | `ROSTER_STATUS_NO_ELIGIBLE_VINTAGE` (blocked); `ROSTER_STATUS_OBSERVED_AFTER_KICKOFF` / `_POSTHOC_CONTAMINATION` (fail) | **PROVEN_CLEAN** — the only family with a content check as well as a clock check |
| **Transactions** | `official_transactions` | **Never captured.** 177 of 177 manifest rows are `BLOCKED`; `url_template=None`, `PENDING_ENDPOINT_VERIFICATION` | `ingest/eligibility.require_prediction_time_eligibility` returns `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE`, and refuses `weekly_rosters.status` by name as a substitute | **PROVEN_CLEAN by non-consumption** (an open debt, not a leak) |
| **Weather** | none | **Not ingested.** `schedules.temp` and `schedules.wind` are quarantined `POSTHOC` (`ingest/allowlist.py:_SCH_POSTHOC`) on the stated ground that they are *observed* game-time conditions | n/a | **PROVEN_CLEAN by non-consumption** — grep over `nfl/production`, `nfl/capture`, `nfl/ingest`, `nfl/product`, `nfl/prospective` returns no reader of `temp`/`wind` |
| **Historical stats refreshed after games** | `nfl/research/inputs/panel_p3.csv.gz`, `denom_panel.csv.gz`, `dc_20xx`, `inj_20xx` | Not selected by clock at all — one committed snapshot, cut by **ordinal** (`season*100+week`) | `PARTICIPATION_HISTORY_EMPTY` / `_STALE`; declared positional-mean fallback | **UNPROVABLE_WITH_CURRENT_METADATA** — see §3.1 |
| **Snap counts** | `snap_counts` | Never captured: 98 of 98 rows `NOT_APPLICABLE[WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE]`; `watch_only=True`, `serves_kinds=()` | n/a | **PROVEN_CLEAN by non-consumption** |
| **Official inactives** | `official_inactives` (112 PASS) | `inactives.sets()` refuses `retrieved_at >= kickoff` (`INACTIVES_POST_KICKOFF`); `make_board._inactive_provenance` additionally refuses an ingestion record that does not describe *this* inactive set | `official_inactive_ids=None` → the board stays a pre-inactives board; `POST_INACTIVES_INCOMPLETE` if only one club resolves | **PROVEN_CLEAN** on the clock; see §3.3 for the publication-time caveat |
| **Schedule metadata** | `schedules` (186 PASS, full 46-column file committed) | `coverage.load_week_plan:251` sorts by **filesystem `st_mtime`** and takes the last; `team_volume_v1.coaches:92` sorts **lexicographically by content hash** and takes the last. Neither takes a clock | `NO_SCHEDULE_SNAPSHOT` / `NO_GAMES_IN_SNAPSHOT` / `NO_COACH_FOR_SLATE` | **UNPROVABLE_WITH_CURRENT_METADATA** — see §2.4 |
| **Play-by-play** | none registered | `pbp` has a quarantine entry but **no source in `capture/registry.py`**; `pbp_participation` is 98/98 `NOT_APPLICABLE` (watch-only, 404 for 2026) | n/a for 2026 | **PROVEN_CLEAN by non-consumption for 2026**; **UNPROVABLE** for the 2020–2025 panel it was distilled into (§3.1) |

---

## 2. Confirmed leaks

### L1 — The appearance layer selects its injury feed with no clock at all

**PROVEN_LEAKING.**

```
nfl/production/nonqb/layers.py:84    def appearance(..., observed_before=None, ...)
nfl/production/nonqb/layers.py:145       rows = RD.latest_injuries_rows(season)
nfl/production/nonqb/readiness.py:62 def latest_injuries_rows(season)  ->  _latest_injuries(season)
nfl/production/nonqb/readiness.py:36 def _latest_injuries(season)       # picks max(retrieved_at) over the WHOLE manifest
```

`_latest_injuries` iterates every `source == 'injuries'`, `state == 'PASS'` row
in `nfl/vintage_manifest.jsonl` and keeps the one with the largest
`retrieved_at`. There is no `as_of` parameter, no `written_at`, no kickoff.

This is not the selector the same module wrote for this job.
`readiness._all_injury_captures(season, as_of=...)` (`:242`) exists precisely
because applying the cut *after* selection was a defect — its own docstring
says so — and `layers.py:145` bypasses it.

The path is the production path, not a rehearsal one:

```
run_forecast.build → FE.run_game(..., injuries_rows=None, observed_before=args.written_at)
  football_engine.py:307   fixture = None            # because injuries_rows is None
  football_engine.py:311   LY.appearance(..., observed_before=observed_before)
  layers.py:145            rows = RD.latest_injuries_rows(season)   # observed_before IGNORED
  layers.py:153/163        _run_real(..., observed_before=observed_before)  # used only for the DEPTH chart
```

`observed_before` is in scope at line 145 and is not used there.

**Reproduction** (`repro_ws12.py`, section L1), measured at HEAD:

```
latest_injuries_rows(2026) retrieved_at = 2026-09-13T23:12:09.422344+00:00
rows returned                           = 182
teams whose kickoff it is AT OR AFTER   = 28 of 32  (16 week-1 games)
```

Content, not merely clock. For `2026_01_NE_SEA` (kickoff 2026-09-10T00:20Z) the
lawful pre-kickoff vintage is the capture retrieved 2026-09-08T17:06:04Z. Five
player rows carry a *different designation* in the vintage the layer actually
consumes:

```
NE   00-0037413  pre=('', 'Did Not Participate In Practice')  consumed=('Out', ...)
NE   00-0040734  pre=('', 'Did Not Participate In Practice')  consumed=('Out', ...)
SEA  00-0038765  pre=('', 'Did Not Participate In Practice')  consumed=('Out', ...)
SEA  00-0040648  pre=('', 'Limited Participation in Practice') consumed=('Questionable', ...)
SEA  00-0040733  pre=('', 'Limited Participation in Practice') consumed=('Questionable', ...)
```

`readiness.NEEDS_REPORT_STATUS` (`:34`) records that `teammate_availability`
reads `report_status`, and `inputs.APPEARANCE_CONTRACT` lists it under both
`practice_progression` and `teammate_availability`. So these are model inputs,
not decoration.

**Why it is masked today, and why that is not a defence.** NE and SEA are two of
the six games the readiness gate currently refuses, on exactly the empty
`report_status` the pre-kickoff vintage shows. So the gate, which *is* bounded,
stops the run before the unbounded feed is read. The gate and the feed are
therefore answering the same question from two different information sets, and
the run either halts or consumes bytes the gate never saw. Neither is the
contract `as_of_cut` states.

### L2 — The readiness gate inside the appearance layer is bounded by kickoff, never by `written_at`

**PROVEN_LEAKING.**

```
nfl/production/nonqb/layers.py:117
    tr = [RD.team_readiness(season, week, t, kickoff_utc=kickoff_utc)
          for t in teams]
```

`team_readiness` accepts `written_at` (`readiness.py:361`) and `make_board.py:184`
passes it. This call site does not, although `observed_before` — which *is*
`args.written_at` — is a parameter of the enclosing function. `as_of_cut` then
resolves to `kickoff - 1µs` instead of `written_at`, so every capture retrieved
between the forecast's declared cutoff and kickoff is admitted.

**Reproduction** (`repro_ws12.py`, section L2). Ten of sixteen week-1 games pass
the gate today. Taking a plausible `written_at` of kickoff minus 24 hours for
each, and comparing the vintage lawful at that cutoff against the vintage the
kickoff-bounded gate admits:

```
ARI  differ= 5   ATL differ=11   BAL differ= 4   CAR differ= 2   CHI differ= 6
CIN  differ= 5   CLE differ= 2   DAL differ= 2   DET differ= 3   IND differ= 4
JAX  differ= 2   LA  differ= 7   LAC differ= 4   NO  differ= 5   NYG differ= 2
NYJ  differ= 4   PIT differ= 1   SF  differ=11   TB  differ= 4   TEN differ= 1
TOTAL player rows differing: 85
```

Representative transitions, all of them the Friday game-status filing landing
after a Thursday cutoff:

```
ATL 00-0039917  ('', 'Full Participation in Practice')    -> ('Out', 'Full Participation in Practice')
CHI 00-0033579  ('', 'Limited Participation in Practice') -> ('Questionable', 'Limited Participation in Practice')
TB  00-0038951  ('', 'Limited Participation in Practice') -> ('Doubtful', 'Limited Participation in Practice')
CIN 00-0040756  ('', 'Limited Participation in Practice') -> ('Doubtful', 'Did Not Participate In Practice')
```

85 player-rows is the measured size of the written_at gap on this one week. It
is not a rounding error and it moves in the most informative direction there
is: unfiled → a filed game-status designation.

L1 and L2 are one repair — thread `observed_before` into both — but they are
listed separately because they fail differently. L2 uses the wrong bound; L1
uses no bound.

### L3 — `board.depth_rank` selects a depth vintage by glob order

**PROVEN_LEAKING** on the R6 configuration. **Already recorded**, and still
live: `NFL_R7_APPEARANCE_FRAME_AUDIT.md` §1 item 4 states that
`board.depth_rank` "accepts `season` and `week` and uses neither… with no check
that the capture predates the forecast clock", and the repair it names
(`depth_vintage.py`) was wired into R7 and R8 only.

```
nfl/product/board.py:55           def depth_rank(season, week, teams, blob=None)
nfl/production/run_forecast.py:681    _PBRD.depth_rank(args.season, args.week, teams)
nfl/production/run_forecast.py:688    RP.assign_tiers(..., depth_rank=dr)   -> tiers -> FE.slate_fits
```

With `blob=None` the function globs every reduced blob, iterates in filename
order, and does **not** break — so the answer comes from the *last* blob in
content-hash order that carries rows for those teams, and within it the newest
`dt`.

**Reproduction** (`repro_ws12.py`, section L3):

```
depth_charts.361f1c69443cba69  rows=140  max dt=2026-09-09T12:06:21Z
depth_charts.76d7bcb384ec11e3  rows=140  max dt=2026-09-06T11:29:30Z
depth_charts.a14e8dfe865a4b03  rows=139  max dt=2026-09-13T12:42:08Z
depth_charts.db0a09454965e6fc  rows=139  max dt=2026-09-10T12:01:46Z
depth_charts.ecc4973e8715d866  rows=140  max dt=2026-09-07T13:13:25Z
depth_charts.f57ef0724d907160  rows=140  max dt=2026-09-08T11:56:57Z   <- chosen
```

The chosen chart is neither the newest nor the point-in-time one. A forecast
written 2026-09-07T12:00Z gets a chart stamped ~24h after its own cutoff; a
forecast written 2026-09-13T20:00Z gets one five days stale. Which error you get
depends on a content hash. The R6 configuration's own declaration in
`candidate_mode.R6_REPAIR` says "class weight = own history shrunk toward
**point-in-time** depth tier"; on this call site it is not point-in-time.

`run_forecast.py:679-684` wraps the call in `except Exception: dr = {}`, so a
total failure to load any chart is indistinguishable from every player lacking
a rank — the failure-open pattern the same audit already named.

### L4 — Two schedule selectors, neither with a clock

**UNPROVABLE_WITH_CURRENT_METADATA**, and a latent leak.

* `nfl/capture/coverage.py:251` sorts schedule snapshots by **`st_mtime`** and
  takes the last. `st_mtime` is a local filesystem property that git does not
  preserve, so this selection is not reproducible across checkouts — the
  vintage a replay resolves depends on checkout order.
* `nfl/production/team_volume_v1.py:92` sorts **lexicographically by content
  hash** and takes the last, then reads `home_coach`/`away_coach`.
  `coach_prior` is the selected point estimator for three of the five volume
  metrics, so this is a load-bearing prediction-time input, and it is chosen by
  a string sort over hashes.

Measured: the snapshot `coverage.load_week_plan` resolves today carries **final
scores for 10 of the 16** 2026 week-1 games, and `total_line` is populated for
**16 of 16** in every snapshot inspected. Only `season`, `game_type`, `week`,
`gameday`, `gametime` and the team codes are read out of it by `season_plan`,
and kickoff times are identical across the snapshots I compared — so no
post-game or market value reaches a number **today**. But the guard is absence
of a reader, not a bound on the selector, and the file containing scores and
sportsbook lines is what the selector hands over.

---

## 3. Evidence ceilings — exactly which bytes and which metadata are missing

### 3.1 The historical panels carry no clock at all

`nfl/research/inputs/INPUT_MANIFEST.json` records, per leaf:
`sha256_decompressed`, `sha256_gz`, `bytes_decompressed`, `bytes_gz`,
`stored_as`, `origin_dir`, `provenance`. A scan for any key matching
`retriev|date|as_of|cutoff|time|captur|vintage` returns **none**.

`panel_p3.csv.gz` holds 57,670 rows spanning 2020 w1 – 2025 w18;
`denom_panel.csv.gz` holds 3,230 rows over the same span. Both are distillations
of nflverse `pbp` / `pbp_participation` / `snap_counts`, which are **refreshed
after games and revised afterwards**. The manifest fixes their *identity*
(hashes verified at every stage) but not their *as-of*. So:

* For a 2026 week-1 forecast the panel ends at 2025 w18 and the ordinal cut in
  `participation_prior._history` (`o >= ordinal_cut → skip`) is strictly
  earlier-only. Clean by construction, for this week.
* For **any** backtest into 2020–2025, it is unprovable that the row a replay
  reads is the row that existed at that replay's cutoff. One snapshot of a
  revised panel cannot answer a point-in-time question. Nothing in the tree
  claims otherwise, and nothing in the tree could establish it.

**What would close it:** a `retrieved_at` (or upstream `Last-Modified`) per
leaf in `INPUT_MANIFEST.json`, and, for a genuine point-in-time backtest,
multiple vintages of each leaf rather than one.

**Latent, not live:** `appearance_r7.build_frame` and `appearance_r8.predict`
take no ordinal cut. `predict` computes `prev_appeared = past[-1]['appeared']`
over the *whole* frame for that player. Today the frame stops at 2025 w18 so
`past[-1]` cannot be the game being forecast. The moment a 2026 panel lands,
`past[-1]` becomes a current-season row with no cut between it and the forecast
week. That is a guard that does not exist rather than one that fails.

### 3.2 The quarantine is declared and never invoked

`nfl/ingest/allowlist.py` declares 9 sources and 63 quarantined columns.
`assert_columns_allowed` and `forecast_safe_columns` are called from
**`nfl/tests/` only** — grep over `nfl/` and `sportsplatform/` finds no
production, capture, feature or research caller.

What actually keeps quarantined columns out of production is *physical*: the
capture reducer (`registry.reduce_cols`) writes `weekly_rosters` as
`season,week,team,gsis_id,position` and `depth_charts` as
`dt,team,gsis_id,pos_abb,pos_rank`, dropping `status` and everything else. That
works — and it is why `roster_status.py` has to read `nfl_vintage/raw/` to see
`status` at all.

It does **not** work for `schedules`, whose durability is `commit_raw`: all 46
columns, including `spread_line`, `total_line`, `result`, `home_score`, `temp`,
`wind`, `away_qb_id`, are on disk in every one of the 132 committed blobs, and
the two readers above open them with a bare `csv.DictReader`. The quarantine is
a declaration that no code consults.

I checked the two committed panels against the quarantine directly: no column
of `panel_p3` or `denom_panel` appears in any quarantine map. `pbp` is
quarantined but is **not a registered source**, so the quarantine names a
source the capture registry cannot produce and the panels were distilled from
it outside the governed path.

### 3.3 Retrieval time wearing publication authority

Measured over all 1,061 `PASS` rows of `nfl/vintage_manifest.jsonl`
(12,123,320 bytes, 1,672 rows), comparing `value.effective_scope.valid_from`
against `retrieved_at`:

| source | header used | scope kind | scope authority | n | lag (retrieved − valid_from), hours |
|---|---|---|---|---|---|
| `depth_charts` | `Last-Modified` | EXACT_TIMESTAMP | SOURCE_PROVIDED | 175 | min 0.09, med 11.45, max 25.62 |
| `weekly_rosters` | `Last-Modified` | DATE_INTERVAL | DERIVED_DETERMINISTIC | 175 | min 0.04, med 11.10, max 25.64 |
| `injuries` | `Last-Modified` | DATE_INTERVAL | DERIVED_DETERMINISTIC | 146 | min 0.01, med 10.23, max 26.65 |
| `schedules` | `Last-Modified` | DATE_INTERVAL | DERIVED_DETERMINISTIC | 175 | min 0.00, med 0.37, max 4.34 |
| **`official_inactives`** | **`Date`** | **EXACT_TIMESTAMP** | **SOURCE_PROVIDED** | **94** | **0.000 in every row** |
| **`official_injury_report`** | **`Date`** | **EXACT_TIMESTAMP** | **SOURCE_PROVIDED** | **94** | **0.000 in every row** |

For the two OFFICIAL sources the "source-provided exact timestamp" is the HTTP
`Date` response header — the instant the origin answered *our* request. It is
retrieval time, recorded under `authority: SOURCE_PROVIDED`, with a lag of
exactly zero in all 188 rows. The nflverse mirrors, by contrast, carry a real
upstream `Last-Modified` sitting a median of 10–11 hours before retrieval.

**For leakage this is conservative** — retrieval is never earlier than
publication, so `retrieved_at < kickoff` still implies `published < kickoff`,
and `inactives.store` keeps `published_at` as a separate field and says in its
own evidence that the two "are different quantities and neither substitutes for
the other". Only 16 manifest rows carry a `published_at`.

**The ceiling is that the league's own publication instant is not recorded for
the sources whose whole value is *when* they were published.** You cannot ask
"was this inactives list posted before or after the 90-minute mark" from this
metadata; you can only ask when we looked. And the scope object asserts
`EXACT_TIMESTAMP / SOURCE_PROVIDED`, which a reader is entitled to take as the
league's clock. No consumer reads `valid_from` today — every selector in the
tree keys on `retrieved_at` or `capture_id` — so the false label costs nothing
yet.

### 3.4 Where an observation time is inferred rather than recorded

`information_set.observations()` (`nfl/research/shadow/information_set.py:56`)
falls back to parsing the `capture_id` as a UTC instant when no explicit
`retrieved_at` exists, and labels it `observed_basis: 'capture_id'`. The
docstring argues correctly that this is an upper bound and can only be
conservative.

Measured: every current `PASS` row carries a real clock — 1,034 at
`value.provenance.retrieved_at`, 27 at `value.retrieved_at`, **zero** falling
through to `capture_id`. So the inference path is presently unused, and the
labelling that would expose it if it were used is in place.

`first_observation()` keys on `(source, sha256)` and keeps the **earliest**
capture of that exact content, so a refetch returning identical bytes never
moves a source forward. That is the right direction and is stated in the
selection rule the information set writes into every board.

### 3.5 String comparison of clocks

`roster_status.py:144` (`if observed_before and at >= observed_before`) and
`make_board.py:146` (`if rec['observed_at'] >= written_at`) compare ISO
timestamps as **strings**. This is correct only while both sides are
`...Z`-suffixed with the same shape. A `written_at` supplied as
`2026-09-10T16:00:00+00:00` sorts `'+'` below `'Z'` and mis-orders same-second
comparisons; a space separator instead of `T` would mis-order worse. The
direction of the same-second error is over-exclusion, which is safe, but the
guard's correctness rests on an input format nothing validates. Not a leak;
a fragile guard.

---

## 4. What I checked and found clean

Recorded so the next pass does not re-open them.

* **`roster_status.status_map`** — the POSTHOC trap the brief points at. Both
  guards are present and ordered correctly: the clock check runs *first*
  (`:183`) because the content check cannot see a capture taken in the gap
  between kickoff and the vendor populating `INA`, and the module says so.
  `active_pool` keeps players with unknown or unrecognised status and names the
  code rather than dropping them. I looked for other members of this class;
  `schedules` is the only other source that re-partitions after a game, and no
  post-game column of it is read.
* **`participation_prior`** — `bisect.bisect_left(ords[pid], cut)` on strictly
  earlier ordinals; the duplicate-row-per-ordinal hazard is named and handled.
  The `PARTICIPATION_HISTORY_STALE` refusal from week 2 prevents last season
  being weighted as though it were last week. The fallback is a declared
  positional mean, counted in the evidence, never a silent zero.
* **EWMA / rolling features** — `appearance_r8.enriched_frame` accumulates
  `hist[(pid, season)]` *before* appending the current row, so no row enters its
  own window. `reliability_k(..., cut=args.season * 100)` is strictly prior
  seasons. `rushing_a1` cuts per-team EWMA at `season * 100 + week`.
  `role_prior.build(panel, share, pos, cut)` takes the same cut. I found no
  rolling window that spans its own cutoff.
* **Official inactives** — `inactives.sets` refuses `retrieved_at >= kickoff`
  outright; `make_board._inactive_provenance` refuses an ingestion record whose
  player set differs from the set being sealed, which is the
  previous-run-contamination case.
* **`delivered_injuries`** — writes into the same `injuries` schema so the same
  selectors apply, records `acquisition: EXTERNAL_AUTHORITATIVE_DELIVERY`
  distinctly, refuses a status outside the governed vocabulary, refuses an
  ambiguous name, and lists `ROSTER_FORBIDDEN_COLUMNS = ('status', ...)` so the
  post-hoc roster field cannot enter through the delivery door.
* **`make_board.build_one`** — three clock guards, all correct:
  `written_at < kickoff` (`:118`), `written_at <= now` (`:138`, which exists
  because a future cutoff silently *widens* the information set), and a
  post-selection assertion that no selected source post-dates `written_at`
  (`:146`). The information set is selected against `min(written_at, kickoff)`
  and absent sources are listed under `absent` rather than dropped.
* **`coverage.performed_from_manifest`** — verifies each blob exists and
  re-hashes it; an undated `PASS` row is a refusal, not a skip; unattributed
  captures are counted and explicitly cannot discharge.

---

## 5. Ranked summary

| # | Finding | Where | Class | Measured size |
|---|---|---|---|---|
| L1 | Injuries feed selected with no clock | `layers.py:145` | PROVEN_LEAKING | consumed capture is post-kickoff for 28 of 32 week-1 teams; 5 designation changes on NE/SEA |
| L2 | Readiness gate bounded by kickoff, not `written_at` | `layers.py:117` | PROVEN_LEAKING | 85 player-rows differ across the 20 teams of the 10 executable games |
| L3 | Depth vintage chosen by glob order | `board.py:55` via `run_forecast.py:681` | PROVEN_LEAKING (R6 path) | chart used is 5 days from the newest; selection is by content hash |
| L4 | Schedule vintage by `st_mtime` / hash order | `coverage.py:251`, `team_volume_v1.py:92` | UNPROVABLE | chosen snapshot carries 10/16 final scores and 16/16 market lines |
| E1 | Historical panels carry no as-of | `INPUT_MANIFEST.json` | UNPROVABLE | 0 clock keys over 14 leaves |
| E2 | Quarantine never invoked outside tests | `ingest/allowlist.py` | UNPROVABLE | 0 production callers; `schedules` committed with all 46 columns |
| E3 | `Date` header recorded as source-provided exact timestamp | `capture/registry.py` | UNPROVABLE | lag 0.000h in 188 of 188 OFFICIAL rows |
| E4 | Clocks compared as strings | `roster_status.py:144`, `make_board.py:146` | fragile guard | n/a |

**CODE CHANGED: NO.**

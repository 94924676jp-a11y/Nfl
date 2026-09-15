# P7 — the data plane: predictive-time availability audit

Agent P7. Written 2026-09-15. Repository `/home/user/nfl`, `python3.12`.
Nothing committed or pushed.

Everything numbered below was measured from this checkout on this date. Where a
figure comes from another agent's artifact rather than from my own measurement
it says so. No source was added or promoted on a vendor's claim about
availability; every availability statement is derived from
`nfl/vintage_manifest.jsonl` or from the captured bytes themselves.

---

## 0. Headline

**One CONFIRMED leak.** `nfl/production/run_forecast.py:501` calls
`qb_allocation.allocate(...)` without `kickoff_utc` and without `written_at`.
`allocate` guards its depth chart with

```python
for label, bound in (('kickoff', kickoff_utc), ('written_at', written_at)):
    if bound and got and str(got) >= str(bound):
        return Outcome.fail('DEPTH_CHART_CHRONOLOGY_FAILURE', ...)
```

With both bounds `None` the guard body is unreachable. The chart it is
guarding is selected by `sorted(glob.glob(...))[-1]` — lexicographic content-hash
order, no clock, no `as_of`. Measured today that resolves to
`nfl/vintage/depth_charts.f66f0c2583dba463.reduced.csv.gz`, vendor publication
instant **2026-09-14T13:53:31Z**, which is **after 15 of the 16 week-1
kickoffs**. The QB room ordering read from it feeds dropback allocation.

This is the same defect as the repaired `board.depth_rank`, on the same source,
one function over. There, the guard fired on every run and a bare
`except Exception` destroyed the evidence. Here, the guard exists and is correct
— section C1b of the test proves it refuses the chart the moment a caller passes
a Sunday kickoff — and **neither of its two callers arms it**, so it has never
fired in production. A guard nobody arms is not weaker than no guard; it is
worse, because it reads as coverage.

Failing test: `nfl/tests/test_p7_data_plane.py::test_c1_CONFIRMED_LEAK_depth_chart_guard_is_disarmed_by_its_caller`.

**No P0.** Hard Rock is not wired as a predictive input. See section 4.

---

## 1. The availability table

Twelve declared sources. Ten in `SOURCE_REGISTRY`; two were stored with manifest
rows and declared nowhere until this work (section 4).

| Source | The pipeline uses it for | Real availability vs kickoff (measured) | Enforced? | Leak risk | Evidence |
|---|---|---|---|---|---|
| `injuries` | `practice_progression`, `teammate_availability` for the appearance mechanism (`inputs.APPEARANCE_CONTRACT`), via `readiness.lawful_injuries_rows` → `layers.py:145`; `eligibility_gate.py:210` | **Revised ACROSS kickoff.** `report_status` was blank in every capture predating the NE@SEA kickoff (2026-09-10T00:20Z) and first populated in the capture retrieved **2026-09-10T05:05:18Z — 4h45m after kickoff**. 5 of 182 week-1 player rows changed status after their own kickoff. The series is non-monotone: 11, 11, 29, 139, 167, **48**, 182 rows. | **YES.** `vintage_selector.resolve_as_of` raises rather than defaulting; `readiness._resolve_feed_cut` refuses without explicit / declared-context / gate-handoff cut; the feed composes each team's newest lawful *block*, not the newest file. | **NONE** on the guarded feed. **POSSIBLE** on `readiness.injuries_readiness(..., as_of=None)`, which is unbounded by default and is labelled an operator view. | 7 distinct content vintages on disk; measurement reproduced in §2.1 |
| `schedules` | `coverage.load_week_plan` kickoff times; `team_volume_v1.coaches` → `coach_prior`, the selected estimator for 3 of 5 volume metrics; `q9shadow/seal` | Kickoff times are scheduled months ahead. **The same file accumulates outcomes and market lines**: on `schedules.bfb4ca5952e3a974.csv.gz` (retrieved 2026-09-14T17:39Z) week-1 `result` is present for 15 of 16 games, `total_line` for weeks 1–2, `temp` for 9 week-1 games. | **PARTIAL.** `q9shadow/seal` has a column allowlist. `coverage.load_week_plan` now orders on manifest transaction time and accepts `as_of` (repaired here, §3). `team_volume_v1.coaches` has **no clock at all**. | **POSSIBLE** | §2.2 |
| `depth_charts` | `role_prior.assign_tiers` tier fallback via `board.depth_rank`; **`qb_allocation.captured_depth_chart` → QB room ordering → dropback allocation** | Source-provided effective instant. **Correction to the declared ceiling:** `vintage_selector.FAMILIES['depth_charts']['ceiling']` says the `dt` is a daily stamp; the 2026 captures carry full instants (`2026-09-14T13:53:31Z`). The ceiling understates the source. | **`board.depth_rank` YES** (clocked by the earlier repair). **`qb_allocation` NO.** | **CONFIRMED** | §0, §2.3 |
| `weekly_rosters` | `roster_status.status_map` (raw), `board.roster_identity` (reduced), display names | **`status` is post-hoc**: the vendor re-partitions ACT/INA after a team plays (INA → 0 snaps of 3,438; that figure is from the existing artifacts, not re-measured here). | **YES, and it is the reference design.** A clock check *and* a content check; `q9shadow/inputs.RESTRICTED_SOURCES`; the reduced blobs drop `status` entirely so it cannot be read from them. | **NONE** | existing `roster_status` + `NFLVERSE_INJURY_SOURCE_STATUS_RESOLUTION_01.json` |
| `official_injury_report` | the `practice` and `final_status` capture kinds | Filing deadline 16:00 New York. **Its recorded `published_at` IS our own retrieval instant** — HTTP `Date`, lag 0.000h in 188 of 188 rows (E3, WS12). | Annotated at selection by `_RETRIEVAL_TIME_AUTHORITIES`. **No parser exists**, so nothing reads its fields. | **NONE** | 94 PASS / 54 FAIL / 34 BLOCKED rows |
| `official_inactives` | the `inactives` kind; `layers.py:245`; `eligibility_gate` inactive ids | ~T−90. `schedule.WINDOWS['inactives']` opens at T−90 and closes 80 minutes later, i.e. at T−10. | **YES.** `_clears` requires a declared game identity and an authorised discharging basis; an in-window capture from an undeclared run discharges nothing. | **NONE** | 112 PASS / 54 FAIL / 31 BLOCKED |
| `espn_injuries_json` | **nothing** | Semantics never audited. | `serves_kinds=()`. | **NONE** | 148 PASS captures stored; grep over `nfl/production`, `nfl/product`, `nfl/prospective` returns **zero** consumers |
| `official_transactions` | nothing — no verified endpoint | n/a | `PENDING_ENDPOINT_VERIFICATION`; `resolve()` refuses to invent a URL | **NONE** | 179 BLOCKED rows, 0 captures. This is the open `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` debt |
| `pbp_participation` | the P component's `share_history`, declared `history_only: True` | **Post-kickoff by construction** — per-play participation exists only after the plays. 404 for 2026. | **YES, doubly.** `watch_only=True` *and* `serves_kinds=()`; `can_discharge` refuses; `availability.assert_no_discharge`. | **NONE today.** See the standing hazard in §5. | 100 `NOT_APPLICABLE` rows, 0 captures |
| `snap_counts` | same, and it carries no pass/run split so it cannot substitute | same | same | **NONE today** | 100 `NOT_APPLICABLE` rows |
| `hardrock_market_snapshot` *(delivered)* | **nothing in the forecast path** | delivered 2026-09-13T18:13:12Z | Declared `forecast_eligible=False` here; what actually holds is that no forecast-path module imports anything that reads it | **NONE — not a P0** | §4 |
| `official_status_evidence` *(delivered)* | nothing | delivered 2026-09-13T18:12:01Z | its own delivery record: `readiness_contract_verdict: DOES_NOT_SATISFY` | **NONE** | 19 rows, all `game_status` BLANK (9) or UNSPECIFIED (10) |

### The third question, answered separately: does the selector enforce, or merely record?

It enforces, for the four families it declares — and **it declares only four**.
`vintage_selector.FAMILIES` covers `injuries`, `depth_charts`, `weekly_rosters`
and `schedules`. The other eight declared sources have **no clocked selector at
all**; a consumer of one of them reaches the bytes by globbing. That is not a
present leak, because seven of the eight are consumed by nothing. It is the
reason both confirmed and possible findings below are glob-shaped.

---

## 2. The measurements

### 2.1 The injuries feed is revised across a kickoff

Seven distinct content vintages of `injuries_2026.csv` are on disk. Tracking
every `(team, gsis_id)` week-1 row across them, against each team's own kickoff
taken from `schedules.bfb4ca5952e3a974.csv.gz`:

```
week-1 player rows tracked                                        182
rows whose FIRST observation postdates their own kickoff            0
rows whose report/practice status CHANGED after their own kickoff   5
    NE 00-0037413, NE 00-0040734,
    SEA 00-0038765, SEA 00-0040648, SEA 00-0040733
```

All five are NE@SEA, the Wednesday-night opener (kickoff 2026-09-10T00:20Z). The
change is the same in all five: `report_status` went from `''` to `Out` or
`Questionable`, in the capture retrieved **2026-09-10T05:05:18Z**.

Two things follow and they point in opposite directions.

**The enforcement is load-bearing.** A reader that took the newest file on disk
would put a game-status designation into a NE@SEA forecast that the forecast did
not have. That is the defect `vintage_selector` was built for, and it is still
live in the data.

**And the blank is not a licence.** For NE@SEA there is *no* lawful capture
carrying a designation at all — the pre-kickoff vintages are blank, and blank is
"not filed yet in this mirror", not "no designation". `delivered_injuries.py`
already names the three states the nflverse schema can spell only two of. A
consumer that reads blank as "playing" gets the answer right by accident when the
player plays and wrong when he does not.

### 2.2 The schedules family: 48 of 134 blobs are orphans

```
schedules.*.csv.gz on disk                     134
of which appear in NO manifest row              48
distinct content hashes among PASS rows          87
```

An orphan blob has no `retrieved_at`, no provenance and no content attribution.
It cannot be placed against any cut. `team_volume_v1.coaches(2026, 1)` returns
`snapshot = schedules.fcaa2bb1adac5d67.csv.gz` — **one of the 48**. Its own
docstring calls `coaches` "a load-bearing prediction-time input, not a
convenience".

I read the file it lands on. For 2026 it carries `result` for **zero** games and
`home_coach` for every game in every week, so no post-kickoff *content* is
demonstrated to reach a forecast through this path today. The mechanism is what
is wrong: lexicographic sha order is not a clock, is not even "newest", and can
move backwards the next time a capture lands with a lower hash.

### 2.3 The depth chart the QB allocator actually reads

```
QA.captured_depth_chart() -> PASS DEPTH_CHART_OK
  blob          depth_charts.f66f0c2583dba463.reduced.csv.gz
  evidence['retrieved_at']   '2026-09-14T13:53:31Z'
  n_teams 32, n_qb_rows 92
```

Two separate problems in that one line of evidence.

**The key is misnamed.** `retrieved_at` there is `max(dt)` over the QB rows —
the *vendor's* publication instant — not the instant we retrieved the file. The
manifest knows the real retrieval instant and this function does not consult it.
A future reader who trusts the key name will compare the wrong clock.

**The comparison is a string comparison.** `str(got) >= str(bound)` is E4 from
WS12, the defect `vintage_selector.parse_ts` exists to retire: `Z` and `+00:00`
sort differently, so the answer depends on which spelling the caller happens to
use. Today it errs conservative, which is luck, not design.

And neither matters while no caller arms the guard.

### 2.4 Freshness at week-1 kickoffs

`nfl/capture/freshness.py`, run over all 16 week-1 kickoffs from the captured
plan:

```
NO_DECLARED_FRESHNESS_OBLIGATION  80     STALE  18
FRESH                             14     NEVER_CAPTURED  16
WATCH_ONLY_NOT_A_GAME_INPUT       32
```

Per source, age of the newest lawful capture at kickoff:

```
official_injury_report   STALE 15 / FRESH  1   max age 5,731 min (95.5 h)
official_inactives       FRESH 13 / STALE  3   max age 1,741 min (29.0 h)
official_transactions    NEVER_CAPTURED 16
pbp_participation        WATCH_ONLY 16
snap_counts              WATCH_ONLY 16
injuries / schedules / depth_charts / weekly_rosters / espn_injuries_json
                         ungraded, ages 11.7 min to 1,873.9 min
```

The three `official_inactives` STALE rows are the halted executor, and DEN@KC is
one of them at 1,741 minutes against an 80-minute budget. That is Part C
reappearing through an independent mechanism, which is the point of having two.

---

## 3. What I hardened, and what I only specified

### Hardened — implemented, tested, running

**`nfl/capture/bitemporal.py` (new).** Every stored fact on both time axes:
valid time (when it was true) and transaction time (when we learned it), with
the authority of each clock carried on the record. `readable_at(fact, cut)`
enforces the one rule — `learned_at < cut`, strictly, on parsed instants, never
on strings — and `assert_forecast_reads_only_learned_before_cut(facts, cut)` is
the gate the brief asked for. It refuses an empty fact set rather than passing
vacuously. `from_manifest_row` / `facts_from_manifest` adapt the existing vintage
manifest, and carry E3's warning — that `official_inactives` and
`official_injury_report` publication clocks *are* our retrieval time — onto the
record where a consumer sees it, instead of leaving it in a comment.

It also refuses a clock it cannot resolve precisely enough:
`LEARNED_TIME_GRANULARITY_TOO_COARSE`. A calendar-day learned time is lawful only
when the whole day closes at or before the cut. Reading a bare date as midnight
is what would let a chart published on a Sunday evening certify a Sunday
afternoon kickoff.

**`nfl/capture/freshness.py` (new).** Staleness per source against kickoff, with
a closed verdict vocabulary. The part that mattered most to get right:
**there is no invented threshold.** A budget is derived from
`schedule.WINDOWS` — the place this project already wrote down how long each
artifact stays the current vintage — and a source that serves no kind is
reported with its measured age and **explicitly not graded**
(`NO_DECLARED_FRESHNESS_OBLIGATION`). A test asserts the module contains no
duration literal of its own.

**`nfl/capture/coverage.py` (repaired).** `load_week_plan` ordered schedule
snapshots by `p.stat().st_mtime` — the first entry on `vintage_selector`'s own
forbidden list. It now orders on manifest transaction time through
`bitemporal`, counts the 48 orphan blobs instead of silently ranking them,
orders any orphan *first* so it can never win, reports the ordering basis on the
Outcome, and takes an optional `as_of`. The mtime path survives as one named
fallback for a caller passing a synthetic `vintage_dir`, and the basis field
says when it is in use. **Verdicts are unchanged**: week-1 coverage is still
covered 15 / missed 48.

**`nfl/capture/registry.py` (extended).** A `DELIVERED` table for the two sources
that had stored blobs, manifest rows and no declaration anywhere —
`hardrock_market_snapshot` and `official_status_evidence`. They are declared
*outside* `REGISTRY` on purpose: `capture_vintage._sources()` iterates
`REGISTRY` and would start planning fetches for artifacts that have no endpoint
and no cadence, manufacturing a capture obligation that can never be discharged
and was never owed. `declared_sources()` is the union; `forecast_eligible(name)`
answers for a delivered source from its declaration and **refuses to answer for a
fetched one**, because for a fetched source eligibility is a property of the cut
and not of the source.

**`nfl/tests/test_p7_data_plane.py` (new).** 59 checks. Auto-discovered by
`run_suite.py`, which needs no edit.

### Specified, not built — and I am labelling it rather than half-shipping it

The brief's Part B list runs `SOURCE_REGISTRY`, `RAW_CAPTURE_STORE`,
`PLAYER_STATE`, `GAME_STATE`, bitemporal assertions, freshness monitor,
dependency DAG, incremental recomputation. Two of those are built. The rest are a
multi-week programme and are specified in
`nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md`. Nothing in this repository
implements a dependency DAG or incremental recomputation today, and no artifact
of mine implies otherwise.

---

## 4. The P0 scan: Hard Rock, Fantasy Cruncher, external projections

**No P0 finding. Nothing forbidden is wired as a predictive input.**

The trace, because "I grepped and found nothing" is not evidence:

- `nfl/vintage/hardrock_market_snapshot.3d9b22dc39e12e54.csv.gz` exists and has a
  manifest PASS row (`PRESERVED_BY_DELIVERY`, 166 quotes, delivered
  2026-09-13T18:13:12.712Z).
- The only module that reads it is `nfl/product/market_cdf.py`.
- `market_cdf` is imported by exactly two non-test modules:
  `nfl/tools/market_comparison.py` and `nfl/research/market_outcome_audit.py`.
- Neither is in the forecast path. `run_forecast.py` imports neither, directly or
  transitively.
- No forecast-path module *reads* a market or odds column. This is checked by
  AST, looking for a string used as a subscript key or as a `.get()` argument —
  not by substring, because `vintage_selector.FAMILIES['schedules']['ceiling']`
  names `spread_line` and `total_line` precisely in order to record that nothing
  reads them, and a substring scan would push that warning toward deletion.
- `fantasycruncher`, `fantasy_cruncher` and `fantasypros` appear nowhere in the
  repository.

The manifest's own claim — `never_a_model_input: "read only by
nfl/product/market_cdf.py and nfl/tools/market_comparison.py"` — is **correct as
far as it goes and was incomplete**: it omits `market_outcome_audit.py`. That
module is also strictly downstream of every seal, so the conclusion stands and
the wording does not.

---

## 5. Part C: immutable prospective capture

Verified, three ways.

1. **Zero manifest rows carry a `retrieved_at` inside the DEN@KC inactives
   window** (2026-09-14T22:45Z – 2026-09-15T00:05Z). The latest `retrieved_at`
   anywhere in the manifest is **2026-09-14T17:39:41.517748Z**, five hours before
   the window opened. Nothing has been written into it.
2. **The target is still recorded MISSED** with exactly that window:
   `2026_01_DEN_KC / inactives / window 2026-09-14T22:45Z → 2026-09-15T00:05Z /
   kickoff 2026-09-15T00:15:00Z`, cadence `confirmed: true`.
3. **The week tally is unchanged at covered 15 / missed 48.** My `load_week_plan`
   repair moved which schedule snapshot the plan is built from and did not move a
   single verdict.

Refusals are still stored with causes: 179 `ENDPOINT_NOT_YET_VERIFIED`, 61
`NO_EGRESS` / `LOCAL_EXECUTOR_NO_EGRESS`, 40 `SOURCE_NOT_YET_PUBLISHED`, 108
`SOURCE_RAISED`, 200 `WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE`. Nothing is stubbed
and no backfill has occurred.

**A standing hazard to record before it becomes a defect.** When
`pbp_participation` or `snap_counts` publishes for 2026, retrieval-time
enforcement alone *is* sufficient for them — but for a specific reason that
should be written into the family declaration rather than rediscovered: they are
accumulating season files whose rows cannot describe a game that has not been
played, so `retrieved_at <= cut` bounds their content as well as their
acquisition. That reasoning holds only while consumers keep the `history_only`
discipline `inputs.PARTICIPATION_CONTRACT` declares. `vintage_selector.FAMILIES`
has no entry for either source, so today there is nowhere for that reasoning to
live. It should be added *before* either file is consumed, not after.

---

## 6. Findings, ordered by what they cost

| # | Finding | Risk | Owner | Test |
|---|---|---|---|---|
| **L1** | `run_forecast.py:501` and `engine_rehearsal.py:121` call `QA.allocate` with neither `kickoff_utc` nor `written_at`, so the depth-chart chronology guard is unreachable. The globbed chart is dated 2026-09-14T13:53:31Z, after 15 of 16 week-1 kickoffs. | **CONFIRMED** | not P7 | `test_c1_...` — **FAILS** |
| **L1b** | `captured_depth_chart` reports its evidence key as `retrieved_at` while carrying the vendor `dt`, and the guard compares ISO strings (`Z` vs `+00:00`, WS12 E4). | contributing | not P7 | `test_c1b_...` — passes, documents |
| **L2** | `team_volume_v1.coaches` — self-described "load-bearing prediction-time input" — reads `sorted(glob)[-1]`, landing on an orphan blob with no manifest row. 48 of 134 schedule blobs are orphans. | **POSSIBLE** | not P7 | `test_c2_...` — **FAILS** |
| **L3** | `coverage.load_week_plan` ordered by filesystem mtime. | POSSIBLE | P7 | **repaired**, `test_c3_...` passes |
| **L4** | `readiness.team_kickoff` wraps `coverage.load_week_plan` in `except Exception: table = {}`. A failure there silently returns kickoff `None`, degrading the cut from `min(written_at, kickoff)` to `written_at` with no record. Same shape as the `board.depth_rank` swallow. | POSSIBLE | not P7 | not written — `readiness.py` is not mine to touch |
| **L5** | `readiness.injuries_readiness(..., as_of=None)` enumerates unbounded by default. Labelled an operator view, and its docstring says so; the default is still the unsafe one. | POSSIBLE | not P7 | not written |
| **L6** | `vintage_selector.FAMILIES` declares 4 families against 12 declared sources. Eight sources have no clocked selector; seven of those are consumed by nothing, which is the only reason it does not bite. | structural | shared | — |
| **L7** | `vintage_selector.FAMILIES['depth_charts']['ceiling']` says the `dt` is a daily stamp; the 2026 captures carry full instants. The ceiling understates the source. | correction | shared | — |

**L1 and L2 are the two failing checks in my suite and they are not breakage I
introduced.** `test_p7_data_plane.py` reports **56 passed, 3 failed** today (two
failures in C1, one in C2). It will go green when the two call sites are
repaired, and not before.

---

## 7. What I did not do

- I did not edit `run_forecast.py`, `qb_allocation.py`, `team_volume_v1.py` or
  `readiness.py`. They are other agents' files. L1 is a two-keyword change at
  `run_forecast.py:501` and `engine_rehearsal.py:121` — pass `kickoff_utc` and
  `written_at`, which the caller already holds — and it should be made by whoever
  owns those modules, with the failing test above as the acceptance criterion.
- I did not tune, inspect or seek anything about the DEN@KC realised outcome.
- I did not write into `nfl/research/live/` and preserved every seal.
- I did not need anything from outside this checkout, so nothing was written to
  `docs/AGENT_OUTBOX.md`.
- I did not commit or push.

## 8. Files

Written by P7:

```
nfl/capture/bitemporal.py                   new
nfl/capture/freshness.py                    new
nfl/tests/test_p7_data_plane.py             new
nfl/research/v4/p7/P7_DATA_PLANE.md         new  (this file)
nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md new
nfl/capture/coverage.py                     modified — load_week_plan ordering
nfl/capture/registry.py                     modified — DELIVERED table
```

# G0A — Pre-Kickoff Integrity Gate: checklist and current state

**Revision 3**, audited 2026-09-06 22:40 UTC.
Revisions 1 (2/12, mine) and 2 (12/12, mine — **owner-overruled to 10/12**) are
preserved in git history.
**Week 1 kickoff:** 2026-09-09.

**Headline: 11 of 12. Item 1 remains FAIL on an external dependency; item 4 is
closed.**

The owner overruled revision 2 from 12/12 to 10/12 and was right on both counts.
Item 4 especially: I marked it PASS because all five provenance fields existed,
which is schema-correctness standing in for semantic-correctness — the exact
substitution this repository exists to eliminate, made inside the checklist
written to catch it.** Every verdict cites code or a test. No control was weakened to
reach a pass, and the residuals are listed so the owner can overrule any verdict
they think is too generous — item 1 is the one most open to that reading.

**Test evidence: 829 assertions across nine files, 0 failing**, written by agents
that did not write the code under test.

---

## Verdicts

| # | Requirement | State | Evidence |
|---|---|---|---|
| 1 | Kickoff-anchored capture **scheduled and demonstrably running** | **FAIL** ¹ | `nfl/capture/schedule.py` computes per-game cadence; scheduled trigger fires every 6h (`trig_01WvoJ…`, next 2026-09-07T00:38Z); 23 manifest rows over 5 captures. 94 tests. |
| 2 | Raw bytes **before** parse | **PASS** | `curl -o` then `read_bytes()`; headers saved by `-D` before the body is touched. |
| 3 | Append-only / content-addressed | **PASS** | Manifest opened `"a"`; blobs named by digest. **Durability defect from rev 1 resolved**: durable blobs gzipped and committed under `nfl/vintage/` at **532 KB/capture** (was 23 MB). |
| 4 | Complete five-clock provenance | **PASS** ² | A real `Provenance` is constructed and `validate()`d per capture. `SOURCE_TIMESTAMP_ABSENT` refuses to backfill an absent source clock. |
| 5 | sha256 **inside** execution identity | **PASS** ³ | `execution_identity.py`. Proven: a one-character change to any consumed partition's sha256 moves `fingerprint()`, as do the provenance clocks, partition add/drop/rename, spec hash, seed, code version and interpreter — while read order does not. |
| 6 | Leakage quarantine at ingest | **PASS** | `nfl/ingest/allowlist.py`. 47 model-derived pbp columns, 8 schedules market columns, 5 outcome, 11 post-hoc incl. `weekly_rosters.status`, `temp`, `wind`. Purpose axis: ARCHIVE/DESCRIPTIVE pass, FORECAST refuses. |
| 7 | Replay test **fails if the guard is removed** | **PASS** | `nfl/tests/bypass.py`; **10 load-bearing proofs**. The helper itself is tested to reject a test that would pass with the guard deleted. |
| 8 | Denominator-aware non-null validation | **PASS** | `nfl/ingest/validate.py`. A denominator is required with no default. Both directions tested: empty-on-its-own-denominator FAILS, correctly-scoped nulls PASS. |
| 9 | Named `PFR_ID_UNMAPPED` + replay test | **PASS** | `nfl/ingest/identifiers.py`. Well-definedness and injectivity are separate checks with separate codes; `map_by_name` refuses by design. |
| 10 | Draw-archive schema frozen, incl. `cross_game_dependence` | **PASS** | `nfl/schema/draw_archive.schema.json`, frozen and hashed in `DRAW_ARCHIVE_FREEZE.json` (`04114a4f…`). |
| 11 | `written_at`/`captured_at`/kickoff ordering | **PASS** | `nfl/identity/seal.py`, **corrected order** `source/effective → retrieved → written → kickoff`. 97 tests, 0 failing. |
| 12 | Seal a forecast immutably before kickoff | **PASS** | `seal_forecast` + `append_seal`; re-sealing with different content is `SEAL_IMMUTABLE_VIOLATION`. |

---

## The three residuals, named rather than waived

**¹ Item 1 — FAIL, per owner override, and correctly.** The perishable official
cascade — practice participation, final game status, inactives — is what the
vintage requirement exists to preserve. None of it is captured. `injuries` is
`DEFERRED` (nflverse 404 for 2026) and the three official sources are
`BLOCKED / ENDPOINT_NOT_YET_VERIFIED`. What runs is `schedules`, `depth_charts`
and `weekly_rosters`, and a scheduler alive for non-critical sources does not
satisfy the requirement.

`registry.unmet_targets()` now prints this on **every capture run**:
`UNMET CAPTURE TARGETS: ['final_status', 'inactives', 'practice']`. The gap is
machine-readable rather than a footnote.

**The T−90 half is now implemented and no longer part of why item 1 fails.**
Targets carry one-sided windows; the inactives window is exactly 80 minutes from
T−90; a 6-hourly poll cannot discharge it, nor can a mirror source. What remains
is the endpoint, which is an external dependency — **more code here moves
nothing.**

**² Item 4 — CLOSED.** `nfl/identity/effective_scope.py` plus
`registry.bound_from_series`. The narrowing layer answers
`assert_usable_for(game_id, forecast_timestamp)` directly, refuses relabelling,
never overwrites a source value, and refuses a derived value wearing source
authority.

The honest consequence, stated rather than hidden: a season file narrowed only by
its own `Last-Modified` is **FILE-level** and is correctly `TOO_COARSE` for
game-level certification, because an interval open at the top cannot separate two
games in a season. `bound_from_series` closes the interval from the vintage
series — deterministically, evidenced by the content hash that changed — and a
bounded vintage then certifies a specific game. An unsuperseded vintage stays
`DEFERRED / VINTAGE_NOT_YET_SUPERSEDED` rather than being given a fabricated
upper bound.

**³ Item 5 — proven, not yet exercised by a production run.** The identity
machinery is demonstrated by test, but nothing has consumed it end to end because
NFL-1 has not executed. That is inherent to a gate that runs *before* execution,
not a gap in the control — but it means the first real exercise happens at G1,
and G1 should be read as also validating this.

---

## Two behaviours documented rather than filed as defects

So that a future change to either shows up as a diff rather than a surprise:

- `missed_captures` tolerance is **symmetric**, so a capture taken 5h *before* a
  4pm filing deadline currently counts as satisfying it.
- The Thursday, Monday, Saturday and midweek cadences are **`confirmed=False`**.
  Only the Sunday pattern, the 4pm New York filing deadline and the 90-minute
  inactives lead were externally reported; the rest are inferences and are
  flagged as such in every plan entry they produce.

---

## What the tests actually found

The adversarial pass found **twelve real defects in these controls**, all fixed.
Three reproduced the exact failure classes this repository catalogues — inside
the guards written to prevent them:

- `is_null` did not recognise `float('nan')`, so fed the **real** motivating case
  (`ngs_air_yards`, 0 non-null of 45,919) through a pandas reader, the validator
  returned **PASS at 1.0 non-null**. Class A, inside the Class A guard.
- `HEADER_ONLY_PAYLOAD` counted newlines rather than data rows, so a header
  padded with blank lines became a recorded vintage with a durable blob written.
- The model-derived comment claimed **45** over a tuple of **41** while the
  provenance audit said **31** — three copies, three numbers, nothing comparing
  them. Class C.

Also: 13 leaking columns absent from the quarantine (including `qb_epa`, at
availability 1.0000 on dropbacks); an eligibility escape hatch that accepted
`weekly_rosters.status` — the exact field the module quarantines — as a closing
source; an injectivity check that tested well-definedness instead; and a redirect
hop's `Last-Modified` stamped onto a payload that carried none.

**The seal was the one control that survived unchanged**: 97 of 97.

# ESPN injuries has never returned a plausible row count, and both states passed

Measured 2026-09-25 from `nfl/vintage_manifest.jsonl` at HEAD `4083f4c`, over
648 captures of `espn_injuries_json` carrying `value.n_data_rows`.

## The measurement

An injury feed covering 32 clubs should vary from day to day. This one takes
**exactly two values across 648 captures**:

| n_data_rows | captures | window |
|---|---|---|
| **35** | 436 | 2026-09-07T00:24Z → 2026-09-15T17:05Z |
| **800** | 212 | 2026-09-15T19:36Z → 2026-09-24T12:07Z |

They are **temporally separated, not interleaved**. Something changed between
17:05Z and 19:36Z on 2026-09-15.

Every one of the 648 is `state: PASS`, `code: CAPTURED`. Payload size is
~8.7–9.0 MB in both eras, with 270 and 141 distinct byte counts respectively,
so the **document was always arriving whole and varying**; what changed is how
much of it became rows.

## Two different defects, and neither is a server cap alone

**Before 2026-09-15 ~18:00Z — under-extraction.** 35 rows out of an 8.8 MB
document, held for 436 consecutive captures across 8 days. 35 rows cannot
describe 32 clubs' injury reports. The bytes were there and the parser took
almost none of them.

**After — the 25-per-club cap.** 800 is exactly **25 × 32**. This is the cap
already recorded in
`nfl/research/findings/2026-09-24_ESPN_FEED_TRUNCATED_AT_25.md`, and the
manifest now gives it an independent arithmetic confirmation rather than an
inference from one probe.

## Why this matters more than either number

The seven source-validity axes exist for exactly this. Transport succeeded in
both eras — the bytes arrived, the hash was taken, the record says PASS.
**Content completeness failed in both eras, differently, and nothing in the
capture path had an opinion about it.** A `PASS` on this source has never meant
the feed was complete; for 436 captures it did not even mean it was mostly
complete.

A step change of 23× in a parsed row count, held for months on either side, is
also the signature the mandate calls *silent schema drift*. It was not detected
when it happened. It was detected today by asking a question nobody had asked
of the manifest: *how many distinct row counts does this source ever produce?*

## The detector, generalised

`nfl/tools/source_rowcount_census.py` asks that question of every source. The
signature worth alarming on is not a specific number, it is **degeneracy**: a
feed whose row count takes very few distinct values, or takes a step and never
returns. Measured across the manifest today:

| source | captures | distinct counts | reading |
|---|---|---|---|
| `espn_injuries_json` | 648 | **2** | both degenerate, see above |
| `schedules` | 690 | **1** (7548 every time) | plausibly static, and see below |
| `official_inactives` | 382 | 5 | per-game lists; needs a human read |
| `injuries` | 655 | 12 | varies, the shape a live feed should have |
| `depth_charts` | 690 | 20 | varies |
| `weekly_rosters` | 690 | 10 | varies |
| `official_injury_report` | 594 | 37 | varies most, as expected |

`schedules` returning **exactly 7548 rows on all 690 captures** is consistent
with a static season file and is probably correct. It is recorded here because
it also means the capture path stored the same content 690 times, which is part
of why `vintage_manifest.jsonl` is 53.55 MB. That is a storage observation, not
a correctness one.

## What is NOT established

* **Whether the 35-row era corrupted any forecast.** Nothing here traces those
  captures into a run. `espn_injuries_json` is a secondary availability source
  and `availability_feed.states()` already refuses to read absence as health,
  so the exposure may be small. It has not been measured and must not be
  assumed either way.
* **What changed on 2026-09-15.** A parser edit, a schema change at the source,
  or a capture-path change. The commit range is narrow and this is answerable;
  it has not been answered.
* **Whether 800 is still the ceiling today.** The last capture in this manifest
  is 2026-09-24T12:07Z.

## What follows

1. A content-completeness assertion on this source, expressed as a plausible
   range per club rather than a fixed number, refusing outside it.
2. Re-derive the 2026-09-15 change from the commit history and record which of
   the three causes it was.
3. Trace whether any sealed run consumed a 35-row capture.

None of these requires an owner decision.

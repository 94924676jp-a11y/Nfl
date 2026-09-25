# The authoritative availability sources went dark before the game, and the board knew

Measured 2026-09-25 from `nfl/vintage_manifest.jsonl` at HEAD `4083f4c`.

## What the capture record says

| source | attempts | last attempt | last attempt's verdict |
|---|---|---|---|
| `injuries` | 695 | 2026-09-24T06:07Z | PASS/CAPTURED |
| `depth_charts` | 694 | 2026-09-24T06:07Z | PASS/CAPTURED |
| `weekly_rosters` | 694 | 2026-09-24T06:07Z | PASS/CAPTURED |
| `official_injury_report` | 688 | 2026-09-24T12:07Z | PASS/CAPTURED |
| `espn_injuries_json` | 685 | 2026-09-24T12:07Z | PASS/CAPTURED |
| **`official_inactives`** | 704 | **2026-09-21T17:52Z** | **BLOCKED/NO_EGRESS** |
| **`official_transactions`** | 684 | **2026-09-21T17:52Z** | **BLOCKED/ENDPOINT_NOT_YET_VERIFIED** |

Two things are true at once and must not be collapsed.

**The last row-bearing capture of `official_inactives` was 2026-09-15T17:05Z.**
After that the source produced rows for nobody.

**The last capture ATTEMPT was 2026-09-21T17:52Z**, and the attempts between
those dates failed in two distinct ways, in order:

* `DEFERRED / SOURCE_HAS_NO_ROWS_YET` — HTTP 200, 403,520 bytes that render and
  carry 23 occurrences. The page was up and simply had no inactives posted yet,
  which on a Saturday is the correct answer and the correct verdict.
* `BLOCKED / NO_EGRESS` — from 2026-09-20T16:07Z, no HTTP response at all for
  `https://www.nfl.com/inactives/`.

**Then nothing.** No attempt of any kind on 09-22, 09-23 or 09-24. The Atlanta
at Green Bay game kicked off 2026-09-25T00:15Z.

## This is the cause of yesterday, named

Three things I handled by hand on 2026-09-24 have one upstream explanation:

1. **The board's `AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` gate read
   INSUFFICIENT_EVIDENCE.** It was not a gate being pedantic. The source had
   been dark for nine days. The gate was reporting a fact.
2. **I relayed the inactive list from the owner as text.** Correctly, as a
   secondary source — but the reason a secondary was needed was this, and I did
   not know it.
3. **Josh Jacobs.** `official_transactions` is the feed that would carry a
   reserve/exempt designation, and it has never been captured successfully:
   every attempt ends `ENDPOINT_NOT_YET_VERIFIED`. The owner caught by eye what
   no source in this repository could have told us, because the endpoint that
   would say it was never verified.

## The defect is not the outage. It is the silence about it.

An egress failure on a third-party site is ordinary and the capture layer
recorded it honestly, by name, with the URL. What is missing is anything that
**notices a source has stopped**. Five sources ran to within eighteen hours of
kickoff; two stopped three days out; nothing anywhere raised that asymmetry.
`source_census` was built on 2026-09-24 to detect exactly this class and it has
**zero non-test consumers**, so it detected nothing.

A source that goes dark looks identical, from downstream, to a source with
nothing to report. That is the same shape as every other defect in this audit:
absence read as a benign answer.

## What is NOT established

* **Why capture stopped entirely after 2026-09-21.** Attempts ceased rather
  than continuing to fail. A schedule change, a workflow failure, or a
  deliberate pause — not determined here, and the distinction matters because
  only one of the three is self-healing.
* **Whether `official_transactions` has a working endpoint at all.**
  `ENDPOINT_NOT_YET_VERIFIED` on every one of 684 attempts is consistent with
  an endpoint that was never right, not with one that broke.
* **Whether the 09-15 to 09-21 `DEFERRED` verdicts were correct at the time.**
  They look correct — a page with no inactives posted yet is not a failure —
  but that has not been checked against the posting schedule.

## What follows, none of it owner-gated

1. A staleness assertion per source, driven off the capture record: if a source
   the run depends on has no row-bearing capture within its own governed
   window, the run says so before it simulates. `run_input.py` already has
   `AGE_NOT_BOUNDED`; nothing calls it.
2. Wire `source_census` to something that runs.
3. Resolve `official_transactions` to a verified endpoint, or declare in code
   that reserve/exempt status has **no** automated source and must be supplied.
   Either is honest. The present state — 684 failed attempts and silence — is
   not.

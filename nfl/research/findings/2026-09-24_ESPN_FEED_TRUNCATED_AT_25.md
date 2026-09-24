# The ESPN injuries feed is truncated at 25 players per club, silently

**Date:** 2026-09-24
**Measured offline** over the entire preserved capture history. No network.
**Severity:** coverage loss, not a false inference. Read the "What this does
not mean" section before acting on it.

## The measurement

Every `espn_injuries_json` blob in `nfl/vintage/`, all 648 captures, decoded
and counted per club:

| Quantity | Value |
|---|---|
| Captures | 648 |
| Club entries (648 x 32) | 20,736 |
| Club entries carrying **exactly 25** injury items | **20,736** |
| Club entries carrying any other count | **0** |

Not one club, in any capture, across the whole season to date, ever returned
24 items or 26. The distribution has a single value. A live injury census over
32 clubs and six weeks does not do that; a page size does.

The response carries `"status": "success"` and no pagination metadata
whatsoever -- no `count`, no `pageIndex`, no `pageCount`, no `next`. The top
level is exactly `['injuries', 'season', 'status', 'timestamp']` and a club
entry is exactly `['displayName', 'id', 'injuries']`. **Nothing in the
document says it has been cut.** That is what makes this the project's Class A
defect rather than an ordinary API limit: a partial answer arrives wearing the
word "success".

## The cost is worse than 25 would suggest

The cap is not spent on injured players. Across one capture's 800 items:

| status | n | share |
|---|---|---|
| Active | 585 | 73.1% |
| Questionable | 161 | 20.1% |
| Injured Reserve | 25 | 3.1% |
| Out | 22 | 2.8% |
| Doubtful | 7 | 0.9% |

One club's 25 slots held 16 `Active`, 4 `Questionable`, 4 `Injured Reserve`
and a single `Out`. So roughly three quarters of the window we are allowed is
consumed by rows that carry no actionable availability signal, and a genuinely
`Out` player ranked past the 25th is invisible to us. We are not seeing the 25
most important injury facts per club; we are seeing the first 25 of an
unspecified ordering, mostly healthy.

## What this does NOT mean

`availability_feed.states()` does not convert absence into health. A player
with no item is `NO_ITEM` / `NOT_IDENTIFIED`, and the module says so in those
words: *"ABSENCE FROM AN INJURY FEED IS NOT EVIDENCE OF HEALTH."* That
refusal is already correct and this finding does not weaken it.

So the truncation does not put a wrong number anywhere. What it does is
**lose a signal we could have had**: a player who really is OUT, past slot 25,
lands in `NOT_IDENTIFIED` instead of `UNAVAILABLE`. The forecast then treats
him as an open question rather than as ruled out. That is a coverage loss and
an honest one, but it is still a loss, and until now nothing recorded that it
was happening.

## What changes

1. The feed records `feed_truncated` when every club returns exactly the cap,
   so the condition is visible in the artifact instead of inferred by someone
   re-deriving it later.
2. A `NO_ITEM` join state on a truncated capture says so in its reason. The
   difference matters: "this feed listed nobody for him" and "this feed was
   cut off before it could list him" are different epistemic positions, and
   only the second is a reason to go looking elsewhere.
3. Nothing is inferred from the cap. We do not estimate how many players were
   dropped, and we do not treat a truncated feed as evidence about anyone.

## The open question, which needs network

Whether the cap can be lifted is not answerable from inside this checkout. It
is in the outbox: does the endpoint honour a `limit`, `page`, or per-club
query that returns the full list? If it does, this is a one-line capture fix
and a real gain in availability coverage. If it does not, ESPN is permanently
a partial secondary source and should be documented as one.

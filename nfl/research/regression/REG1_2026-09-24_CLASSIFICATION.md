# REG-1: prior defects retested at HEAD

**Date:** 2026-09-24. **HEAD:** the commit carrying today's audit work.
**Register:** `nfl/research/live/OPEN_DEFECTS.json`, 24 defects.

**The rule this follows:** no historical severity carries forward
automatically — and, equally, **no historical repair claim carries forward
automatically**. The register's own `repaired` field is treated as a claim to
be checked, not as a result. Every FIXED needs a current test; every
STILL_PRESENT needs a current reproduction.

Classification vocabulary, and nothing else:
`FIXED` · `STILL_PRESENT` · `REGRESSED` · `SUPERSEDED` · `NOT_VERIFIABLE`.

## Classified on current evidence

### D20 — empty-state captures reported PASS — **FIXED**

*Register claim: repaired = True. Verified, and the verification corrects
something I said earlier today.*

The capture states for `official_inactives`, by day, show a regime change:

| day | states |
|---|---|
| 2026-09-12 | PASS=55 |
| 2026-09-13 | PASS=89, BLOCKED=18 |
| 2026-09-14 | PASS=58, BLOCKED=2 |
| 2026-09-15 | PASS=36, DEFERRED=9 |
| **2026-09-16** | **DEFERRED=48, PASS=0** |
| 2026-09-17 | DEFERRED=48, PASS=2, BLOCKED=3 |
| 2026-09-18 | DEFERRED=48 |
| 2026-09-19 | DEFERRED=48 |

From 2026-09-16 the empty-state page stops being recorded as PASS and is
DEFERRED instead. The `content_markers` / `row_container` repair landed and
works.

**Correction to my own earlier statement.** Twice today I cited "402 PASS rows
for official_inactives" as evidence of a live defect. The count is accurate
and the framing was not: those rows are overwhelmingly **pre-repair**, and I
had not checked whether current captures still behave that way. They do not.
The historical rows remain a true description of what the store contains and a
false description of what the capture layer now does. Noted here rather than
quietly dropped, because a wrong framing that flatters a finding is still
wrong.

What this does **not** change: the preserved bytes are still 363 of 367
empty-state pages, so the parser must still refuse them — which it does, by
name — and the outbox request for a content-bearing artifact still stands.

### D16 — nine percentiles cannot support exact CRPS — **FIXED**

*Register claim: repaired = True. Verified.* The current artifact stores
**8,000 draws** across 54 matrices and 3,344,000 draw cells, not nine stored
percentiles. Probability at a line is computed as the share of draws strictly
above plus half the ties, exact rather than interpolated, and
`summarise_draws.prob_over` asserts that property.

### D23 — two runs at the same clock consumed different inputs — **STILL_PRESENT**

*Register claim: repaired = True. Contradicted by a current reproduction.*

`nfl/tests/test_replay_pins_its_inputs.py` passes 11/11 and its own output
reads:

```
sealed   6477fddd245bcc26
pinned   6477fddd245bcc26   IDENTICAL
reselect 6970cb9b6ea65fa8   DIFFERS
```

with the check labelled *"re-selecting at the same clock does NOT -- D23 is
still live"*. The **pinned** path is repaired and reproduces the seal exactly.
Re-selection at the same declared clock still diverges, which is the original
defect. So the repair added a correct path beside the broken one rather than
removing the broken one, and the register records the first half.

This is consistent with today's A1 audit: **eight production modules still
glob the vintage store at forecast time** and select their own evidence, which
is the mechanism by which two runs at one clock can differ.

### D04 — officially inactive quarterbacks kept dropback share — **NOT_VERIFIABLE today, with an adjacent STILL_PRESENT**

*Register claim: repaired = True, with `test_required` itself stating what is
outstanding: "a post-repair board for a game with an inactive QB to confirm
end to end".* No such board exists yet — tonight's ATL @ GB has no officially
inactive quarterback because the inactive list has not published. So the
end-to-end confirmation the register asks for cannot be done, and the honest
classification is NOT_VERIFIABLE rather than FIXED.

**The adjacent finding is not adjacent by much.** Today's
`unavailable_owns_nothing` invariant found that Jayden Reed — GB, WR, declared
OUT with a neck injury and a did-not-practise — holds the largest WR gadget
share in the game at 0.241 of draws. The repair zeroed inactive rows before
R2/Hamilton in the QB allocation path; the gadget pool filters on roster class
and never consults availability. So the *rule* D04 established is still broken
in a layer D04 did not reach.

## Not yet classified

The remaining twenty defects are **NOT_VERIFIABLE at this sitting** — not
because they are unverifiable in principle, but because each needs a specific
reproduction that has not been run. They are not being carried forward at
their historical severity, and none of their `repaired` claims is being
accepted on its own authority.

Nine of twenty-four carry `repaired = True`; fourteen carry `False`; one
carries a sentence rather than a boolean (`D21`: "MECHANISM COMPLETE AND
PROVEN; ONE PUBLISH STEP REMAINS AND IT IS NAMED"), which is a more honest
field value than either boolean and is worth copying.

## What this exercise established

Two of four checked repair claims did not survive contact with current
evidence in the form the register states them — D23 outright, D04 by its own
admission. One of my own findings from earlier today needed correcting in the
same direction. The lesson is symmetrical and worth stating: **a repair claim
and a defect claim decay at the same rate, and neither should be quoted
without a date and a reproduction.**

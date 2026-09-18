# The Buffalo non-QB role defect, reviewed prospectively

**Prospective means no outcome is read.** Every number below comes from the
board sealed `2026-09-16T15:45:14Z` and the depth vintage as it stood at that
instant. The DET @ BUF result is not in this document, is not needed for any
claim in it, and would not change one. Nothing here is fitted, tuned or
calibrated to a game.

## What the diagnostic already established, and what it did not

`P2_DIAGNOSTIC.md` established the mechanism: CS1 is
`current-season-qb-panel-1`, a **quarterback** panel, so week-1 receiving and
rushing usage never reaches non-QB role allocation. It also established the
symptom on one room — James Cook, Buffalo RB1, `P(carries = 0) = 0.375`
against Ray Davis at `0.292`.

What it did not establish is whether anything in the pipeline would ever
**notice**. It did not, and that is the gap this pass closes. The defect was
written down on 2026-09-17, the board shipped on 2026-09-17, and a 40-lineup
portfolio went out at 72.5% Ray Davis. Writing a defect down is not the same as
guarding against it.

## The guard

`nfl/production/nonqb/role_invariants.py`. Within a room — **one club, one
position** — a player listed ahead on the official depth chart may not carry a
higher probability of zero opportunity than a player listed behind him.

It is an ordering constraint on the model's own output. It fits nothing, tunes
nothing, and is indifferent to what any player actually did.

**The tolerance is derived rather than chosen.** Two probabilities estimated
from the same N Monte Carlo draws differ by sampling noise alone, so the flag
fires only when the inversion exceeds two standard errors of the difference,
`sqrt(p1(1-p1)/n + p2(1-p2)/n)`. A board with fewer draws raises fewer flags,
correctly. No constant was invented to make a number come out.

## What it finds on the board that shipped

`ROLE_ORDERING_PROSPECTIVE.json`, 36 ordered pairs across 6 rooms, 8,000 draws:

| club | room | ahead | P(zero) | behind | P(zero) | excess | SE |
|---|---|---|---:|---|---:|---:|---:|
| BUF | RB | James Cook (#3) | 0.3719 | Ray Davis (#8) | 0.1801 | +0.1918 | 27.8 |
| DET | WR | Tom Kennedy (#12) | 0.8551 | Tay Martin (#15) | 0.7672 | +0.0879 | 14.3 |

The first is the known defect, caught automatically for the first time. **The
second is new.** Nobody had looked that far down Detroit's receiver chart; its
football consequence is small and its mechanism is the same one. A guard that
only ever finds what you already knew is not a guard.

## The two players it cannot protect

Greg Dortch and Frank Gore Jr. carry **no depth rank at all**, so they are in
no room and no ordering check can constrain them. Both are Buffalo. **Frank
Gore Jr. is the player the delivered portfolio carried at 55% exposure.**

This is worth stating plainly: the exposure that did the most damage sat in the
one place the invariant has nothing to say about. An unranked player is not a
safe player, he is an unconstrained one, and the honest response is to surface
him rather than to invent a rank for him.

## The mistake this check made first, kept on the record

The first pass pooled both clubs and reported seven inversions. Five were
artefacts: the depth vintage ranks offence-wide **within a club**, so ranks
from two clubs are two different scales, and the run confidently compared
Buffalo's RB1 against Detroit's. The check now **requires** a club and refuses
a player who carries a rank without one. `test_D` pins it.

It is the same failure the whole project keeps meeting: a join that looked
like an identity and was an inference.

## What this does NOT establish

Two clubs on one slate. **It says nothing about how often the model inverts a
room in general**, and no rate may be quoted from it. Measuring that needs
boards across many clubs and weeks, which do not exist here yet. What it
establishes is narrower and still worth having: the invariant fires on the
known defect, it found one nobody had seen, and it names the players it cannot
cover.

It also does not repair anything. Which of the two rows in an inversion is
wrong is a modelling question — and it is the question CS2 exists to answer,
since the missing input is exactly the current-season non-QB usage that would
tell Cook's row from Davis's.

## What follows

1. CS2, the current-season non-QB role-state layer, still design-only. The
   invariant makes its absence visible on every future board instead of on a
   postmortem.
2. The unranked-player gap is a **capture** problem — a depth source that
   covers the full roster — not a modelling one, and is recorded as owed.

**No fitted threshold, exposure cap or architectural change is proposed here,
and none may be derived from this document.**

**MARKET IS DIAGNOSTIC EVIDENCE ONLY, NOT A TARGET**

**V2 NOT YET EARNED**

# CS2: a current-season state layer for non-quarterbacks. Design only.

**Nothing is implemented.** This is the sibling to CS1, which the P2
diagnostic confirmed is `current-season-qb-panel-1` — a **quarterback** panel,
30 clubs, 35 rows. The refresh that fixed the QB season-boundary problem has no
non-QB counterpart, so week-1 receiving and rushing usage never reaches role
allocation for RB, WR or TE.

CS1 is not modified by anything here.

## The decomposition, and why it cannot be one parameter

For every non-QB participant, three states are estimated **separately**:

```
  P(eligible)                         is he permitted to play at all
  P(appears | eligible)               does he take a snap
  opportunity share | appears         what fraction of the room's work
```

**The P2 defect is the argument for this shape.** In the sealed DET-BUF board
James Cook carries `P(carries = 0) = 0.375` against Ray Davis's `0.292` — the
RB1 absent more often than his backup — while Cook's carry share **conditional
on appearing** is `0.692`, close to the week-1 RB-room evidence of `0.867`.
One number cannot hold both facts. A single "role" parameter that produced
Cook's 0.454 unconditional share is averaging a defensible conditional share
against an indefensible absence mass, and the average hides which of the two is
wrong. Estimated separately, the conditional share would have been read as
approximately right and the absence mass as the defect — which is what the
decomposition exists to make visible.

The same argument holds in the other direction: a specialist who plays rarely
but dominates his room when he does (a short-yardage back, a red-zone tight
end) is a **high conditional share with a low appearance probability**, and
collapsing the two would misrepresent him as a mediocre every-down player.

## Inputs, all lawful before the forecast clock

| Input | Role | Governed source status |
|---|---|---|
| Current roster | eligibility | `weekly_rosters`, captured, 468 records |
| Official depth chart | room ordering, NOT role by itself | `depth_charts`, captured, 468 |
| Injury status / official inactives | eligibility, hard | `official_inactives` 392, `official_injury_report` 374, `espn_injuries_json` 428 |
| Prior-week snap counts | appearance | `snap_counts` is **WATCH_ONLY and 404 for 2026** — NOT available |
| Prior-week carries | appearance + conditional share | derivable from the captured `pbp` |
| Prior-week targets | appearance + conditional share | derivable from `pbp` |
| Prior-week receptions | conditional share | derivable from `pbp` |
| Prior-week routes | conditional share | **NO governed source.** `pbp_participation` is 404 for 2026 and is published only after the postseason |
| Prior-season role history | shrunk prior | `pbp` 2024 and 2025, captured and hashed |

**Two inputs the design asks for do not exist in-season and the design must
not pretend otherwise.** Snap counts and routes are the two most natural
appearance and route-share measures, and both are unavailable for 2026:
`snap_counts` returns 404 and is registered WATCH_ONLY; participation-derived
route data arrives after the postseason. CS2 therefore estimates appearance
from **prior-week opportunity** (a carry or a target is proof of a snap), and
records that this is a proxy with a named limitation: a player who played and
was not targeted is indistinguishable from one who did not play.

Closing that gap is a capture problem, not a modelling one, and it is recorded
as owed rather than approximated.

## Invariants, each with the failure it prevents

1. **An official inactive is a hard zero.** Not a small probability. Prevents a
   ruled-out player receiving opportunity in any draw.
2. **Eligible does not imply opportunity.** `P(appears | eligible) < 1` is
   normal and must not be rounded up. Prevents an active third tight end being
   treated as a participant.
3. **Depth rank alone does not determine role.** It orders a room; it does not
   set a share. Prevents the flat-share failure the diagnostic measured on BUF,
   where the WR1 (`role_certainty` 0.2922) and TE1 (0.2014) were shrunk toward
   the room mean.
4. **Current-season evidence may update the historical prior**, and the weight
   it receives is a declared, tuned quantity, not a constant.
5. **Conditional room shares conserve exactly.** `sum(share | appears) = 1` per
   room, to 1e-9. The sealed board already satisfies this — target-share and
   carry-share sums are exactly 1.0000 — and CS2 must not break it.
6. **Appearance probabilities need NOT sum to one.** They are marginal
   probabilities of independent-ish events, not a partition. A room where four
   of five players are near-certain to play is a real room. Asserting a simplex
   here would be the error that creates the inversion.
7. **No silent fallback to stale prior-season state.** A player with no
   current-season evidence falls back, and the fallback is COUNTED and named in
   the artifact — the pattern `B1`'s `to_B0` counter already follows, which is
   what caught a 1,976-lookup silent cold start during the baseline build.
8. **Unresolved current-season evidence is surfaced**, never absorbed. A name
   that does not join, a club with no rows, a week with no capture: each is a
   named refusal in the verdict, not a quiet default.

## What CS2 does not do

It does not set efficiency — yards per carry, yards per target and catch rate
stay where they are. It does not touch CS1, the QB path, or any frozen arm. It
does not read a sportsbook price or a fantasy projection, in the fit or in the
acceptance test. It is a **state layer**, not a projection layer.

## Acceptance, when it is built

Forward-chained against the same governed frame the baselines use, scored on
opportunity (carries, targets) rather than on yards, so that a role improvement
is not confounded with an efficiency change. The comparator is the current
allocation, and **the possibility that the current allocation wins is
preserved**: if CS2 does not beat it out of sample, CS2 is recorded as a
measured negative and the current path stays.

**Nothing here is implemented, and no number in this document is a promotion
target.**

**MARKET IS DIAGNOSTIC EVIDENCE ONLY, NOT A TARGET**

**V2 NOT YET EARNED**

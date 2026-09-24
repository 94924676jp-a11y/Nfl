# Ticket: is the QB room over-hedged, and should it be constrained?

**Raised:** 2026-09-24 from run `2fc4e9599f0889f1`.
**Class:** research, pre-registration required. **Not** a patch.
**Status:** OPEN. Nothing may change in the engine on the strength of what is
written here.

## The observation

Two or more quarterbacks throw in 21.8% of ATL's simulated worlds and 21.1%
of GB's. The historical rate, restricted to QB-position passers and bracketed
for an incomplete position map, is **13.3% to 16.9%** over 1,142 to 1,172
team-games across 2024, 2025 and 2026 to date. The model sits above the upper
bound.

Play probabilities within a room are not constrained to sum to one: ATL sums
to 1.232 across four quarterbacks, GB to 1.211 across two.

## Why this is not yet a finding

Two team-games, from one game, on one date. Under this project's own rules
that is a single cluster and not a rate. The historical bracket is also
approximate: the position map is built from 2026 roster captures, so a 2024
passer who is not on a 2026 roster is dropped, and 1,490 passer rows have no
position at all.

It is entirely possible that ATL's number is high because ATL genuinely has an
unsettled quarterback room this week, which is the model being right rather
than the model being wrong. One game cannot separate those.

## What must be settled before any change

1. **Measure across many team-games**, not this one. Clustered by game and by
   date, or blocked-resampled. A point estimate from one slate is not
   evidence.
2. **Rebuild the position map from contemporaneous rosters** so the historical
   bracket collapses to a usable interval instead of a range that spans the
   question.
3. **Decide what the target actually is.** The rate of two QBs *throwing* is
   not the rate of an uncertain *starter*. A backup entering a decided game in
   the fourth quarter and a genuine week-long competition produce the same
   statistic and call for opposite treatments. Separate them before fitting to
   either.
4. **Decide whether a sum-to-one constraint is even correct.** Exactly one QB
   starts, but more than one may throw, so P(throws) summing above one is not
   by itself an error. The constraint that might be justified is on *starting*,
   which the artifact does not currently represent as its own quantity.
5. **Establish what it would cost.** Collapsing the room raises the conditional
   spread of the starter's projection and could raise discrimination, which is
   the project's objective. It also removes hedging that may be honest. Both
   directions need measuring, not asserting.

## What must not happen

* No coefficient may be fitted to make the model's 21% match a historical
  13-17%. That is tuning to a target derived from the same family of data and
  it is exactly what the no-silent-constants rule forbids.
* No change may be justified by "the projections look more reasonable".
* This ticket may not be closed by the ATL @ GB rerun tonight. One more game
  is one more cluster.

## The cheap part that is not blocked

The reporting fix in
`nfl/research/findings/2026-09-24_QB_ALLOCATION_AND_CONDITIONALITY.md` --
carrying `P(plays)` and the conditional mean beside the unconditional one --
alters no projection and does not depend on any of the above. It should not
wait for this ticket.

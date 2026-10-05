# Week 4 Early Only: findings from the DraftKings standings (2026-10-05)

Not frozen; the graded numbers are in the two standings addenda (`FROZEN_2026W4_EARLY_STANDINGS_ADDENDUM_1/2.json`).

## F1: DST points allowed excludes the opponent's non-offensive touchdowns (DK rule; our grader is wrong)

DK FPTS agree with our component scoring for every player in all three contests except one: **Cardinals
DST, DK 9.0, ours 6.0**. Components (nflverse week 4): 4 sacks, 2 INT, 1 opponent fumble recovered = 10.
The Giants scored 36, but one Giants touchdown was an interception return (D. Banks, 0:11 Q4, off Brissett;
nflverse play-by-play retrieved 2026-10-05). DK's points allowed excludes it: 36 - 7 = 29, tier -1, total 9.
`classic_week.actual_points` passes the final score, which gives tier -4.

- The frozen grade is not edited; it is wrong by 3.0 for this one DST, and the addenda record it.
- The same rule applies to the simulator: `nfl/sim/game.py` scores a DST from the opponent's simulated
  points, which include non-offensive scores through the measured remainder. That over-counts points
  allowed slightly whenever a defensive or return TD is in the world. It belongs to the P0 joint-event work
  (docs/NFL_SHOWDOWN_EXCELLENCE_PROGRAM.md, items 2 and 6), where defensive and return TDs become explicit
  per-world events and points allowed can then be computed as DK defines it.

## F2: Field ownership (first real field data)

All 173 of our lineups were unique in their fields. Our median lineup's summed ownership was 112.8% / 119.1%
/ 106.5% (150-max / 20-max / 3-entry) against the fields' 143.3% / 141.1% / 133.1%. Ownership was
reconciled in each file (DK lists a player once per roster slot; the slot shares are summed).
These are the first archived contest ownership rows for the field model (OUT-040, roadmap P2).

## F3: Payout table still missing

No standings export carries prizes, so cash rate, winnings and ROI remain BLOCKED.

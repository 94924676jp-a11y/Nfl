# NYG backfield role inversion in d90d80c0b4a7f95e — mechanism identified

Measured 2026-09-21T23:59Z, ~15 minutes before kickoff. Reported, not repaired.

## The inversion

| NYG RB | corpus wk1 carries | carry share | snap % | d90 simulated carries |
|---|---|---|---|---|
| Cam Skattebo | **18** | 0.486 | 0.61 | **6.14** |
| Tyrone Tracy Jr. | **2** | 0.054 | 0.03 | **8.09** |
| Devin Singletary | 6 | 0.162 | 0.36 | 4.38 |
| Najee Harris | no row | — | none | 5.25 |

The corpus is correct. `usage_vintage` and `load_snaps` both carry the right
week-1 values, and the candidate `role_state` layer classified Skattebo
STARTER at 0.61 and Tracy BACKUP at 0.03. The defect is downstream of role,
inside the simulator's own opportunity allocation.

## The mechanism

The depth listing the engine consumes:

    Cam Skattebo        RB1
    Najee Harris        RB2
    Tyrone Tracy Jr.    KR2
    Devin Singletary    KR3

Tracy and Singletary are listed in the KICK RETURNER group, not the running
back group. `role_prior.assign_tiers` takes `depth_rank` as an integer and
anchors on the tier that rank implies, WITHOUT checking that `pos_abb` names
the room being allocated. So **KR2 is read as though it were RB2**, and Tracy
receives a near-lead-back anchor for the carries room.

This is independently corroborated: reporting has Tracy working as a kickoff
returner this week, which is precisely what the KR2 listing encodes. The
engine ingested the right fact into the wrong room.

Najee Harris compounds it from the other side: a genuine RB2 listing with
zero observed games, so `weight()` returns the anchor outright and the depth
chart is his entire forecast — the cold-start defect already recorded in
role_prior's own docstring. He was a healthy scratch in week 1, which is why
no usage row exists.

## Why scaling cannot fix this

The two errors sit in the same room in opposite directions. Multiplying every
projection by the externally fitted 1.39 would move Tracy further from the
evidence and leave Skattebo only superficially closer. The global-level
finding and this role defect are separate problems and must be repaired
separately.

## The fix, specified but NOT applied

When a depth rank is used to anchor a room, accept it only when `pos_abb`
names a position that competes in that room (RB, FB, HB for carries). A
listing from another group — KR, PR, ST — must be treated as ABSENT, which
`assign_tiers` already handles correctly by anchoring on the deepest measured
tier. This is a correctness repair, not a tuning change: reading KR2 as RB2
is simply wrong.

NOT APPLIED TONIGHT, and the reason is the clock. This sits inside the
accepted candidate chain V1_CANDIDATE_R9_W1P_GSVUCY. Changing an accepted
config fifteen minutes before kickoff, with no time to run the suite or
compare a before-and-after, is the failure mode this project's rules exist to
prevent. The finding is worth more than a rushed patch, and the lineups are
already submitted.

## Consequence for tonight's board

Tracy carries 14 of 20 lineup exposure on a projection this defect inflates.
His DFS support audit passed on the evidence test -- he has measured snaps and
measured usage -- but the magnitude is not supported, and this is the reason.
Skattebo, at 2 of 20 exposure, is the player the defect suppressed.

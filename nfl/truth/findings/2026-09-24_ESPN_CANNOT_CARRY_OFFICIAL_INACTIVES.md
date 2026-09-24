# ESPN injuries feed cannot carry official game-day inactives

**Date:** 2026-09-24
**Result:** NEGATIVE — the option is closed, not pending.
**Measured offline** against the captured blob. No network was used.

## Why this was tested

`https://www.nfl.com/inactives/` was proven to be a client-rendered shell: 382
capture PASSes, none whose preserved bytes contain an inactive list. The
proposed fallback was ESPN, on the reasoning that the availability feed already
ranks `OFFICIAL_GAMEDAY_INACTIVE` above secondary reports and `combine()` is
built for exactly that handoff. Whether our captured JSON carries them was
testable offline, so it was tested rather than assumed.

## What was measured

Blob: `nfl/vintage/espn_injuries_json.7291a7378c17df0e.json.gz`
Capture timestamp: `2026-09-24T12:07:44Z`
Shape: top-level keys `['injuries', 'season', 'status', 'timestamp']`; 32 team
entries; each `injuries[]` item carries `athlete`, `date`, `details`, `id`,
`longComment`, `shortComment`, `source`, `status`, `type`.

The complete `status` vocabulary across all 32 teams, with counts:

| status | n | type | n |
|---|---|---|---|
| Active | 585 | INJURY_STATUS_ACTIVE | 585 |
| Questionable | 161 | INJURY_STATUS_QUESTIONABLE | 161 |
| Injured Reserve | 25 | INJURY_STATUS_IR | 25 |
| Out | 22 | INJURY_STATUS_OUT | 22 |
| Doubtful | 7 | INJURY_STATUS_DOUBTFUL | 7 |

Total 800 rows. The vocabulary is closed — these five values are all of it.

## The finding

**There is no inactive value in this vocabulary.** Neither the `status` strings
nor the `INJURY_STATUS_*` types contain a game-day-inactive concept. Every
value ESPN emits is an *injury designation* issued by a club during the practice
week, which is a different claim, from a different authority, at a different
time, than the officially filed 90-minutes-before-kickoff inactive list.

`Out` is the nearest-looking value and it is the trap. Converting `Out` to
`OFFICIAL_GAMEDAY_INACTIVE` is forbidden by standing owner constraint:

> Do not convert an injury designation such as OUT into
> `OFFICIAL_GAMEDAY_INACTIVE`.

They are ranked differently by `availability` on purpose. A player designated
`Out` on Friday is overwhelmingly likely to be inactive, but "overwhelmingly
likely" is inference, and the availability layer exists precisely so that
inference does not get laundered into an official fact. The 585 `Active` rows
are the mirror trap: they are injury-report status, not confirmation that a
player will dress, and reading them that way would be inferring ACTIVE from a
non-inactive designation.

## Consequence

ESPN is **not** a candidate carrier for official inactives. This does not
degrade ESPN's existing role — it remains a legitimate injury-designation
source and continues to feed `availability` at that rank. What it cannot do is
close `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE`.

With `nfl.com/inactives/` a rendered shell and ESPN's vocabulary closed against
the concept, **no source currently inside this repository can supply official
game-day inactives.** The outstanding outbox request to the networked agent is
therefore not one option among several; it is the only known path. If it
returns `NO_VERIFIED_OFFICIAL_INACTIVES_ARTIFACT`, that is a real result and the
pre-inactive forecast stands as the terminal pregame product for this game.

## What would change this

A carrier must satisfy the acceptance test already written in the outbox: the
**preserved raw bytes** must themselves identify the inactive players for ATL
and GB without inference. Endpoints whose bytes are a client-rendered shell
fail that test at HTTP 200. Any future ESPN endpoint would need a distinct
game-day-inactives resource, not a richer read of this one — this one's
vocabulary has no room for the concept.

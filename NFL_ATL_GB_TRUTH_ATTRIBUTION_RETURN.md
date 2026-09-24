# ATL @ GB — game-attribution truth layer

**Game** `2026_03_ATL_GB` · ATL @ GB · 2026-09-24 20:15 local · outdoors, grass
**Kickoff** 2026-09-25T00:15:00Z
**Built** from capture `20260924T120743Z` (capture-prod `b970749`)

## What was asked

Turn the existing captured ATL/GB evidence into a trustworthy structured truth
state for `2026_03_ATL_GB`, smallest valid path, no architecture campaign.

## What was found, and it narrows the job substantially

**Two briefing lines are stale and the work is smaller than they imply.**

`CLAUDE.md` says the open G0A item is open "because **no parser exists**. Do not
write one against markup nobody has inspected." Measured today:

1. **A parser already exists.** `nfl/parse/injury_report.py`, built from
   captured bytes in September. Run against today's capture it returns
   `PASS / REPORT_PARSED`, **259 rows, 2026 week 3, 16 games**, with one
   refusal: `PLAYER_GSIS_UNMAPPED`.
2. **Four of the five sources need no parser at all.** They are nflverse CSVs
   that already carry `team`, `week` and `gsis_id`. For those, attribution to a
   game is a **filter, not a parse**.

So the gap was never "parse the evidence". It was that the capture layer stores
LEAGUE-WIDE artifacts — the manifest says so itself, `source_artifact_scope:
LEAGUE_WIDE`, with the note that "fetching it for one target does not make the
artifact that target's document" — and nothing turned those bytes into this
game's state.

## Artifacts inspected, with observed structure

Every structure below was read out of the stored bytes, not assumed.

| source | state | stored as | observed shape |
|---|---|---|---|
| `depth_charts` | PASS | `depth_charts.9bbba4b5067b5fe6.reduced.csv.gz` | `dt,team,gsis_id,pos_abb,pos_rank`; 2,228 rows, newest-dt slice `2026-09-24T06:01:34Z` |
| `weekly_rosters` | PASS | `weekly_rosters.0efeaede1505ab6e.reduced.csv.gz` | `season,week,team,gsis_id,position`; 8,034 rows |
| `injuries` | PASS | `injuries.b9f0740139d052ff.csv.gz` | 16 cols incl. `report_status`, `report_primary_injury`, `practice_status`; 692 rows |
| `schedules` | PASS | `schedules.9d3644487c6021f2.csv.gz` | `game_id,season,week,gameday,gametime,away_team,home_team,roof,surface,…` |
| `espn_injuries_json` | PASS | `espn_injuries_json.7291a7378c17df0e.json.gz` | 8.7 MB JSON — **not consumed**; the CSVs already carry the spine |
| `official_injury_report` | PASS | `official_injury_report.43040e5a746b8635.html.gz` | nfl.com HTML; parses to 259 week-3 rows across 16 games, players gsis-unmapped |
| `official_inactives` | DEFERRED | — | correctly deferred; not released yet |

## The live 2026 injury feed is now verified, and it was an open question

`nfl/NFLVERSE_INJURY_SOURCE_STATUS_RESOLUTION_01.json` (2026-09-06) closed with:
"injuries_2026.csv remained 404 as of 2026-09-06" and "**whether the restored
pipeline will produce reliable live 2026 updates remains unverified**."

It is now verified for week 3, and by an independent check rather than by the
file agreeing with itself. The owner supplied eight designations from outside
this repository. The captured file reproduces **all eight exactly**, and adds
the injury and the practice participation for each:

| team | player | pos | designation | injury | practice |
|---|---|---|---|---|---|
| ATL | Samson Ebukam | DL | OUT | Hamstring | Did Not Participate |
| ATL | Billy Bowman Jr. | DB | QUESTIONABLE | Achilles | Full Participation |
| GB | Aaron Banks | OL | OUT | Knee | Did Not Participate |
| GB | Zach Bako-Bewele | OL | OUT | Knee | Did Not Participate |
| GB | Jayden Reed | WR | OUT | Neck | Did Not Participate |
| GB | Warren Brinson | DL | OUT | Calf | Did Not Participate |
| GB | Javon Hargrave | DL | QUESTIONABLE | Knee | Limited Participation |
| GB | Anthony Campbell | DL | QUESTIONABLE | Ankle | Limited Participation |

8/8. This does **not** establish point-in-time integrity of the upstream file,
which the resolution record separately warns about; it establishes that the
feed carries correct current week-3 designations and that our vintage of it is
timestamped and hashed on our side.

## What was built

`nfl/truth/game_truth.py` (`game_truth/1.0.0`) — attributes league-wide
vintages to one game. Roughly 250 lines, no new abstraction layer, no
governance change.

It uses the nflverse CSVs for the state and leaves the official report as
corroboration. That ordering is deliberate: the official report is
authoritative but carries **no gsis_id**, so every row of it is
`PLAYER_GSIS_UNMAPPED` against this project's spine — its own parser says so.
Building state from it would require a name crosswalk, and a silent name match
is what this project refuses.

### The rule the records are shaped by

**Absence of a row is never availability.** Default is
`UNKNOWN_NO_DESIGNATION`, and every record carries `availability_basis` of
either `DECLARED_GAME_DESIGNATION` or `NO_DECLARATION_FOUND`.

This is not hypothetical in this game. **A.J. Terrell (ATL, DB) did not
participate in practice and carries an empty `report_status`.** Reading that as
ACTIVE would be inference from omission and would promote a doubtful player to
a certain one. He is `UNKNOWN_NO_DESIGNATION` with his DNP preserved.

## Result

```
ATL: roster 80  on_depth_chart 64  OUT 1  QUESTIONABLE 1  UNKNOWN 78
GB : roster 79  on_depth_chart 61  OUT 4  QUESTIONABLE 2  UNKNOWN 73
unresolved identities: 1
```

**Checkpoint A — attribute ATL/GB records from raw evidence: PASS.**
**Checkpoint B — reconcile into canonical identities: PASS, with one surfaced.**

### The one unresolved identity, named rather than counted

```
gsis_id 00-0008818 — "Marlon Jones", GB, RCB, pos_rank 3
  on the depth chart at the current dt 2026-09-24T06:01:34Z
  NOT on the week-3 weekly roster
  espn_id 4570773
```

Checked against raw bytes: 133 rows spanning 2026-05-20 → 2026-09-24, so it is
a live row and not a stale slice leaking through the newest-dt filter. The
pairing of a modern `espn_id` with an old-format `gsis_id` suggests an upstream
identifier-join artifact. **Not matched by name into anything.** Surfaced.

Every other depth-chart and injury identity for both teams resolves to the
weekly roster: 0 unresolved for ATL, 1 for GB.

## G0A before / after — honest answer: unchanged

Before: every source `eligible: False` for this game. After: **still
`eligible: False`.** The parser does not clear it, and I did not touch
governance to make it pass.

The refusals are independent of attribution:

```
depth_charts / weekly_rosters / injuries / schedules  SOURCE_NOT_AUTHORISED_FOR_KIND
official_injury_report                                BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP
official_inactives                                    CAPTURE_NOT_PASS:DEFERRED
official_transactions                                 CAPTURE_NOT_PASS:BLOCKED
```

`SOURCE_NOT_AUTHORISED_FOR_KIND` is a source-authorization rule: these sources
are not authorised to discharge this obligation kind, regardless of whether
their contents are attributed. `BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP` is about
the *basis* of the capture — a scheduled sweep, not a kickoff-anchored
execution — and is also unrelated to parsing.

Per instruction this is where I stop on G0A. **Governance and the parser are
separate concerns and the parser was never going to clear those codes.**

## Snapshot

`nfl/truth/snapshots/2026_03_ATL_GB/PRE_INACTIVE_20260924T120743Z.json`
— 69,576 bytes, carrying source paths and sha256 for all four vintages,
`official_inactives_ingested: false`, the full 159-player state, and the
unresolved identity.

## Still open

- **Checkpoint C not yet answered**: whether the participation/projection
  pipeline can consume this snapshot. That is the next step, not a finding.
- `official_transactions` has been `BLOCKED` on all 857 captures. Not
  investigated today; it is not on tonight's critical path.
- The official-inactives parse path is next, tested against a prior game's
  PASS artifact rather than discovered at 18:45.

## What needs the owner

Nothing. Continuing to Checkpoint C.


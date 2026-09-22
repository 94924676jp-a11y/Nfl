# Phase 1 root cause — and a retraction of my own claim

Pre-game evidence only. Sealed boundary: `PRE_GAME_BOUNDARY.json`, sealed
2026-09-22T00:14:24Z at HEAD `7db3dec`.

## RETRACTION

Commit `c182e68` asserted:

> `role_prior` incorrectly interprets Tyrone Tracy Jr.'s `KR2` depth-chart
> rank as if it were an `RB2` depth rank.

**That is wrong.** Two measurements refute it.

1. `depth_vintage.daily` already excludes the return groups, and says so in
   its own source: *"`KR`, `PR` and `KOR` are `pos_abb` values in this vendor
   ... `pos not in SKILL` already drops them before any ordering happens.
   Verified on the six persisted blobs: 104 `KR` rows and 81 `PR` rows read,
   0 reaching a rank."*

2. The live production map, read at tonight's cut, returns:

   | Player | production depth |
   |---|---|
   | Cam Skattebo | `('RB', 1)` |
   | Najee Harris | `('RB', 2)` |
   | Devin Singletary | `('RB', 3)` |
   | **Tyrone Tracy Jr.** | **`('RB', 4)`** |

   The engine's depth view of that room is correct. Tracy is RB4.

The `KR2` and `KR3` I saw came from `player_universe`, a different and coarser
depth blob in the **candidate** layer — my code, not the production path. I
asserted a mechanism from one layer and attributed it to another without
checking. The claim is withdrawn.

## What is genuinely wrong, measured

### 1. Cross-group rank leakage exists — as FB, not KR

`run_forecast` builds its rank map with

    for k, v in _dro.value.items():
        dr[k] = v[1]          # keeps the RANK, discards the GROUP v[0]

and `assign_tiers` then groups players by their **model** position. Where the
depth group and the model position disagree, a rank crosses rooms. On
tonight's pool, 3 of 31 ranked skill players disagree:

| Player | model | depth group | rank |
|---|---|---|---|
| **Patrick Ricard** | RB | **FB** | 1 |
| Harrison Mevis | K | PK | 1 |
| Dominic Zvada | K | PK | 1 |

Ricard is the consequential one: `FB1` becomes a **rank-1 anchor inside the
New York running back room** — the lead back's anchor — for a blocking
fullback who took zero week-1 carries. The kicker cases are harmless (one
kicker per room) but are the same defect.

### 2. The production map is offence- AND defence-wide

119 entries including `SLB`, `RCB`, `LDE`, `NT` and the offensive line, plus
`H1` for both punters and `LS1` for both long snappers. None reaches a skill
room, because `assign_tiers` groups by model position. Recorded because a map
that wide is a large surface for exactly the leak above.

### 3. The Tracy/Skattebo inversion is NOT explained by depth

Tracy is correctly RB4 and still received more simulated carries than the
RB1:

| | week-1 measured | d90 simulated carries |
|---|---|---|
| Skattebo | 18 carries, 48.6% share, 61% snaps | 6.14 |
| Tracy | 2 carries, 5.4% share, 3% snaps | 8.09 |

**This remains UNRESOLVED.** What is now excluded: depth contamination, a
wrong corpus, and a wrong role classification — `role_state` independently
placed Skattebo STARTER at 0.61 and Tracy BACKUP at 0.03. The defect is
downstream of tiering, in how the player-level share is formed from the tier
and the trailing snap share, or in the rushing allocator's within-category
split. That is the next trace and it is not finished.

## The repair applied

A typed depth-chart role, `nfl/production/universe/depth_role.py`. A rank may
inform a workload room only when the depth position group resolves to the same
room; otherwise the answer is the explicit state `OFFENSIVE_DEPTH_UNKNOWN`
with a named reason, never a borrowed rank and never a silent absence.
Special-teams standing is returned on its own axis, so a player is `KR2` and
`OFFENSIVE_DEPTH_UNKNOWN` simultaneously without either contaminating the
other.

Wired into `player_universe` (new `offensive_depth_rank`,
`offensive_depth_state`, `special_teams_role` fields) and `role_state` (the
conflict check and the room-competition ranks now use the typed accessor).

`guard_rank_map` implements the same filter over the exact map shape
production builds, returning the safe map plus every refusal by name.

**It is NOT wired into `run_forecast`.** That is an accepted config change and
the governance rule requires a baseline, one change, a run, and a comparison.
Wiring it would also change `d90d80c0b4a7f95e`, which is frozen. The function
is tested and ready; the wiring is a separate, measured step.

## Blockers

- The Tracy inversion's true cause is not yet located.
- Phases 3 and 4 (global underprojection decomposition, TE room audit) need
  historical PIT work against football data, not started.

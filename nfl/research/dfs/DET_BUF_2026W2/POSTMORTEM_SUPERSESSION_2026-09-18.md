# Supersession: two findings in POSTMORTEM.md were wrong, and one badly

`POSTMORTEM.md` is **not edited**. It stands as what was believed on
2026-09-17. This file records what the 2026-09-18 correction pass established
against it.

## 1. The kicker finding was an artefact, and it inverted

**What the postmortem said.** The delivered portfolio rostered Tyler Bass and
Jake Bates at 22.5% each, against a `P(optimal)` the model could not produce —
read at the time as exposure to players who did not belong in optimal lineups.

**What is true.** `P(optimal)` was not low for them. It was **UNDEFINED**: the
optimal-world solve ran over a universe that excluded kickers, so the two
numbers set side by side were computed over different sets of players. That is
the `DFS_METRIC_COMPARISON_UNIVERSE_MISMATCH` the universe contract now
refuses.

Measured once the kickers were resolved by player id and admitted
(`OPTIMAL_WORLDS_v3.json`, same 8,000 sealed worlds):

| player | p_optimal | p_optimal_captain |
|---|---:|---:|
| Jake Bates | **0.1996** | 0.0041 |
| Tyler Bass | **0.1856** | 0.0032 |

A kicker belongs in roughly **one optimal lineup in five** on this slate. A
22.5% exposure against a 19-20% optimal frequency is not a defect — it is
close to the model's own answer. **The postmortem's kicker row should not be
cited.**

## 2. The mechanism was misdiagnosed, including by the review

Both the postmortem and the 2026-09-18 repo review recorded this as "the
kicking layer is team-keyed, so a kicker can only be matched by (team,
position)".

**The kicking layer was player-keyed all along.** Its `row_ids` are
`['00-0036162', '00-0039172']` — gsis_ids — and `row_teams` is a descriptive
column beside the key, not the key. The postgame capture confirms both ids
independently: nflverse gives Tyler Bass `00-0036162` and Jake Bates
`00-0039172`.

What was actually missing is a **name**. `frozen_board_names.json` publishes 29
offensive gsis_ids and omits these two, so every name-based join failed and
(team, position) was the only thing left to reach for. The defect was a
publication gap in a name map, and the positional join was its symptom.

The repair is therefore upstream and small: `kicker_identity.resolve` matches
those ids against the governed pre-seal roster vintage
`weekly_rosters.698183b8ab2a09fa`. **The positional join is still refused** —
`KICKER_IDENTITY_MUST_BE_PLAYER_KEYED` — there is simply no longer any reason
to reach for it.

## 3. What did NOT change

The role-state finding stands. Ray Davis at 72.5% exposure and 15% captain
against a `p_optimal` of 0.266 and `p_optimal_captain` of 0.043 in v3 is still
a `ROLE_STATE_CONCERN` player carried far above the model's own frequency, and
`KNOWN_MODEL_DEFECT_AMPLIFIED_BY_OPTIMIZER` still describes what happened.
Correcting a kicker comparison does not retire that.

## 4. The site-legality correction, measured

Separately and on the same 8,000 worlds, the both-teams rule moved from a
post-hoc field into the DP state (`OPTIMAL_WORLDS_v2.json`). On the 28-player
universe it changed the optimum in **57 worlds of 8,000 (0.71%)** — every one
of which previously carried a lineup that could not have been entered — and
moved the mean optimal score by −0.015. The largest `p_optimal` move was
0.0010 and the largest `p_optimal_captain` move 0.0001.

**The defect was real and its numerical effect on this slate was small.** Both
halves of that sentence are the finding.

## Artifact lineage

| artifact | what it is |
|---|---|
| `OPTIMAL_WORLDS.json` | v1. History. Not lawful: no team rule, no kickers. Do not cite as a site-optimal result. |
| `OPTIMAL_WORLDS_v2.json` | + site legality in the DP state. Same 28-player universe. |
| `OPTIMAL_WORLDS_v3.json` | + both kickers, resolved by gsis_id. **Current.** |
| `OPTIMAL_WORLDS_LEGALITY_DELTA.json` | v1 → v2, per player |
| `OPTIMAL_WORLDS_KICKER_DELTA.json` | v2 → v3, per player |
| `DFS_UNIVERSE_CONTRACT.json` | the four universes, per player, with every exclusion reason |

Nothing was fitted to DET @ BUF. Every number above is a property of the
sealed pregame board and the contest file.

**V2 NOT YET EARNED**

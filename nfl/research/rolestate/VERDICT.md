# The role-state cap, measured — and a recorded negative verdict that does not survive it

**Status: MEASURED. No production change is made by this work.** `PROJECTION_SYSTEM_STATE` stays
`NOT_VALIDATED`. What changes is that one cell of the scoreboard — out-of-sample ranking skill against
a current-season-only baseline — now reads the opposite of what the repository recorded, and the
reason is a defect in the evaluation harness rather than a change to the model.

Run it with `python3.12 nfl/research/rolestate/study.py`. Artifacts:
`nfl/research/rolestate/ROLE_STATE_STUDY.json`, and the reconstruction itself in
`nfl/tools/role_state_history.py`.

## What was not being measured

`forward_chain.historical_band` said so in its own docstring: *"Role state is not reconstructible for
a historical week ... the evidence CEILING cannot be applied here ... the chain does NOT test the
appearance adjustment or the starter cap."* So the mechanism that stops an injury-replacement share
outliving the injury — the thing built after Drew Lock projected 17.88 DK points on snaps he held only
because Sam Darnold was hurt — was asserted in production and measured nowhere.

A second, quieter gap sat beside it. `historical_band` is evaluated at `through = season - 1`, which
makes the band **season-constant**: a player promoted in week 4 carries last season's band through
week 18, and a player who lost his job keeps his. **Production does not do this.** The live path
rebuilds role state weekly. So the chain was not measuring the configuration production runs.

## Why ROLE_HISTORY could not simply be read, which is the trap

`ROLE_HISTORY` already carries `depth`, `depth_rank` and `transition` per season-week-player, and its
rank is position-scoped inside the club-week — exactly the shape wanted. It is still unusable as a
pregame state, because `role_history.build` ranks players **by that week's own usage measure**. The
rank for week W is a description of what happened in week W. Feeding it in as a week-W input is direct
outcome leakage under a name that looks completely innocent.

So the rank is rebuilt from prior weeks only, and the claim is proved rather than asserted:
`assert_no_leakage` rebuilds the whole state from a panel with the scored week **and every later
week deleted** and requires every band and rank to be identical. It is run at four season-weeks in
the test suite and passes at all of them, over 387–401 players each.

## The arms, declared before any ran

| arm | band | cap | availability |
|---|---|---|---|
| `CURRENT_SEASON_ONLY` | — | — | no multi-season prior at all; the thing V1 replaced |
| `SEASON_CONSTANT` | one per season, from the previous season | none | what the chain did |
| `WEEKLY_NO_CAP` | weekly, from prior weeks | none | isolates "update weekly" from "cap" |
| `WEEKLY_CAPPED_PREGAME` | weekly | pregame depth rank | **production's mechanism minus the injury report** |
| `WEEKLY_CAPPED_ORACLE` | weekly | pregame depth rank | **ORACLE** — who actually appeared is supplied |

Primary outcome preregistered as within-slate-week Spearman rank correlation with a **week-blocked**
standard error. Selection 2023–2025 (42 weeks), confirmation 2022 (14 weeks). 2021 is void: the panel
begins there, so no prior season exists and no arm can differ.

| arm | ρ selection | ρ confirmation | MAE selection | level selection |
|---|---|---|---|---|
| `CURRENT_SEASON_ONLY` | 0.4780 | 0.4541 | 4.830 | 1.024 |
| `SEASON_CONSTANT` | 0.4417 | 0.4173 | 4.943 | 1.010 |
| `WEEKLY_NO_CAP` | 0.4889 | 0.4737 | 4.755 | 0.982 |
| **`WEEKLY_CAPPED_PREGAME`** | **0.4931** | **0.4877** | **4.744** | 0.978 |
| `WEEKLY_CAPPED_ORACLE` *(oracle)* | 0.5635 | 0.5549 | 4.411 | 0.989 |

## The decomposition

Paired, week-blocked, against `SEASON_CONSTANT`:

| step | Δρ selection | z | Δρ confirmation | z |
|---|---|---|---|---|
| update the band weekly | +0.0472 | 16.5 | +0.0564 | 10.1 |
| …and cap it by depth rank | +0.0515 | 12.1 | +0.0704 | 8.1 |
| …and know who is out *(oracle)* | +0.1218 | 22.0 | +0.1376 | 18.3 |

Read as increments: **updating weekly is worth +0.047 to +0.056**, the **cap adds a further +0.004 to
+0.014**, and **knowing who is out adds +0.067 to +0.072 more than everything else combined.** MAE
improves at every step, 4.943 → 4.744 → 4.411, and calibration level stays within 0.978–0.989 of
nominal against 1.010 for the season-constant arm.

## The finding that matters, and it reverses something recorded

`FORWARD_CHAIN_VERDICT.md` concluded that the multi-season prior **loses** to `CURRENT_SEASON_ONLY`
on ranking, by −0.0181 ρ from week 5, and the GAP_STATUS confidence line read *"No out-of-sample
ranking skill above a current-season baseline has been demonstrated."* Paired against
`CURRENT_SEASON_ONLY` in this harness:

| arm | Δρ selection | z | Δρ confirmation | z | ΔMAE selection |
|---|---|---|---|---|---|
| `SEASON_CONSTANT` | **−0.0364** | −21.7 | **−0.0369** | −15.7 | +0.113 |
| `WEEKLY_NO_CAP` | +0.0108 | 3.1 | +0.0196 | 3.2 | −0.075 |
| **`WEEKLY_CAPPED_PREGAME`** | **+0.0151** | **3.2** | **+0.0336** | **3.7** | **−0.085** |
| `WEEKLY_CAPPED_ORACLE` *(oracle)* | +0.0854 | 14.6 | +0.1007 | 13.7 | −0.419 |

The `SEASON_CONSTANT` row **reproduces the verdict**: same sign, same direction, larger magnitude. The
`WEEKLY_CAPPED_PREGAME` row **flips it**, on both splits, on ρ and on MAE, with z above 2.6
everywhere.

**So the recorded negative verdict measured a configuration production does not run.** It is not
superseded because the model improved — nothing about the model changed here. It is superseded because
the harness was handing V1 a season-constant role band while the live path rebuilds one weekly, and
the size of that harness defect (−0.036 ρ) is twice the gap the verdict rested on.

## What this does and does not license

**It does** mean out-of-sample ranking skill above a current-season-only baseline is now demonstrated,
forward-chained, point-in-time, on selection and confirmation seasons, on two metrics that agree.
That sentence in GAP_STATUS is corrected.

**It does not** validate the projection system, and `PROJECTION_SYSTEM_STATE` stays `NOT_VALIDATED`.
One cell of a three-part scoreboard moved. Nothing here tests economic usefulness — no edge, no
closing line, no realised contest result — and nothing here tests calibration beyond a level ratio.
The margin is small: +0.015 to +0.034 ρ on a base of 0.48. Confirmation is 14 weeks of one season
that has already been read for other questions, so it is not an untouched holdout, and five arms were
compared with no multiplicity correction. A single demonstrated cell is not a validated system, and
the difference between those two is the whole reason this project keeps the states separate.

## The oracle arm, and why it is the most valuable number here

`WEEKLY_CAPPED_ORACLE` is fed the set of players who actually appeared in the scored week, so the cap
falls on the right player. **That is an oracle condition** — the same kind as feeding a simulator the
actual batting order — and it must never be quoted as live performance. Its value is the *gap*: the
difference between it and `WEEKLY_CAPPED_PREGAME` is **+0.067 to +0.072 ρ and −0.33 MAE**, and that
gap is precisely what an injury report buys.

That is larger than every other effect measured this session put together, including the whole
shrinkage study (+0.026). **Official inactives and injury reports are therefore the highest-value
outstanding item in the project, by measurement rather than by intuition** — task A7 and OUT-038,
which were both sitting below research work worth a quarter as much.

The refusals enforce the separation: asking for the oracle arm without an appearance set FAILs
(`ORACLE_ARM_WITHOUT_ORACLE`) rather than silently running pregame, and handing an appearance set to
the pregame arm FAILs (`PREGAME_ARM_GIVEN_THE_OUTCOME`) rather than ignoring it.

## Limits

- The pregame arm cannot know who is out, and this is **not** proxied by who played — that is the
  oracle arm, kept separate. No injury or inactive report exists in this checkout for a past Sunday
  (OUT-038).
- The pregame depth ordering uses a **declared** 3-week lookback, matching `role_history`'s own
  transition lookback. A single prior week would read one rested starter as a demotion. It is not
  fitted, and a test confirms ranks do not move when weeks outside the window are deleted.
- The band thresholds (0.25 / 0.18 / 0.10 / 0.04 share of club) are the live module's declared
  thresholds, reused rather than re-fitted here.
- Nothing is adopted. Making the chain use a weekly capped band is a change to the evaluation
  harness, and changing the harness and production in one commit is forbidden; it goes on its own
  commit with the baseline snapshotted.

# Pre-registration — TD1, touchdown / red-zone oracle decomposition

Written 2026-09-08, **before any evaluation result was computed or inspected**.
Start HEAD `2ec21cd`.

**EXPLORATORY.** 2022–2025 are heavily mined. Diagnosis and recoverability
characterisation only, never confirmation, never promotion.

## 1. Provenance audit — done first, results fixed here

Source nflverse pbp 2020–2025 REG, CC BY 4.0. No FTN, no PFR-restricted field,
no market, no DFS, no 2026 data.

**Named exclusions, measured (2020–2025):**

| exclusion | plays | why |
|---|---|---|
| `no_play` | 26,592 | penalty-nullified; never an opportunity |
| `yardline_100` NULL | 4,806 | **measured composition (2024): `no_play` 2,007 and blank play_type 1,371 — never a live scrimmage play.** Excluded, never coerced to 0, because 0 reads as the 1-yard line, i.e. maximum red-zone opportunity |
| kneel / spike | 2,931 | not competitive opportunities |
| two-point attempts | 794 | matches the participation and RC1 joins |
| defensive TD (`td_team != posteam`) | 388 | not an offensive player TD |
| recovery / blocked-kick TD | 45 | **measured: end-zone fumble recoveries and blocked punts/FGs.** Neither pass, rush nor return TD; excluded from player TD and counted in a named bucket |

**`qb_scramble` without `rush_attempt`: 289 — all `play_type == no_play`**,
penalty-nullified, and therefore already excluded. Scrambles are charged to the
**rusher** (4,091 of 4,380 carry `rusher_player_id`, **0 carry
`passer_player_id`**), preserving the project's standing warning.

**Designed rush and scramble are kept distinct** for QB rushing, as §3 requires.

## 2. Primitives, defined exactly

Receiving: `targets`, `rz_targets` (`yardline_100 <= 20`), `in10_targets`,
`in5_targets`, `g2g_targets` (`goal_to_go == 1`), `rec_td` (`pass_touchdown` on
a play credited to the receiver).

Rushing: `carries`, `rz_carries`, `in10_carries`, `in5_carries`,
`g2g_carries`, `rush_td`, split into `designed_rushes` and `scrambles`.

**End-zone targets are NOT defined.** `yardline_100` gives the line of scrimmage,
not the target's depth, so an "end-zone target" cannot be reconstructed from
these fields. Per §3.2 it is marked **unavailable** rather than approximated by
a proxy that would silently mean something else.

## 3. The decomposition

For each of receiving TD and rushing TD, the exact identity

    TD  =  (TeamOpp x Share) x [ Z x k_rz  +  (1 - Z) x k_nrz ]

with four components:

| id | component | definition |
|---|---|---|
| `V` | team scoring environment | the team-game's opportunity volume (team targets / team carries) |
| `S` | player opportunity share | player opportunities / team opportunities |
| `Z` | red-zone allocation | player red-zone opportunities / player opportunities |
| `K` | conversion | the pair (`k_rz`, `k_nrz`) — TD per red-zone opportunity and TD per non-red-zone opportunity |

The identity is exact including the degenerate cases: with zero opportunities
the product is zero; with `Z = 0` the `k_rz` term vanishes; with `Z = 1` the
`k_nrz` term vanishes. **All four oracled must reproduce the realised TD count
exactly**, and that is asserted rather than assumed.

**Attribution: exact Shapley over the 2⁴ = 16 coalitions**, order-invariant, on
the CRPS-reduction scale. Efficiency (parts summing to the grand coalition) is
asserted.

## 4. Frame and scoring

Evaluation seasons **2022–2025**, walk-forward, fitted on strictly prior seasons.
Positions WR/TE/RB for receiving; RB/QB/WR/TE for rushing. Appeared player-games
with at least one prior appeared game. Chronology by strict ordinal prefix cut.

Baseline: draw-based, 2,000 draws, prior-only, seed 20260908, with the same
history/pool shrinkage constant `K = 4` inherited from Stage 2's cohort boundary.

**Scoring: CRPS (primary), MAE, RMSE, bias, Brier score for `TD >= 1`, and
coverage.** TD counts are small integers, so **Brier on `P(TD >= 1)` is reported
alongside CRPS** — a count metric alone would hide whether the probability that
actually matters is calibrated. **Bootstrap: 1,000 resamples clustered by
`game_id`.**

## 5. Prohibitions

- **A large oracle share does not imply modelability.** Oracle opportunity and
  recoverable signal are reported as separate quantities and never conflated.
- No promotion language without a predeclared margin and a TOST; none is
  predeclared, so none may be used.
- Nothing is promoted. P4C, ABC_MPR, Stage 2 `ewma_hl2`, G0A and NFL-1 are
  untouched.
- No threshold, frame or metric may change after a result is seen.

**Seed 20260908, fixed now.**

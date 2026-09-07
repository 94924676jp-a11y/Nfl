# P4 pre-declaration — written before any P4 model was fitted

Written 2026-09-07, after the field-classification audit in §0 and before any
plays / pass-rate / dropback result existed. Departures are labelled where they
occur; the original text stays.

## 0. Field classification, fixed before use

Every candidate field in `schedules` and `pbp`, classified per the directive's
data-integrity requirement:

| field | class | verdict |
|---|---|---|
| `posteam`, `defteam`, `week`, `season`, `game_id` | observed primitive | **safe** |
| `play_type`, `qb_dropback`, `pass_attempt`, `rush_attempt`, `sack`, `qb_scramble` | observed primitive | **safe** (denominators documented below) |
| `down`, `ydstogo`, `yardline_100`, `score_differential`, `game_seconds_remaining`, `half_seconds_remaining`, timeouts | observed play state | **safe** as inputs to a self-fitted model over PAST games |
| `home_coach`, `away_coach` | pregame-knowable | **safe**, with the R1 caveat that it is a final-file value |
| `home_rest`, `away_rest`, `div_game`, `roof`, `surface` | schedule structure | **safe** |
| `home_qb_id`, `away_qb_id` | the QB who actually started | **conditionally safe** — see §3 |
| `spread_line`, `total_line` | **market-derived** | **FORBIDDEN** |
| `result`, `total`, `home_score`, `away_score` | postgame outcome | **FORBIDDEN as a feature** |
| `temp`, `wind` | **observed** weather, no forecast analogue | **FORBIDDEN** |
| `xpass`, `pass_oe`, `wp`, `epa`, `cpoe` (nflfastR model columns) | model-derived, fitting window undocumented | **QUARANTINED** — see §4 |

## 1. Target definitions, with denominators documented

All at team-game level, regular season only. Denominator ambiguity is the defect
P1 already found once (`pass_attempt` silently includes sacks), so each is
stated explicitly.

| target | definition |
|---|---|
| `plays` | offensive plays with a `posteam`, excluding two-point attempts |
| `dropbacks` | `qb_dropback == 1` — **includes sacks and scrambles** |
| `pass_att_ex_sacks` | `pass_attempt == 1 AND sack == 0` |
| `sacks` | `sack == 1` |
| `scrambles` | `qb_scramble == 1`, charged to the **rusher** (P1 defect 2) |
| `designed_qb_rush` | `rush_attempt == 1 AND qb_scramble == 0 AND rusher is the game's QB` |
| `nonqb_rush_att` | `rush_attempt == 1` minus scrambles minus designed QB rushes |
| `pass_rate` | `dropbacks / plays` |
| `neutral_pass_rate` | dropbacks / plays restricted to **`abs(score_differential) <= 8`, quarters 1–3, `down <= 2`** |
| `early_down_pass_rate` | dropbacks / plays on `down in (1, 2)` |
| `sec_per_play` | mean gap between consecutive `game_seconds_remaining` for that team's plays, restricted to the same neutral filter |

## 2. Baselines, applied to every target

league mean · team expanding mean · last game · rolling-3 · rolling-5 · EWMA
(half-life 3). For pass/run targets additionally: previous-season team mean, and
a play-caller (head coach) prior computed on prior seasons only.

No model is promoted unless it materially beats these, judged by a
team-block bootstrap interval excluding zero.

## 3. The QB-identity decision, made now

`home_qb_id` / `away_qb_id` record who actually started. For most games that is
announced days ahead and is genuinely pregame; for a game-time decision it is
not. Rather than assume, this is split into two arms and both are reported:

- **Arm A (strict):** prior-game QB identity only; a "QB differs from last game"
  flag cannot be computed for the current game.
- **Arm B (announced-starter):** current-game QB identity is allowed, labelled
  as assuming the starter is known pregame.

Arm B's incremental value over Arm A is reported as the value of knowing the
starter, not as a free feature.

## 4. PROE / xPass — reconstruction plan, fixed before fitting

nflfastR's `xpass` and `pass_oe` are quarantined: their fitting window is not
documented in the artifact and may include the seasons being evaluated. They are
not used.

Instead xPass is **rebuilt**: a logistic model of `P(dropback)` on play state
(`down`, `ydstogo`, `yardline_100`, `score_differential`, `game_seconds_remaining`,
`half`, timeouts), **fitted only on seasons strictly before the evaluation
season**, and applied to past games to compute each team-game's realized PROE.
PROE for game *t* is then used only as a feature for game *t+1* or later.

If that reconstruction cannot be shown leakage-safe, the return is
**PROE UNAVAILABLE FOR P4 — PROVENANCE/LEAKAGE NOT SUFFICIENT**, and no
nflfastR column is substituted.

## 5. Evaluation

Strict chronological walk-forward. Training 2016–(eval−1); evaluation seasons
2022, 2023, 2024, 2025. No random splits. No tuning on the evaluation season.
Team-block bootstrap, 400 resamples, seed 20260907 — the resampling unit is the
**team**, because a team's games are not independent.

## 6. What would count as a negative result

If a target's best model does not beat the best simple baseline by more than the
bootstrap interval on a majority of evaluation seasons, the return says that
target is **not usefully forecastable beyond shrinkage**, in those words. Given
P1 measured team dropbacks at r ≈ 0.10–0.22 from QB history, a negative result
on at least one target is a live possibility and is not to be avoided.

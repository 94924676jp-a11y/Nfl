# P1 pre-declaration — written BEFORE any result was computed

Timestamp of writing: 2026-09-07, immediately after `build_panel.py` was
launched and before its output was read. Nothing below was chosen after seeing a
number. Where I later depart from this, the departure is labelled and the
original text stays.

## Frame

Seasons 2020–2025, regular season only. 2026 is excluded entirely: the directive
forbids consuming any 2026 outcome, and the live capture track holds 2026
artifacts that must not be touched.

## Targets (realised in game t)

| Target | Definition | Denominator |
|---|---|---|
| `snap_share` | `offense_snaps / team offensive snaps` | snap_counts `offense_pct` |
| `rpr` | player pass-play participations / team dropbacks | participation `offense_players` on `qb_dropback==1` |
| `target_share` | player targets / team pass attempts | pbp |
| `carry_share` | player carries / team rush attempts | pbp |
| `rz_carry_share` | player red-zone carries / team red-zone rushes | pbp, `yardline_100 <= 20` |
| `team_dropbacks` | team dropbacks in the game | pbp (QB target) |
| `pass_att_as_passer` | QB pass attempts | pbp |

`air_yards_share` is computed but treated as SUSPECT until its provenance is
checked; W4 already found `ngs_air_yards` unusable and `route` mis-named.

## Chronology rule, stated before any feature is written

A feature for the row at `(season s, week w)` may read only rows with
`(season, week)` strictly less than `(s, w)` in the ordering
`season * 100 + week`. No same-game column, no future week, no season-level
aggregate that spans the target week. Cross-season carryover is permitted only
as an explicitly named prior-season feature.

I will test this rather than assert it: a leakage probe shuffles each player's
target values within player and re-runs the feature builder; any baseline whose
error does not degrade is reading something it should not.

## Baselines, in the order the directive lists them

1. pooled positional prior (position mean over all prior games)
2. season-to-date mean (this player, this season, weeks < w)
3. previous game (lag 1)
4. trailing 3-game mean
5. trailing 5-game mean
6. EWMA, half-life 3 games
7. shrinkage: `(n*player_mean + k*prior) / (n + k)`, k chosen on training
   seasons only

## Evaluation

Walk-forward by season: train on all seasons strictly before the evaluation
season, evaluate on the evaluation season. Evaluation seasons 2022–2025. No
random shuffling of games. Metrics: MAE, RMSE, Pearson r, R² against the
pooled-prior baseline, n player-games.

Clustering: standard errors on any difference between models are computed by
block bootstrap over PLAYERS, not over player-games, because a player's games
are not independent. 1000 resamples, seed 20260907.

## Subgroups, declared now

- position: WR, TE, RB, QB
- season
- stable role vs role change, where role change is declared as
  `|snap_share(t-1) - mean snap_share(t-2..t-4)| > 0.20`
- starter vs backup: prior-game snap_share >= 0.50 vs < 0.50
- limited history: fewer than 4 prior games in the panel

## What would count as a negative result

If the best model for a target does not beat "previous game" by more than the
block-bootstrap interval on the evaluation seasons, I will report that the
target is not usefully forecastable beyond persistence, and say so in those
words rather than finding a subgroup where it looks better.

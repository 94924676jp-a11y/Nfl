#!/usr/bin/env python3.12
"""The baselines V1 has to beat. Each one is trivial to compute and hard to beat by accident.

WHY THESE SEVEN. A model is only worth its complexity if it beats the cheap thing. The list is the
owner's, and each entry is a different cheap thing:

  LAST_GAME            pure recency. Beats a lot of models and is one number.
  MEAN_3_GAME          recency with noise reduction.
  SEASON_MEAN          this season's form, all of it.
  CAREER_MEAN          the player's own long-run level, ignoring role entirely.
  POSITIONAL_MEAN      no player information at all. The floor: anything that cannot beat this has
                       learned nothing about players.
  VEGAS_ONLY           the club's implied total times the position's average share of club scoring.
                       No player-specific information beyond his position and club. This is the one
                       that matters most, because it is free and public.
  EXTERNAL_BOARD       an archived third-party projection. NOT AVAILABLE historically in this
                       checkout -- only a current-week export is held -- so it is reported as
                       unavailable rather than approximated by the current file, which would leak
                       today's information into a 2023 evaluation.

EVERY BASELINE IS PREGAME. Each reads only weeks strictly before the scored week, the same boundary
the model gets. A baseline with hindsight is not a baseline, it is a trick.
"""
from __future__ import annotations

import collections
import statistics

NAMES = ('LAST_GAME', 'MEAN_3_GAME', 'SEASON_MEAN', 'CAREER_MEAN', 'POSITIONAL_MEAN',
         'VEGAS_ONLY', 'EXTERNAL_BOARD')

UNAVAILABLE = {
    'EXTERNAL_BOARD': ('no ARCHIVED third-party projections for past weeks are held; only a '
                       'current-week export. Using it would leak present information into a past '
                       'evaluation, so the baseline is reported unavailable.'),
}


def build_history(player_game_rows):
    """player -> ordered [(season, week, dk_points)] and position -> pooled values."""
    hist = collections.defaultdict(list)
    for r in player_game_rows:
        hist[r['player_id']].append((r['season'], int(r['week']),
                                     r.get('dk_points_current_rules')))
    for v in hist.values():
        v.sort()
    return hist


def predict(name, *, player_id, position, season, week, hist, pos_pool, club_implied,
            pos_share_of_club_points):
    """One baseline's prediction, or None where it has nothing to say."""
    prior = [p for (s, w, p) in hist.get(player_id, ())
             if (s < season or (s == season and w < week)) and p is not None]
    this_season = [p for (s, w, p) in hist.get(player_id, ())
                   if s == season and w < week and p is not None]
    if name == 'LAST_GAME':
        return prior[-1] if prior else None
    if name == 'MEAN_3_GAME':
        return statistics.fmean(prior[-3:]) if prior else None
    if name == 'SEASON_MEAN':
        return statistics.fmean(this_season) if this_season else None
    if name == 'CAREER_MEAN':
        return statistics.fmean(prior) if prior else None
    if name == 'POSITIONAL_MEAN':
        v = pos_pool.get(position)
        return v if v is not None else None
    if name == 'VEGAS_ONLY':
        if club_implied is None:
            return None
        sh = pos_share_of_club_points.get(position)
        return club_implied * sh if sh is not None else None
    if name == 'EXTERNAL_BOARD':
        return None
    raise ValueError(f'unknown baseline {name}')


def positional_pool(player_game_rows, pos_of, through_season, through_week=None):
    """Mean DK points by position over everything strictly before the boundary."""
    acc = collections.defaultdict(list)
    for r in player_game_rows:
        s, w = r['season'], int(r['week'])
        if s > through_season or (through_week is not None and s == through_season
                                 and w >= through_week):
            continue
        p = pos_of.get(r['player_id'])
        if p and r.get('dk_points_current_rules') is not None:
            acc[p].append(r['dk_points_current_rules'])
    return {p: round(statistics.fmean(v), 5) for p, v in acc.items() if v}


def positional_share_of_club_points(player_game_rows, pos_of, through_season,
                                    club_implied_by_cw):
    """A position's mean DK points as a fraction of its club's implied total.

    This is what makes VEGAS_ONLY a real baseline rather than a constant: it converts a club's
    market expectation into a per-player number using only the player's position.
    """
    per = collections.defaultdict(list)
    by_cw = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in player_game_rows:
        if r['season'] > through_season:
            continue
        p = pos_of.get(r['player_id'])
        if p and r.get('dk_points_current_rules') is not None:
            by_cw[(r['season'], int(r['week']), r['club'])][p].append(
                r['dk_points_current_rules'])
    for k, d in by_cw.items():
        imp = club_implied_by_cw.get(k)
        if not imp:
            continue
        for p, vals in d.items():
            # A SHARE, not a level. The first version returned the mean player's DK points and was
            # named as though it returned a share, which would have made VEGAS_ONLY a constant that
            # ignored the market entirely -- the one thing that baseline exists to use.
            per[p].append(statistics.fmean(vals) / imp)
    return {p: round(statistics.fmean(v), 6) for p, v in per.items() if v}


def club_implied_index(team_game_rows):
    """(season, week, club) -> implied total, from the warehouse team-game table."""
    out = {}
    for r in team_game_rows:
        if r.get('implied_total') is not None:
            out[(r['season'], int(r['week']), r['club'])] = r['implied_total']
    return out

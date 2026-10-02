#!/usr/bin/env python3.12
"""A club's expected points from football evidence only: no line, no spread, no implied total.

WHY. The incumbent projection lets the sportsbook in at three places -- the volume layer's market
response, the club touchdown pool (regressed on the implied total) and the DST points-allowed centre
(the opponent's implied total) -- and the joint simulator draws every scoring world around the total
line and the spread. The owner's rule is that no sportsbook price may enter proprietary prediction.
A football-only arm therefore needs a scoring centre measured from what clubs actually did, and a
dispersion measured around THAT centre, not around the market's.

WHAT IT IS, AND WHAT IT IS NOT. A club's expected points for week W of season S is the same blend
the volume layer already uses for plays and attempts: the current season's points per game through
week W-1, weighted by its games, plus the prior season's points per game weighted by
TEAM_VOLUME_PRIOR_GAMES declared pseudo-games. No new coefficient. It is an OWN-OFFENCE centre: it
carries no opponent adjustment (that is NOT_MODELLED by owner instruction, item 9) and no weather.
Home field enters as one measured number: the mean of the actual margin minus the centre's margin
over every fitted game, which is the home-field bias the own-offence centre leaves behind.

RESIDUALS ARE MEASURED AROUND THIS CENTRE. The total and margin residual sets are
actual - football centre over seasons <= THROUGH_SEASON with the centre built forward-only (weeks
before W, prior season), so no realised outcome leaks into its own expectation. They are wider than
the market-centred residuals in SHARED_STATE.json, as they must be: the market knows more. The DST
layer gets points-allowed residuals around the opponent's football centre the same way.

The module never reads total_line, club_spread, implied_total or moneyline; a test asserts that by
AST, and a second test asserts the output does not move when every line in the table is perturbed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome, Cause  # noqa: E402

TG = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT = _REPO / 'nfl/sim/FOOTBALL_POINTS.json'
PRIOR_GAMES = 4.0          # == proj_v1.TEAM_VOLUME_PRIOR_GAMES, the declared pseudo-game weight
THROUGH_SEASON = 2025      # == proj_v1.THROUGH_SEASON: nothing after this season is fitted
FIRST_FIT_SEASON = 2001    # the first season with a prior season behind it
MIN_GAMES = 1000
FIELDS_FORBIDDEN = ('total_line', 'club_spread', 'implied_total', 'opponent_implied_total',
                    'moneyline', 'spread_line_raw')


def _rows():
    art = json.loads(TG.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    return [r for r in rows if r.get('points') is not None and r.get('season') is not None
            and r.get('week') is not None and r.get('club')]


def club_points_table(rows):
    """{club: {season: {week: points}}} from the club-game rows, points only."""
    t = {}
    for r in rows:
        t.setdefault(r['club'], {}).setdefault(int(r['season']), {})[int(r['week'])] = float(r['points'])
    return t


def expected_points(table, club, season, week):
    """Own-offence centre for (club, season, week), forward-only. None when no history at all."""
    cur = {w: p for w, p in (table.get(club, {}).get(season) or {}).items() if w < week}
    prv = table.get(club, {}).get(season - 1) or {}
    n_cur = len(cur)
    per_cur = (sum(cur.values()) / n_cur) if n_cur else None
    per_prv = (sum(prv.values()) / len(prv)) if prv else None
    if per_cur is None and per_prv is None:
        return None, {'state': 'NO_SCORING_HISTORY'}
    if per_prv is None:
        return per_cur, {'state': 'CURRENT_ONLY', 'n_cur': n_cur}
    if per_cur is None:
        return per_prv, {'state': 'PRIOR_ONLY', 'n_prv': len(prv)}
    wc, wp = float(n_cur), PRIOR_GAMES
    return (per_cur * wc + per_prv * wp) / (wc + wp), {'state': 'BLENDED', 'n_cur': n_cur, 'n_prv': len(prv),
                                                        'w_cur': wc, 'w_prv': wp}


def build() -> Outcome:
    if not TG.exists():
        return Outcome.blocked('FOOTBALL_POINTS_NO_TEAM_GAME', 'team-game table missing', cause=Cause.DATA)
    rows = _rows()
    table = club_points_table(rows)
    games = {}
    for r in rows:
        games.setdefault(r['game_id'], {})[r['club']] = r
    total_res, margin_res, hfa_terms, pa_res, keep = [], [], [], [], 0
    td_obs = []
    for gid, sides in games.items():
        if len(sides) != 2:
            continue
        a, b = sides.values()
        if a.get('is_home') is None or int(a['season']) < FIRST_FIT_SEASON or int(a['season']) > THROUGH_SEASON:
            continue
        home = a if a['is_home'] else b
        away = b if a['is_home'] else a
        eh, _ = expected_points(table, home['club'], int(home['season']), int(home['week']))
        ea, _ = expected_points(table, away['club'], int(away['season']), int(away['week']))
        if eh is None or ea is None:
            continue
        keep += 1
        hfa_terms.append((home['points'] - away['points']) - (eh - ea))
        total_res.append((home['points'] + away['points']) - (eh + ea))
        margin_res.append((home['points'] - away['points']) - (eh - ea))   # home-field is carried in the set's mean
        for side, opp_e in ((home, ea), (away, eh)):
            if isinstance(side.get('points_allowed'), (int, float)):
                pa_res.append(float(side['points_allowed']) - opp_e)
            if isinstance(side.get('offensive_td'), (int, float)):   # a sentinel string is not a count
                e_own = eh if side is home else ea
                td_obs.append((e_own, float(side['offensive_td'])))
    if keep < MIN_GAMES:
        return Outcome.blocked('FOOTBALL_POINTS_TOO_FEW_GAMES', f'{keep} games', cause=Cause.DATA, need=MIN_GAMES)
    # touchdown pool regressor: offensive TD on the FOOTBALL expected points (the market version regresses
    # on actual points and feeds the implied total; here the fit and the feed are the same quantity)
    n = len(td_obs); sx = sum(x for x, _ in td_obs); sy = sum(y for _, y in td_obs)
    sxx = sum(x * x for x, _ in td_obs); sxy = sum(x * y for x, y in td_obs)
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    art = {
        'ARTIFACT': 'FOOTBALL_POINTS', 'spec_version': 'football-points-1',
        'built_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'NO_MARKET_INPUT': ('reads points, points_allowed, offensive_td, is_home, season, week, club, game_id '
                            'only; never ' + ', '.join(FIELDS_FORBIDDEN)),
        'centre': {'form': 'own-offence points per game: current season through week W-1 weighted by its games '
                           'plus prior season per game weighted by PRIOR_GAMES pseudo-games (the volume layer\'s blend)',
                   'prior_games': PRIOR_GAMES, 'OPPONENT_ADJUSTMENT': 'NOT_MODELLED (owner item 9)', 'WEATHER': 'NOT_MODELLED'},
        'fit_seasons': [FIRST_FIT_SEASON, THROUGH_SEASON], 'n_games': keep,
        'home_field': {'mean_margin_residual': round(statistics.fmean(hfa_terms), 4),
                       'MEANING': 'actual home margin minus the centre margin, averaged: the home-field the own-offence centre leaves behind; '
                                  'it is carried by the margin residual set\'s mean, not added twice'},
        'total_residual': {'mean': round(statistics.fmean(total_res), 4), 'sd': round(statistics.pstdev(total_res), 4), 'n': len(total_res)},
        'margin_residual': {'mean': round(statistics.fmean(margin_res), 4), 'sd': round(statistics.pstdev(margin_res), 4), 'n': len(margin_res)},
        'points_allowed_residual': {'mean': round(statistics.fmean(pa_res), 4), 'sd': round(statistics.pstdev(pa_res), 4), 'n': len(pa_res),
                                    'MEANING': 'points allowed minus the OPPONENT\'s football centre: conditional on the opponent, unlike the DST layer\'s league-mean residuals'},
        'td_fit': {'state': 'MEASURED', 'n_club_games': n, 'td_per_point_slope': round(slope, 6), 'intercept': round(intercept, 6),
                   'regressor': 'football expected club points', 'mean_expected_points': round(sx / n, 4), 'mean_offensive_td': round(sy / n, 4)},
        'empirical_residuals': {'total': [round(x, 3) for x in sorted(total_res)], 'margin': [round(x, 3) for x in sorted(margin_res)],
                                'points_allowed': [round(x, 3) for x in sorted(pa_res)]},
        'inputs': {'TEAM_GAME.json': hashlib.sha256(TG.read_bytes()).hexdigest()},
    }
    OUT.write_text(json.dumps(art, indent=1))
    return Outcome.ok('FOOTBALL_POINTS_BUILT', {k: v for k, v in art.items() if k != 'empirical_residuals'},
                      f"{keep} games {FIRST_FIT_SEASON}-{THROUGH_SEASON}; total residual sd {art['total_residual']['sd']}, "
                      f"margin sd {art['margin_residual']['sd']}, home-field {art['home_field']['mean_margin_residual']:+.3f}")


def load():
    return json.loads(OUT.read_text()) if OUT.exists() else None


def centre_for_game(home, away, season, week, table=None):
    """Football centre for one game: total, home margin (home-field carried in the residual mean), per club."""
    table = table or club_points_table(_rows())
    eh, bh = expected_points(table, home, season, week)
    ea, ba = expected_points(table, away, season, week)
    if eh is None or ea is None:
        return None
    return {'home_expected': eh, 'away_expected': ea, 'total': eh + ea, 'home_margin': eh - ea,
            'basis': {'home': bh, 'away': ba}, 'BASIS': 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND'}


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code); print(' ', o.detail)
    raise SystemExit(0 if o.state.value == 'PASS' else 1)

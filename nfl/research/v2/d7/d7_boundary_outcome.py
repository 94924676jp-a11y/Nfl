#!/usr/bin/env python3.12
"""Is week 1 actually different, on the OUTCOME side, from the rest of a season?

WHY THIS EXISTS. Every forward-valid sealed board in this repository is a week-1
2026 board, and every club in week 1 is at a season boundary. The
boundary-versus-non-boundary contrast the diagnostic was asked for therefore has
an EMPTY comparison arm: there is no non-boundary forecast to score. That is a
missing measurement and no amount of care recovers it.

What CAN be measured without any forecast is whether the realised world is
different at the boundary. If quarterback dropbacks concentrate on one passer
just as tightly in week 1 as in week 12, then a model that spreads dropback mass
across a wide room in week 1 is not responding to a real week-1 phenomenon. That
does not identify the model's boundary sensitivity -- only a non-boundary
forecast would -- but it removes one available excuse for the spread.

LAWFUL BY CONSTRUCTION: historical play-by-play only, no forecast, no board, no
2026 row, and the unit is (game_id, posteam), never the game.

REGULAR SEASON ONLY. Postseason has no week-1 analogue and its week numbering
continues past 18; including it would mix two different quantities.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve()
while _REPO.name and not (_REPO / 'nfl' / 'tests' / 'run_suite.py').exists():
    _REPO = _REPO.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from nfl.research import same_day_retrospective as SDR                # noqa: E402

FIELDS = ('game_id', 'season', 'season_type', 'week', 'posteam',
          'qb_dropback', 'passer_player_id')


def team_games(path):
    """(game_id, posteam) -> {passer_id: dropbacks} for one season file."""
    out = collections.defaultdict(collections.Counter)
    meta = {}
    with gzip.open(path, 'rt', newline='') as fh:
        for row in csv.DictReader(fh):
            if row.get('season_type') != 'REG':
                continue
            if str(row.get('qb_dropback')) not in ('1', '1.0'):
                continue
            pid = row.get('passer_player_id') or ''
            team = row.get('posteam') or ''
            gid = row.get('game_id') or ''
            if not pid or not team or not gid:
                # A dropback with no identified passer is a real play with an
                # unattributable actor. It is counted in the denominator and
                # named, never silently dropped -- dropping it would inflate
                # the top passer's share.
                out[(gid, team)]['__UNATTRIBUTED__'] += 1
            else:
                out[(gid, team)][pid] += 1
            meta[(gid, team)] = int(float(row['week']))
    return out, meta


def main():
    files = sorted(glob.glob(str(_REPO / 'nfl' / 'research' / 'postgame'
                                 / 'pbp_202[1-4].*.csv.gz')))
    if not files:
        raise SystemExit('D7_BOUNDARY_NO_HISTORICAL_PBP: nothing matched.')
    rows = []
    per_season = {}
    for f in files:
        season = int(pathlib.Path(f).name.split('.')[0].split('_')[1])
        tg, meta = team_games(f)
        if not tg:
            raise SystemExit(f'D7_BOUNDARY_EMPTY_PARSE: {f} yielded no rows.')
        per_season[season] = len(tg)
        for key, cnt in tg.items():
            gid, team = key
            tot = sum(cnt.values())
            if tot == 0:
                continue
            named = {k: v for k, v in cnt.items() if k != '__UNATTRIBUTED__'}
            top = max(named.values()) if named else 0
            rows.append({
                'season': season, 'game_id': gid, 'posteam': team,
                'week': meta[key], 'dropbacks': tot,
                'top_passer_share': top / tot,
                'n_passers_ge1': len(named),
                'n_passers_ge5': sum(1 for v in named.values() if v >= 5),
                'unattributed': cnt['__UNATTRIBUTED__'],
            })
    if not rows:
        raise SystemExit('D7_BOUNDARY_EMPTY_RESULT')

    def cell(sel, label):
        if not sel:
            return None
        s = np.array([r['top_passer_share'] for r in sel], float)
        n1 = np.array([r['n_passers_ge1'] for r in sel], float)
        n5 = np.array([r['n_passers_ge5'] for r in sel], float)
        return {
            'label': label,
            'n_team_games': len(sel),
            'n_game_clusters': len({r['game_id'] for r in sel}),
            'n_season_week_clusters': len({(r['season'], r['week'])
                                           for r in sel}),
            'mean_top_passer_share': round(float(s.mean()), 4),
            'median_top_passer_share': round(float(np.median(s)), 4),
            'p10_top_passer_share': round(float(np.percentile(s, 10)), 4),
            'mean_n_passers_ge1': round(float(n1.mean()), 4),
            'mean_n_passers_ge5': round(float(n5.mean()), 4),
            'share_of_team_games_with_2plus_passers_ge5': round(
                float((n5 >= 2).mean()), 4),
            'mean_dropbacks': round(float(
                np.mean([r['dropbacks'] for r in sel])), 4),
            'unattributed_dropbacks': int(sum(r['unattributed'] for r in sel)),
        }

    w1 = [r for r in rows if r['week'] == 1]
    rest = [r for r in rows if r['week'] != 1]
    d = np.array([r['top_passer_share'] for r in w1], float)
    o = np.array([r['top_passer_share'] for r in rest], float)
    # CLUSTERED BY GAME within each arm; the two arms are disjoint sets of
    # games, so the difference of two game-clustered means has the SE below.
    se1 = SDR._cluster_se(d - d.mean() + d.mean(), [r['game_id'] for r in w1])
    se2 = SDR._cluster_se(o - o.mean() + o.mean(), [r['game_id'] for r in rest])
    diff = float(d.mean() - o.mean())
    se = float(np.sqrt((se1 or 0) ** 2 + (se2 or 0) ** 2))
    out = {
        'artifact': 'D7_SEASON_BOUNDARY_OUTCOME_SIDE',
        'spec_version': 'd7-boundary-outcome/1.0.0',
        'governance': ('DIAGNOSTIC ONLY. Outcome-side description of the '
                       'historical world. Contains no forecast and scores no '
                       'model, so it CANNOT identify the engine\'s '
                       'sensitivity to the season boundary. It bounds one '
                       'explanation, nothing more.'),
        'sources': [str(pathlib.Path(f).relative_to(_REPO)) for f in files],
        'team_games_per_season': per_season,
        'unit': '(game_id, posteam)',
        'scope': 'REG season only',
        'week_1': cell(w1, 'SEASON BOUNDARY (week 1)'),
        'weeks_2_plus': cell(rest, 'NON-BOUNDARY (weeks 2+)'),
        'difference_week1_minus_rest': {
            'mean_top_passer_share': round(diff, 4),
            'se_game_clustered_both_arms': round(se, 4) if se else None,
            'z': round(diff / se, 3) if se else None,
            'note': ('descriptive. No equivalence margin was predeclared and '
                     'no two-one-sided test was run, so a small difference is '
                     'not evidence that the two are the same.'),
        },
        'what_this_does_not_establish': [
            'It does not measure the model. No forecast enters it.',
            'It does not supply the missing non-boundary forecast arm, and '
            'nothing here may be used as a substitute for one.',
            'Seasons 2021-2024 are not 2026 and roster churn differs by year.',
        ],
    }
    print(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    main()

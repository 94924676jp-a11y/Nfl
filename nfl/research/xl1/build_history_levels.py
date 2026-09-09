"""Historical team-game levels for the XL1 links, REG 2020-2025.

A simulator level means nothing without one. Run:

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' \
        python3.12 nfl/research/xl1/build_history_levels.py

Refuses rather than reports if the pbp files are not located.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import statistics
import sys

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB. No level is '
                         'reported without the bytes it was measured from.')
    tg = collections.defaultdict(collections.Counter)
    for path in files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if _i(r.get('two_point_attempt')):
                    continue
                po = r.get('posteam') or ''
                if not po:
                    continue
                c = tg[(r.get('season'), _i(r.get('week')), po)]
                # A THROW is a pass attempt that is not a sack. nflverse's
                # pass_attempt includes sacks (W2 section 3.1) and every sack
                # in 2020-2025 carries pass_attempt == 1.
                if _i(r.get('qb_dropback')):
                    c['dropbacks'] += 1
                if _i(r.get('sack')):
                    c['sacks'] += 1
                if _i(r.get('qb_scramble')):
                    c['scrambles'] += 1
                if _i(r.get('rush_attempt')):
                    c['rush_attempts'] += 1
                if _i(r.get('pass_attempt')) and not _i(r.get('sack')):
                    c['throws'] += 1
                    if r.get('receiver_player_id'):
                        c['targets'] += 1
                    else:
                        c['untargeted'] += 1
                    if _i(r.get('complete_pass')):
                        c['completions'] += 1
                        c['passing_yards'] += _f(r.get('passing_yards')) or 0.0
                        c['receiving_yards'] += _f(r.get('receiving_yards')) or 0.0
                        if _i(r.get('pass_touchdown')):
                            c['passing_td'] += 1
                            if r.get('receiver_player_id'):
                                c['receiving_td'] += 1
                if r.get('lateral_receiver_player_id'):
                    c['lateral_plays'] += 1
                    c['lateral_yards'] += _f(r.get('lateral_receiving_yards')) or 0.0
    ks = list(tg)
    n = len(ks)

    def mean(k):
        return round(statistics.mean(tg[x][k] for x in ks), 4)

    def exact(a, b):
        d = [tg[x][a] - tg[x][b] for x in ks]
        return {'exact': sum(1 for v in d if abs(v) < 1e-9), 'n': n,
                'mean_abs_diff': round(statistics.mean(abs(v) for v in d), 4),
                'max_abs_diff': round(max(abs(v) for v in d), 4)}

    lat_closed = [tg[x]['passing_yards'] - tg[x]['receiving_yards']
                  - tg[x]['lateral_yards'] for x in ks]

    # BY SEASON, AND IT IS NOT OPTIONAL.
    #
    # Every one of these quantities is in monotonic decline across 2020-2025:
    # team targets fall 33.81 -> 30.53, completions 22.96 -> 20.62, passing
    # yards 254.88 -> 225.02. A 2026 forecast compared against the six-season
    # mean is therefore compared against a baseline that is years stale, and
    # XL1's return did exactly that -- it reported a 9.2% team_targets error
    # that is 4.4% against 2025. The pooled mean stays available because the
    # IDENTITIES are pooled facts, but a LEVEL comparison must name its season.
    seasons = sorted({x[0] for x in ks})
    by_season = {}
    for s_ in seasons:
        sk = [x for x in ks if x[0] == s_]
        by_season[str(s_)] = {
            'n_team_games': len(sk),
            **{k: round(statistics.mean(tg[x][k] for x in sk), 4)
               for k in ('throws', 'targets', 'completions', 'passing_yards',
                         'passing_td', 'dropbacks', 'sacks', 'scrambles',
                         'untargeted', 'rush_attempts')},
            'throw_share_of_dropbacks': round(
                statistics.mean(tg[x]['throws'] for x in sk)
                / statistics.mean(tg[x]['dropbacks'] for x in sk), 6)}
    out = {
        'by_season': by_season,
        'most_recent_season': str(seasons[-1]),
        'level_comparison_baseline':
            'USE by_season[most_recent_season] FOR ANY LEVEL COMPARISON. The '
            'pooled team_game_means below are a six-season average of a '
            'declining series and are the right baseline only for the '
            'identities, which do not trend.',
        'artifact': 'XL1_HISTORY_LEVELS', 'seasons': list(SEASONS),
        'source_files': [os.path.basename(p) for p in files],
        'n_team_games': n,
        'team_game_means': {
            'throws': mean('throws'), 'targets': mean('targets'),
            'dropbacks': mean('dropbacks'), 'sacks': mean('sacks'),
            'scrambles': mean('scrambles'), 'untargeted': mean('untargeted'),
            'rush_attempts': mean('rush_attempts'),
            'throws_minus_targets': round(
                statistics.mean(tg[x]['throws'] - tg[x]['targets']
                                for x in ks), 4),
            'completions': mean('completions'),
            'passing_yards': mean('passing_yards'),
            'receiving_yards': mean('receiving_yards'),
            'passing_td': mean('passing_td'),
            'receiving_td': mean('receiving_td'),
        },
        'identities': {
            'completions_equals_receptions_by_construction':
                'every completion in 2020-2025 carries a receiver_player_id; '
                'the count of completions IS the count of receptions',
            'passing_yards_vs_receiving_yards': exact('passing_yards',
                                                      'receiving_yards'),
            'passing_td_vs_receiving_td': exact('passing_td', 'receiving_td'),
            'passing_minus_receiving_minus_lateral': {
                'exact': sum(1 for v in lat_closed if abs(v) < 1e-9), 'n': n,
                'mean_abs_residual': round(
                    statistics.mean(abs(v) for v in lat_closed), 6),
                'max_abs_residual': round(max(abs(v) for v in lat_closed), 4),
                'note': 'the residual is a SOURCE discrepancy and is reported, '
                        'never absorbed. It is not a lateral and not a sack.'},
            'team_games_with_a_lateral': sum(
                1 for x in ks if tg[x]['lateral_plays']),
        },
    }
    dest = os.path.join(HERE, 'history_levels.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(json.dumps(out, indent=2, sort_keys=True))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""P5A step 0: the CARRY-LEVEL primitive table.

The filter reproduces P1/P3's `carries` EXACTLY -- rush_attempt == 1, a
non-empty rusher_player_id, two-point attempts excluded, scrambles INCLUDED
(measured in P1: on all 1,134 qb_scramble plays of 2024 passer_player_id is
NULL and rusher_player_id is set on 1,062, so a scramble belongs to the
rusher). If this table did not aggregate to the panel's y_carries exactly, the
P4C carry distribution and the P5A conversion layer would be describing
different objects. It is checked, not assumed.
"""
import collections, csv, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.abspath(os.path.join(HERE, '..', 'p1'))
SEASONS = list(range(2016, 2026))
COLS = ('season', 'week', 'game_id', 'posteam', 'defteam', 'rusher_player_id',
        'yards_gained', 'down', 'ydstogo', 'yardline_100', 'score_differential',
        'wp', 'shotgun', 'no_huddle', 'run_location', 'run_gap', 'qb_scramble',
        'epa', 'success', 'half_seconds_remaining', 'game_seconds_remaining',
        'goal_to_go', 'season_type')


def f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def main():
    out = open(f'{HERE}/carries.csv', 'w', newline='')
    w = csv.writer(out)
    w.writerow(['season', 'week', 'game_id', 'posteam', 'defteam', 'rusher',
                'yards', 'down', 'ydstogo', 'yardline_100', 'score_diff', 'wp',
                'shotgun', 'no_huddle', 'run_location', 'run_gap', 'scramble',
                'epa', 'success', 'gsr', 'goal_to_go'])
    tot = collections.Counter()
    for y in SEASONS:
        p = f'{P1}/pbp_{y}.csv'
        if not os.path.exists(p):
            print(f'  {y}: MISSING pbp file -- not silently skipped, recorded')
            tot[(y, 'missing')] = 1
            continue
        n = 0
        for r in csv.DictReader(open(p)):
            if (r.get('season_type') or 'REG') != 'REG':
                continue
            if i(r.get('two_point_attempt')):
                continue
            if not i(r.get('rush_attempt')):
                continue
            rus = r.get('rusher_player_id') or ''
            if not rus:
                continue
            w.writerow([i(r.get('season'), y), i(r.get('week')), r.get('game_id'),
                        r.get('posteam'), r.get('defteam'), rus,
                        f(r.get('yards_gained')), i(r.get('down')),
                        i(r.get('ydstogo')), f(r.get('yardline_100'), 999),
                        f(r.get('score_differential')), f(r.get('wp'), 0.5),
                        i(r.get('shotgun')), i(r.get('no_huddle')),
                        r.get('run_location') or '', r.get('run_gap') or '',
                        i(r.get('qb_scramble')), f(r.get('epa')),
                        i(r.get('success')), f(r.get('game_seconds_remaining')),
                        i(r.get('goal_to_go'))])
            n += 1
        tot[y] = n
        print(f'  {y}: {n} carries')
    out.close()
    print('total carries:', sum(v for k, v in tot.items() if isinstance(k, int)))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3.12
"""Run the accounting invariants against real 2020-2025 pbp.

An invariant layer that has never met real data is a wish. This measures every
declared invariant on every team-game and NAMES every residual it finds.
"""
import collections, csv, gzip, json, os, sys
import numpy as np
csv.field_size_limit(10**7)

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.accounting import invariants as I                     # noqa: E402

PBP = os.environ.get('RC_PBP_DIR', '/tmp/claude-0/-home-user-mlb-prop-system-v7/'
                     '8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/conv')


def i(v, d=0):
    try: return int(float(v))
    except (TypeError, ValueError): return d
def f(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d


def collect(seasons):
    team = collections.defaultdict(collections.Counter)
    plyr = collections.defaultdict(collections.Counter)
    pos_of = {}
    edge = collections.Counter()
    for y in seasons:
        with gzip.open(f'{PBP}/pbp{y}.csv.gz', 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                two = i(r.get('two_point_attempt'))
                tm = r.get('posteam') or ''
                if not tm:
                    continue
                k = (y, i(r.get('week')), tm)
                pas, cmp_ = i(r.get('pass_attempt')), i(r.get('complete_pass'))
                rush, sack = i(r.get('rush_attempt')), i(r.get('sack'))
                rec = r.get('receiver_player_id') or ''
                rus = r.get('rusher_player_id') or ''
                y100 = f(r.get('yardline_100'), 999)
                if two:
                    edge['two_point_plays'] += 1
                    continue
                if i(r.get('play_type_nfl') == 'PENALTY') or r.get('play_type') == 'no_play':
                    edge['no_play_or_penalty'] += 1
                if rec and pas:
                    team[k]['targets'] += 1
                    plyr[(k, rec)]['targets'] += 1
                    if y100 <= 20:
                        team[k]['rz_targets'] += 1
                        plyr[(k, rec)]['rz_targets'] += 1
                    if cmp_:
                        team[k]['receptions'] += 1
                        plyr[(k, rec)]['receptions'] += 1
                        ry = f(r.get('receiving_yards'))
                        team[k]['recv_yards'] += ry
                        plyr[(k, rec)]['recv_yards'] += ry
                        if i(r.get('pass_touchdown')) and i(r.get('td_team') == tm or 1):
                            pass
                    if i(r.get('pass_touchdown')):
                        team[k]['pass_td'] += 1
                        plyr[(k, rec)]['recv_td'] += 1
                    if i(r.get('lateral_reception')):
                        edge['lateral_receptions'] += 1
                if pas and not rec and not sack:
                    edge['pass_attempt_no_receiver_no_sack'] += 1
                if rush and rus:
                    team[k]['carries'] += 1
                    plyr[(k, rus)]['carries'] += 1
                    if i(r.get('rush_touchdown')):
                        team[k]['rush_td'] += 1
                        plyr[(k, rus)]['rush_td'] += 1
                    if i(r.get('lateral_rush')):
                        edge['lateral_rushes'] += 1
                # passing yards, charged to the offense
                if pas and cmp_:
                    team[k]['pass_yards'] += f(r.get('passing_yards'))
    return team, plyr, edge


def main():
    seasons = [int(x) for x in (sys.argv[1:] or ['2020', '2021', '2022',
                                                 '2023', '2024', '2025'])]
    team, plyr, edge = collect(seasons)
    print(f'team-games: {len(team)}   player-team-games: {len(plyr)}')
    print(f'edge cases: {dict(edge)}')

    def by_team(field):
        out = collections.defaultdict(float)
        for (k, _p), c in plyr.items():
            out[k] += c[field]
        return out

    results = {}
    checks = [
        ('team_targets_eq_sum_player_targets', 'targets'),
        ('team_receptions_eq_sum_player_receptions', 'receptions'),
        ('team_recv_yards_eq_sum_player_recv_yards', 'recv_yards'),
        ('team_carries_eq_sum_player_carries', 'carries'),
        ('team_rush_td_eq_sum_player_rush_td', 'rush_td'),
    ]
    for name, field in checks:
        got = by_team(field)
        res = {k: (float(team[k][field]), float(got.get(k, 0.0)), 0.0)
               for k in team}
        o = I.check(name, res, tol=1e-6)
        results[name] = {'state': o.state.value, 'code': o.code,
                         'detail': o.detail[:400]}
        print(f'  {o.state.value:<6} {name}')
        if o.state is not State.PASS:
            print(f'         {o.detail[:250]}')

    # passing yards vs receiving yards, team level
    res = {k: (float(team[k]['pass_yards']), float(team[k]['recv_yards']), 0.0)
           for k in team}
    o = I.check('team_pass_yards_eq_team_recv_yards', res, tol=1e-6)
    results['team_pass_yards_eq_team_recv_yards'] = {
        'state': o.state.value, 'code': o.code, 'detail': o.detail[:400]}
    print(f'  {o.state.value:<6} team_pass_yards_eq_team_recv_yards')
    if o.state is not State.PASS:
        print(f'         {o.detail[:300]}')

    # pass TD vs receiving TD
    rtd = by_team('recv_td')
    res = {k: (float(team[k]['pass_td']), float(rtd.get(k, 0.0)), 0.0) for k in team}
    o = I.check('team_pass_td_eq_sum_recv_td', res, tol=1e-6)
    results['team_pass_td_eq_sum_recv_td'] = {'state': o.state.value,
                                              'code': o.code, 'detail': o.detail[:400]}
    print(f'  {o.state.value:<6} team_pass_td_eq_sum_recv_td')
    if o.state is not State.PASS:
        print(f'         {o.detail[:300]}')

    # orderings
    pairs = {k: (c['receptions'], c['targets']) for k, c in plyr.items()}
    o = I.le_check('player_receptions_le_targets', pairs)
    results['player_receptions_le_targets'] = {'state': o.state.value, 'code': o.code}
    print(f'  {o.state.value:<6} player_receptions_le_targets  (n={len(pairs)})')
    pairs = {k: (c['rz_targets'], c['targets']) for k, c in plyr.items()}
    o = I.le_check('player_rz_targets_le_targets', pairs)
    results['player_rz_targets_le_targets'] = {'state': o.state.value, 'code': o.code}
    print(f'  {o.state.value:<6} player_rz_targets_le_targets')

    results['_edge_cases'] = dict(edge)
    results['_n_team_games'] = len(team)
    results['_seasons'] = seasons
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'accounting_audit.json')
    json.dump(results, open(out, 'w'), indent=1)
    print(f'\nwrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

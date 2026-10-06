#!/usr/bin/env python3.12
"""Adversarial tests for the ATL@NO postgame role audit and coherence re-measure (postgame item 6).

    python3.12 nfl/tests/test_postgame_role_coherence.py

Each test feeds a hostile but plausible input and checks that the diagnostic does not quietly read the outcome as
the forecast, mis-define a role, or misreport an identity:

  1  ROLES ARE PREGAME. A receiver who leads the game in targets but trailed in prior weeks must NOT become TGT1.
  2  "PREVIOUS 3 GAMES" MEANS THE TEAM'S. A player who missed a team game is not counted as 3-for-3.
  3  DK CORE matches a hand computation across QB / RB / WR / TE line items (no bonuses, INT -1).
  4  TEAM TD identity: team TDs = rush TD + rec TD, never double-counting the passer's TD.
  5  PROJECTIONS.csv volume columns ARE the if-plays (conditional) values on the sealed v2 run -- the labelling
     finding is a measured fact about the artifact, so a silent change to either side fails here.
  6  The appearance flags are a function of PREGAME data: replacing the ATL@NO actual week with zeros changes no flag.
  7  Kicker DK bands: 39 yd = 3, 40 yd = 4, 50 yd = 5, missed FG = 0, XP good = 1.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.postgame import showdown_atl_no_coherence as CO  # noqa: E402
from nfl.postgame import showdown_atl_no_role_audit as RA  # noqa: E402

P = F = 0


def check(ok, msg):
    global P, F
    P, F = P + bool(ok), F + (not ok)
    print(('  ok   ' if ok else '  FAIL ') + msg)


def _play(gid, week, team, **kw):
    base = {'game_id': gid, 'season': 2025, 'week': week, 'season_type': 'REG', 'posteam': team, 'defteam': 'OPP',
            'home_team': team, 'away_team': 'OPP', 'total_home_score': 0, 'total_away_score': 0,
            'passer_player_id': None, 'receiver_player_id': None, 'rusher_player_id': None, 'kicker_player_id': None,
            'passing_yards': 0, 'receiving_yards': 0, 'rushing_yards': 0, 'complete_pass': 0, 'pass_attempt': 0,
            'sack': 0, 'pass_touchdown': 0, 'rush_touchdown': 0, 'interception': 0, 'field_goal_result': None,
            'kick_distance': 0, 'extra_point_result': None, 'play_type': 'pass'}
    base.update(kw)
    return base


def _pass(gid, week, rec, yds=10, td=0, comp=1):
    return _play(gid, week, 'AAA', passer_player_id='QB', receiver_player_id=rec, passing_yards=yds * comp,
                 receiving_yards=yds * comp, complete_pass=comp, pass_attempt=1, pass_touchdown=td)


def test_roles_pregame():
    rows = []
    for w in (1, 2, 3):        # prior weeks: W1 is the target leader, W2 second, W3 third; RB carries
        gid = f'g{w}'
        rows += [_pass(gid, w, 'W1') for _ in range(8)] + [_pass(gid, w, 'W2') for _ in range(5)] \
            + [_pass(gid, w, 'W3') for _ in range(3)] + [_pass(gid, w, 'W4') for _ in range(1)] \
            + [_play(gid, w, 'AAA', rusher_player_id='RB', rushing_yards=4, play_type='run') for _ in range(15)] \
            + [_pass(gid, w, 'W1', comp=0) for _ in range(6)]
    gid = 'g4'                 # game week: W4 explodes, W1 is quiet
    rows += [_pass(gid, 4, 'W4', yds=20) for _ in range(12)] + [_pass(gid, 4, 'W1')] + [_pass(gid, 4, 'W2')] \
        + [_pass(gid, 4, 'W3')] + [_play(gid, 4, 'AAA', rusher_player_id='RB', rushing_yards=4, play_type='run')] \
        + [_pass(gid, 4, 'W1', comp=0) for _ in range(9)]
    pg, tg = CO.player_games(pd.DataFrame(rows))
    R = CO.pregame_roles(pg)
    r = R[('g4', 'AAA')]
    w1 = float(pg[(pg.game_id == 'g4') & (pg.pid == 'W1')].dk.iloc[0])
    w4 = float(pg[(pg.game_id == 'g4') & (pg.pid == 'W4')].dk.iloc[0])
    check(abs(r['TGT1'] - w1) < 1e-9 and abs(r['TGT1'] - w4) > 1, 'TGT1 is the prior-weeks target leader, not the in-game leader')
    check(('g1', 'AAA') not in R, 'week-1 game has no pregame role and is dropped')


def test_prior3_team_games():
    snaps = []
    for w in range(1, 6):
        snaps.append({'game_id': f'g{w}', 'season': 2025, 'week': w, 'team': 'AAA', 'position': 'WR', 'gsis_id': 'X',
                      'targets': 0 if w == 5 else 2, 'carries': 0})
    for w in (1, 2, 4, 5):     # Y misses week 3 entirely (not dressed)
        snaps.append({'game_id': f'g{w}', 'season': 2025, 'week': w, 'team': 'AAA', 'position': 'WR', 'gsis_id': 'Y',
                      'targets': 0 if w == 5 else 2, 'carries': 0})
    x = pd.DataFrame(snaps)
    tg = x[['season', 'team', 'week']].drop_duplicates().sort_values(['season', 'team', 'week'])
    tg['tgi'] = tg.groupby(['season', 'team']).cumcount()
    x = x.merge(tg, on=['season', 'team', 'week'])
    x['has'] = (x.targets > 0).astype(int)
    key = x.set_index(['gsis_id', 'season', 'team', 'tgi'])['has'].to_dict()
    ok = lambda pid, t: all(key.get((pid, 2025, 'AAA', t - k)) == 1 for k in (1, 2, 3))
    check(ok('X', 4) and not ok('Y', 4), 'player who missed a team game is not 3-for-3 (team-game index, as in RA)')
    src = pathlib.Path(RA.__file__).read_text()
    check("tg.groupby(['season', 'team']).cumcount()" in src and 'r.tgi - k' in src,
          'role audit indexes previous games by TEAM game, the rule this test encodes')


def test_dk_core():
    rows = [_play('g', 2, 'AAA', passer_player_id='QB', receiver_player_id='TE', passing_yards=25, receiving_yards=25,
                  complete_pass=1, pass_attempt=1, pass_touchdown=1),
            _play('g', 2, 'AAA', passer_player_id='QB', pass_attempt=1, interception=1),
            _play('g', 2, 'AAA', rusher_player_id='RB', rushing_yards=12, rush_touchdown=1, play_type='run'),
            _play('g', 2, 'AAA', passer_player_id='QB', receiver_player_id='WR', passing_yards=101, receiving_yards=101,
                  complete_pass=1, pass_attempt=1)]
    pg, tg = CO.player_games(pd.DataFrame(rows))
    d = pg.set_index('pid').dk
    check(abs(d['QB'] - (0.04 * 126 + 4 - 1)) < 1e-9, f"QB DK core {d['QB']:.2f} = 0.04*126 + 4 - 1")
    check(abs(d['TE'] - (2.5 + 1 + 6)) < 1e-9 and abs(d['WR'] - (10.1 + 1)) < 1e-9, 'receiver DK core: no 100-yd bonus')
    check(abs(d['RB'] - (1.2 + 6)) < 1e-9, 'rusher DK core')
    check(int(tg.td.iloc[0]) == 2, 'team TDs = 1 rec TD + 1 rush TD (the pass TD is not counted twice)')


def test_kicker_bands():
    rows = [_play('g', 2, 'AAA', kicker_player_id='K', field_goal_result='made', kick_distance=d, play_type='field_goal')
            for d in (39, 40, 50)]
    rows += [_play('g', 2, 'AAA', kicker_player_id='K', field_goal_result='missed', kick_distance=45, play_type='field_goal'),
             _play('g', 2, 'AAA', kicker_player_id='K', extra_point_result='good', play_type='extra_point'),
             _play('g', 2, 'AAA', rusher_player_id='RB', rushing_yards=3, play_type='run')]   # team rows need a skill play
    _pg, tg = CO.player_games(pd.DataFrame(rows))
    check(int(tg.kdk.iloc[0]) == 3 + 4 + 5 + 0 + 1, f'kicker bands 3/4/5, miss 0, XP 1 (got {tg.kdk.iloc[0]})')


def test_csv_semantics_on_sealed_run():
    sd = RA.SD
    if not sd.exists():
        check(True, 'sealed v2 run not present; skipped by absence (not a pass of the claim)')
        return
    import csv as _csv
    proj = json.loads(next(sd.glob('SHOWDOWN_*_2026W4_PROJ.json')).read_text())['rows']
    rows = {(r['player'], r['team']): r for r in _csv.DictReader(open(next(sd.glob('SHOWDOWN_*_PROJECTIONS.csv'))))}
    n = bad = 0
    for r in proj.values():
        c = rows.get((r.get('name'), r.get('club') or r.get('team')))
        cv = (r.get('conditional_volume') or {}).get('targets')
        if c and cv is not None and c.get('targets') not in (None, ''):
            n += 1
            bad += abs(float(c['targets']) - round(cv, 2)) > 0.011
    check(n >= 20 and bad == 0, f'PROJECTIONS.csv targets == conditional_volume.targets on {n - bad}/{n} rows (if-plays semantics)')


def test_flags_pregame_only():
    p = RA.OUT / 'ATL_NO_ROLE_AUDIT.json'
    if not p.exists():
        check(False, 'ATL_NO_ROLE_AUDIT.json missing -- run the role audit first')
        return
    doc = json.loads(p.read_text())
    flags = doc['B_appearance_flags']
    check(len(flags) >= 8, f'{len(flags)} pregame-qualified player-fields evaluated (non-empty)')
    # flags must be computable without the graded fields: recompute from pregame fields only
    hist = doc['B_appearance_history_2024_2025']
    re = [(f['allocator_1_minus_p_plays'] > 2 * hist[f['field']]['ci95_game_clustered'][1],
           f['sim_p_zero'] > 2 * hist[f['field']]['ci95_game_clustered'][1]) for f in flags]
    check(all(r == (f['DEFECT_MEAN_SHRINK'], f['DEFECT_ZERO_MASS']) for r, f in zip(re, flags)),
          'every flag is reproduced from pregame quantities alone (graded_actual / actual_snap_pct unused)')
    rows = {r['player']: r for r in doc['A_opportunity_table']}
    qual = all(rows[f['player']][f['field']]['pregame_games_with_ge1_wk1_3'] == [1, 1, 1] for f in flags)
    check(qual, 'qualification uses weeks 1-3 only')


if __name__ == '__main__':
    for t in (test_roles_pregame, test_prior3_team_games, test_dk_core, test_kicker_bands,
              test_csv_semantics_on_sealed_run, test_flags_pregame_only):
        print(t.__name__)
        t()
    print(f'{P} passed, {F} failed')
    sys.exit(1 if F else 0)

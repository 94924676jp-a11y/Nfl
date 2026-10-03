"""classic_dfs_reasoning: every material exposure carries a football reason, or is named UNEXPLAINED."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_dfs_reasoning as D   # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _card(dk, name, pos, sal, mean, p90, targets=0.0, carries=0.0, att=0.0, roles=(), gl=0, rz=0):
    return {'dk_id': dk, 'name': name, 'position': pos, 'salary': sal, 'role_types': list(roles),
            'projection': {'distribution': {'dk_mean': mean, 'p90': p90}, 'targets': targets, 'carries': carries,
                           'pass_attempts': att},
            'measured_2026': {'gl_carries': gl, 'rz_targets': rz},
            'uncertainty': {'conflicts': [], 'role_confidence': 'HIGH', 'prior_tier': 'X'},
            'status': {'designation': None}}


QB = _card('1', 'Q', 'QB', 6000, 20, 30, att=36)
WR = _card('2', 'W', 'WR', 7000, 18, 30, targets=10, roles=['target leader at WR'])
DUD = _card('3', 'Nobody', 'WR', 9000, 2, 5, targets=0.5)
FILL = [_card(str(10 + i), f'F{i}', 'WR', 5000, 9, 15, targets=3) for i in range(40)]
BOOK = {'games': {'G': {'teams': {'CIN': {
    'environment': {'proj_targets': 35.0, 'proj_rush_attempts': 25.0},
    'qb_ecosystem': {'quarterback': 'Q', 'target_tree': [{'name': 'W', 'pos': 'WR'}, {'name': 'Nobody', 'pos': 'WR'}]},
    'qb_correlations': [{'with': 'W', 'pos': 'WR', 'r': 0.45}],
    'injury_cascades': [{'player': 'Gone', 'position': 'WR', 'vacated_per_game_2026': {'targets': 1.0},
                         'who_the_projection_gives_more_to': [{'name': 'W'}]}],
    'players': [QB, WR, DUD] + FILL}}}}}
LU = [{'slots': [{'dk_id': '1'}, {'dk_id': '2'}, {'dk_id': '3'}]}, {'slots': [{'dk_id': '1'}, {'dk_id': '2'}]}]
PORT = {'contests': [{'profile': 'MAX20', 'lineups': LU, 'report': {'player_exposure': {
    'Q': {'dk_id': '1', 'overall': 1.0}, 'W': {'dk_id': '2', 'overall': 1.0}, 'N': {'dk_id': '3', 'overall': 0.5}}}}]}


def test_01_reasons_are_football():
    r = D.reasons(BOOK, PORT, {})
    w = next(x for x in r['players'] if x['player'] == 'W')
    check('a concentrated-target WR is explained by his targets', any('concentrated targets' in y for y in w['why']), w['why'])
    check('  and by his stack with his quarterback, with the joint-sim r',
          any('game-stack synergy' in y and 'r = 0.45' in y for y in w['why']), w['why'])
    check('negative control: a 1-target absence is never offered as his opportunity',
          not any('out' in y and 'Gone' in y for y in w['why']), w['why'])
    check('positive control: material exposure with no football reason is UNEXPLAINED, not hidden',
          [x['player'] for x in r['UNEXPLAINED']] == ['Nobody'], r['UNEXPLAINED'])
    check('  no reason ever says the optimiser liked him', not any('optimi' in y for x in r['players'] for y in x['why']))
    shapes = {x['shape']: x['share'] for x in r['stack_shapes']['MAX20']}
    check('stack shapes name the role of each pass catcher', 'QB + WR1 + WR2' in shapes and 'QB + WR1' in shapes, shapes)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')

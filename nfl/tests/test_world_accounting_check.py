"""Published-world accounting checker (nfl/tools/world_accounting_check.py), QBCTX-C1.

Synthetic scenario directories in the exact published format (WORLDS.npz + DRAWS.json). A coherent world passes every
check; each ordinary-event break is caught; and the independent audit's counterexample (QB 100 / WR 100 raw yards,
QB conditional 50 per 10 attempts) is pushed through the REAL `classic_slate_run.efficiency_worlds` and caught.
"""
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
import numpy as np  # noqa: E402

from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.tools import world_accounting_check as W  # noqa: E402

PASSED = FAILED = 0
FIELDS = ['pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td', 'targets', 'receptions',
          'rec_yards', 'rec_td', 'interceptions']


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print('  ok  ', msg)
    else:
        FAILED += 1
        print('  FAIL', msg)


def scenario(lines, points, takeaways, players=None):
    """lines: {key: [11-tuple per world]}. points: [(home, away)] per world. takeaways: {club: [per world]}."""
    sd = pathlib.Path(tempfile.mkdtemp(prefix='acct_'))
    keys = sorted(lines)
    st = np.array([lines[k] for k in keys], dtype=float)
    for f in ('pass_yards', 'rush_yards', 'rec_yards'):
        st[:, :, FIELDS.index(f)] *= 10
    meta = {'keys': keys, 'fields': FIELDS, 'yard_scale': 10, 'yard_fields': ['pass_yards', 'rush_yards', 'rec_yards'],
            'games': [{'game_id': 'G', 'home': 'HHH', 'away': 'AAA'}]}
    np.savez(sd / 'X_WORLDS.npz', stats=np.round(st).astype('int16'),
             points=np.array([points], dtype='float32'), meta=np.frombuffer(json.dumps(meta).encode(), dtype='uint8'))
    draws = {k: [CR.dk_from_stats(*w) for w in lines[k]] for k in keys}
    (sd / 'X_DRAWS.json').write_text(json.dumps({
        'draws': draws, 'dst_components': {f'D|{c}': [[2, t, 0, 0] for t in v] for c, v in takeaways.items()}}))
    if players is not None:
        (sd / 'X_STATE.json').write_text(json.dumps({'players': players}))
    return sd


QB = (30, 250.0, 2, 3, 12.0, 0, 0, 0, 0.0, 0, 1)
WR1 = (0, 0.0, 0, 0, 0.0, 0, 9, 6, 150.0, 1, 0)
WR2 = (0, 0.0, 0, 0, 0.0, 0, 7, 5, 100.0, 1, 0)


def coherent(n=4):
    return {'Q|AAA': [QB] * n, 'R1|AAA': [WR1] * n, 'R2|AAA': [WR2] * n,
            'Q|HHH': [QB] * n, 'R1|HHH': [WR1] * n, 'R2|HHH': [WR2] * n}


def test_coherent_passes():
    r = W.check(scenario(coherent(), [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4}))
    check(r['VIOLATED'] == {}, f"a coherent published world passes every check ({r['VIOLATED']})")


def test_each_break_is_caught():
    L = coherent()
    L['R2|AAA'] = [(0, 0.0, 0, 0, 0.0, 0, 7, 5, 60.0, 1, 0)] * 4            # 250 thrown, 210 caught
    r = W.check(scenario(L, [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4}))
    check(r['VIOLATED'].get('AAA:PASS_YDS_EQ_REC_YDS') == 4, 'passer yards != receiver yards is caught')
    L = coherent()
    L['R2|AAA'] = [(0, 0.0, 0, 0, 0.0, 0, 7, 0, 100.0, 1, 0)] * 4           # yards and a TD with no catch
    r = W.check(scenario(L, [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4}))
    check(r['VIOLATED'].get('YDS_WITHOUT_CATCH') == 4 and r['VIOLATED'].get('REC_TD_WITHOUT_CATCH') == 4,
          'receiving yards / a receiving TD without a reception are caught')
    r = W.check(scenario(coherent(), [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [0] * 4}))
    check(r['VIOLATED'].get('AAA:INT_LE_OPP_TAKEAWAYS') == 4 and 'HHH:INT_LE_OPP_TAKEAWAYS' not in r['VIOLATED'],
          'an interception the opposing DST did not take away is caught (and only for that club)')
    r = W.check(scenario(coherent(), [(17.0, 10.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4}))
    check(r['VIOLATED'].get('AAA:POINTS_GE_6_PER_TD') == 4, 'club points below 6 x its offensive TDs are caught')
    st = {'q': {'name': 'R2', 'team': 'AAA', 'current_availability': {'status': 'OUT'}}}
    r = W.check(scenario(coherent(), [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4}, players=st))
    check(r['VIOLATED'].get('INACTIVE_NO_EVENTS') == 4, 'an ordinary-OUT player recording events is caught')


def test_independent_audit_counterexample_through_real_transform():
    """QB 100 / WR 100 raw yards on 10 attempts / 10 targets; QB conditional 50 per 10 attempts, WR 100 per 10."""
    n = 20
    raw = {'Q|AAA': [(10, 100.0, 0, 0, 0.0, 0, 0, 0, 0.0, 0)] * n,
           'R|AAA': [(0, 0.0, 0, 0, 0.0, 0, 10, 7, 100.0, 0)] * n}
    rows = {'Q|AAA': {'conditional_volume': {'pass_yards': 50.0, 'pass_attempts': 10.0}},
            'R|AAA': {'conditional_volume': {'rec_yards': 100.0, 'targets': 10.0}}}
    dk, worlds, meta = CR.efficiency_worlds(raw, rows, 0.0, 1)
    qy, ry = worlds['Q|AAA'][0][1], worlds['R|AAA'][0][8]
    check(abs(qy - 50.0) < 1e-9 and abs(ry - 100.0) < 1e-9,
          f'the real efficiency_worlds reproduces the audit counterexample (QB {qy:.1f}, WR {ry:.1f})')
    L = {k: [tuple(w) for w in v] for k, v in worlds.items()}
    L.update({'Q|HHH': [QB] * n, 'R1|HHH': [WR1] * n, 'R2|HHH': [WR2] * n})
    r = W.check(scenario(L, [(17.0, 17.0)] * n, {'AAA': [0] * n, 'HHH': [0] * n}))
    check(r['VIOLATED'].get('AAA:PASS_YDS_EQ_REC_YDS') == n,
          'the checker catches it in every published world (the raw certificate would not)')


def test_bonus_line_rounding_is_not_a_violation():
    L = coherent()
    L['Q|HHH'] = [(30, 299.96, 2, 3, 12.0, 0, 0, 0, 0.0, 0, 1)] * 4            # stored as 300.0
    L['R1|HHH'] = [(0, 0.0, 0, 0, 0.0, 0, 9, 6, 199.96, 1, 0)] * 4
    sd = scenario(L, [(17.0, 17.0)] * 4, {'AAA': [1] * 4, 'HHH': [1] * 4})
    r = W.check(sd)
    d = r['checks']['DK_FROM_PUBLISHED']
    check(d['violations'] == 0 and d['bonus_line_storage_rounding_cells'] == 4,
          'a DK bonus tipped only by 0.1-yard storage rounding is classified as rounding, not a scoring break')


if __name__ == '__main__':
    for t in (test_coherent_passes, test_each_break_is_caught, test_independent_audit_counterexample_through_real_transform,
              test_bonus_line_rounding_is_not_a_violation):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

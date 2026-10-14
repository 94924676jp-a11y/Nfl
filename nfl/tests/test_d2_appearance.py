#!/usr/bin/env python3.12
"""D2 player-level appearance re-weighting (PREREG_D2_APPEARANCE.md; ledger APPEAR-D1).

Off by default; 'CURRENT' reproduces the incumbent exactly (golden); every arm preserves each club's field totals;
q is the pre-registered beta-binomial posterior mean; features are pregame (weeks strictly before W)."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

PASSED = FAILED = 0
PARAMS = {'SHRINK': {'kappa': 5, 'm_pooled': 0.6},
          'ROLE': {'kappa': 2, 'm_role': {'WR|1|1': 0.9}, 'm_pos': {'QB': 0.5, 'RB': 0.5, 'WR': 0.4, 'TE': 0.5}}}


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _panel():
    # club AAA played weeks 1-3; g1 appeared in all three, g2 only in week 1, g3 in week 3 (the last game)
    rows = {'g1': {1: 'AAA', 2: 'AAA', 3: 'AAA'}, 'g2': {1: 'AAA'}, 'g3': {3: 'AAA'}}
    return {'players': {g: {'2023': {str(w): {'team': c} for w, c in ws.items()}} for g, ws in rows.items()}}


def _crows():
    def r(g, rank, tg, p):
        return {'gsis': g, 'position': 'WR', 'targets': tg, 'p_plays': {'targets': p},
                'allocation': {'targets': {'depth_rank_in_group': rank}}}
    return [r('g1', 1, 10.0, 1.0), r('g2', 2, 6.0, 1.0), r('g3', 5, 4.0, 0.8)]


def test_default_is_off():
    check(F.D2_ARM[0] is None and F.D2_FEATURE_SINK is None, 'D2 is off by default (production behaviour)')


def test_features_are_pregame_and_q_is_the_registered_formula():
    F._CLUB_WEEKS.clear()
    pan = _panel()
    c = _crows()
    f1 = F.d2_features(c[0], pan, 'AAA', 2023, 4)
    f2 = F.d2_features(c[1], pan, 'AAA', 2023, 4)
    f3 = F.d2_features(c[2], pan, 'AAA', 2023, 4)
    check(f1 == ('WR|1|1', 3, 3), f'g1: rank 1, appeared last game, 3 of 3 ({f1})')
    check(f2 == ('WR|2|0', 1, 3), f'g2: rank 2, missed the last game, 1 of 3 ({f2})')
    check(f3 == ('WR|4|1', 1, 3), f'g3: rank 5 buckets to 4, appeared last game ({f3})')
    F._CLUB_WEEKS.clear()
    fw = F.d2_features(c[0], pan, 'AAA', 2023, 3)
    check(fw == ('WR|1|1', 2, 2), f'at W=3 the week-3 row is not read ({fw})')
    check(abs(F.d2_q('ROLE', PARAMS, 'WR', 'WR|1|1', 3, 3) - (3 + 2 * 0.9) / 5) < 1e-12, 'ROLE q uses the role prior')
    check(abs(F.d2_q('ROLE', PARAMS, 'WR', 'WR|2|0', 1, 3) - (1 + 2 * 0.4) / 5) < 1e-12, 'an unfitted role falls back to the position')
    check(abs(F.d2_q('SHRINK', PARAMS, 'WR', 'x', 1, 3) - (1 + 5 * 0.6) / 8) < 1e-12, 'SHRINK q uses the pooled prior')
    check(F.d2_q('NONE', PARAMS, 'WR', 'x', 0, 9) == 1.0, 'NONE q = 1')
    try:
        F.d2_q('BOGUS', PARAMS, 'WR', 'x', 0, 1)
        check(False, 'an unknown arm refuses')
    except ValueError:
        check(True, 'an unknown arm refuses')


def test_reweight_preserves_club_totals_and_current_is_a_no_op():
    pan = _panel()
    for arm in (None, 'CURRENT'):
        F._CLUB_WEEKS.clear()
        c = _crows()
        F.reweight_appearance(c, pan, 'AAA', 2023, 4, arm, PARAMS)
        check([r['targets'] for r in c] == [10.0, 6.0, 4.0], f'arm {arm}: targets unchanged')
    for arm in ('NONE', 'SHRINK', 'ROLE'):
        F._CLUB_WEEKS.clear()
        c = _crows()
        F.reweight_appearance(c, pan, 'AAA', 2023, 4, arm, PARAMS)
        check(abs(sum(r['targets'] for r in c) - 20.0) < 1e-9, f'arm {arm}: the club total 20 is preserved')
    F._CLUB_WEEKS.clear()
    c = _crows()
    F.reweight_appearance(c, pan, 'AAA', 2023, 4, 'ROLE', PARAMS)
    check(c[1]['targets'] < 6.0 and c[0]['targets'] > 10.0,
          f"ROLE moves volume from the player who missed his club's last game to the regular ({[round(r['targets'], 3) for r in c]})")
    c = _crows()
    c[2]['p_plays']['targets'] = 0.0
    F._CLUB_WEEKS.clear()
    F.reweight_appearance(c, pan, 'AAA', 2023, 4, 'ROLE', PARAMS)
    check(c[2]['targets'] == 4.0 and abs(c[0]['targets'] + c[1]['targets'] - 16.0) < 1e-9,
          'a player with p = 0 is left unchanged and excluded from the renormalisation')


def test_golden_current_reproduces_the_incumbent_chain():
    po = P.load_panel()
    saved = (F.D2_ARM[0], F.PER_PLAYER_SINK_DFS, F.D2_FEATURE_SINK)

    def run():
        F.PER_PLAYER_SINK_DFS = []
        F.evaluate(po.value, P.position_index(), [2023], [('PROD', 1.0, None)], max_weeks=2)
        return list(F.PER_PLAYER_SINK_DFS)
    try:
        F.D2_ARM[0] = None
        base = run()
        F.D2_ARM[0] = 'CURRENT'
        F.D2_FEATURE_SINK = []
        cur = run()
        check(len(base) > 0 and cur == base, f'CURRENT with the feature sink on reproduces the incumbent rows exactly ({len(base)})')
        check(len(F.D2_FEATURE_SINK) > 0, f'the feature sink recorded pool players ({len(F.D2_FEATURE_SINK)})')
        F.D2_FEATURE_SINK = None
        F.D2_ARM[0] = 'NONE'
        none = run()
        check(none != base and len(none) == len(base), 'NONE changes projections but not the row set')
    finally:
        F.D2_ARM[0], F.PER_PLAYER_SINK_DFS, F.D2_FEATURE_SINK = saved


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

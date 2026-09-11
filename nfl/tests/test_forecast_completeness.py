"""Orchestration success is not forecast completeness, and the code says so.

THE DEFECT THIS FILE EXISTS FOR.

The slate runner reported "12 games complete / 0 blocked" for 2026-09-13.
Every one of those boards had sealed, and every one carried ONLY the
quarterback layer -- six to nine players, no rushing, no receiving, no
touchdown allocation -- because those clubs filed injury rows with
report_status unset and the appearance layer correctly deferred.
Orchestration had succeeded completely; the football forecast had not.

Every verdict here is computed from whether a declared layer produced a real
stored distribution. None is read from a status string.
"""
from __future__ import annotations

import glob
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import daily_board as PB                            # noqa: E402
from nfl.research import completeness as CP                          # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _load(gid, cand='R8'):
    fs = [f for f in sorted(glob.glob(
        f'{_ROOT}/nfl/research/live/{gid}/**/board.json', recursive=True))
        if cand in f]
    if not fs:
        return None
    d = pathlib.Path(fs[0]).parent
    mj = d / 'player_draws_manifest.json'
    return (json.load(open(fs[0])),
            json.load(open(mj)) if mj.exists() else None,
            PB._load_draws(d))


def test_a_a_constant_row_is_not_a_distribution():
    """An all-zero row has the right SHAPE and carries no information."""
    man = {'layers': {'rushing': {'row_ids': ['a', 'b']}}}
    zeros = {'rushing__carries': np.zeros((2, 100))}
    ok, why = CP._has_distribution(zeros, man, 'rushing/carries')
    check('an all-zero metric is NOT a distribution', not ok, str(why))
    const = {'rushing__carries': np.full((2, 100), 7.0)}
    ok2, why2 = CP._has_distribution(const, man, 'rushing/carries')
    check('  a constant non-zero metric is not one either', not ok2, str(why2))
    real = {'rushing__carries': np.vstack([np.zeros(100),
                                           np.arange(100, dtype=float)])}
    ok3, _ = CP._has_distribution(real, man, 'rushing/carries')
    check('  but one varying row is enough to count', ok3)
    ok4, why4 = CP._has_distribution(None, man, 'rushing/carries')
    check('  and absent draws say so by name', not ok4, str(why4))


def test_b_a_qb_only_board_is_reported_as_qb_only():
    got = _load('2026_01_BUF_HOU')
    if not got:
        print('  ..   no sealed BUF_HOU board; skipped')
        return
    board, man, draws = got
    mx = CP.layer_matrix(board, man, draws)
    check('the board sealed', board.get('pipeline_status') == 'SEALED',
          str(board.get('pipeline_status')))
    check('  and is nonetheless QB_ONLY',
          CP.forecast_completeness(mx) == 'QB_ONLY',
          CP.forecast_completeness(mx))
    for lay in CP.QB_LAYERS + ('team_volume',):
        check(f'  {lay} PASS', mx[lay] == 'PASS', mx[lay])
    for lay in CP.NONQB_LAYERS:
        check(f'  {lay} is deferred, and names the real cause',
              mx[lay].startswith('DEFERRED_INJURY'), mx[lay])


def test_c_a_complete_board_is_reported_as_full():
    got = _load('2026_01_SF_LA')
    if not got:
        print('  ..   no sealed SF_LA board; skipped')
        return
    board, man, draws = got
    mx = CP.layer_matrix(board, man, draws)
    check('every declared layer produced a distribution',
          all(v == 'PASS' for v in mx.values()),
          str({k: v for k, v in mx.items() if v != 'PASS'}))
    check('  so the verdict is FULL',
          CP.forecast_completeness(mx) == 'FULL',
          CP.forecast_completeness(mx))


def test_d_completeness_is_per_market_not_per_game():
    """The point of item 3: do not make a whole game binary."""
    qb_only = {k: ('PASS' if k in CP.QB_LAYERS + ('team_volume',)
                   else 'DEFERRED_INJURY_REPORT_INCOMPLETE')
               for k in CP.LAYER_NAMES}
    ok, miss = CP.market_rankable('qb/pyds', qb_only)
    check('QB passing yards STAYS rankable when its path is intact',
          ok and not miss, str(miss))
    ok2, miss2 = CP.market_rankable('rushing/carries', qb_only)
    check('  RB carries does not, and names the missing layer',
          not ok2 and miss2 == ['carries'], str(miss2))
    ok3, miss3 = CP.market_rankable('receiving/receiving_yards', qb_only)
    check('  receiving yards names its whole broken path',
          not ok3 and set(miss3) == {'targets', 'receptions',
                                     'receiving_yards'}, str(miss3))
    ok4, miss4 = CP.market_rankable('receiving/receptions', qb_only)
    check('  receptions needs targets AND receptions',
          not ok4 and set(miss4) == {'targets', 'receptions'}, str(miss4))
    unknown, why = CP.market_rankable('made/up', qb_only)
    check('  a market with no declared causal path is never rankable',
          not unknown and why == ['MARKET_HAS_NO_DECLARED_CAUSAL_PATH'],
          str(why))


def test_e_the_four_completeness_states_are_distinguished():
    allp = {k: 'PASS' for k in CP.LAYER_NAMES}
    check('all layers -> FULL', CP.forecast_completeness(allp) == 'FULL')
    qb = {k: ('PASS' if k in CP.QB_LAYERS + ('team_volume',) else 'DEFERRED_X')
          for k in CP.LAYER_NAMES}
    check('QB layers only -> QB_ONLY',
          CP.forecast_completeness(qb) == 'QB_ONLY')
    mixed = dict(allp)
    mixed['td_allocation'] = 'DEFERRED_X'
    check('some of each -> PARTIAL',
          CP.forecast_completeness(mixed) == 'PARTIAL')
    none = {k: 'BLOCKED_X' for k in CP.LAYER_NAMES}
    check('nothing at all -> NO_USABLE_FORECAST',
          CP.forecast_completeness(none) == 'NO_USABLE_FORECAST')
    # A NON-QB-ONLY partial must not be mislabelled QB_ONLY.
    rb = dict(none)
    rb['team_volume'] = rb['carries'] = 'PASS'
    check('  non-QB layers without QB layers is PARTIAL, not QB_ONLY',
          CP.forecast_completeness(rb) == 'PARTIAL',
          CP.forecast_completeness(rb))


def test_f_the_slate_summary_never_collapses_to_complete_slash_blocked():
    per = {
        'g1': {'forecast_completeness': 'QB_ONLY',
               'layer_matrix': {'carries': 'DEFERRED_INJURY_REPORT_INCOMPLETE'}},
        'g2': {'forecast_completeness': 'FULL', 'layer_matrix': {}},
        'g3': {'forecast_completeness': 'NO_USABLE_FORECAST',
               'layer_matrix': {}},
    }
    s = CP.summarise(per)
    check('full, partial, qb-only and unusable are counted apart',
          (s['games_fully_modeled'], s['games_qb_only'],
           s['games_unusable']) == (1, 1, 1), str(s))
    check('  and games awaiting injury information are counted',
          s['games_awaiting_injury_information'] == 1, str(s))
    check('  every completeness state has its own counter',
          len({'games_fully_modeled', 'games_partially_modeled',
               'games_qb_only', 'games_unusable'} & set(s)) == 4, str(sorted(s)))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

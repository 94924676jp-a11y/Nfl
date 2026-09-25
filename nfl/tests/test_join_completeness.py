"""The completeness contract, including every refusal it can raise.

A test that only exercises the success path proves a contract can pass, which
is not the property anybody needs from a contract. 524 of 949 refusal codes in
this repository had no test reference when this file was written; these do.

The regression at the bottom is the real one: the 2026-09-24 Showdown universe.
"""
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.contracts import completeness as CC       # noqa: E402
from nfl.dfs import player_universe as PU                     # noqa: E402

FAIL = []


def check(label, fn):
    try:
        fn()
        print(f'  ok    {label}')
    except AssertionError as e:
        FAIL.append(f'{label}: {e}')
        print(f'  FAIL  {label}: {e}')
    except Exception as e:                                     # noqa: BLE001
        FAIL.append(f'{label}: unexpected {type(e).__name__}: {e}')
        print(f'  ERROR {label}: {type(e).__name__}: {e}')


def raises(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        assert needle is None or needle in str(e), \
            f'raised {exc.__name__} without {needle!r}: {e}'
        return
    raise AssertionError(f'did not raise {exc.__name__}')


# ---- policy ---------------------------------------------------------------
def t_default_is_refusal():
    pol, reason = CC.policy_for('a.consumer.nobody.declared')
    assert pol == CC.REQUIRES_COMPLETE, pol
    assert reason is None


def t_permits_partial_needs_reason():
    CC.CONSUMER_POLICY['tmp.bad'] = (CC.PERMITS_PARTIAL, None)
    try:
        raises(CC.PolicyUndeclared, lambda: CC.policy_for('tmp.bad'),
               'no reason recorded')
    finally:
        del CC.CONSUMER_POLICY['tmp.bad']


# ---- report construction --------------------------------------------------
def t_empty_expected_refused():
    raises(CC.JoinIncomplete,
           lambda: CC.join_report('j', [], [], [], []),
           'expected_keys is empty')


def t_complete_join():
    r = CC.join_report('j', ['a', 'b'], ['a', 'b'], ['a', 'b'], ['a', 'b'])
    assert r['complete'] is True
    assert r['coverage'] == 1.0
    assert CC.assert_complete(r, 'dfs.showdown.selector')['verdict'] == 'COMPLETE'


def t_missing_right_is_upstream():
    """Priced and never modelled: the kicker shape."""
    r = CC.join_report('j', ['a', 'k'], ['a', 'k'], ['a'], ['a'])
    assert r['missing_right'] == ['k'], r['missing_right']
    assert r['dropped_rows'] == [], r['dropped_rows']
    assert r['coverage'] == 0.5


def t_dropped_is_not_missing():
    """Present on both sides and absent from output is a DROP, not an absence.

    These must never collapse into one field: an absence is an upstream gap and
    a drop is a decision this join made.
    """
    r = CC.join_report('j', ['a', 'b'], ['a', 'b'], ['a', 'b'], ['a'])
    assert r['dropped_rows'] == ['b'], r['dropped_rows']
    assert r['missing_right'] == [], r['missing_right']


def t_unmatched_identity_blocks_even_at_full_coverage():
    r = CC.join_report('j', ['a'], ['a'], ['a'], ['a'],
                       unmatched_identities=['b robinson'])
    assert r['coverage'] == 1.0
    assert r['complete'] is False, 'an unresolved identity is not completeness'


def t_refusal_names_the_side():
    r = CC.join_report('j', ['a', 'k'], ['a', 'k'], ['a'], ['a'])
    raises(CC.JoinIncomplete,
           lambda: CC.assert_complete(r, 'dfs.showdown.selector'),
           'never produced upstream')


def t_partial_permitted_for_a_diagnostic():
    r = CC.join_report('j', ['a', 'k'], ['a', 'k'], ['a'], ['a'])
    out = CC.assert_complete(r, 'tools.pool_audit')
    assert out['verdict'] == 'PARTIAL_PERMITTED', out['verdict']
    assert out['policy_reason'], 'a permission must carry its reason'


# ---- layer discovery ------------------------------------------------------
def t_layers_discovered_not_listed():
    man = {'layers': {
        'dk_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']},
        'kicking': {'row_axis': 'gsis_id', 'metrics': ['fga', 'dk_points']},
        'team_volume': {'row_axis': 'team', 'metrics': ['dk_points']},
        'receiving': {'row_axis': 'gsis_id', 'metrics': ['targets']}}}
    assert PU.dk_bearing_layers(man) == ['dk_scoring', 'kicking']


def t_a_new_scoring_layer_is_picked_up_with_no_edit():
    """The property that makes this a fix and not a patch for one instance."""
    man = {'layers': {
        'dk_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']},
        'dst_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']}}}
    assert 'dst_scoring' in PU.dk_bearing_layers(man)


def t_no_dk_layer_refuses():
    raises(CC.JoinIncomplete,
           lambda: PU.dk_bearing_layers(
               {'layers': {'receiving': {'row_axis': 'gsis_id',
                                         'metrics': ['targets']}}}),
           'must not be faked')


def t_empty_salary_file_refuses(tmp='/tmp/_pu_empty.csv'):
    open(tmp, 'w').write('nothing,useful\n')
    try:
        raises(CC.JoinIncomplete, lambda: PU.priced(tmp), 'no priced rows')
    finally:
        os.unlink(tmp)


def t_norm_is_declared_and_not_fuzzy():
    assert PU.norm('Brian Robinson Jr.') == PU.norm('brian robinson')
    assert PU.norm('Bijan Robinson') != PU.norm('Brian Robinson Jr.'), \
        'two real players must never collapse to one key'


# ---- the 2026-09-24 regression -------------------------------------------
_ART = os.path.join(
    _ROOT, 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1')


def t_20260924_showdown_universe_would_have_refused():
    """The defect this module exists for, on the real artifact.

    A selector reading `dk_scoring` alone got 27 of 29 players and reported ten
    finished lineups. The contract must refuse, and must name the players it
    could not cover rather than returning a shorter list that looks whole.
    """
    man = os.path.join(_ART, 'player_draws_manifest.json')
    if not os.path.exists(man):
        print('  skip  2026-09-24 regression (artifact absent)')
        return
    layers = PU.dk_bearing_layers(json.loads(open(man).read()))
    assert layers == ['dk_scoring', 'kicking'], layers
    z = np.load(os.path.join(_ART, 'player_draws.npz'), allow_pickle=True)
    assert 'kicking__dk_points' in z.files
    kick_rows = json.loads(open(man).read())['layers']['kicking']['row_ids']
    dk_rows = set(json.loads(open(man).read())['layers']['dk_scoring']['row_ids'])
    assert not (set(kick_rows) & dk_rows), \
        'kickers are a separate universe; that is why the join is mandatory'


if __name__ == '__main__':
    print('join completeness contract')
    for name, fn in sorted(globals().items()):
        if name.startswith('t_') and callable(fn):
            check(name[2:], fn)
    print()
    if FAIL:
        print(f'{len(FAIL)} failure(s)')
        raise SystemExit(1)
    print('all pass')

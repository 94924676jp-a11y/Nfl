"""The completeness contract, including every refusal it can raise.

A test that only exercises the success path proves a contract can pass, which
is not the property anybody needs from a contract. 524 of 949 refusal codes in
this repository had no test reference when this file was written; these do.

The regression at the bottom is the real one: the 2026-09-24 Showdown universe.

NOTE ON FORM. The first version of this file named its functions `t_*` and kept
its own failure list, so `run_suite.py` reported it as `0 fn, NO TALLY` and
every check in it was invisible to the suite -- the same false-green shape the
runner's own comment records for four modules written on 2026-09-21. It is
written to the runner's convention here because a test the measurement system
cannot see has not run.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.contracts import completeness as CC       # noqa: E402
from nfl.dfs import player_universe as PU                     # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    """(did_raise_with_needle, detail)."""
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                     # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def test_A_policy_defaults_to_refusal():
    print('\nA. an unclassified consumer gets the safe behaviour')
    pol, reason = CC.policy_for('a.consumer.nobody.declared')
    check('unknown consumer REQUIRES_COMPLETE', pol == CC.REQUIRES_COMPLETE, pol)
    check('and carries no permission reason', reason is None, repr(reason))
    CC.CONSUMER_POLICY['tmp.bad'] = (CC.PERMITS_PARTIAL, None)
    try:
        ok, d = raised(CC.PolicyUndeclared,
                       lambda: CC.policy_for('tmp.bad'), 'no reason recorded')
        check('PERMITS_PARTIAL without a reason is an error', ok, d)
    finally:
        del CC.CONSUMER_POLICY['tmp.bad']


def test_B_report_construction():
    print('\nB. the report cannot be made vacuously complete')
    ok, d = raised(CC.JoinIncomplete,
                   lambda: CC.join_report('j', [], [], [], []),
                   'expected_keys is empty')
    check('an empty requirement is refused', ok, d)
    r = CC.join_report('j', ['a', 'b'], ['a', 'b'], ['a', 'b'], ['a', 'b'])
    check('a complete join reads complete', r['complete'] is True, r)
    check('coverage is 1.0', r['coverage'] == 1.0, r['coverage'])
    out = CC.assert_complete(r, 'dfs.showdown.selector')
    check('and a strict consumer proceeds', out['verdict'] == 'COMPLETE',
          out['verdict'])


def test_C_missing_and_dropped_never_collapse():
    print('\nC. an upstream absence is not a decision this join made')
    r = CC.join_report('j', ['a', 'k'], ['a', 'k'], ['a'], ['a'])
    check('priced and unmodelled lands in missing_right',
          r['missing_right'] == ['k'], r['missing_right'])
    check('and NOT in dropped_rows', r['dropped_rows'] == [], r['dropped_rows'])
    check('coverage halves', r['coverage'] == 0.5, r['coverage'])
    r2 = CC.join_report('j', ['a', 'b'], ['a', 'b'], ['a', 'b'], ['a'])
    check('present on both sides and absent from output is a DROP',
          r2['dropped_rows'] == ['b'], r2['dropped_rows'])
    check('and NOT an upstream absence', r2['missing_right'] == [],
          r2['missing_right'])


def test_D_unmatched_identity_blocks_at_full_coverage():
    print('\nD. coverage is not the only completeness question')
    r = CC.join_report('j', ['a'], ['a'], ['a'], ['a'],
                       unmatched_identities=['b robinson'])
    check('coverage still reads 1.0', r['coverage'] == 1.0, r['coverage'])
    check('but the join is not complete', r['complete'] is False, r)


def test_E_refusal_names_which_side():
    print('\nE. an operator needs to know WHERE the keys went')
    r = CC.join_report('j', ['a', 'k'], ['a', 'k'], ['a'], ['a'])
    ok, d = raised(CC.JoinIncomplete,
                   lambda: CC.assert_complete(r, 'dfs.showdown.selector'),
                   'never produced upstream')
    check('the refusal names the side', ok, d)
    out = CC.assert_complete(r, 'tools.pool_audit')
    check('a diagnostic proceeds', out['verdict'] == 'PARTIAL_PERMITTED',
          out['verdict'])
    check('carrying its written reason', bool(out['policy_reason']), out)


def test_F_layers_are_discovered_not_listed():
    print('\nF. the property that makes this a fix and not a patch')
    man = {'layers': {
        'dk_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']},
        'kicking': {'row_axis': 'gsis_id', 'metrics': ['fga', 'dk_points']},
        'team_volume': {'row_axis': 'team', 'metrics': ['dk_points']},
        'receiving': {'row_axis': 'gsis_id', 'metrics': ['targets']}}}
    check('player-keyed dk_points layers only',
          PU.dk_bearing_layers(man) == ['dk_scoring', 'kicking'],
          PU.dk_bearing_layers(man))
    man2 = {'layers': {
        'dk_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']},
        'dst_scoring': {'row_axis': 'gsis_id', 'metrics': ['dk_points']}}}
    check('a NEW scoring layer is picked up with no edit here',
          'dst_scoring' in PU.dk_bearing_layers(man2),
          PU.dk_bearing_layers(man2))
    ok, d = raised(CC.JoinIncomplete,
                   lambda: PU.dk_bearing_layers(
                       {'layers': {'receiving': {'row_axis': 'gsis_id',
                                                 'metrics': ['targets']}}}),
                   'must not be faked')
    check('an artifact with no DK layer is refused', ok, d)


def test_G_inputs_that_look_fine_and_are_empty():
    print('\nG. zeros and empties are errors, not results')
    tmp = '/tmp/_pu_empty_universe.csv'
    with open(tmp, 'w') as fh:
        fh.write('nothing,useful\n')
    try:
        ok, d = raised(CC.JoinIncomplete, lambda: PU.priced(tmp),
                       'no priced rows')
        check('a salary file yielding nothing is refused', ok, d)
    finally:
        os.unlink(tmp)
    check('declared normalisation joins a suffix variant',
          PU.norm('Brian Robinson Jr.') == PU.norm('brian robinson'))
    check('and never collapses two real players',
          PU.norm('Bijan Robinson') != PU.norm('Brian Robinson Jr.'))


def test_H_20260924_regression():
    print('\nH. the 2026-09-24 Showdown universe, on the real artifact')
    art = _REPO / 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1'
    man_p = art / 'player_draws_manifest.json'
    if not man_p.exists():
        check('artifact present', False, f'{man_p} absent')
        return
    man = json.loads(man_p.read_text())
    check('two DK-bearing layers are discovered',
          PU.dk_bearing_layers(man) == ['dk_scoring', 'kicking'],
          PU.dk_bearing_layers(man))
    z = np.load(art / 'player_draws.npz', allow_pickle=True)
    check('the kicking DK array exists', 'kicking__dk_points' in z.files)
    kick = set(man['layers']['kicking']['row_ids'])
    dk = set(man['layers']['dk_scoring']['row_ids'])
    check('kickers are a SEPARATE universe, which is why the join is mandatory',
          not (kick & dk), sorted(kick & dk))

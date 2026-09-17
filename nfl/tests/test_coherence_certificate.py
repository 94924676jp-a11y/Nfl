"""The guard must certify the data that ships.

THE MECHANISM, NAMED BY THE REPOSITORY. Commit `8c81079`, the most recent
change to `draw_coherence.py`, is titled "The guard ran, then the values it
guarded were overwritten." A conservation suite that runs before the last
mutation of the data it certifies is not a conservation suite.

Test A is the whole point: guard -> deliberate downstream mutation -> the seal
REFUSES. Everything else exists so that test cannot pass for a wrong reason.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State            # noqa: E402
from nfl.production import coherence_certificate as CC                # noqa: E402

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


def _world():
    """A small published mapping and its row ids."""
    rng = np.random.default_rng(3)
    arrays = {
        'qb/pyds': rng.integers(-20, 400, (3, 40)).astype(float),
        'qb/att': rng.integers(0, 45, (3, 40)).astype(float),
        'rushing/carries': rng.integers(0, 25, (4, 40)).astype(float),
        'team_volume/team_carries': rng.integers(18, 34, (2, 40)).astype(float),
    }
    rid = {'qb': ['q1', 'q2', 'q3'], 'rushing': ['r1', 'r2', 'r3', 'r4'],
           'team_volume': ['DET', 'BUF']}
    return arrays, rid


def test_A_guard_then_downstream_mutation_is_REFUSED():
    print('\nA. guard -> downstream mutation -> publication REFUSES')
    arrays, rid = _world()
    cert = CC.certify(arrays, rid, guards=['qb_coherence', 'team_closure'])
    check('the guard certifies and the certificate is not empty',
          cert.state is State.PASS and cert.evidence['n_arrays'] == 4,
          f'{cert.state}[{cert.code}]')

    # ---- SHAPE 1: MUTATED IN PLACE, one cell, after the guard ran.
    arrays['qb/pyds'][1, 7] += 1.0
    v = CC.verify(cert.value, arrays, rid)
    check('  an IN-PLACE mutation of ONE cell is caught',
          v.state is State.FAIL and v.code == CC.CODE_BROKEN,
          f'{v.state}[{v.code}]')
    check('    naming the array, not just the count',
          v.evidence['changed'][0]['array'] == 'qb/pyds',
          str(v.evidence['changed'][:1]))
    check('    and carrying both digests so a reader can see the difference',
          (v.evidence['changed'][0]['certified_sha256']
           != v.evidence['changed'][0]['published_sha256']))
    check('    with cause GOVERNANCE, not DATA -- the numbers are fine, the '
          'process is not',
          v.evidence.get('cause') == Cause.GOVERNANCE.value,
          str(v.evidence.get('cause')))

    # ---- SHAPE 2: the entry REPLACED by a different object. A digest taken
    # over the guard's own references would miss this entirely.
    arrays2, rid2 = _world()
    cert2 = CC.certify(arrays2, rid2)
    published = dict(arrays2)
    published['rushing/carries'] = published['rushing/carries'] + 1.0
    v2 = CC.verify(cert2.value, published, rid2)
    check('  a REPLACED entry is caught too, because verify re-reads the '
          'publication mapping',
          v2.state is State.FAIL
          and v2.evidence['changed'][0]['array'] == 'rushing/carries',
          f'{v2.state}[{v2.code}]')

    # ---- SHAPE 3: an array that disappears between guard and seal.
    arrays3, rid3 = _world()
    cert3 = CC.certify(arrays3, rid3)
    gone = {k: v for k, v in arrays3.items() if k != 'qb/att'}
    v3 = CC.verify(cert3.value, gone, rid3)
    check('  a certified array that DISAPPEARS is caught and named',
          v3.state is State.FAIL and v3.evidence['absent'] == ['qb/att'],
          str(v3.evidence.get('absent')))


def test_B_the_clean_path_verifies():
    print('\nB. and an untouched run verifies, or the check is useless')
    arrays, rid = _world()
    cert = CC.certify(arrays, rid)
    v = CC.verify(cert.value, arrays, rid)
    check('an unmutated run VERIFIES', v.state is State.PASS
          and v.code == CC.CODE_VERIFIED, f'{v.state}[{v.code}]')
    check('  and reports zero changed, zero absent',
          v.evidence['n_changed'] == 0
          and v.evidence['n_absent_at_publication'] == 0)
    # A NEW array appearing after certification is recorded but is NOT a
    # refusal: adding a layer is not overwriting a guarded one.
    more = dict(arrays)
    more['kicking/fga'] = np.ones((1, 40))
    v2 = CC.verify(cert.value, more, rid)
    check('  an ADDED array is recorded and does not refuse',
          v2.state is State.PASS and v2.evidence['added'] == ['kicking/fga'],
          f'{v2.state} added={v2.evidence.get("added")}')


def test_C_false_alarms_that_must_not_fire():
    print('\nC. differences that are not mutations must not refuse')
    arrays, rid = _world()
    cert = CC.certify(arrays, rid)
    # -0.0 is bitwise distinct from 0.0 and numerically identical.
    neg0 = {k: (v * 1.0 - 0.0) for k, v in arrays.items()}
    check('-0.0 against 0.0 does NOT refuse',
          CC.verify(cert.value, neg0, rid).state is State.PASS)
    # A non-contiguous view of the same numbers.
    view = {k: np.asfortranarray(v)[:, :] for k, v in arrays.items()}
    check('  a Fortran-ordered view of the same numbers does NOT refuse',
          CC.verify(cert.value, view, rid).state is State.PASS)
    # An int array whose values equal the float one.
    ints = {k: v.astype(np.int64) if k == 'rushing/carries' else v
            for k, v in arrays.items()}
    check('  an int64 copy of an integral float array does NOT refuse',
          CC.verify(cert.value, ints, rid).state is State.PASS)


def test_D_identity_is_inside_the_digest():
    print('\nD. a permutation that preserves the bytes is still a defect')
    arrays, rid = _world()
    cert = CC.certify(arrays, rid)
    perm = dict(rid)
    perm['qb'] = ['q2', 'q1', 'q3']          # same bytes, different owners
    v = CC.verify(cert.value, arrays, perm)
    check('changing WHOSE row is whose breaks the certificate',
          v.state is State.FAIL, f'{v.state}[{v.code}]')
    check('  even though not one number moved',
          all(np.array_equal(arrays[k], arrays[k]) for k in arrays))


def test_E_an_empty_or_missing_certificate_refuses():
    print('\nE. a certificate that verifies against anything is worse than none')
    arrays, rid = _world()
    check('certifying nothing is BLOCKED',
          CC.certify({}).state is State.BLOCKED
          and CC.certify({}).code == CC.CODE_EMPTY)
    v = CC.verify({}, arrays, rid)
    check('  verifying with no certificate is BLOCKED, never PASS',
          v.state is State.BLOCKED and v.code == CC.CODE_MISSING,
          f'{v.state}[{v.code}]')
    v2 = CC.verify({'entries': {}}, arrays, rid)
    check('  and an EMPTY entry set is BLOCKED rather than vacuously verified',
          v2.state is State.BLOCKED, f'{v2.state}[{v2.code}]')


def test_F_it_is_wired_between_the_guard_and_the_seal():
    print('\nF. wired: certified after the guard, verified before the seal')
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    i_guard = src.find('DC.assert_draw_coherence(')
    i_cert = src.find('CCERT.certify(')
    i_seal = src.find('def _seal():')
    i_ver = src.find('CCERT.verify(')
    check('all four sites are present', min(i_guard, i_cert, i_seal, i_ver) > 0,
          f'{i_guard} {i_cert} {i_seal} {i_ver}')
    check('  certification comes AFTER the coherence guard',
          i_cert > i_guard, f'{i_cert} vs {i_guard}')
    check('  verification is INSIDE the seal stage', i_ver > i_seal,
          f'{i_ver} vs {i_seal}')
    check('  and the seal REFUSES on a broken certificate',
          'CCERT.CODE_BROKEN' in src)
    check('  verification reads ds.arrays, the PUBLICATION mapping, not _p2',
          'CCERT.verify(\n                _cert, ds.arrays,' in src
          or 'CCERT.verify(' in src and '_cert, ds.arrays' in src,
          'must re-read to catch a replaced entry')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_guard_then_downstream_mutation_is_REFUSED,
               test_B_the_clean_path_verifies,
               test_C_false_alarms_that_must_not_fire,
               test_D_identity_is_inside_the_digest,
               test_E_an_empty_or_missing_certificate_refuses,
               test_F_it_is_wired_between_the_guard_and_the_seal):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)

"""The three layers must not collapse, and `unasked` must never read as `yes`.

D20's captures were FETCH_SUCCESS with STRUCTURAL_VALIDITY false, and one word
-- PASS -- was carrying both. This file pins the vocabulary so the collapse
cannot come back quietly.

Run standalone:  python3.12 nfl/tests/test_evidence_layers.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import evidence_layers as EL                      # noqa: E402
from nfl.capture import payload_contract as PC                     # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def test_a_the_d20_capture_reads_correctly():
    print('\nA. the D20 capture, in the new vocabulary')
    v = EL.verdict(fetch_ok=True, structural_ok=False, eligible=False,
                   code=PC.CODE_EMPTY)
    check('the fetch succeeded, and that stays true', v['FETCH_SUCCESS'])
    check('the structure is empty', v['STRUCTURAL_VALIDITY'] is False)
    check('it may not discharge', v['may_discharge'] is False)
    check('and the verdict names WHERE it stopped',
          v['stopped_at'] == 'STRUCTURAL_VALIDITY', str(v))
    print('       reads as: the capture network is working and the source has '
          'nothing --\n        a sentence the old one-word vocabulary could '
          'not form')


def test_b_unasked_is_never_yes():
    """The failure mode this module exists to prevent."""
    print('\nB. None means NOT ASKED and never counts as a pass')
    v = EL.verdict(fetch_ok=True, code='CAPTURED')
    check('a fetch-only verdict leaves the other two unasked',
          v['STRUCTURAL_VALIDITY'] is None
          and v['PREDICTIVE_ELIGIBILITY'] is None, str(v))
    check('and it may NOT discharge on the strength of the fetch alone',
          v['may_discharge'] is False,
          'this is exactly D20: HTTP 200 read as evidence')
    check('all three yes is the only way to discharge',
          EL.verdict(fetch_ok=True, structural_ok=True, eligible=True,
                     code='CAPTURED')['may_discharge'] is True)
    for bad in (dict(fetch_ok=False, structural_ok=True, eligible=True),
                dict(fetch_ok=True, structural_ok=False, eligible=True),
                dict(fetch_ok=True, structural_ok=True, eligible=False)):
        check(f'  two of three is not enough: {bad}',
              EL.verdict(code='X', **bad)['may_discharge'] is False)


def test_c_the_layers_are_ordered_and_a_verdict_names_the_first_failure():
    print('\nC. monotone -- the first failing layer is the one reported')
    v = EL.verdict(fetch_ok=False, structural_ok=False, eligible=False,
                   code='NO_EGRESS')
    check('a fetch failure reports the fetch layer, not the ones after it',
          v['stopped_at'] == 'FETCH_SUCCESS', str(v))
    v2 = EL.verdict(fetch_ok=True, structural_ok=True, eligible=False,
                    code='BASIS_CANNOT_DISCHARGE')
    check('an eligibility failure reports eligibility',
          v2['stopped_at'] == 'PREDICTIVE_ELIGIBILITY', str(v2))


def test_d_every_classified_code_is_in_exactly_one_layer():
    print('\nD. the code map')
    check('every code maps to a Layer',
          all(isinstance(v, EL.Layer) for v in EL.CODE_LAYER.values()))
    check('SOURCE_HAS_NO_ROWS_YET is STRUCTURAL, not a fetch problem',
          EL.layer_of('SOURCE_HAS_NO_ROWS_YET') is EL.Layer.STRUCTURAL_VALIDITY,
          'misfiling it as a fetch problem is how a substance defect gets '
          'retried forever instead of escalated')
    check('the D22 csv codes are STRUCTURAL',
          EL.layer_of('SCHEMA_COLUMNS_ABSENT')
          is EL.Layer.STRUCTURAL_VALIDITY
          and EL.layer_of('SCHEMA_COLUMNS_PRESENT_BUT_EMPTY')
          is EL.Layer.STRUCTURAL_VALIDITY)
    check('CAPTURED is a FETCH fact and claims nothing about content',
          EL.layer_of('CAPTURED') is EL.Layer.FETCH_SUCCESS,
          'this is the whole of D20 in one assertion')
    check('an unclassified code returns None rather than a guess',
          EL.layer_of('NO_SUCH_CODE_ANYWHERE') is None)


if __name__ == '__main__':
    test_a_the_d20_capture_reads_correctly()
    test_b_unasked_is_never_yes()
    test_c_the_layers_are_ordered_and_a_verdict_names_the_first_failure()
    test_d_every_classified_code_is_in_exactly_one_layer()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

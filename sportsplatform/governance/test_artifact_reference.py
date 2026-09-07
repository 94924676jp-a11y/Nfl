"""Rule 006 tested on the defect it was written for, and on the ways a gate
quietly stops being a gate.

The seeded test the directive names is section B: replace the artifact-read
value with the rounded literal that actually shipped in P4E, and prove the
gate catches it. Section G deletes the guard and proves the catch was the
guard's doing rather than luck.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from governance.outcome import Cause, State
from governance import artifact_reference as A

P = F = 0


def check(l, c, d=''):
    global P, F
    if c:
        P += 1
        print(f'  ok   {l}')
    else:
        F += 1
        print(f'  FAIL {l}  {d}')


# The real numbers. LEFT is p4c_results.json; RIGHT is what P4E's source said.
EXACT = {'2022': 1.9295611633207923, '2023': 1.9972817321788165,
         'C2024': 2.110274841594967, '2025': 2.054493485111525}
SHIPPED_LITERAL = 2.1102566719055176          # the wrong constant, verbatim
EXACT_2024 = 2.110274841594967

TMP = tempfile.mkdtemp(prefix='rule006_')
ART = os.path.join(TMP, 'p4c_results.json')
LOG = os.path.join(TMP, 'run_p4c.log')
with open(ART, 'w') as fh:
    json.dump({'carries': {'2024': {'scores': {'C': {'crps': EXACT_2024,
                                                     'mae': 3.193}}}}}, fh)
with open(LOG, 'w') as fh:
    fh.write('  carries 2024 n= 2166 G=544 CRPS A=2.1744 C=2.1103\n')

SEL = ('carries', '2024', 'scores', 'C', 'crps')


def test_the_p4e_defect():
    print('\nA. THE defect: the gate compared against a number nobody read')
    o = A.read_gate_value(ART, SEL)
    check('the value loads from the artifact', o.state is State.PASS, str(o)[:70])
    ref = o.unwrap()
    check('  and it is the exact float, not the printed one',
          ref.value == EXACT_2024, repr(ref.value))
    check('  carrying the bytes it came from', len(ref.sha256) == 64)
    check('  and saying so in its own description',
          ref.short_sha in ref.describe(), ref.describe())
    good = A.assert_gate(EXACT_2024, ART, SEL, tolerance=1e-9,
                         code='P4E_BASELINE')
    check('a correctly reproduced control passes',
          good.state is State.PASS, str(good)[:70])
    check('  and the run output carries the hash',
          good.evidence['sha256'] == ref.sha256)


def test_the_seeded_rounded_literal():
    print('\nB. SEEDED: swap the artifact read for the rounded literal')
    o = A.assert_gate(SHIPPED_LITERAL, ART, SEL, tolerance=1e-9,
                      code='P4E_BASELINE')
    check('the gate FAILS on the literal that shipped',
          o.state is State.FAIL, str(o)[:70])
    check('  reporting the real difference',
          abs(o.evidence['abs_diff'] - abs(SHIPPED_LITERAL - EXACT_2024)) < 1e-18,
          o.evidence['abs_diff'])
    check('  which is the 1.8e-05 that cost the cycle',
          1.5e-5 < o.evidence['abs_diff'] < 2.0e-5, o.evidence['abs_diff'])
    check('  and it names the transcription signature',
          'agree to 4 decimals' in o.detail, o.detail[-90:])
    # a hand-built reference is the other way the same mistake arrives
    forged = A.ArtifactRef(path=ART, sha256=A._sha256(ART), selector=SEL,
                           value=SHIPPED_LITERAL)
    v = A.verify(forged)
    check('a hand-built ref carrying the literal is refused',
          v.state is State.FAIL, str(v)[:70])
    check('  naming that it did not come from the artifact',
          v.code == 'GATE_VALUE_NOT_FROM_ARTIFACT', v.code)
    check('  and reporting 4 agreeing decimals',
          v.evidence['agreeing_decimals'] == 4,
          v.evidence['agreeing_decimals'])


def test_a_display_rounding_is_never_gate_truth():
    print('\nC. a log is a rendering, not an artifact')
    o = A.read_gate_value(LOG, ('anything',))
    check('reading a gate value out of a .log is BLOCKED',
          o.state is State.BLOCKED, str(o)[:70])
    check('  by GOVERNANCE, not by a defect', o.cause is Cause.GOVERNANCE
          if hasattr(o, 'cause') else o.evidence.get('cause') == 'GOVERNANCE',
          str(o.as_dict())[:90])
    check('  and it says why', 'rounded for display' in o.detail, o.detail[:70])
    for suffix in ('.txt', '.out', '.md'):
        p = os.path.join(TMP, 'x' + suffix)
        open(p, 'w').write('1.0\n')
        check(f'  {suffix} is refused too',
              A.read_gate_value(p, ('a',)).code == 'GATE_SOURCE_IS_DISPLAY_ONLY')


def test_an_absent_or_empty_artifact_is_not_a_pass():
    print('\nD. absence is never success')
    o = A.assert_gate(1.0, os.path.join(TMP, 'nope.json'), SEL,
                      tolerance=1e-9, code='X')
    check('a missing artifact BLOCKS', o.state is State.BLOCKED, str(o)[:60])
    check('  naming the dependency', o.code == 'GATE_ARTIFACT_ABSENT', o.code)
    e = os.path.join(TMP, 'empty.json')
    open(e, 'w').close()
    check('an empty artifact BLOCKS',
          A.read_gate_value(e, SEL).code == 'GATE_ARTIFACT_EMPTY')
    b = os.path.join(TMP, 'bad.json')
    open(b, 'w').write('{not json')
    check('an unparseable artifact BLOCKS',
          A.read_gate_value(b, SEL).code == 'GATE_ARTIFACT_UNPARSEABLE')
    check('a selector that finds nothing FAILS rather than defaulting',
          A.read_gate_value(ART, ('carries', '2099', 'x')).code
          == 'GATE_SELECTOR_NOT_FOUND')
    check('an empty selector is refused',
          A.read_gate_value(ART, ()).code == 'GATE_SELECTOR_MISSING')


def test_the_artifact_must_still_be_the_one_that_was_read():
    print('\nE. a reference is against bytes, not against a path')
    ref = A.read_gate_value(ART, SEL).unwrap()
    check('verify passes while the bytes are unchanged',
          A.verify(ref).state is State.PASS)
    moved = os.path.join(TMP, 'moved.json')
    json.dump({'carries': {'2024': {'scores': {'C': {'crps': EXACT_2024,
                                                     'mae': 9.999}}}}},
              open(moved, 'w'))
    stale = A.ArtifactRef(path=moved, sha256=ref.sha256, selector=SEL,
                          value=ref.value)
    o = A.verify(stale)
    check('a changed artifact under an old hash FAILS',
          o.state is State.FAIL and o.code == 'GATE_ARTIFACT_CHANGED', o.code)
    check('  even though the VALUE still matches',
          o.evidence['expected_sha256'] != o.evidence['actual_sha256'])


def test_a_bare_number_has_no_provenance():
    print('\nF. a float and a loaded value are indistinguishable, so refuse')
    o = A.verify(2.110274841594967)
    check('a bare float cannot be verified',
          o.state is State.FAIL and o.code == 'GATE_VALUE_UNSOURCED', o.code)
    check('  and it says why a typed number is not evidence',
          'typed rather than read' in o.detail, o.detail[-60:])
    try:
        A.assert_gate(1.0, ART, SEL, tolerance=-1e-9, code='X')
        check('a negative tolerance raises', False, 'no raise')
    except A.ArtifactReferenceError as exc:
        check('a negative tolerance raises', 'NEGATIVE_TOLERANCE' in str(exc))


def test_guard_deletion():
    print('\nG. delete the guard and the catch goes away')
    # G1: the value-identity guard inside verify()
    orig = A._same
    try:
        A._same = lambda a, b: True          # guard DELETED
        forged = A.ArtifactRef(path=ART, sha256=A._sha256(ART), selector=SEL,
                               value=SHIPPED_LITERAL)
        check('with _same stubbed true, the rounded literal PASSES',
              A.verify(forged).state is State.PASS)
    finally:
        A._same = orig
    check('and with the guard restored it FAILS again',
          A.verify(A.ArtifactRef(path=ART, sha256=A._sha256(ART), selector=SEL,
                                 value=SHIPPED_LITERAL)).state is State.FAIL)
    # G2: the display-only source guard
    orig_sfx = A.DISPLAY_ONLY_SUFFIXES
    try:
        A.DISPLAY_ONLY_SUFFIXES = ()         # guard DELETED
        o = A.read_gate_value(LOG, ('a',))
        check('with the suffix list emptied, a .log is no longer refused '
              'as display-only', o.code != 'GATE_SOURCE_IS_DISPLAY_ONLY', o.code)
    finally:
        A.DISPLAY_ONLY_SUFFIXES = orig_sfx
    check('and with it restored the .log is refused again',
          A.read_gate_value(LOG, ('a',)).code == 'GATE_SOURCE_IS_DISPLAY_ONLY')


def test_transcription_signature_is_diagnostic_only():
    print('\nH. the rounding signature explains, it never excuses')
    check('it finds the 4-decimal agreement',
          A.transcription_signature(SHIPPED_LITERAL, EXACT_2024) == 4)
    check('an unrelated number has no signature',
          A.transcription_signature(7.0, EXACT_2024) is None)
    check('an identical value has no signature',
          A.transcription_signature(EXACT_2024, EXACT_2024) is None)
    check('and a signature does not make the gate pass',
          A.assert_gate(SHIPPED_LITERAL, ART, SEL, tolerance=1e-9,
                        code='X').state is State.FAIL)


if __name__ == '__main__':
    for t in (test_the_p4e_defect, test_the_seeded_rounded_literal,
              test_a_display_rounding_is_never_gate_truth,
              test_an_absent_or_empty_artifact_is_not_a_pass,
              test_the_artifact_must_still_be_the_one_that_was_read,
              test_a_bare_number_has_no_provenance, test_guard_deletion,
              test_transcription_signature_is_diagnostic_only):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)

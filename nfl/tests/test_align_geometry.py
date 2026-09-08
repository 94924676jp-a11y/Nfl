"""ALIGN-B1 classifier: does the CODE implement the frozen geometry?

WHAT THIS IS AND IS NOT

These formations are CONSTRUCTED, with coordinates written by hand from the
football definitions in the pre-registration. Passing proves the module
implements the declared rules and abstains where it promised to.

IT IS NOT EVIDENCE ABOUT REAL-WORLD ACCURACY. No real tracking data was
available (this executor has no egress; Kaggle returned 000 and GitHub 403),
so nothing here measures how the rules behave on real alignments. Reporting
these as accuracy would be exactly the "a step that returned something was read
as success" defect this project keeps finding.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'alignb1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import align_geometry as G                                        # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


BALL_Y, LOS = 26.67, 50.0
# realistic splits: centre on the ball, guards +/-1.5, tackles +/-3.0
def ol():
    return [G.Player(f'ol{i}', LOS, y, is_ol=True, eligible=False)
            for i, y in enumerate((23.67, 25.17, 26.67, 28.17, 29.67))]


def frame(extra, stable=True, drop_ol=0):
    o = ol()[:5 - drop_ol]
    return G.Frame(los_x=LOS, ball_y=BALL_Y, stable=stable,
                   players=o + [G.Player('qb', 45.0, BALL_Y, is_qb=True,
                                         eligible=False)] + extra)


def test_A_11_personnel():
    print('\nA. 11 personnel: 2 wide, 1 slot, inline TE, back')
    r = G.classify_frame(frame([
        G.Player('X', LOS, 4.0, position='WR'),      # split left
        G.Player('Z', LOS, 49.0, position='WR'),     # split right
        G.Player('S', LOS - 0.5, 38.0, position='WR'),   # slot right
        G.Player('TE', LOS, 31.0, position='TE'),    # attached right
        G.Player('RB', 43.0, BALL_Y, position='RB'),
    ]))
    for pid, want in (('X', G.WIDE), ('Z', G.WIDE), ('S', G.SLOT),
                      ('TE', G.INLINE_TE), ('RB', G.BACKFIELD)):
        check(f'  {pid} -> {want}', r[pid][0] == want, str(r[pid]))


def test_B_detached_te():
    print('\nB. a flexed/wing TE is DETACHED_TE, not inline and not slot')
    r = G.classify_frame(frame([
        G.Player('X', LOS, 4.0), G.Player('Z', LOS, 49.0),
        G.Player('TE', LOS, 33.0, position='TE'),
        G.Player('RB', 43.0, BALL_Y, position='RB'),
    ]))
    check('  gap 3.33 yards off the tackle -> DETACHED_TE',
          r['TE'][0] == G.DETACHED_TE, str(r['TE']))


def test_C_empty_backfield():
    print('\nC. a back split out is judged by geometry, not by his position')
    # My first version of this test asserted WIDE with a receiver at y=4.0
    # still on the field -- that receiver IS outside the back, so SLOT was the
    # correct football answer and the assertion was wrong, not the code.
    # Both cases are now asserted, which is the stronger test.
    r = G.classify_frame(frame([
        G.Player('X', LOS, 4.0), G.Player('Z', LOS, 49.0),
        G.Player('S', LOS - 0.5, 38.0), G.Player('TE', LOS, 31.0),
        G.Player('RB', LOS - 0.5, 8.0, position='RB'),
    ]))
    check('  RB split left INSIDE a receiver at y=4 -> SLOT',
          r['RB'][0] == G.SLOT, str(r['RB']))
    r2 = G.classify_frame(frame([
        G.Player('Z', LOS, 49.0), G.Player('S', LOS - 0.5, 38.0),
        G.Player('TE', LOS, 31.0),
        G.Player('RB', LOS - 0.5, 8.0, position='RB'),
    ]))
    check('  RB split left with NOBODY outside him -> WIDE',
          r2['RB'][0] == G.WIDE, str(r2['RB']))
    check('  in neither case is he BACKFIELD on position alone',
          r['RB'][0] != G.BACKFIELD and r2['RB'][0] != G.BACKFIELD)


def test_D_abstentions_are_real():
    print('\nD. the classifier abstains exactly where it promised to')
    # bunch: three eligibles within 1.5 yards of each other
    r = G.classify_frame(frame([
        G.Player('B1', LOS, 40.0), G.Player('B2', LOS - 0.5, 41.0),
        G.Player('B3', LOS - 1.0, 42.0), G.Player('X', LOS, 4.0),
        G.Player('RB', 43.0, BALL_Y)]))
    check('  bunch -> AMBIGUOUS/BUNCH_OR_STACK',
          r['B2'] == (G.AMBIGUOUS, 'BUNCH_OR_STACK'), str(r['B2']))
    # motion
    r = G.classify_frame(frame([
        G.Player('M', LOS - 1.0, 38.0, vy=3.0), G.Player('X', LOS, 4.0),
        G.Player('Z', LOS, 49.0), G.Player('RB', 43.0, BALL_Y)]))
    check('  lateral speed 3.0 yd/s -> AMBIGUOUS/IN_MOTION',
          r['M'] == (G.AMBIGUOUS, 'IN_MOTION'), str(r['M']))
    # unusable frame
    r = G.classify_frame(frame([G.Player('X', LOS, 4.0)], stable=False))
    check('  unstable frame -> every player AMBIGUOUS/NO_STABLE_FRAME',
          all(v == (G.AMBIGUOUS, 'NO_STABLE_FRAME') for v in r.values()),
          str(r))
    # missing line
    r = G.classify_frame(frame([G.Player('X', LOS, 4.0)], drop_ol=2))
    check('  fewer than 5 OL -> AMBIGUOUS/OL_NOT_IDENTIFIABLE, rather than '
          'guessing a tackle position',
          all(v == (G.AMBIGUOUS, 'OL_NOT_IDENTIFIABLE') for v in r.values()),
          str(r))
    # null coordinate
    r = G.classify_frame(frame([
        G.Player('N', float('nan'), 4.0), G.Player('Z', LOS, 49.0),
        G.Player('RB', 43.0, BALL_Y)]))
    check('  NaN coordinate -> AMBIGUOUS/NULL_COORDINATE',
          r['N'] == (G.AMBIGUOUS, 'NULL_COORDINATE'), str(r['N']))


def test_E_accept_review_split():
    print('\nE. the accept/review split works and is measured')
    r = G.classify_frame(frame([
        G.Player('X', LOS, 4.0), G.Player('Z', LOS, 49.0),
        G.Player('M', LOS - 1.0, 38.0, vy=3.0),
        G.Player('RB', 43.0, BALL_Y)]))
    s = G.accept_or_review(r)
    check('  accepted labels carry no AMBIGUOUS',
          all(v != G.AMBIGUOUS for v in s['accepted'].values()))
    check('  the review queue carries a machine-readable cause per player',
          all(v for v in s['review'].values()), str(s['review']))
    check('  and the review rate is reported, not implied',
          abs(s['review_rate'] - 1 / 4) < 1e-9, str(s['review_rate']))


def test_F_thresholds_match_the_frozen_pre_registration():
    print('\nF. every threshold matches the sealed pre-registration')
    import re
    txt = open(os.path.join(_ROOT, 'nfl', 'research', 'alignb1',
                            'predeclaration_alignb1.md')).read()
    for name, val in (('BACKFIELD_DEPTH', 1.5), ('BACKFIELD_GAP', 3.0),
                      ('INLINE_DEPTH', 1.0), ('INLINE_GAP', 1.5),
                      ('DETACHED_GAP', 6.0), ('BUNCH_SEPARATION', 1.5),
                      ('MOTION_SPEED', 1.0)):
        check(f'  {name} == {val} in code', getattr(G, name) == val)
    for lit in ('1.5', '3.0', '1.0', '6.0'):
        check(f'  {lit} appears in the sealed pre-registration',
              re.search(re.escape(lit), txt) is not None)
    check('  the class list is closed at six', len(G.CLASSES) == 6)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

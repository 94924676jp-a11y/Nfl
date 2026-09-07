"""The pre-flight detects the things it exists to detect. Directive 7 §10.

A pre-flight that always returns clear is worse than none: it converts an
unchecked assumption into a green tick. So each check is broken on purpose here
and required to notice.

Run standalone:  python3.12 nfl/tests/test_preflight.py
"""
import datetime as dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import preflight_t90 as P  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def run():
    return P._checks(2026, 1)


def by(results, fragment):
    return next(o for lbl, o in results if fragment in lbl)


def test_A_it_is_clear_right_now():
    print('\nA. the honest current state')
    r = run()
    fails = [(l, o.code) for l, o in r if o.state is State.FAIL]
    check('every check passes today', not fails, str(fails))
    check('and there are enough of them to be worth running', len(r) >= 8,
          str(len(r)))
    check('the first target is NE@SEA', by(r, 'first upcoming').value
          == '2026_01_NE_SEA')
    check('and it is reported as not yet covered',
          by(r, 'not already covered').code == 'TARGET_OPEN')


def test_B_it_notices_a_stale_cron():
    print('\nB. a cron gone stale is caught')
    import nfl.tools.gen_t90_schedule as G
    original = G.WORKFLOW.read_text()
    try:
        G.WORKFLOW.write_text(original.replace("- cron: '50,55 22 9 9 *'",
                                               "- cron: '50,55 22 1 1 *'"))
        r = run()
        check('a hand-edited cron entry is caught as drift',
              by(r, 'matches the current schedule').code == 'WORKFLOW_STALE')
    finally:
        G.WORKFLOW.write_text(original)
    check('and restoring it clears the check',
          by(run(), 'matches the current schedule').state is State.PASS)


def test_C_it_notices_a_loosened_gate():
    print('\nC. a loosened discharge gate is caught')
    import nfl.capture.execution as X
    original = X.DISCHARGING_BASES
    try:
        X.DISCHARGING_BASES = (X.BASIS_ANCHORED, X.BASIS_SWEEP)
        r = run()
        check('letting a sweep discharge is caught',
              by(r, 'sweep cannot discharge').code == 'BASIS_GATE_OPEN')
    finally:
        X.DISCHARGING_BASES = original

    orig_basis = X.declaration_basis
    try:
        X.declaration_basis = lambda ident: X.BASIS_ANCHORED
        r = run()
        check('an unknown workflow being treated as anchored is caught',
              by(r, 'unknown workflow').code == 'BASIS_FAILSAFE_OPEN')
    finally:
        X.declaration_basis = orig_basis


def test_D_it_notices_a_renamed_workflow():
    print('\nD. a workflow rename that would silently disable anchoring')
    import nfl.capture.execution as X
    original = X.ANCHORED_WORKFLOW
    try:
        X.ANCHORED_WORKFLOW = 'Some Other Name'
        r = run()
        check('a name mismatch is caught -- otherwise every anchored run would '
              'silently classify as a sweep and discharge nothing forever',
              by(r, 'name matches').code == 'WORKFLOW_NAME_MISMATCH')
    finally:
        X.ANCHORED_WORKFLOW = original
    check('and it clears once the names agree',
          by(run(), 'name matches').state is State.PASS)


def test_E_it_notices_a_moved_window():
    print('\nE. the T-90 -> T-10 window cannot be widened unnoticed')
    import nfl.capture.schedule as S
    original = S.WINDOWS['inactives']
    try:
        S.WINDOWS['inactives'] = (dt.timedelta(0), dt.timedelta(hours=6))
        r = run()
        check('widening the window to six hours is caught',
              by(r, "owner's T-90").code == 'WINDOW_ALTERED')
    finally:
        S.WINDOWS['inactives'] = original
    check('and the real window is 80 minutes at kickoff minus 90',
          by(run(), "owner's T-90").state is State.PASS)


def test_F_it_would_notice_a_premature_cover():
    print('\nF. anything covered before the event is a failure, not a pass')
    import nfl.tools.preflight_t90 as PF
    import nfl.capture.coverage as C
    from sportsplatform.governance.outcome import Outcome
    original = C.coverage
    try:
        C.coverage = lambda *a, **k: Outcome.ok(
            'WINDOWS_COVERED', value={}, detail='x', covered=1, missed=0,
            not_yet_due=0)
        r = run()
        check('a target reading covered before its window is caught',
              by(r, 'not already covered').code == 'TARGET_ALREADY_COVERED')
    finally:
        C.coverage = original
    check('and the real state is open', by(run(), 'not already covered').code
          == 'TARGET_OPEN')


if __name__ == '__main__':
    test_A_it_is_clear_right_now()
    test_B_it_notices_a_stale_cron()
    test_C_it_notices_a_loosened_gate()
    test_D_it_notices_a_renamed_workflow()
    test_E_it_notices_a_moved_window()
    test_F_it_would_notice_a_premature_cover()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

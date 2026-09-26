"""A gate that cannot refuse is a label.

`build_postinactives_package.assert_no_inactive_in_playable` calls itself THE
GATE. Its result was written to `audits.inactive_exclusion`, printed, and then
ignored: `emit_package.main()` wrote the package and returned 0 whatever it
said. An officially inactive player carrying a playable DK projection got
PUBLISHED, with the failure recorded beside it as a field.

This is the third instance of one shape in this repository and the reason it
is worth a permanent suite:

  DEF-058   `effective_mode` was computed and never branched on, so the paid
            step had no `if:` and every MOCK task would have billed.
  DEF-063   grading reported `state: GRADED` on a failed name lookup, so a
            wiring defect entered the ledger as model error.
  here      an audit that says FAIL and publishes anyway.

A computed check that nothing acts on is not a weaker check. It is an ABSENT
check wearing the costume of a present one, and it is worse than no check
because the artifact now carries evidence that it was verified.

NOT_CERTIFIED is deliberately NOT blocking. Before the league publishes its
inactive declarations there is nothing to intersect against; that is the
normal pre-publication state and refusing there would make the board
unbuildable every week until ~15:30Z.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import emit_package as EP  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


def _pkg(inactive_state, shared_state='PASS'):
    return {'audits': {
        'inactive_exclusion': {
            'state': inactive_state, 'code': f'X_{inactive_state}',
            'survivors': ([{'gsis_id': '00-0041443', 'name': 'Skyler Bell'}]
                          if inactive_state == 'FAIL' else []),
            'method': 'test fixture'},
        'shared_draws': {'state': shared_state, 'code': f'Y_{shared_state}',
                         'survivors': [], 'method': 'test fixture'}}}


def test_a_failing_audit_blocks_publication():
    print('\n[1] FAIL refuses')
    f = EP.blocking_failures(_pkg('FAIL'))
    check('an inactive-exclusion FAIL is blocking', len(f) == 1,
          str([x['audit'] for x in f]))
    check('and it carries the survivors that caused it',
          bool(f) and f[0]['survivors'], str(f[0]['survivors'] if f else []))
    f2 = EP.blocking_failures(_pkg('PASS', shared_state='FAIL'))
    check('a shared-draws FAIL is blocking too', len(f2) == 1,
          str([x['audit'] for x in f2]))
    f3 = EP.blocking_failures(_pkg('FAIL', shared_state='FAIL'))
    check('both failing reports both, not the first',
          len(f3) == 2, str([x['audit'] for x in f3]))


def test_a_clean_package_publishes():
    print('\n[2] PASS publishes')
    check('nothing blocking on a clean package',
          EP.blocking_failures(_pkg('PASS')) == [])


def test_not_certified_does_not_block():
    print('\n[3] NOT_CERTIFIED is not a failure')
    check('NOT_CERTIFIED does not block',
          EP.blocking_failures(_pkg('NOT_CERTIFIED')) == [],
          'before the league publishes there is nothing to intersect against; '
          'refusing here would make the board unbuildable until ~15:30Z')
    check('and NOT_CERTIFIED is not in the blocking state',
          EP.BLOCKING_STATE == 'FAIL', EP.BLOCKING_STATE)


def test_the_refusal_is_wired_into_main_not_just_available():
    print('\n[4] main() acts on it, which is the whole defect')
    import inspect
    src = inspect.getsource(EP.main)
    check('main calls blocking_failures', 'blocking_failures(' in src)
    check('main returns non-zero when it refuses', 'return 1' in src)
    # THE ORDERING IS THE FIX. Writing first and refusing after would still
    # publish the bad package.
    check('main refuses BEFORE it writes',
          src.index('blocking_failures(') < src.index('write_text'),
          'a refusal after the write is not a refusal')
    check('both audits are declared blocking',
          set(EP.BLOCKING_AUDITS) == {'inactive_exclusion', 'shared_draws'},
          str(EP.BLOCKING_AUDITS))


def test_a_missing_audit_block_is_not_read_as_a_pass():
    print('\n[5] an absent audit is not a clean one')
    # An audits block that lost a key must not silently look publishable. It
    # currently does NOT block, which is honest to record rather than assert
    # away: this documents the behaviour so a change to it is deliberate.
    empty = EP.blocking_failures({'audits': {}})
    check('an empty audits block yields no blocking failure', empty == [],
          'RECORDED, NOT ENDORSED: a package with no audits section is not '
          'refused here. It is caught upstream by build() always emitting '
          'both audits; if that ever stops being true this is where it leaks')
    check('build() always emits both audit keys',
          all(f"'{k}': " in Path(_REPO / 'nfl/dfs/salaries/emit_package.py'
                                 ).read_text() for k in EP.BLOCKING_AUDITS),
          str(EP.BLOCKING_AUDITS))


def main():
    print(__doc__.strip().splitlines()[0])
    test_a_failing_audit_blocks_publication()
    test_a_clean_package_publishes()
    test_not_certified_does_not_block()
    test_the_refusal_is_wired_into_main_not_just_available()
    test_a_missing_audit_block_is_not_read_as_a_pass()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())

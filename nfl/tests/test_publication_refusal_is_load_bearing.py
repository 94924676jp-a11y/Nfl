"""DEF-065's real acceptance test: bad state -> guard FAIL -> NO ARTIFACT.

A-02 in nfl/research/audit/2026-09-25_CONSOLIDATED_DEFECT_LEDGER.md already
specified this shape -- "entry point refuses when a gate is seeded to fail" --
and my first test for DEF-065 did not meet it. That test asserted two weaker
things:

  * `blocking_failures()` classifies a seeded FAIL correctly, and
  * `main()`'s source contains a `return 1` positioned before a `write_text`.

The second is a SOURCE-ORDER ARGUMENT about exactly the thing DEF-065 proved
you cannot argue from source: a control can be present, correctly written, and
still not protect anything. `test_p6_false_greens` independently flags six
other test functions in this repository for the same defect class --
TAUTOLOGICAL_BYPASS_PROOF, a "fails when bypassed" proof that compares literal
against literal and reaches no production alias. Mine would have been the
seventh.

So this test runs the publication path and then looks at the disk.

TWO TRAPS IT HAS TO AVOID, both of which would make it pass while proving
nothing:

  1. A LEFTOVER FILE. Asserting "no artifact exists" is meaningless if the
     path was already empty for unrelated reasons, and asserting one appears
     is meaningless if a previous run left it there. Both directions are
     established against a directory whose state is checked immediately
     before the call -- the same trap as build_gpp20.py importing cleanly
     only because two /tmp files from Sep 21 happened to survive.
  2. TESTING THE CLASSIFIER INSTEAD OF THE GATE. `main()` is called. Not
     `blocking_failures`, not the source text.
"""
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
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


def _pkg(inactive='PASS', shared='PASS'):
    """A package skeleton carrying only what the gate reads."""
    return {'audits': {
        'inactive_exclusion': {
            'state': inactive, 'code': f'INACT_{inactive}',
            'survivors': ([{'gsis_id': '00-0041443', 'name': 'Skyler Bell'}]
                          if inactive == 'FAIL' else []),
            'method': 'seeded by test'},
        'shared_draws': {'state': shared, 'code': f'SHARED_{shared}',
                         'survivors': [], 'method': 'seeded by test'}},
        # The keys main() PRINTS after writing. A skeleton thin enough to
        # exercise only the gate made main() raise KeyError past the write,
        # which would have masked the positive case behind a test-fixture bug.
        'provenance': {'games_present': [], 'games_missing': []},
        'football_board': [], 'dfs_board': [],
        'prop_board': {'rows': [], 'counts': {}}}


def _run_main_against(tmp, pkg):
    """Call the REAL main() with _REPO and build() redirected.

    Returns (exit_code, output_path, existed_before).
    """
    out_dir = pathlib.Path(tmp) / 'nfl' / 'research' / 'sunday'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / EP.OUT_NAME
    existed_before = out.exists()
    real_repo, real_build = EP._REPO, EP.build
    EP._REPO = pathlib.Path(tmp)
    EP.build = lambda: pkg
    try:
        rc = EP.main()
    finally:
        EP._REPO, EP.build = real_repo, real_build
    return rc, out, existed_before


def test_a_seeded_inactive_failure_writes_nothing():
    print('\n[1] bad state -> FAIL -> no artifact on disk')
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, existed = _run_main_against(tmp, _pkg(inactive='FAIL'))
        check('the output path was empty before the call', not existed,
              'otherwise "no artifact" proves nothing')
        check('main() returns non-zero', rc != 0, f'rc={rc}')
        check('AND NO PACKAGE WAS WRITTEN', not out.exists(),
              'this is the assertion DEF-065 actually needed; the earlier test '
              'never looked at the disk')


def test_a_seeded_shared_draws_failure_also_writes_nothing():
    print('\n[2] the second gate is load-bearing too, not just the first')
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, existed = _run_main_against(tmp, _pkg(shared='FAIL'))
        check('the output path was empty before the call', not existed)
        check('main() returns non-zero', rc != 0, f'rc={rc}')
        check('and no package was written', not out.exists())


def test_a_clean_package_DOES_write():
    print('\n[3] the refusal is selective, not a broken main()')
    # WITHOUT THIS THE SUITE IS SATISFIED BY A main() THAT NEVER WRITES.
    # "No artifact after a FAIL" is trivially true of a function that is simply
    # broken, so the positive case has to be proven in the same shape.
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, existed = _run_main_against(tmp, _pkg())
        check('the output path was empty before the call', not existed,
              'so an appearing file cannot be a leftover')
        check('main() returns zero', rc == 0, f'rc={rc}')
        check('AND the package WAS written', out.exists(),
              str(out.name) if out.exists() else 'nothing appeared')
        if out.exists():
            doc = json.loads(out.read_text())
            check('...carrying the audits that let it through',
                  (doc.get('audits') or {}).get('inactive_exclusion', {})
                  .get('state') == 'PASS')


def test_not_certified_publishes_because_it_is_not_a_failure():
    print('\n[4] NOT_CERTIFIED is not a refusal')
    # Before the league publishes its declarations there is nothing to
    # intersect against. Refusing here would make the board unbuildable every
    # week until ~15:30Z, so this proves the gate distinguishes "unchecked"
    # from "checked and bad".
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, existed = _run_main_against(
            tmp, _pkg(inactive='NOT_CERTIFIED'))
        check('the output path was empty before the call', not existed)
        check('main() returns zero', rc == 0, f'rc={rc}')
        check('and the package IS written', out.exists(),
              'an unpublished inactive list is the normal pre-15:30Z state')


def test_both_gates_failing_still_writes_nothing():
    print('\n[5] two failures do not cancel out')
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, existed = _run_main_against(
            tmp, _pkg(inactive='FAIL', shared='FAIL'))
        check('the output path was empty before the call', not existed)
        check('main() returns non-zero', rc != 0, f'rc={rc}')
        check('and no package was written', not out.exists())


def main():
    print(__doc__.strip().splitlines()[0])
    test_a_seeded_inactive_failure_writes_nothing()
    test_a_seeded_shared_draws_failure_also_writes_nothing()
    test_a_clean_package_DOES_write()
    test_not_certified_publishes_because_it_is_not_a_failure()
    test_both_gates_failing_still_writes_nothing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())

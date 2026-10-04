"""classic_slate_pipeline / classic_change_log: the lock-critical order, and causes read from evidence."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_pipeline as PL   # noqa: E402
from nfl.tools import classic_change_log as CL       # noqa: E402

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


def test_01_the_order_is_the_owners():
    names = [n for n, _ in PL.stages('S', '2026-10-04T15:40:00Z', 'i.json', 'p.html')]
    want = ['state', 'run', 'book', 'portfolios', 'verify', 'book_with_exposures', 'board', 'fc', 'props', 'audit', 'prelock', 'changes', 'finalize', 'page']
    check('stages run in the declared lock-critical order', names == want, names)
    check('  lineups come only after the research book', names.index('portfolios') > names.index('book'))
    check('  Hard Rock is compared only after the projection, book, seal and lineups exist',
          names.index('props') > max(names.index(x) for x in ('run', 'book', 'portfolios')))
    check('  only FC and Hard Rock may refuse without stopping the run', PL.DOWNSTREAM_ONLY == {'fc', 'props'})
    st = dict(PL.stages('S', 'T', 'i.json', 'p.html'))['state']
    check('  the official inactive list reaches the state builder', '--official-inactives' in st and 'i.json' in st)
    sg = dict(PL.stages('S', 'T', None, 'p.html', 'pk.json'))
    check('  the evidence packet reaches both the state builder and the prelock check',
          sg['state'][-2:] == ['--evidence-packet', 'pk.json'] and sg['prelock'][-2:] == ['--evidence-packet', 'pk.json'])
    check('  negative control: no packet -> no packet flag anywhere',
          not any('--evidence-packet' in (c if isinstance(c[0], str) else sum(c, []))
                  for c in dict(PL.stages('S', 'T', None, 'p.html')).values()))
    pt = sg['portfolios']
    check('  the production build runs beside two tagged reproducibility builds, production first',
          len(pt) == 3 and '--tag' not in pt[0] and [c[-1] for c in pt[1:]] == ['reproA', 'reproB'])
    check('  finalize comes after audit, prelock and the change log, and before the page',
          names.index('finalize') > max(names.index(x) for x in ('audit', 'prelock', 'changes', 'verify'))
          and names.index('finalize') == names.index('page') - 1)
    check('  only the comparisons and the two post-run verdicts may refuse without stopping',
          PL.NON_STOPPING == {'fc', 'props', 'prelock', 'finalize'})


def test_02_a_dry_run_writes_no_snapshot():
    before = set((PL.OUT_DIR / 'runs').rglob('*')) if (PL.OUT_DIR / 'runs').exists() else set()
    led = PL.run('NOPE', 'T', None, '/dev/null', dry=True)
    after = set((PL.OUT_DIR / 'runs').rglob('*')) if (PL.OUT_DIR / 'runs').exists() else set()
    check('negative control: a dry run copies nothing', before == after and led['snapshot']['files'] == [], led['snapshot'])
    (PL.OUT_DIR / 'DK_NOPE_EARLY_RUN_LEDGER.json').unlink(missing_ok=True)


def test_03_change_causes_come_from_the_two_states():
    a = {'current_availability': {'status': 'UNKNOWN_ACTIVE_STATE', 'designation': 'QUESTIONABLE'}, 'depth_rank': 2,
         'predicted_lineup_context': {}}
    b = {'current_availability': {'status': 'REPORTED_INACTIVE_HIGH_CONFIDENCE', 'designation': 'QUESTIONABLE'}, 'depth_rank': 2,
         'predicted_lineup_context': {}}
    check('an availability change is named as the cause', 'availability' in CL._cause(a, b), CL._cause(a, b))
    c = dict(a, depth_rank=1)
    check('  a depth change is named', 'depth rank 2 -> 1' in CL._cause(a, c))
    check('negative control: no change in his own evidence -> reallocation, said plainly',
          CL._cause(a, dict(a)).startswith('reallocation inside the club'))
    check('  a player new to the slate is named as new', CL._cause(None, a) == 'new to the slate')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')

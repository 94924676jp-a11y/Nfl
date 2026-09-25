""""Not yet" must stop being sayable once the window it refers to has closed."""
from __future__ import annotations

import datetime as dt
import gzip
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import deferral_escalation as DE                # noqa: E402

PASSED = 0
FAILED = 0

K = dt.datetime(2026, 9, 25, 0, 15, tzinfo=dt.timezone.utc)
AFTER = K + dt.timedelta(hours=6)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                       # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


_IN_WINDOW = [K - dt.timedelta(minutes=m) for m in (80, 50, 20)]


def _ev(n=10, rows=0, shell=0, landing=0):
    return {'n_blobs': n, 'n_with_row_container': rows, 'n_js_shell': shell,
            'n_landing_page': landing}


def test_A_an_open_window_is_still_a_debt():
    print('\nA. zero rows on a Tuesday is not a defect')
    r = DE.classify('official_inactives', _IN_WINDOW, _ev(),
                    kickoffs=[K], now=K - dt.timedelta(hours=1))
    check('the window is still open so it stays a debt',
          r['verdict'] == DE.DEBT_WITHIN_WINDOW, r['verdict'])
    check('and it does not refuse', DE.assert_no_structural_debt(r) is r)


def test_B_a_closed_window_with_no_rows_ever_is_structural():
    print('\nB. ten days of "not yet" for something that is "not here"')
    r = DE.classify('official_inactives', _IN_WINDOW, _ev(n=367, landing=363),
                    kickoffs=[K], now=AFTER)
    check('it escalates to SOURCE_PATH_CANNOT_YIELD_ROWS',
          r['verdict'] == DE.CANNOT_YIELD, r['verdict'])
    check('the reading says a parser rewrite cannot help',
          'rewriting the parser cannot help' in r['reading'])
    check('and names the landing page',
          'check back soon' in r['reading'], r['reading'][:80])
    ok, d = raised(DE.EscalationError,
                   lambda: DE.assert_no_structural_debt(r),
                   'must not remain filed as')
    check('carrying it as a debt is refused', ok, d)


def test_C_rows_present_and_extraction_empty_is_a_different_defect():
    print('\nC. sending somebody to fix the wrong layer is the costly error')
    r = DE.classify('official_inactives', _IN_WINDOW,
                    _ev(n=100, rows=100), kickoffs=[K], now=AFTER)
    check('it escalates to CONTENT_PRESENT_EXTRACTION_EMPTY',
          r['verdict'] == DE.EXTRACTION_EMPTY, r['verdict'])
    check('and blames the extractor, not the URL',
          'the extractor is the defect' in r['reading'])


def test_D_a_js_shell_gets_a_different_remedy():
    print('\nD. render it, versus find the real URL')
    r = DE.classify('official_inactives', _IN_WINDOW,
                    _ev(n=50, shell=50), kickoffs=[K], now=AFTER)
    check('still CANNOT_YIELD', r['verdict'] == DE.CANNOT_YIELD, r['verdict'])
    check('but the remedy named is rendering',
          'rendering may be the remedy' in r['reading'], r['reading'][-90:])


def test_E_an_undeclared_window_cannot_be_late():
    print('\nE. a source with no declared window')
    r = DE.classify('some_other_source', _IN_WINDOW, _ev(), kickoffs=[K],
                    now=AFTER)
    check('reads NO_WINDOW_DECLARED', r['verdict'] == DE.NO_WINDOW_DECLARED,
          r['verdict'])
    check('and says declaring one is the fix',
          'Declaring one is the fix' in r['reading'])
    check('it does not refuse, because lateness is not established',
          DE.assert_no_structural_debt(r) is r)


def test_F_blob_evidence_counts_what_is_there():
    print('\nF. the evidence function, on bytes it can see')
    d = pathlib.Path(tempfile.mkdtemp())
    (d / 'x.1.html.gz').write_bytes(gzip.compress(
        b'<html><body><table><tr><td>Player</td></tr></table></body></html>'))
    (d / 'x.2.html.gz').write_bytes(gzip.compress(
        b'<html>Please check back soon for NFL Inactive Reports</html>'))
    (d / 'x.3.html.gz').write_bytes(gzip.compress(
        b'<html><script>window.__INITIAL = {}</script></html>'))
    (d / 'x.4.html.gz').write_bytes(b'not gzip at all')
    ev = DE.blob_evidence(d, 'x.*.html.gz')
    check('unreadable blobs are skipped, not counted',
          ev['n_blobs'] == 3, ev)
    check('one row container found', ev['n_with_row_container'] == 1, ev)
    check('one landing page found', ev['n_landing_page'] == 1, ev)
    check('one JS shell found', ev['n_js_shell'] == 1, ev)


def test_G_the_real_official_inactives_record():
    print('\nG. the live capture-prod record and committed blobs')
    ev = DE.blob_evidence(_REPO / 'nfl/vintage',
                          'official_inactives.*.html.gz')
    if not ev['n_blobs']:
        check('blobs present', False, 'no committed blobs found')
        return
    check('no committed capture carries a row container',
          ev['n_with_row_container'] == 0, ev)
    check('almost all are landing pages',
          ev['n_landing_page'] > 0.9 * ev['n_blobs'], ev)
    check('and none is a JS shell, so rendering is not the remedy',
          ev['n_js_shell'] == 0, ev)
    r = DE.classify('official_inactives', _IN_WINDOW, ev, kickoffs=[K],
                    now=AFTER)
    check('the live record escalates to CANNOT_YIELD',
          r['verdict'] == DE.CANNOT_YIELD, r['verdict'])

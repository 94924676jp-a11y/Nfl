"""designations_from_injuries: formal report_status only; overrides are recorded, never silent."""
import csv
import gzip
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from nfl.tools.designations_from_injuries import build  # noqa: E402

COLS = ['season', 'week', 'team', 'full_name', 'report_status', 'practice_status']
ROWS = [['2026', '5', 'TB', 'QB One', 'Out', 'Did Not Participate In Practice'],
        ['2026', '5', 'TB', 'WR Two', '', 'Did Not Participate In Practice'],
        ['2026', '5', 'DAL', 'LB Three', 'Questionable', 'Full Participation in Practice']]


PASSED = FAILED = 0


def check(ok, label=''):
    """Counted check (nfl/tests/run_suite.py reads PASSED/FAILED around every test function)."""
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)

def _file(rows=ROWS):
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / 'inj.csv.gz'
    with gzip.open(p, 'wt', newline='') as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    return p


def _refuses(fn, code):
    try:
        fn()
    except SystemExit as e:
        check(code in str(e), e)
        return
    raise AssertionError(f'expected {code}')


def test_formal_only_practice_never_designates():
    des, prov = build(_file(), 2026, 5, {'TB', 'DAL'})
    check(des == {'QB One': 'OUT', 'LB Three': 'QUESTIONABLE'}, "des == {'QB One': 'OUT', 'LB Three': 'QUESTIONABLE'}")
    check([x['player'] for x in prov['practice_only_no_formal_status']] == ['WR Two'], "[x['player'] for x in prov['practice_only_no_formal_status']] == ['WR Two']")


def test_counterfactual_remove_is_recorded():
    des, prov = build(_file(), 2026, 5, {'TB', 'DAL'}, counterfactual_remove=['QB One'])
    check('QB One' not in des, "'QB One' not in des")
    check(prov['COUNTERFACTUAL_REMOVED_FORMAL_STATUS'] == {'QB One': 'OUT'}, "prov['COUNTERFACTUAL_REMOVED_FORMAL_STATUS'] == {'QB One': 'OUT'}")
    check('QB One' not in prov['formal_designations'], "'QB One' not in prov['formal_designations']")


def test_counterfactual_remove_needs_a_formal_status():
    _refuses(lambda: build(_file(), 2026, 5, {'TB'}, counterfactual_remove=['WR Two']),
             'COUNTERFACTUAL_TARGET_HAS_NO_FORMAL_STATUS')


def test_empty_report_refuses():
    _refuses(lambda: build(_file(), 2026, 6, {'TB'}), 'NO_INJURY_ROWS')


def test_a_requested_club_with_no_rows_refuses():
    # 2026-10-12 BUF@LAR: --teams BUF,LAR silently returned no Rams rows (nflverse files them as LA)
    _refuses(lambda: build(_file(), 2026, 5, {'TB', 'LAR'}), 'NO_INJURY_ROWS_FOR_TEAM')


def test_formal_designations_keep_practice_status_and_injury():
    rows = [['2026', '5', 'TB', 'QB One', 'Questionable', 'Limited Participation in Practice'],
            ['2026', '5', 'DAL', 'LB Three', 'Out', 'Did Not Participate In Practice']]
    _des, prov = build(_file(rows), 2026, 5, {'TB', 'DAL'})
    d = prov['formal_detail']
    check(d['QB One']['practice_status'] == 'Limited Participation in Practice' and d['QB One']['team'] == 'TB', "d['QB One']['practice_status'] == 'Limited Participation in Practice' and d['QB One']['team'] == 'TB'")
    check(set(d) == {'QB One', 'LB Three'}, "set(d) == {'QB One', 'LB Three'}")


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED when run standalone."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    for k, v in list(globals().items()):
        if k.startswith('test_'):
            v()
            print('PASS', k)

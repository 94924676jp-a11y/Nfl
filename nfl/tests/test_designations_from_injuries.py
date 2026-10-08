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
        assert code in str(e), e
        return
    raise AssertionError(f'expected {code}')


def test_formal_only_practice_never_designates():
    des, prov = build(_file(), 2026, 5, {'TB', 'DAL'})
    assert des == {'QB One': 'OUT', 'LB Three': 'QUESTIONABLE'}
    assert [x['player'] for x in prov['practice_only_no_formal_status']] == ['WR Two']


def test_counterfactual_remove_is_recorded():
    des, prov = build(_file(), 2026, 5, {'TB', 'DAL'}, counterfactual_remove=['QB One'])
    assert 'QB One' not in des
    assert prov['COUNTERFACTUAL_REMOVED_FORMAL_STATUS'] == {'QB One': 'OUT'}
    assert 'QB One' not in prov['formal_designations']


def test_counterfactual_remove_needs_a_formal_status():
    _refuses(lambda: build(_file(), 2026, 5, {'TB'}, counterfactual_remove=['WR Two']),
             'COUNTERFACTUAL_TARGET_HAS_NO_FORMAL_STATUS')


def test_empty_report_refuses():
    _refuses(lambda: build(_file(), 2026, 6, {'TB'}), 'NO_INJURY_ROWS')


if __name__ == '__main__':
    for k, v in list(globals().items()):
        if k.startswith('test_'):
            v()
            print('PASS', k)

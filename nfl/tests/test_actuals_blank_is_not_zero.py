"""A blank cell in the actuals feed is missing. It is not a realised zero.

`actuals.load_weekly` coerced None/''/'NA' straight to 0.0 for all 18 numeric
columns. These ARE the actuals, so a blank cell became a realised zero and
grading scored a projection against it as though the player had genuinely
recorded nothing -- the repo-wide invariant inverted in the place it costs
most.

MEASURED before changing anything, because the size of a risk is part of it:
0 blank or NA cells across 1,674 rows and all 18 columns of the pinned
snapshot. So the refusal changes NOTHING today and this is a latent hole, not
a live defect. It is worth closing because the snapshot is REPLACED each week:
the hash pin refuses a file that changed underneath us, but it cannot object
to the new file a human deliberately pins, and that is exactly when a feed
carrying blanks would arrive unannounced.

The module was already alert to this class one level up -- its schema guard
says 'reading a renamed column as absent would grade every player at zero'.
The same argument applies cell by cell, which is all this adds.
"""
import csv
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import actuals as A  # noqa: E402

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


def test_the_pinned_snapshot_has_no_blanks_and_says_so():
    print('\n[1] the real feed, measured rather than assumed')
    r = A.load_weekly(2026, 2)
    check('it loads', r.state.name == 'PASS', f'{r.state.name}[{r.code}]')
    if r.state.name != 'PASS':
        return
    ev = r.as_dict()['evidence']
    check('and reports that it CHECKED, not merely that it passed',
          ev.get('blank_numeric_cells') == 0
          and 'blank_numeric_cells_note' in ev,
          'an absent count and a verified-zero count are different facts')
    p = A.RAW / A.WEEKLY[0]
    rows = list(csv.DictReader(open(p, newline='')))
    blank = sum(1 for x in rows for c in A.NUMERIC
                if x.get(c) in (None, '', 'NA'))
    check('independently: zero blank cells in the whole file', blank == 0,
          f'{blank} across {len(rows)} rows x {len(A.NUMERIC)} columns')


def test_a_blank_cell_is_refused_not_zeroed():
    print('\n[2] a blank cell, executed')
    # Build a snapshot with ONE blanked cell and pin the loader to it, so the
    # refusal is proven by running it rather than by reading the source.
    src = A.RAW / A.WEEKLY[0]
    with tempfile.TemporaryDirectory() as tmp:
        dst_dir = Path(tmp)
        dst = dst_dir / A.WEEKLY[0]
        rows = list(csv.DictReader(open(src, newline='')))
        cols = list(rows[0])
        target = next(x for x in rows
                      if x['season'] == '2026' and x['week'] == '2')
        target['receiving_yards'] = ''
        with dst.open('w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        old_raw, old_weekly = A.RAW, A.WEEKLY
        A.RAW = dst_dir
        A.WEEKLY = (A.WEEKLY[0], A._sha256(dst))   # re-pin to the new bytes
        try:
            r = A.load_weekly(2026, 2)
        finally:
            A.RAW, A.WEEKLY = old_raw, old_weekly
        check('one blank cell refuses the whole load',
              r.state.name != 'PASS', f'{r.state.name}[{r.code}]')
        check('...with a named code',
              r.code == 'ACTUALS_NUMERIC_CELL_BLANK', str(r.code))
        ev = r.as_dict()['evidence']
        check('...naming the column it found',
              (ev.get('blank_cells_by_column') or {}).get('receiving_yards')
              == 1, str(ev.get('blank_cells_by_column')))
        check('...and NOT returning a row with a 0.0 in it',
              r.value is None or not isinstance(r.value, dict) or not r.value,
              'the previous behaviour returned this player with '
              'receiving_yards 0.0 and called it an actual')


def test_the_hash_pin_still_refuses_a_changed_file_first():
    print('\n[3] the existing guard is not weakened')
    old_weekly = A.WEEKLY
    A.WEEKLY = (A.WEEKLY[0], '0' * 64)
    try:
        r = A.load_weekly(2026, 2)
    finally:
        A.WEEKLY = old_weekly
    check('a wrong hash still blocks',
          r.code == 'ACTUALS_SNAPSHOT_BYTES_CHANGED', str(r.code))
    check('and that check runs BEFORE the blank scan',
          'ACTUALS_SNAPSHOT_BYTES_CHANGED' in
          (_REPO / 'nfl/postgame/actuals.py').read_text()
          .split('ACTUALS_NUMERIC_CELL_BLANK')[0],
          'bytes first, then contents')


def main():
    print(__doc__.strip().splitlines()[0])
    test_the_pinned_snapshot_has_no_blanks_and_says_so()
    test_a_blank_cell_is_refused_not_zeroed()
    test_the_hash_pin_still_refuses_a_changed_file_first()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())

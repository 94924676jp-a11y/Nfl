"""The QB-inactive ownership repair, and the assertion that keeps it repaired.

THE DEFECT THIS FILE EXISTS FOR.

`official_inactive_ids` reached the non-QB engine only -- one argument at
run_forecast.py:713 -- so the QB share pool never saw it. On the sealed SF@LA
board of 2026-09-11, Kurtis Rourke held 0.90 dropbacks and Ty Simpson 0.73
while both were on the league's published inactive list.

The mean understated it badly. Measured on the real 2026 week-1 SF/LA pool,
Rourke's share PEAKED at 0.2256 -- in some simulated worlds an inactive third
quarterback took nearly a quarter of his team's dropbacks. That is why the
assertion below checks the maximum over draws and not the mean: a mean of
0.0004 is one draw holding a snap for a man who was not dressed.

WHY THE REPAIR IS IN THE ALLOCATION AND NOT DOWNSTREAM. The share is the thing
that is wrong, so zeroing the inactive rows and renormalising the remainder is
the earliest causal repair. R2's largest-remainder apportionment is untouched;
it simply receives the correct pool. Subtracting afterwards would have been a
second mechanism compensating for the first, which this project forbids.
"""
from __future__ import annotations

import csv
import glob
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import qb_accounting as QBACC                    # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402

PASSED = FAILED = 0
ROURKE = '00-0040589'
SIMPSON = '00-0041568'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _real_pool():
    """The actual 2026 week-1 SF/LA quarterback pool from the roster vintage."""
    out = []
    for r in sorted(glob.glob(os.path.join(_ROOT, 'nfl_vintage', 'raw',
                                           'weekly_rosters.*.csv'))):
        for row in csv.DictReader(open(r)):
            if (row.get('season') == '2026' and row.get('week') == '1'
                    and row.get('team') in ('SF', 'LA')
                    and row.get('position') == 'QB' and row.get('gsis_id')):
                if not any(q['gsis_id'] == row['gsis_id'] for q in out):
                    out.append({'gsis_id': row['gsis_id'],
                                'team': row.get('team'),
                                'full_name': row.get('full_name')})
    return out


def test_a_an_inactive_quarterback_owns_exactly_zero_in_every_draw():
    pool = _real_pool()
    if not pool:
        print('  ..   roster vintage unavailable; skipped')
        return
    base = QA.allocate(2026, 1, ['SF', 'LA'], pool, m=200, seed=20260908)
    fixed = QA.allocate(2026, 1, ['SF', 'LA'], pool, m=200, seed=20260908,
                        inactive_ids=[ROURKE, SIMPSON])
    check('both allocations succeed',
          base.state is State.PASS and fixed.state is State.PASS,
          f'{base.code} / {fixed.code}')
    check('the repair reports what it zeroed',
          fixed.evidence.get('n_inactive_qb_zeroed') == 2,
          str(fixed.evidence.get('n_inactive_qb_zeroed')))
    for team, pid, who in (('SF', ROURKE, 'Rourke'), ('LA', SIMPSON, 'Simpson')):
        b, f = base.value[team], fixed.value[team]
        if pid not in b['pids']:
            continue
        i = b['pids'].index(pid)
        check(f'  {who} held share BEFORE the repair',
              float(b['shares'][i].max()) > 0.0,
              f"peak {float(b['shares'][i].max()):.4f}")
        check(f'  {who} holds EXACTLY zero in every draw after it',
              float(np.abs(f['shares'][i]).max()) == 0.0,
              f"max {float(np.abs(f['shares'][i]).max()):.12f}")
        col = f['shares'].sum(0)
        check(f'  {team} shares still close to 1 in every draw',
              float(np.abs(col - 1.0).max()) < 1e-12,
              f'worst deviation {float(np.abs(col - 1.0).max()):.2e}')
        check(f'  {team} mass went to the dressed quarterbacks, not nowhere',
              float(f['shares'].sum(0).min()) > 0.999999)


def test_b_the_mass_is_redistributed_rather_than_discarded():
    """The removed share must reappear on the remaining quarterbacks."""
    pool = _real_pool()
    if not pool:
        print('  ..   roster vintage unavailable; skipped')
        return
    base = QA.allocate(2026, 1, ['SF', 'LA'], pool, m=200, seed=20260908)
    fixed = QA.allocate(2026, 1, ['SF', 'LA'], pool, m=200, seed=20260908,
                        inactive_ids=[ROURKE, SIMPSON])
    for team, pid in (('SF', ROURKE), ('LA', SIMPSON)):
        b, f = base.value[team], fixed.value[team]
        if pid not in b['pids']:
            continue
        i = b['pids'].index(pid)
        others = [j for j in range(len(b['pids'])) if j != i]
        gained = float(f['shares'][others].sum(0).mean()
                       - b['shares'][others].sum(0).mean())
        lost = float(b['shares'][i].mean())
        check(f'  {team}: what the inactive QB lost, the others gained',
              abs(gained - lost) < 1e-9,
              f'lost {lost:.6f} gained {gained:.6f}')


def test_c_the_assertion_rejects_a_seeded_violation():
    """A repair with no assertion is a repair that regresses silently.

    This is exactly how the defect arose in the first place: the argument
    simply stopped being threaded through, and nothing objected.
    """
    rows = [{'gsis_id': 'A', 'season': 2026, 'week': 1, 'team': 'SF'},
            {'gsis_id': 'B', 'season': 2026, 'week': 1, 'team': 'SF'}]
    clean = {'db': np.array([[10, 11, 9], [0, 0, 0]]),
             'att': np.array([[9, 10, 8], [0, 0, 0]])}
    o = QBACC.assert_inactive_qbs_own_nothing(clean, rows, ['B'])
    check('a clean allocation passes the assertion',
          o.state is State.PASS and o.code == 'QB_INACTIVE_OWNS_NOTHING', o.code)

    # ONE dropback in ONE draw out of three. A mean test would call this 0.33
    # and shrug; it is a quarterback who was not dressed taking a snap.
    seeded = {'db': np.array([[10, 11, 9], [0, 1, 0]]),
              'att': np.array([[9, 10, 8], [0, 0, 0]])}
    bad = QBACC.assert_inactive_qbs_own_nothing(seeded, rows, ['B'])
    check('a single seeded draw IS caught',
          bad.state is State.FAIL
          and bad.code == 'QB_INACTIVE_STILL_OWNS_DROPBACKS', bad.code)
    check('  and the offender is named with its magnitude',
          (bad.evidence.get('offenders') or {}).get('B', {}).get('db') == 1.0,
          str(bad.evidence.get('offenders')))

    # NO LIST IS NOT A PASS. It is DEFERRED: as a HARD invariant that is
    # carried as `hard_owed` rather than refusing the seal, so an ordinary
    # game with no published list still seals while recording plainly that
    # this was never established.
    na = QBACC.assert_inactive_qbs_own_nothing(clean, rows, [])
    check('no inactive list DEFERS rather than passing',
          na.state is State.DEFERRED
          and na.code == 'QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED',
          f'{na.state.name}[{na.code}]')


def test_d_a_team_with_no_dressed_quarterback_refuses():
    """Renormalising over an empty pool would divide by zero. Refuse instead."""
    pool = _real_pool()
    if not pool:
        print('  ..   roster vintage unavailable; skipped')
        return
    all_sf = [q['gsis_id'] for q in pool if q['team'] == 'SF']
    o = QA.allocate(2026, 1, ['SF', 'LA'], pool, m=50, seed=20260908,
                    inactive_ids=all_sf)
    check('every SF quarterback inactive -> a named refusal',
          o.state is State.FAIL
          and o.code == 'QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE', o.code)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

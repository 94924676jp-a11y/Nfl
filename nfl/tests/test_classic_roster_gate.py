"""Classic roster-eligibility gate (found absent from the Classic path 2026-10-09). Real 2026W4 Early-only files.

  * the finalized 2026W4 Classic upload passes (no ineligible player was entered);
  * the same upload with one reserve (RES) player injected is refused, naming him;
  * DK club codes and generational suffixes resolve (LAR -> LA, James Cook III); a fixed pool offset that read the
    Classic pool as empty is refused rather than read as 'everyone unknown'.
"""
import csv
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.dfs.salaries import early_only as EO  # noqa: E402
from nfl.tools import classic_upload_verify as V, roster_eligibility as E, showdown_run_guards as G  # noqa: E402

PASSED = FAILED = 0
UP = _REPO / 'nfl/dfs/salaries/DK_2026W4_EARLY_FINAL_DK_UPLOAD_POST_INACTIVES.csv'
ROSTERS = _REPO / 'nfl/vintage/weekly_rosters.dba8eeff1f9c0878.raw.csv.gz'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def test_classic_week4_upload_and_injected_reserve():
    pl = V._plain(EO.slate_files('2026W4'))
    pool = E.dk_pool(pl)
    check(len(pool) > 300, f'Classic pool read from its own header ({len(pool)} players)')
    b, rep = G.upload_roster_eligibility(UP, pl, ROSTERS, 2026, 4)
    check(b == [] and rep['status'] == 'PASS', f'finalized 2026W4 Classic upload passes ({b[:1]})')
    res = E.classify(pool, E.roster_rows(ROSTERS, 2026, 4))
    for k in (('Matthew Stafford', 'LAR'), ('Puka Nacua', 'LAR'), ('James Cook III', 'BUF')):
        check(res.get(k, {}).get('eligible') is True, f'{k[0]} {k[1]} resolves and is ELIGIBLE ({res.get(k, {}).get("reason")})')
    reserve = next((k for k, v in res.items() if v['reason'] == 'RESERVE' and pool[k]['pos'] in ('RB', 'WR', 'TE')), None)
    check(reserve is not None, f'a reserve skill player exists in the pool ({reserve})')
    rows = list(csv.reader(open(UP, encoding='utf-8-sig')))
    hdr = rows[0]
    wr = hdr.index('WR')
    rows[1][wr] = f'{reserve[0]} ({pool[reserve]["ids"][0]})'
    tmp = pathlib.Path(tempfile.mkdtemp()) / 'injected.csv'
    with tmp.open('w', newline='') as f:
        csv.writer(f).writerows(rows)
    b2, rep2 = G.upload_roster_eligibility(tmp, pl, ROSTERS, 2026, 4)
    check(b2 and b2[0].startswith('ROSTER_INELIGIBLE_IN_UPLOAD') and f'{reserve[0]}|{reserve[1]}' in rep2['ineligible_players'],
          f'injected reserve player refused by name ({rep2.get("ineligible_players")})')


def test_pool_header_required():
    tmp = pathlib.Path(tempfile.mkdtemp()) / 'nopool.csv'
    tmp.write_text('Entry ID,Contest Name\n1,x\n')
    try:
        E.dk_pool(tmp)
        check(False, 'an export without a pool block must raise')
    except ValueError as e:
        check('DK_POOL_HEADER_NOT_FOUND' in str(e), f'no pool block refused ({e})')


def test_classic_verify_fails_closed_for_new_slates():
    src = (_REPO / 'nfl/tools/classic_upload_verify.py').read_text()
    check("'ROSTER_ELIGIBILITY_UNVERIFIED (slate declares no roster_capture)'" in src
          and V.LEGACY_PRE_ROSTER_GATE == frozenset({'2026W2', '2026W3', '2026W4'}),
          'a slate from 2026W5 on without roster_capture fails closed; only W2-W4 are legacy NOT_CHECKED')


if __name__ == '__main__':
    test_classic_week4_upload_and_injected_reserve()
    test_pool_header_required()
    test_classic_verify_fails_closed_for_new_slates()

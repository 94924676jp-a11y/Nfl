"""The football universe does not depend on the DK entries export (owner directive 2026-10-09).

`early_only.pool` finds the pool header by its own cells, so a DKSalaries export (pool at column 0) and a DKEntries
export (pool at column 14) give the same rows; `slate_files` carries `pool_blob` defaulting to the entries export, so
registered weeks are unchanged; and a slate with no DK file at all gets a roster-derived research universe whose
ids can never be uploaded."""
import csv
import gzip
import io
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _gz(rows):
    b = io.StringIO()
    csv.writer(b).writerows(rows)
    raw = b.getvalue().encode()
    p = pathlib.Path(tempfile.mkdtemp()) / 'x.csv.gz'
    p.write_bytes(gzip.compress(raw))
    return p


def test_salaries_and_entries_layouts_give_the_same_pool():
    from nfl.dfs.salaries import early_only as EO
    hdr = ['Position', 'Name + ID', 'Name', 'ID', 'Roster Position', 'Salary', 'Game Info', 'TeamAbbrev', 'AvgPointsPerGame']
    body = [['WR', 'A B (1)', 'A B', '1', 'WR/FLEX', '8100', 'CIN@MIA 10/11/2026 01:00PM ET', 'CIN', '15'],
            ['QB', 'C D (2)', 'C D', '2', 'QB', '6000', 'CIN@MIA 10/11/2026 01:00PM ET', 'MIA', '18']]
    sal = _gz([hdr] + body)
    ent = _gz([['Entry ID', 'Contest Name'] + [''] * 12 + ['', 'Instructions'],
               ['1', 'X'] + [''] * 12] + [[''] * 14 + hdr] + [[''] * 14 + r for r in body])
    a, b = EO.pool(sal, None), EO.pool(ent, None)
    check(a.state.value == 'PASS' and b.state.value == 'PASS', f'both layouts parse ({a.code}, {b.code})')
    strip = lambda rows: [{k: v for k, v in r.items()} for r in rows]  # noqa: E731
    check(strip(a.value) == strip(b.value), 'DKSalaries (col 0) and DKEntries (col 14) give identical pool rows')
    check(a.evidence['pool_header_column'] == 0 and b.evidence['pool_header_column'] == 14,
          f"header found by its cells at columns {a.evidence['pool_header_column']} / {b.evidence['pool_header_column']}")
    try:
        EO.pool(_gz([['Entry ID', 'Contest Name'], ['1', 'X']]), None)
        check(False, 'a file with no pool block must raise')
    except EO.PoolNotFound:
        check(True, 'a file with no pool block raises PoolNotFound, never an empty pool')


def test_registered_weeks_unchanged_and_w5_has_no_dk_file():
    from nfl.dfs.salaries import early_only as EO
    f4 = EO.slate_files('2026W4')
    check(f4['pool_blob'] == f4['entries_blob'] and f4['pool_sha'] == f4['entries_sha'] and f4['entries_sha'],
          '2026W4: pool defaults to the entries export, hash from the manifest')
    f5 = EO.slate_files('2026W5')
    check(f5['pool_blob'] is None and f5['entries_blob'] is None, '2026W5: no DK file is registered (none exists)')


def test_research_universe_is_roster_derived_and_not_uploadable():
    from nfl.tools import research_universe as RU
    raw = _REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5'
    u = RU.build('2026W5', raw)
    check(u.state.value == 'PASS' and u.code == RU.CODE, f'{u.code}: {u.detail}')
    rows = u.value
    check(all(r['dk_id'].startswith('RU-') for r in rows), 'every id is synthetic RU-, never a DK id')
    check(all(r['salary'] is None for r in rows), 'no price enters the football universe')
    check(all(r['universe_kind'] == RU.KIND for r in rows), 'every row says NOT_UPLOADABLE')
    clubs = {r['team'] for r in rows}
    check(len(clubs) == 16 and sum(1 for r in rows if r['dk_pos'] == 'DST') == 16, '16 clubs, one defence each')
    ex = u.evidence['excluded_non_act_by_status']
    check(ex.get('DEV', 0) > 0 and ex.get('RES', 0) > 0, f'practice squad and reserve excluded and counted {ex}')
    check({r['kickoff'] for r in rows} == {'10/11/2026 01:00PM ET'}, 'one window, read from the registry')
    from nfl.dfs.salaries import early_only as EO
    s = EO.slate(rows, expected_kickoff='10/11/2026 01:00PM ET')
    check(s.state.value == 'PASS' and len(s.value) == 8, f'the slate check reads 8 games ({s.code})')


def test_research_state_is_never_written_to_the_production_path():
    from nfl.tools import classic_slate_state as CS
    from sportsplatform.governance.outcome import Outcome
    bad = Outcome.ok('SOMETHING_ELSE', value=[])
    o = CS.build('2026W5', as_of='2026-10-09T15:30:00Z', research_universe=bad)
    check(o.state.value != 'PASS' and o.code == 'CLASSIC_STATE_RESEARCH_UNIVERSE_INVALID',
          f'a universe that is not a research universe is refused ({o.code})')


if __name__ == '__main__':
    test_salaries_and_entries_layouts_give_the_same_pool()
    test_registered_weeks_unchanged_and_w5_has_no_dk_file()
    test_research_universe_is_roster_derived_and_not_uploadable()
    test_research_state_is_never_written_to_the_production_path()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

#!/usr/bin/env python3.12
"""Readiness item 7 -- the generic next-slate execution path (nfl/tools/showdown_next_slate.py) refuses by name.

    python3.12 nfl/tests/test_showdown_next_slate.py

Every gate before PROJECT is exercised on the real ATL@NO inputs with one thing broken at a time: a missing config
key, a missing file, the wrong clubs, a starter for one club only, an empty inactive list, a provenance record that
describes a different file, a secondary-source list (runs, never READY), a run after kickoff, a market comparison
before the prop seal. Also: the slate-identity defaults are ATL@NO's, so every existing ATL@NO invocation of the
finishing tools reads and writes the same paths as before.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import showdown_next_slate as NS  # noqa: E402

PASSED = FAILED = 0
R = 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4'
D = 'nfl/dfs/salaries/showdown_atl_no'
BASE = {'tag': 'ATL_NO_2026W4', 'kickoff_utc': '2099-01-01T00:00:00Z', 'scenario': 'TEST_NEVER_RUN',
        'export': f'{R}/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv',
        'designations': f'{D}/DESIGNATIONS_ATL_NO_2026W4_V4_RW_INACTIVES_CHARTFIX.json',
        'official_inactives': f'{R}/OFFICIAL_INACTIVES_ATL_NO_2026W4.json',
        'official_inactives_provenance': f'{R}/OFFICIAL_INACTIVES_ATL_NO_2026W4.PROVENANCE.json',
        'confirmed_starters': f'{D}/STARTERS_ATL_NO_2026W4.json', 'starter_tier': 'PUBLIC_DEPTH_CHART_AND_SNAPS_CITED',
        'depth_chart': f'{R}/depth_charts_2026_ATL_NO.1e6aa6437a6ae01b.csv',
        'contests': {'196285137': {'prize_pool': 100000, 'entry_fee': 0.5, 'max_entries': 150},
                     '196285160': {'prize_pool': 10000, 'entry_fee': 0.25, 'max_entries': 20},
                     '196285161': {'prize_pool': 5000, 'entry_fee': 0.1, 'max_entries': 2}}}


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _write(td, cfg, name='slate.json'):
    p = pathlib.Path(td) / name
    p.write_text(json.dumps(cfg))
    return p


def _refused(fn, code, msg):
    try:
        fn()
        check(False, f'{msg}: not refused')
    except NS.SlateError as e:
        check(str(e).startswith(code), f'{msg} ({str(e)[:100]})')


def _tmpfile(td, name, obj):
    p = pathlib.Path(td) / name
    p.write_text(json.dumps(obj))
    return str(p.relative_to(_REPO)) if p.is_relative_to(_REPO) else str(p)


def test_discover():
    with tempfile.TemporaryDirectory() as td:
        cfg, h = NS.discover(_write(td, BASE), 'final')
        check(set(h) >= {'export', 'official_inactives', 'depth_chart'} and all(len(v['sha256']) == 64 for v in h.values()),
              'every declared input is hashed at discovery')
        bad = {k: v for k, v in BASE.items() if k != 'official_inactives'}
        _refused(lambda: NS.discover(_write(td, bad), 'final'), 'SLATE_CONFIG_MISSING',
                 'final mode without the official inactive list is refused')
        cfg2, _ = NS.discover(_write(td, {k: v for k, v in bad.items() if k != 'official_inactives_provenance'}),
                              'precompute')
        check(cfg2['scenario'] == 'TEST_NEVER_RUN', 'precompute mode may run without the list')
        _refused(lambda: NS.discover(_write(td, {**BASE, 'depth_chart': f'{R}/NO_SUCH.csv'}), 'final'),
                 'INPUT_FILE_MISSING_OR_EMPTY', 'a missing input file is refused')
        _refused(lambda: NS.discover(_write(td, {**BASE, 'tag': 'ATLNO'}), 'final'), 'SLATE_TAG_SHAPE', 'bad tag')
        c = copy.deepcopy(BASE)
        del c['contests']['196285137']['entry_fee']
        _refused(lambda: NS.discover(_write(td, c), 'final'), 'CONTEST_FIELDS_MISSING', 'contest without a fee')
        c = copy.deepcopy(BASE)
        c['contests']['196285137']['max_entries'] = None
        _refused(lambda: NS.discover(_write(td, c), 'final'), 'CONTEST_FIELDS_MISSING',
                 'an unstated entry limit without a declared lower bound')
        c['contests']['196285137']['max_entries_lower_bound'] = 150
        NS.discover(_write(td, c), 'final')
        check(True, 'an unstated entry limit with a declared lower bound (entries held) is accepted, not invented')


def test_verify_inputs():
    with tempfile.TemporaryDirectory(dir=_REPO / 'nfl/tests') as td:
        v = NS.verify_football_inputs(BASE, 'final')
        check(v['officially_verified'] and v['teams'] == ['ATL', 'NO'] and not v['starters_confirmed']
              and not v['ready_eligible'],
              f"official ATL@NO inputs verify ({v['official_inactives_n']} inactives) but with no starter confirmation "
              f"the run is never READY")
        import hashlib as _h
        sha = _h.sha256((_REPO / BASE['confirmed_starters']).read_bytes()).hexdigest()
        okp = _tmpfile(td, 'sp.json', {'sha256': sha, 'CONFIRMED': True, 'source': 'unit test fixture'})
        v = NS.verify_football_inputs({**BASE, 'confirmed_starters_provenance': okp}, 'final')
        check(v['starters_confirmed'] and v['ready_eligible'], 'confirmed starters + official inactives -> READY-eligible')
        nosrc = _tmpfile(td, 'sp2.json', {'sha256': sha, 'CONFIRMED': True})
        check(not NS.verify_football_inputs({**BASE, 'confirmed_starters_provenance': nosrc}, 'final')['ready_eligible'],
              'a confirmation without a source is not a confirmation')
        bad = _tmpfile(td, 'sp3.json', {'sha256': '0' * 64, 'CONFIRMED': True, 'source': 'x'})
        _refused(lambda: NS.verify_football_inputs({**BASE, 'confirmed_starters_provenance': bad}, 'final'),
                 'STARTERS_PROVENANCE_DESCRIBES_ANOTHER_FILE', 'starter provenance for another file is refused')
        _refused(lambda: NS.verify_football_inputs({**BASE, 'tag': 'ATL_TB_2026W4'}, 'final'), 'SLATE_TEAMS_MISMATCH',
                 'an export for other clubs is refused')
        one = _tmpfile(td, 's.json', {'Michael Penix Jr.': 'ATL'})
        _refused(lambda: NS.verify_football_inputs({**BASE, 'confirmed_starters': one}, 'final'),
                 'STARTERS_NOT_CONFIRMED_FOR_BOTH_CLUBS', 'a starter for one club only is refused')
        empty = _tmpfile(td, 'e.json', [])
        _refused(lambda: NS.verify_football_inputs({**BASE, 'official_inactives': empty}, 'final'),
                 'OFFICIAL_INACTIVES_EMPTY', 'an empty inactive list is an error, not "nobody inactive"')
        other = _tmpfile(td, 'o.json', ['Somebody Else'])
        _refused(lambda: NS.verify_football_inputs({**BASE, 'official_inactives': other}, 'final'),
                 'INACTIVES_PROVENANCE_DESCRIBES_ANOTHER_FILE', 'provenance for a different list is refused')
        rw = {**BASE, 'official_inactives': f'{R}/ROTOWIRE_INACTIVES_ATL_NO_2026W4.json',
              'official_inactives_provenance': f'{R}/ROTOWIRE_INACTIVES_ATL_NO_2026W4.PROVENANCE.json'}
        v = NS.verify_football_inputs(rw, 'final')
        check(not v['ready_eligible'] and not v['officially_verified'],
              'a secondary-source list verifies but can never make the run READY')
        check(not NS.verify_football_inputs({**BASE, 'rehearsal': True, 'confirmed_starters_provenance': okp}, 'final')['ready_eligible'],
              'a rehearsal is never READY-eligible')
        import csv
        rows = [r for r in csv.DictReader(open(_REPO / BASE['depth_chart'])) if r['team'] == 'ATL']
        dc = pathlib.Path(td) / 'dc.csv'
        with dc.open('w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        _refused(lambda: NS.verify_football_inputs({**BASE, 'depth_chart': str(dc.relative_to(_REPO))}, 'final'),
                 'DEPTH_CHART_DOES_NOT_COVER_BOTH_CLUBS', 'a chart covering one club is refused')


def test_run_refusals():
    with tempfile.TemporaryDirectory() as td:
        st = NS.run.__wrapped__ if hasattr(NS.run, '__wrapped__') else NS.run
        _refused(lambda: st(_write(td, {**BASE, 'kickoff_utc': '2026-10-06T00:15:00Z'}), 'final'),
                 'RUN_AFTER_KICKOFF', 'a run after kickoff is refused before any projection')
        _refused(lambda: NS.market(_write(td, {**BASE, 'market_dir': 'nfl/tests/NO_SUCH_MARKET_DIR'}), 'x.csv'),
                 'MARKET_BEFORE_SEAL', 'a Hard Rock board before the prop seal is refused')
        ledger = _REPO / D / 'RUN_LEDGER_TEST_NEVER_RUN.json'
        if ledger.exists():
            ledger.unlink()
        # write-once: a refused re-run of an existing scenario leaves that scenario's ledger untouched
        sd, orig = _REPO / D / 'TEST_EXISTING_SCENARIO', _REPO / D / 'RUN_LEDGER_TEST_EXISTING_SCENARIO.json'
        sd.mkdir(exist_ok=True)
        orig.write_text('{"ORIGINAL": true}')
        try:
            _refused(lambda: st(_write(td, {**BASE, 'scenario': 'TEST_EXISTING_SCENARIO'}), 'final'),
                     'SCENARIO_EXISTS', 'a re-run of an existing scenario is refused')
            refused = sorted((_REPO / D).glob('RUN_LEDGER_TEST_EXISTING_SCENARIO.REFUSED_*.json'))
            check(orig.read_text() == '{"ORIGINAL": true}' and len(refused) == 1
                  and 'SCENARIO_EXISTS' in refused[0].read_text(),
                  'the refusal is written to its own ledger; the original run ledger is unchanged')
        finally:
            for f in (_REPO / D).glob('RUN_LEDGER_TEST_EXISTING_SCENARIO*.json'):
                f.unlink()
            sd.rmdir()


def test_postgame_phase():
    import io
    from contextlib import redirect_stdout
    with tempfile.TemporaryDirectory() as td:
        cfg = _write(td, {**BASE, 'scenario': 'TEST_POSTGAME'})
        _refused(lambda: NS.postgame(cfg, []), 'POSTGAME_NEEDS_STANDINGS', 'postgame without standings is refused')
        _refused(lambda: NS.postgame(cfg, ['999=x.zip']), 'POSTGAME_UNDECLARED_CONTEST',
                 'standings for an undeclared contest are refused')
        out = _REPO / D / 'POSTGAME_TEST_POSTGAME.json'
        try:
            with redirect_stdout(io.StringIO()):
                rc = NS.postgame(cfg, ['196285160=already-archived'])
            doc = json.loads(out.read_text())
            c = doc['contests']['196285160']
            check(rc == 0 and c['reconciliation'] == 'RECONCILED' and str(c['grade']).startswith('NOT_GRADED: no sealed shadow'),
                  f"archived ATL@NO 20-max reconciles; with no sealed shadow it is NOT_GRADED, never zero ({c.get('grade')})")
        finally:
            if out.exists():
                out.unlink()


def test_appearance_seal_covers_tb_dal():
    from nfl.research.appearance import grade_appearance_seal as GA
    doc = GA.load_seal(_REPO / 'nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W5_SEAL.json')
    check('2026_05_TB_DAL' in doc['games'] and doc['written_at'] < doc['first_kickoff_utc'],
          f"the week-5 appearance seal verifies and covers TB@DAL, written {doc['written_at']} before {doc['first_kickoff_utc']}")


def test_scenario_isolation_plumbing():
    from nfl.tools import showdown_slate_run as SR
    import tempfile as _tf
    w = pathlib.Path(_tf.mkdtemp())
    P = SR.paths('TB_DAL_2026W5', work=w)
    inside = all(P[k].parent == w for k in ('state', 'proj', 'draws', 'worlds', 'role', 'dst_rates'))
    check(inside, 'with a work directory every intermediate (state, proj, draws, worlds, role, DST rates) is written there')
    legacy = SR.paths('TB_DAL_2026W5')
    check(legacy['role'] is None and legacy['state'].parent == legacy['dir'],
          'without one, the legacy per-tag paths are unchanged')
    before = {'nfl/derived/ROLE_STATE.json': (1, 1), 'nfl/derived/SOURCE_MEASUREMENT_CACHE.json': (1, 1)}
    after = {'nfl/derived/ROLE_STATE.json': (1, 2), 'nfl/derived/SOURCE_MEASUREMENT_CACHE.json': (2, 2)}
    br = NS.shared_writes(before, after, allowed=tuple(NS.SHARED_WRITE_ALLOWED))
    check(br == ['nfl/derived/ROLE_STATE.json'],
          f'a shared write is a breach unless declared scenario-independent ({br})')
    check(NS.shared_writes(before, dict(before)) == [], 'no write, no breach')
    snap = NS._shared_snapshot(w)
    check(isinstance(snap, dict) and any(k.startswith('nfl/derived/') for k in snap),
          'the snapshot covers nfl/derived')


def test_slate_env_defaults_are_atl():
    from nfl.tools import showdown_slate_env as E
    check(E.PREFIX == 'SHOWDOWN_ATL_NO' and E.TAG == 'ATL_NO_2026W4' and E.WEEK == '4'
          and E.RAW_DIR == _REPO / R and E.MAIN_CONTEST == '196285137' and E.TWO_ENTRY == '196285161',
          f'defaults reproduce the ATL@NO literals ({E.PREFIX}, {E.RAW_DIR.name}, {E.MAIN_CONTEST}, {E.TWO_ENTRY})')
    check({c: (v['prize_pool'], v['entry_fee']) for c, v in E.CONTESTS.items()} ==
          {'196285137': (100000, 0.50), '196285160': (10000, 0.25), '196285161': (5000, 0.10)},
          'default contest prizes equal the old CONTEST_PRIZE literal')
    left = []
    for f in ('nfl/tools/showdown_portfolio_audit.py', 'nfl/field/showdown_shadow_field.py',
              'nfl/field/showdown_shadow_board.py', 'nfl/field/showdown_archetype_field.py',
              'nfl/tools/showdown_external_claims.py', 'nfl/tools/showdown_prelock_board.py',
              'nfl/tools/showdown_cycle1_checks.py'):
        s = (_REPO / f).read_text()
        if 'SHOWDOWN_ATL_NO_' in s or 'showdown_atl_no_2026W4' in s or "'196285" in s:
            left.append(f)
    check(left == [], f'no ATL@NO file prefix, raw path or contest id left in the finishing tools ({left})')


if __name__ == '__main__':
    for t in (test_discover, test_verify_inputs, test_run_refusals, test_postgame_phase, test_appearance_seal_covers_tb_dal,
              test_scenario_isolation_plumbing, test_slate_env_defaults_are_atl):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

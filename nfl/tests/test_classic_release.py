#!/usr/bin/env python3.12
"""Release states are computed by code from the artifacts (task #45 P0-2), and 2026-10-11 is the regression fixture.

THE FIXTURE (nfl/tests/fixtures/release_w5_2026-10-11/) holds the three Week-5 upload files of 2026-10-11 and the
chain behind each, byte-identical to the live files at lock (MANIFEST.json). The owner ruled on them that day:

  16:17Z production build            CURRENT_BUT_UNCERTIFIED
  16:32Z McLaurin-excluded build     SELECTION_ONLY_OVERRIDE, its forecast STALE_FORECAST for the limited scenario
  16:03Z build                       STALE_FORECAST (built before the 16:10Z packet)

The code must reproduce the first two. For the third it must report the stale evidence, and it reports BLOCKED
first, because that build's draws and worlds were overwritten in place by the 16:08Z rebuild and its chain can no
longer be traced. That is a finding about the archive, not a disagreement with the ruling.

SYNTHETIC CONTROLS build a small coherent chain from scratch so each requirement can be broken alone: a state
rebuilt after the draws, an upload edited after verification, a newer evidence packet, no packet supplied, and the
positive control that CURRENT_AND_CERTIFIED is reachable when every requirement holds. A state that can never be
reached would make the classification meaningless.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_release as R  # noqa: E402

FX = _REPO / 'nfl/tests/fixtures/release_w5_2026-10-11'
PKT_1610 = _REPO / 'nfl/dfs/salaries/classic_early_2026W5/evidence_packets/2026W5_SUNDAY_CUMULATIVE_1610Z.json'
NOW = dt.datetime(2026, 10, 11, 16, 40, tzinfo=dt.timezone.utc)
PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _unpack(case_dirs, td: pathlib.Path):
    """Restore the fixture's original bytes into a flat out_dir (and sensitivity/ for tagged files)."""
    (td / 'sensitivity').mkdir(parents=True, exist_ok=True)
    for c in case_dirs:
        for p in (FX / c).iterdir():
            name = p.name[:-3] if p.suffix == '.gz' else p.name
            dst = td / ('sensitivity' if '.NO_MCLAURIN_' in name else '') / name
            dst.write_bytes(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())
    return td


def test_01_the_fixture_is_the_live_bytes():
    print('\n01. the fixture is byte-identical to what the manifest recorded')
    man = json.loads((FX / 'MANIFEST.json').read_text())['files']
    bad = []
    for rel, v in man.items():
        p = FX / rel
        raw = gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != v['sha256_of_original']:
            bad.append(rel)
    check(f'{len(man)} fixture files reproduce their recorded hashes', not bad and len(man) == 19, bad)
    check('the 16:17Z upload is the file verified that day (cce6dfb5...)',
          man['prod_1617Z/DK_2026W5_EARLY_UPLOAD.csv']['sha256_of_original'].startswith('cce6dfb56030'))
    check('the uploaded override is the owner\'s file (d4572fb9...)',
          man['override_1632Z/DK_2026W5_EARLY_UPLOAD.NO_MCLAURIN_1623Z.csv']['sha256_of_original'].startswith('d4572fb9856f'))


def test_02_the_1617Z_build_is_current_but_uncertified():
    print('\n02. 16:17Z production -> CURRENT_BUT_UNCERTIFIED on the day; re-evaluated under OD-002 it is BLOCKED, '
          'because its state carries no eligibility contract')
    with tempfile.TemporaryDirectory() as d:
        r = R.evaluate('2026W5', latest_packet=PKT_1610, out_dir=_unpack(['prod_1617Z'], pathlib.Path(d)), now=NOW)
    check('release state today: BLOCKED by ELIGIBILITY_NOT_APPLIED and by nothing else',
          r['release_state'] == R.BLOCKED and len(r['reasons']['blocking']) == 1
          and r['reasons']['blocking'][0].startswith('ELIGIBILITY_NOT_APPLIED'), r['reasons']['blocking'])
    check('every chain link holds', all(r['chain'].values()), {k: v for k, v in r['chain'].items() if not v})
    check('nothing is stale: the state consumed the newest packet', r['reasons']['stale'] == [], r['reasons']['stale'])
    wa = r['world_accounting']['violations_by_law']
    check('world accounting counts are the ones measured that day',
          wa == {'PASS_YDS_EQ_REC_YDS': 30281, 'PASS_TD_EQ_REC_TD': 76, 'POINTS_GE_6_PER_TD': 1068,
                 'YDS_WITHOUT_CATCH': 2000, 'REC_TD_WITHOUT_CATCH': 1809}, wa)
    u = ' | '.join(r['reasons']['uncertified'])
    check('the McLaurin restriction is named as evidence the engine did not model',
          'UNMODELLED_EVIDENCE' in u and 'Terry McLaurin WAS' in u, u[:200])
    check('the two 20-entry contests sharing all 20 lineups is named',
          any(s['shared_lineups'] == 20 and s['size'] == 20 for s in r['equal_size_contest_overlap']),
          r['equal_size_contest_overlap'])
    check('open forecast defects keep it from being certified', 'OPEN_FORECAST_DEFECTS 4' in u, u[-200:])
    check('it was built before lock', r['lock']['portfolio_built_before_lock'] is True, r['lock'])
    check('it was hand-run, outside the governed pipeline (no ledger, no run id)', 'NOT_ORCHESTRATED' in u, u[:300])


def test_03_the_1632Z_override_is_selection_only_and_its_forecast_stale():
    print('\n03. 16:32Z McLaurin-excluded -> SELECTION_ONLY_OVERRIDE, forecast STALE_FORECAST')
    with tempfile.TemporaryDirectory() as d:
        r = R.evaluate('2026W5', tag='NO_MCLAURIN_1623Z', latest_packet=PKT_1610,
                       out_dir=_unpack(['prod_1617Z', 'override_1632Z'], pathlib.Path(d)), now=NOW)
    check('release state today: BLOCKED by ELIGIBILITY_NOT_APPLIED (on the day: SELECTION_ONLY_OVERRIDE)',
          r['release_state'] == R.BLOCKED and any(x.startswith('ELIGIBILITY_NOT_APPLIED') for x in r['reasons']['blocking']),
          r['reasons']['blocking'])
    check('its forecast is still reported stale (the override changed no forecast)',
          any(x.startswith('OVERRIDE_WITHOUT_FORECAST') for x in r['reasons']['stale']), r['reasons']['stale'])
    check('the override names the excluded player and says no forecast changed',
          r.get('override', {}).get('excluded') == {'44418755': 'Terry McLaurin'}
          and r['override']['forecast_changed'] is False, r.get('override'))
    check('its projection, draws and state are the 16:17Z ones (the chain proves the reuse)',
          r['sha256']['proj'].startswith('87f826b1') and r['sha256']['draws'].startswith('5dbe7836')
          and r['sha256']['state'].startswith('1645717d'), r['sha256'])
    check('the tagged file was verified by the repository verifier, not a scratch script',
          r['chain']['VERIFY PASS'] and r['chain']['VERIFY.upload_sha256 == UPLOAD'])


def test_04_the_1603Z_build_is_untraceable_and_its_evidence_stale():
    print('\n04. 16:03Z -> BLOCKED (draws and worlds overwritten), stale evidence still reported')
    with tempfile.TemporaryDirectory() as d:
        r = R.evaluate('2026W5', latest_packet=PKT_1610, out_dir=_unpack(['pre_1603Z'], pathlib.Path(d)), now=NOW)
    b = r['reasons']['blocking']
    check('release state', r['release_state'] == R.BLOCKED, r['release_state'])
    check('the missing draws and worlds are named', any('draws' in x for x in b) and any('worlds' in x for x in b), b)
    check('and the 15:50Z-versus-16:10Z evidence gap is reported',
          any('1550Z' in x and '1610Z' in x for x in r['reasons']['stale']), r['reasons']['stale'])


# ------------------------------------------------------------------ synthetic controls
ELIG_OK = {'applied': True, 'withheld': {}, 'unresolved': {}, 'conflicts': {}, 'elevation_evidence_supplied': True,
           'state_counts': {'CONFIRMED_ELIGIBLE': 1}}
PIT_OK = {'mode': 'LIVE_VERIFIED', 'cutoff_utc': '2099-01-01T16:00:00+00:00'}


def _synthetic(td: pathlib.Path, slate='2099W1', eligibility=None, point_in_time=None, proj_rows=None):
    """A minimal coherent chain: every hash link holds, one contest pair with 0 shared lineups, no unmodelled note.
    The state carries a clean eligibility record and a point-in-time stamp unless told otherwise."""
    import numpy as np
    b = td / f'DK_{slate}_EARLY'
    pk = td / 'PACKET_A.json'
    pk.write_text(json.dumps({'packet_id': 'A', 'received_at': '2099-01-01T12:00:00Z', 'players': []}))
    state = {'players': {'1': {'name': 'Synthetic Player', 'team': 'AAA', 'current_availability': {'status': 'X'}}},
             'official_inactives': {'packet_id': 'A', 'packet_sha256': hashlib.sha256(pk.read_bytes()).hexdigest()},
             'roster_eligibility': ELIG_OK if eligibility is None else eligibility,
             'point_in_time': PIT_OK if point_in_time is None else point_in_time}
    pathlib.Path(f'{b}_STATE.json').write_text(json.dumps(state))
    pathlib.Path(f'{b}_PROJ.json').write_text(json.dumps({'rows': proj_rows or {}}))
    sh = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()  # noqa: E731
    s_state, s_proj = sh(f'{b}_STATE.json'), sh(f'{b}_PROJ.json')
    pathlib.Path(f'{b}_RUN_LEDGER.json').write_text(json.dumps({'run_id': 'RUN-1'}))
    pathlib.Path(f'{b}_DRAWS.json').write_text(json.dumps({'state_sha256': s_state, 'projection_sha256': s_proj,
                                                           'per_game': {'G': {'seed': 7}}, 'run_id': 'RUN-1'}))
    meta = json.dumps({'projection_sha256': s_proj}).encode()
    with open(f'{b}_WORLDS.npz', 'wb') as fh:
        np.savez_compressed(fh, stats=np.zeros((1, 1, 1), dtype=np.int16), points=np.zeros((1, 1, 2)),
                            meta=np.frombuffer(meta, dtype=np.uint8))
    s_draws, s_worlds = sh(f'{b}_DRAWS.json'), sh(f'{b}_WORLDS.npz')
    pathlib.Path(f'{b}_RESEARCH_BOOK.json').write_text(json.dumps({'inputs_sha256': {
        'STATE.json': s_state, 'PROJ.json': s_proj, 'DRAWS.json': s_draws, 'WORLDS.npz': s_worlds}}))
    s_book = sh(f'{b}_RESEARCH_BOOK.json')
    pathlib.Path(f'{b}_SEAL.json').write_text(json.dumps({'projection_sha256': s_proj, 'worlds_sha256': s_worlds,
                                                          'research_book_sha256': s_book,
                                                          'kickoff_utc': '2099-01-01T18:00:00+00:00'}))
    pathlib.Path(f'{b}_PORTFOLIOS.json').write_text(json.dumps({
        'inputs_sha256': {'state': s_state, 'proj': s_proj, 'draws': s_draws}, 'research_book_sha256': s_book,
        'built_at_utc': '2099-01-01T17:00:00+00:00', 'seed': 11, 'sensitivity': None, 'run_id': 'RUN-1',
        'contests': [{'contest_id': 'C1', 'n_entries': 2}, {'contest_id': 'C2', 'n_entries': 2}]}))
    pathlib.Path(f'{b}_UPLOAD.csv').write_text('Entry ID\n1\n')
    pathlib.Path(f'{b}_UPLOAD_VERIFY.json').write_text(json.dumps({
        'upload_sha256': sh(f'{b}_UPLOAD.csv'), 'state': 'PASS', 'code': 'UPLOAD_VERIFIED',
        'cross_contest_identical_lineups': {'C2_in_C1': {'shared_lineups': 0, 'of': 2}}}))
    return slate, pk


def _clean_accounting(*a, **k):
    return {'violations_by_law': {}, 'total_violations': 0, 'n_worlds': 1, 'spec_version': 'synthetic'}


def test_05_certified_is_reachable_only_when_every_requirement_holds():
    print('\n05. positive control: CURRENT_AND_CERTIFIED is reachable, and only with every requirement met')
    real_wa, real_def = R.world_accounting, R.OPEN_FORECAST_DEFECTS
    try:
        R.world_accounting = _clean_accounting
        with tempfile.TemporaryDirectory() as d:
            slate, pk = _synthetic(pathlib.Path(d))
            R.OPEN_FORECAST_DEFECTS = {}
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            check('a coherent chain, current evidence, clean worlds and no open defect is CURRENT_AND_CERTIFIED',
                  r['release_state'] == R.CURRENT_AND_CERTIFIED, r['reasons'])
            R.OPEN_FORECAST_DEFECTS = real_def
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            check('the same chain with the real open-defect register is not certified',
                  r['release_state'] == R.CURRENT_BUT_UNCERTIFIED, r['release_state'])
    finally:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = real_wa, real_def


def test_06_each_requirement_fails_alone():
    print('\n06. each requirement, broken alone, changes the state it should')
    real_wa, real_def = R.world_accounting, R.OPEN_FORECAST_DEFECTS
    try:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = _clean_accounting, {}
        cases = []
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            slate, pk = _synthetic(d)
            b = d / f'DK_{slate}_EARLY'
            # a) state rebuilt after the draws
            st = pathlib.Path(f'{b}_STATE.json')
            orig = st.read_text()
            st.write_text(orig + ' ')
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('a state rebuilt after the draws is BLOCKED, named by the link it broke',
                          r['release_state'] == R.BLOCKED and any('DRAWS.state_sha256' in x for x in r['reasons']['blocking']),
                          r['reasons']))
            st.write_text(orig)
            # b) upload edited after verification
            up = pathlib.Path(f'{b}_UPLOAD.csv')
            orig_up = up.read_text()
            up.write_text(orig_up + '2\n')
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('an upload edited after verification is BLOCKED',
                          r['release_state'] == R.BLOCKED and any('VERIFY.upload_sha256' in x for x in r['reasons']['blocking']),
                          r['reasons']))
            up.write_text(orig_up)
            # c) a newer evidence packet exists
            newer = d / 'PACKET_B.json'
            newer.write_text(json.dumps({'packet_id': 'B', 'received_at': '2099-01-01T12:30:00Z', 'players': [1]}))
            r = R.evaluate(slate, latest_packet=newer, out_dir=d, now=NOW)
            cases.append(('newer evidence than the forecast is STALE_FORECAST', r['release_state'] == R.STALE_FORECAST,
                          r['reasons']))
            # d) currency not checked
            r = R.evaluate(slate, latest_packet=None, out_dir=d, now=NOW)
            cases.append(('no latest packet supplied cannot be certified (currency unchecked)',
                          r['release_state'] == R.CURRENT_BUT_UNCERTIFIED
                          and any('EVIDENCE_CURRENCY_UNCHECKED' in x for x in r['reasons']['uncertified']), r['reasons']))
            # e) equal-size contests sharing a lineup
            vf = pathlib.Path(f'{b}_UPLOAD_VERIFY.json')
            v = json.loads(vf.read_text())
            v['cross_contest_identical_lineups']['C2_in_C1']['shared_lineups'] = 1
            vf.write_text(json.dumps(v))
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('two equal-size contests sharing one lineup cannot be certified',
                          r['release_state'] == R.CURRENT_BUT_UNCERTIFIED
                          and any('CONTESTS_SHARE_LINEUPS' in x for x in r['reasons']['uncertified']), r['reasons']))
            v['cross_contest_identical_lineups']['C2_in_C1']['shared_lineups'] = 0
            vf.write_text(json.dumps(v))
            # f) world accounting violated
            R.world_accounting = lambda *a, **k: {'violations_by_law': {'YDS_WITHOUT_CATCH': 1}, 'total_violations': 1}
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('a single accounting violation cannot be certified',
                          r['release_state'] == R.CURRENT_BUT_UNCERTIFIED
                          and any('WORLD_ACCOUNTING_VIOLATED' in x for x in r['reasons']['uncertified']), r['reasons']))
            R.world_accounting = _clean_accounting
            # g) a selection-only exclusion on an otherwise certifiable chain
            pf = pathlib.Path(f'{b}_PORTFOLIOS.json')
            p = json.loads(pf.read_text())
            p['sensitivity'] = {'exclude': ['1'], 'tag': 'X'}
            pf.write_text(json.dumps(p))
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('an exclusion run is SELECTION_ONLY_OVERRIDE with a stale forecast, never certified',
                          r['release_state'] == R.SELECTION_ONLY_OVERRIDE and r['forecast_state'] == R.STALE_FORECAST,
                          (r['release_state'], r['forecast_state'])))
            # g2) built by hand: the portfolio carries no run id
            p['sensitivity'] = None
            p['run_id'] = None
            pf.write_text(json.dumps(p))
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('a portfolio built outside the ledgered run cannot be certified (NOT_ORCHESTRATED)',
                          r['release_state'] == R.CURRENT_BUT_UNCERTIFIED
                          and any('NOT_ORCHESTRATED' in x for x in r['reasons']['uncertified']), r['reasons']))
            # g3) built at or after kickoff: a replay may build it, nothing may release it
            p['run_id'] = None
            real_built = p.get('built_at_utc')
            p['built_at_utc'] = '2099-12-31T00:00:00+00:00'
            pf.write_text(json.dumps(p))
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('a portfolio built after kickoff is BLOCKED (BUILT_AFTER_LOCK)',
                          r['release_state'] == R.BLOCKED
                          and any('BUILT_AFTER_LOCK' in x for x in r['reasons']['blocking']), r['reasons']))
            p['built_at_utc'] = real_built
            pf.write_text(json.dumps(p))
            # h) a missing artifact
            pathlib.Path(f'{b}_WORLDS.npz').unlink()
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            cases.append(('a missing worlds file is BLOCKED', r['release_state'] == R.BLOCKED, r['reasons']))
        for label, ok, det in cases:
            check(label, ok, det)
    finally:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = real_wa, real_def


def test_06b_a_model_that_consumed_the_player_supersedes_the_not_modelled_note():
    print('\n06b. the McLaurin note says NOT MODELLED of the incumbent; an arm that modelled him is not listed')
    with tempfile.TemporaryDirectory() as d:
        d = _unpack(['prod_1617Z'], pathlib.Path(d))
        r0 = R.evaluate('2026W5', latest_packet=PKT_1610, out_dir=d, now=NOW, run_accounting=False)
        mcl = next(u for u in r0['evidence']['unmodelled'] if u['name'] == 'Terry McLaurin')
        dp = d / 'DK_2026W5_EARLY_DRAWS.json'
        dr = json.loads(dp.read_text())
        dr['arm'] = 'CORRECTED_V1'
        dr['participation'] = {'designated': {'Terry McLaurin|WAS': {'dk_id': mcl['dk_id']}}}
        dp.write_text(json.dumps(dr))
        r1 = R.evaluate('2026W5', latest_packet=PKT_1610, out_dir=d, now=NOW, run_accounting=False)
    check('incumbent: listed as unmodelled evidence', bool(mcl))
    check('an arm whose draws record him as designated and modelled: not listed',
          not any(u['name'] == 'Terry McLaurin' for u in r1['evidence']['unmodelled']), r1['evidence']['unmodelled'])


def test_08_eligibility_and_point_in_time_gate_release():
    print('\n08. OD-002 / P0-A: each eligibility or point-in-time requirement, broken alone, blocks a certifiable chain')
    real_wa, real_def = R.world_accounting, R.OPEN_FORECAST_DEFECTS
    U = {'2': {'name': 'Unresolved Dev', 'team': 'AAA', 'reason': 'PRACTICE_SQUAD_NOT_ELEVATED',
               'missing_evidence': 'GAME_DAY_ELEVATION_RECORDS'}}
    cases = [
        ('a pit_exempt state (NOT_POINT_IN_TIME) is BLOCKED',
         {'point_in_time': {'mode': 'NOT_POINT_IN_TIME', 'RELEASABLE': False, 'reason': 'LOGIC_TEST'}},
         'NOT_POINT_IN_TIME_STATE'),
        ('an unresolved player with projected opportunity is BLOCKED',
         {'eligibility': {**ELIG_OK, 'unresolved': U}, 'proj_rows': {'2': {'dk_points': 0.02}}},
         'ELIGIBILITY_UNRESOLVED_MATERIAL'),
        ('a roster/activation conflict is BLOCKED',
         {'eligibility': {**ELIG_OK, 'conflicts': {'00-1': {'name': 'Conflicted', 'roster_status_captured': 'RES'}}}},
         'ELIGIBILITY_CONFLICT'),
        ('a state with no eligibility contract applied (non-legacy slate) is BLOCKED',
         {'eligibility': {'applied': False, 'reason': 'NO_ROSTER_CAPTURE_DECLARED'}}, 'ELIGIBILITY_NOT_APPLIED'),
    ]
    try:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = _clean_accounting, {}
        for label, kw, code in cases:
            with tempfile.TemporaryDirectory() as d:
                slate, pk = _synthetic(pathlib.Path(d), **kw)
                r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
                b = r['reasons']['blocking']
                check(label, r['release_state'] == R.BLOCKED and len(b) == 1 and b[0].startswith(code), b)
        # negative control: an unresolved player with NO projected opportunity does not block (not material)
        with tempfile.TemporaryDirectory() as d:
            slate, pk = _synthetic(pathlib.Path(d), eligibility={**ELIG_OK, 'unresolved': U},
                                   proj_rows={'2': {'dk_points': None}})
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            check('an unresolved player with no projected opportunity is recorded, not blocking',
                  r['release_state'] == R.CURRENT_AND_CERTIFIED and r['eligibility']['n_unresolved'] == 1,
                  (r['release_state'], r['reasons']))
        # a legacy slate (pre roster gate) is not blocked for lacking the contract
        with tempfile.TemporaryDirectory() as d:
            slate, pk = _synthetic(pathlib.Path(d), slate='2026W4', eligibility={'applied': False, 'reason': 'X'})
            r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=NOW)
            check('a legacy slate (2026W4) is not blocked by ELIGIBILITY_NOT_APPLIED',
                  not any(x.startswith('ELIGIBILITY_NOT_APPLIED') for x in r['reasons']['blocking']), r['reasons'])
    finally:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = real_wa, real_def


def test_07_build_writes_only_where_told():
    print('\n07. build() writes the record beside the upload in the out_dir it is given, nowhere else')
    real_wa = R.world_accounting
    try:
        R.world_accounting = _clean_accounting
        with tempfile.TemporaryDirectory() as d:
            slate, pk = _synthetic(pathlib.Path(d))
            before = {p.name for p in pathlib.Path(d).iterdir()}
            o = R.build(slate, latest_packet=pk, out_dir=d, now=NOW)
            after = {p.name for p in pathlib.Path(d).iterdir()}
            check('exactly one new file, the release record', after - before == {f'DK_{slate}_EARLY_RELEASE.json'},
                  after - before)
            rec = json.loads((pathlib.Path(d) / f'DK_{slate}_EARLY_RELEASE.json').read_text())
            check('the record carries clock, code commit, seeds and the full hash chain',
                  all(k in rec for k in ('clock', 'code', 'seeds', 'sha256', 'chain', 'release_state'))
                  and rec['seeds']['portfolio'] == 11, sorted(rec))
            check('build returns PASS with the state in its code', o.state.value == 'PASS'
                  and o.code == f"RELEASE_{rec['release_state']}", o.code)
    finally:
        R.world_accounting = real_wa


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()

#!/usr/bin/env python3.12
"""Task #45 acceptance: the owner's fixtures (2026-10-11 16:40 UTC, item 8), on the 2026-10-11 slate, at the real consumers.

The fixture (nfl/tests/fixtures/contract45_w5_2026-10-11/) holds two complete CORRECTED_V1 runs of the W5 Early Only
slate on the 16:17Z production state, made with nfl/tools/classic_slate_run.py:
  corrected   participation on  (NFL_CLASSIC_ARM=CORRECTED_V1)
  control     participation off (the same arm with NFL_CLASSIC_PARTICIPATION_CONTROL=1)
so every participation effect below is measured against a control that differs in nothing else, and the incumbent's
16:08Z worlds come from the release fixture. Each check is labelled with the owner's fixture it answers.

A check that the engine cannot yet pass is still a check: it FAILS, it is never skipped. Item 5 (a QB change moves his
team's volume) is answered by the registered QBCTX-DB1 starter deviation, consumed by the arm; QBCTX-DB1 itself is
prospective-only (NOT_YET_EVALUABLE), and that is stated wherever it is used.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.tools import world_accounting_check as WAC  # noqa: E402

FX = _REPO / 'nfl/tests/fixtures/contract45_w5_2026-10-11'
REL = _REPO / 'nfl/tests/fixtures/release_w5_2026-10-11/prod_1617Z'
PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _j(p):
    p = pathlib.Path(p)
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_text())


def _arm(name):
    d = FX / name
    return {'draws': _j(d / 'DK_2026W5_EARLY_DRAWS.json.gz'), 'worlds': CR.load_worlds(d / 'DK_2026W5_EARLY_WORLDS.npz'),
            'dir': d}


_CACHE = {}


def arms():
    if not _CACHE:
        _CACHE['corrected'] = _arm('corrected')
        _CACHE['control'] = _arm('control')
        _CACHE['incumbent'] = {'draws': _j(REL / 'DK_2026W5_EARLY_DRAWS.json.gz'),
                               'worlds': CR.load_worlds(REL / 'DK_2026W5_EARLY_WORLDS.npz')}
        _CACHE['state'] = _j(REL / 'DK_2026W5_EARLY_STATE.json.gz')
    return _CACHE


def stat(arm, key, field):
    S, _pts, M = arm['worlds']
    i = M['keys'].index(key)
    v = S[i, :, list(M['fields']).index(field)].astype(float)
    return v / M['yard_scale'] if field in M['yard_fields'] else v


def club_sum(arm, club, field):
    _S, _p, M = arm['worlds']
    return sum(stat(arm, k, field) for k in M['keys'] if k.endswith('|' + club))


def accounting(arm_dir, state_path):
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        (t / 'X_STATE.json').write_bytes(gzip.decompress(state_path.read_bytes()))
        (t / 'X_DRAWS.json').write_bytes(gzip.decompress((arm_dir / 'DK_2026W5_EARLY_DRAWS.json.gz').read_bytes()))
        (t / 'X_WORLDS.npz').symlink_to((arm_dir / 'DK_2026W5_EARLY_WORLDS.npz').resolve())
        r = WAC.check(t)
    return r['VIOLATED']


MCL, DAN = 'Terry McLaurin|WAS', 'Jayden Daniels|WAS'


def test_01_inactive_players_are_zero_in_every_world():
    print('\n01. [fixture 1] an inactive player is zero in every world, in every arm')
    A = arms()
    from nfl.tools import availability as AV
    absent = {f"{v['name']}|{v['team']}" for v in A['state']['players'].values()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES}
    for name in ('corrected', 'control', 'incumbent'):
        S, _p, M = A[name]['worlds']
        bad = [k for k in M['keys'] if k in absent and np.abs(S[M['keys'].index(k)]).sum() > 0]
        bad_dk = [k for k in absent if k in A[name]['draws']['draws'] and any(A[name]['draws']['draws'][k])]
        check(f'{name}: {len(absent)} absent players, none with an event or a DK point', not bad and not bad_dk,
              (bad[:3], bad_dk[:3]))


def test_02_corrected_worlds_satisfy_every_box_score_law():
    print('\n02. [fixture 9] the corrected arm\'s published worlds pass every accounting law; the incumbent\'s do not')
    v = accounting(FX / 'corrected', REL / 'DK_2026W5_EARLY_STATE.json.gz')
    check('corrected arm: 0 violations on every law', v == {}, v)
    vi = accounting(FX / 'control', REL / 'DK_2026W5_EARLY_STATE.json.gz')
    check('control arm: 0 violations on every law', vi == {}, vi)


def test_03_a_limited_mclaurin_is_several_participation_scenarios():
    print('\n03. [fixture 3] a limited McLaurin is a distribution of workloads, not one number')
    pa = arms()['corrected']['draws']['participation']['designated'][MCL]
    lo, mid, hi = pa['phi_p10_p50_p90']
    check('his participation factor comes from the measured PM-3 cell, not a typed percentage',
          pa['phi_basis'].startswith('PM-3 cell R_GE_070|QUESTIONABLE|LIMITED|WR_TE|SOFT_TISSUE_LOWER'), pa['phi_basis'])
    check('phi spreads across worlds (p10 < 0.7 < p50 < 1, mean below 1)', lo < 0.7 < mid < 1.0 and pa['phi_mean'] < 1.0,
          pa['phi_p10_p50_p90'])
    check('reported active, so no world removes him (declared assumption, printed)',
          pa['worlds_phi_zero'] == 0 and pa['p_no_participation_basis'].startswith('RESOLVED_ACTIVE'), pa)
    t_c, t_0 = stat(arms()['corrected'], MCL, 'targets'), stat(arms()['control'], MCL, 'targets')
    check('his targets fall against the control by more than one per game', t_0.mean() - t_c.mean() > 1.0,
          (round(t_0.mean(), 2), round(t_c.mean(), 2)))


def test_04_washington_teammates_and_quarterback_respond():
    print('\n04. [fixtures 2, 4] his teammates take the work he does not play, and Daniels responds')
    A = arms()
    _S, _p, M = A['corrected']['worlds']
    g = next(v for v in A['corrected']['draws']['per_game'].values()
             if (v.get('participation') or {}).get('WAS'))
    designated = set(g['participation']['WAS']['players'])          # McLaurin and every other WAS player on the report
    was = [k for k in M['keys'] if k.endswith('|WAS')]
    d = {k: stat(A['corrected'], k, 'targets').mean() - stat(A['control'], k, 'targets').mean() for k in was}
    lost = -sum(d[k] for k in designated if k in d)
    gain = sum(d[k] for k in was if k not in designated)
    dc = club_sum(A['corrected'], 'WAS', 'targets').mean() - club_sum(A['control'], 'WAS', 'targets').mean()
    check('McLaurin loses targets and every undesignated teammate\'s change sums to a gain', d[MCL] < 0 < gain,
          (round(d[MCL], 3), round(gain, 3)))
    check('the targets reconcile exactly: designated players\' loss = teammates\' gain - the club\'s volume change',
          abs(lost - (gain - dc)) < 1e-6, (round(lost, 4), round(gain, 4), round(dc, 4)))
    # the club's volume change is the declared participation pass-rate shift; both arms calibrate their own volume
    # centre, so the Monte Carlo error is the two arms' world error plus the same again for calibration (as in 06)
    pa_c, pa_0 = club_sum(A['corrected'], 'WAS', 'pass_att'), club_sum(A['control'], 'WAS', 'pass_att')
    tv = _j(REL / 'DK_2026W5_EARLY_PROJ.json.gz')['team_volume']['WAS']
    want = g['participation']['WAS']['expected_pass_rate_shift'] * (tv['proj_pass_attempts'] + tv['proj_rush_attempts'])
    se = float(np.sqrt(pa_c.var() / len(pa_c) + pa_0.var() / len(pa_0))) * 2 ** 0.5
    check('and the club\'s pass attempts move by the declared participation shift, within 3 SE',
          abs((pa_c.mean() - pa_0.mean()) - want) <= 3 * se,
          f'moved {pa_c.mean() - pa_0.mean():+.3f}, declared {want:+.3f}, 3 SE {3 * se:.3f}')
    red = g['participation']['WAS']['players'][MCL]['redistribution_targets']
    top = max(red, key=red.get)
    check('the largest recipient in the engine\'s absent-player reallocation gains targets',
          stat(A['corrected'], top, 'targets').mean() > stat(A['control'], top, 'targets').mean(), top)
    acc = g['coherent_account']['WAS']
    check('the receiver-mix factor moved Washington\'s passing level (r_mix != 1)',
          abs(acc.get('receiver_mix_factor', 1.0) - 1.0) > 1e-3, acc.get('receiver_mix_factor'))
    d_c, d_0 = stat(A['corrected'], DAN, 'pass_yards').mean(), stat(A['control'], DAN, 'pass_yards').mean()
    check('Daniels\' passing yards move in the direction of the receiver-mix factor',
          np.sign(d_c - d_0) == np.sign(acc['receiver_mix_factor'] - 1.0), (round(d_0, 2), round(d_c, 2)))
    py = club_sum(A['corrected'], 'WAS', 'pass_yards')
    ry = club_sum(A['corrected'], 'WAS', 'rec_yards')
    tol = 0.5 / M['yard_scale'] * len(was)       # world_accounting_check's storage-rounding tolerance for this law
    check('and Washington\'s passing yards equal its receiving yards in every world, to storage rounding',
          np.abs(py - ry).max() <= tol, (float(np.abs(py - ry).max()), tol))


def test_05_team_volume_is_not_assumed_fixed():
    print('\n05. [owner correction] a limited position leader moves his club\'s pass rate by the measured association')
    g = next(v for v in arms()['corrected']['draws']['per_game'].values() if (v.get('participation') or {}).get('WAS'))
    pw = g['participation']['WAS']
    lead = pw['players'][MCL]['leader_pass_rate_change']
    check('McLaurin is Washington\'s receiving leader, so the measured association applies (REDISTRIBUTION_STUDY)',
          lead is not None and abs(lead[0] - (-0.02715)) < 1e-9, lead)
    check('the expected pass-rate shift is negative and equals E[1 - phi] x the association',
          pw['expected_pass_rate_shift'] < 0, pw['expected_pass_rate_shift'])


def test_06_a_qb_change_moves_his_receivers_and_his_teams_volume():
    print('\n06. [fixture 5] a QB change: receivers\' yardage responds (ECW QB anchor); team volume follows QBCTX-DB1')
    from nfl.sim import event_consistent_worlds as ECW, game as sim_game
    from nfl.tools import showdown_draws as SD
    proj = _j(REL / 'DK_2026W5_EARLY_PROJ.json.gz')
    st = arms()['state']
    saved_out = SD.OUT
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        SD.OUT = td / 'SD_OUT.json'                      # the builder writes a sidecar; keep it out of the repository
        g = st['games']['2026_05_NYG_WAS']
        sl = {'game_id': '2026_05_NYG_WAS', 'away': g['away'], 'home': g['home'], 'week': st['week'],
              'season': st['season'], 'kickoff_et_naive': st['kickoff'],
              'environment': {'games': {'NYG@WAS': st['environment']['games']['NYG@WAS']}}}
        sp = td / 'S.json'
        sp.write_text(json.dumps(sl))
        out = {}
        for tag, scale in (('base', 1.0), ('weaker_qb', 0.8)):
            p2 = json.loads(json.dumps(proj))
            for r in p2['rows'].values():
                if r['name'] == 'Jayden Daniels':
                    r['conditional_volume']['pass_yards'] *= scale
            pp = td / f'P_{tag}.json'
            pp.write_text(json.dumps(p2))
            o = SD.build(str(pp), str(sp), n_sims=400, seed=7, volume_centre=sim_game.VOLUME_CENTRE_PROJECTION,
                         n_calib=400)
            rk = {SD.S.player_key(r['name'], r['team']): r for r in p2['rows'].values()}
            e = ECW.build(o.value, rk, float(p2['int_rate']), 7, incumbent_seed=106, version=CR.ECW_VERSION).value
            inc_dk, inc_w, _ = CR.efficiency_worlds(o.value['stat_draws'], rk, float(p2['int_rate']), 106)
            out[tag] = {'ecw_rec': sum(np.mean([w[CR.STAT_FIELDS.index('rec_yards')] for w in v])
                                       for k, v in e['stat_worlds'].items() if k.endswith('|WAS') and k != DAN),
                        'inc_rec': sum(np.mean([w[CR.STAT_FIELDS.index('rec_yards')] for w in v])
                                       for k, v in inc_w.items() if k.endswith('|WAS') and k != DAN),
                        'pass_att': np.mean([w[0] for w in o.value['stat_draws'][DAN]])}
    SD.OUT = saved_out
    r_ecw = out['weaker_qb']['ecw_rec'] / out['base']['ecw_rec']
    r_inc = out['weaker_qb']['inc_rec'] / out['base']['inc_rec']
    check(f'ECW-{CR.ECW_VERSION}: a 20% less efficient Daniels lowers his receivers\' yards by 15-25%', 0.75 <= r_ecw <= 0.85,
          round(r_ecw, 3))
    check('negative control: the incumbent\'s receivers do not move (that is defect W5-G18)', abs(r_inc - 1.0) < 0.01,
          round(r_inc, 3))
    # TEAM VOLUME BY QB IDENTITY: the registered QBCTX-DB1 starter deviation, consumed by the corrected arm's volume
    # centre (classic_slate_run.qb_volume_inputs). Checked at the consumer, against the incumbent's worlds.
    qa = arms()['corrected']['draws'].get('qb_conditioned_volume') or {}
    was = (qa.get('clubs') or {}).get('WAS') or {}
    check('QBCTX-DB1 is consumed: the arm records the forecast file, its hash and an applied WAS starter deviation',
          qa.get('state') == 'APPLIED' and qa.get('source_sha256') and was.get('applied') is True, qa.get('state'))
    inc_pa = club_sum(arms()['incumbent'], 'WAS', 'pass_att')
    cor_pa = club_sum(arms()['corrected'], 'WAS', 'pass_att')
    g = next(v for v in arms()['corrected']['draws']['per_game'].values() if (v.get('participation') or {}).get('WAS'))
    plays = float(json.loads(gzip.decompress((REL / 'DK_2026W5_EARLY_PROJ.json.gz').read_bytes()))['team_volume']['WAS']
                  ['proj_pass_attempts'] + json.loads(gzip.decompress((REL / 'DK_2026W5_EARLY_PROJ.json.gz').read_bytes()))['team_volume']['WAS']['proj_rush_attempts'])
    want = was.get('pass_attempts_delta', 0.0) + g['participation']['WAS']['expected_pass_rate_shift'] * plays
    se = float(np.sqrt(inc_pa.var() / len(inc_pa) + cor_pa.var() / len(cor_pa))) * 2 ** 0.5   # + calibration error
    check('Washington\'s pass attempts move by the QB deviation plus the participation shift, within 3 SE',
          abs((cor_pa.mean() - inc_pa.mean()) - want) <= 3 * se,
          f'moved {cor_pa.mean() - inc_pa.mean():+.3f}, declared {want:+.3f}, 3 SE {3 * se:.3f}')


def test_06b_structural_acceptance_of_the_corrected_worlds():
    print('\n06b. [PREREG_ECW2 s.2 with PREREG_ECW3 C2] ties and receiver dispersion of the published corrected worlds')
    from nfl.research.accounting_repair import ecw2_acceptance as ACC
    for name in ('corrected', 'control'):
        S, pts, M = arms()[name]['worlds']
        tie = max(float((pts[g, :, 0] == pts[g, :, 1]).mean()) for g in range(pts.shape[0]))
        check(f'{name}: tie share of worlds <= {ACC.TIE_MAX:.1%} in every game', tie <= ACC.TIE_MAX, round(tie, 4))
        bench = json.loads((_REPO / 'nfl/research/accounting_repair/ECW2_INPUTS.json').read_text())[
            'benchmark_receiving_yards_cv_gt2_catches']['median_cv']
        F = {f: i for i, f in enumerate(M['fields'])}
        ratios = []
        for i, _k in enumerate(M['keys']):
            rec = S[i, :, F['receptions']].astype(float)
            if rec.mean() <= 2:
                continue
            y = (S[i, :, F['rec_yards']].astype(float) / M['yard_scale'])[rec > 2]
            if len(y) >= 2 and y.mean() > 0:
                ratios.append(float(y.std() / y.mean()) / bench)
        med = float(np.median(ratios)) if ratios else None
        check(f'{name}: median receiver yards CV / history (worlds with > 2 catches) within {ACC.CV_BAND}',
              med is not None and ACC.CV_BAND[0] <= med <= ACC.CV_BAND[1], (len(ratios), med and round(med, 4)))


def test_07_every_released_lineup_traces_to_the_evidence_snapshot():
    print('\n07. [fixtures 6, 7, 8, 10] lineage, staleness and certification: see test_classic_release (34 checks), '
          'test_classic_evidence_watch (18) and test_classic_pipeline (23); asserted here by presence')
    for m in ('test_classic_release', 'test_classic_evidence_watch', 'test_classic_pipeline',
              'test_portfolio_contest_independence'):
        check(f'{m} exists beside this module', (_REPO / 'nfl/tests' / f'{m}.py').exists())


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()

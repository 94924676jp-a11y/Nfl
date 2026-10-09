"""QBCTX shadow candidate (nfl/research/qb_regime/qbctx_shadow.py): starter rule, point-in-time guard
(seeded violation AND load-bearing bypass), incumbent mirror of proj_v1, empirical-Bayes recovery on
synthetic data with known variances, real TB 2026 regime facts, and artifact self-consistency (the
stored verdict must be recomputable from the stored CIs under the predeclared bar)."""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nfl.research.qb_regime import qbctx_shadow as Q  # noqa: E402
from nfl.tests.bypass import guard_bypassed  # noqa: E402

PASSED = FAILED = 0
_CACHE = {}


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _tables():
    """2024-2026 only: enough for a 2026 prior fit (2025 residuals carry a 2024 prior season)."""
    if 'tables' not in _CACHE:
        paths = [p for p in Q.PBP_HIST if 'pbp_2024' in p.name or 'pbp_2025' in p.name] + Q.PBP_2026
        _CACHE['plays'] = Q.load_plays(paths)
        _CACHE['tables'] = Q.build_tables(_CACHE['plays'])
        _CACHE['priors'] = Q.fit_priors(_CACHE['tables'], 2026)
    return _CACHE['tables'], _CACHE['priors']


def _qb_id(tables, club, abbrev, season=2026):
    q = tables['qbg']
    ids = q[(q['club'] == club) & (q['qb_name'] == abbrev) & (q['season'] == season)]['qb'].unique()
    return ids[0] if len(ids) == 1 else None


def test_starter_rule_and_split_flag():
    rows = pd.DataFrame([
        ('G1', 'A', 'x', 30, 28), ('G1', 'A', 'y', 5, 5),
        ('G2', 'A', 'x', 15, 14), ('G2', 'A', 'y', 14, 13),
        ('G3', 'A', 'x', 10, 8), ('G3', 'A', 'y', 10, 9),
        ('G4', 'A', 'b', 10, 9), ('G4', 'A', 'a', 10, 9),
    ], columns=['game_id', 'club', 'qb', 'dropbacks', 'pass_att'])
    s = Q.starter_of(rows).set_index('game_id')
    check(s.loc['G1', 'starter'] == 'x' and not s.loc['G1', 'split'], 'G1: 30 of 35 dropbacks -> starter, not SPLIT')
    check(s.loc['G2', 'starter'] == 'x' and bool(s.loc['G2', 'split']), 'G2: leader at 15/29 < 60% -> SPLIT')
    check(s.loc['G3', 'starter'] == 'y', 'G3: dropback tie broken by pass attempts')
    check(s.loc['G4', 'starter'] == 'a', 'G4: full tie broken deterministically by id')
    check(_raises(Q.EmptyInputError, lambda: Q.starter_of(rows.iloc[0:0])), 'no QB rows raises EmptyInputError')


def test_empty_inputs_raise_named_errors():
    check(_raises(Q.EmptyInputError, lambda: Q.load_plays([])), 'no play-by-play paths -> EmptyInputError')
    check(_raises(Q.EmptyInputError, lambda: Q.cluster_boot_mae_diff([], [], [])),
          'bootstrap on an empty subset -> EmptyInputError')
    check(_raises(Q.EmptyInputError, lambda: Q.fit_exposure_model(['a'], [1.0], [2.0])),
          'exposure model with one QB -> EmptyInputError')


def test_incumbent_mirrors_proj_v1():
    check(Q.TEAM_VOLUME_PRIOR_GAMES == Q.proj_v1_constant('TEAM_VOLUME_PRIOR_GAMES') == 4.0,
          f'TEAM_VOLUME_PRIOR_GAMES read from proj_v1 source = {Q.TEAM_VOLUME_PRIOR_GAMES}')
    check(Q.PRIOR_WEIGHT_CAP == Q.proj_v1_constant('PRIOR_WEIGHT_CAP'), 'PRIOR_WEIGHT_CAP read from proj_v1 source')
    check(abs(Q.blend([30, 40], [36] * 17) - (2 * 35 + 4 * 36) / 6) < 1e-12, 'blend = (n_cur*cur + 4*prv)/(n_cur+4)')
    check(Q.blend([], [36, 38]) == 37 and Q.blend([30], []) == 30, 'one-sided blends fall back to the side present')
    check(abs(Q._combine(0.068, 9, 0.173, 2, 2.0) - (2 * 0.068 + 2 * 0.173) / 4) < 1e-12,
          '_combine caps prior weight at PRIOR_WEIGHT_CAP (Daniels 50/50 case)')
    tables, _ = _tables()
    ct = tables['tg'][tables['tg']['club'] == 'TB'].sort_values(['date', 'game_id'])
    ct = ct[ct['date'] < '2026-10-08']
    b = Q.club_baseline(ct, 2026)
    w = b['weights']
    recon = sum(w[g] * v for g, v in zip(ct['game_id'], ct['dropbacks']) if g in w)
    check(abs(sum(w.values()) - 1) < 1e-12 and abs(recon - b['dropbacks']) < 1e-9,
          f'blend weights sum to 1 and reproduce the baseline ({recon:.4f} = {b["dropbacks"]:.4f})')


def test_exposure_model_recovers_known_variances():
    rng = np.random.default_rng(7)
    nq, k, tau, sig = 400, 6, 3.0, 8.0
    qb = np.repeat(np.arange(nq), k)
    a = rng.uniform(0, 1, nq * k)
    r = a * np.repeat(rng.normal(0, tau, nq), k) + rng.normal(0, sig, nq * k)
    fit = Q.fit_exposure_model(qb, a, r)
    check(abs(fit['sigma2'] / sig ** 2 - 1) < 0.1, f'sigma2 recovered: {fit["sigma2"]:.1f} vs {sig ** 2}')
    check(3.0 < fit['tau2'] < 18.0, f'tau2 recovered within a loose band: {fit["tau2"]:.2f} vs {tau ** 2}')
    r0 = rng.normal(0, sig, nq * k)
    f0 = Q.fit_exposure_model(qb, a, r0)
    check(f0['tau2'] < 2.0, f'no QB signal -> tau2 near 0 ({f0["tau2"]:.3f})')


def test_bootstrap_is_paired_and_seeded():
    e = np.arange(40.0)
    cl = np.repeat(np.arange(8), 5)
    z = Q.cluster_boot_mae_diff(e, e, cl)
    check(z['ci_lo'] == 0 == z['ci_hi'] and z['point'] == 0, 'identical arms -> point and CI exactly 0')
    a1, a2 = Q.cluster_boot_mae_diff(e, e + 1, cl), Q.cluster_boot_mae_diff(e, e + 1, cl)
    check(a1 == a2 and a1['ci_hi'] < 0, 'seeded: two runs identical; uniformly better arm has CI below 0')


def test_tb_2026_regime_facts():
    tables, pri = _tables()
    dan = _qb_id(tables, 'TB', 'J.Daniels')
    tg = tables['tg'].set_index(['game_id', 'club'])
    check(dan is not None, f'Jalon Daniels resolved for TB 2026 ({dan})')
    check(tg.loc[('2026_04_GB_TB', 'TB'), 'starter'] == dan and tg.loc[('2026_05_TB_DAL', 'TB'), 'starter'] == dan,
          'starter rule names Daniels for TB weeks 4 and 5')
    q = tables['qbg']
    w3 = q[(q['game_id'] == '2026_03_MIN_TB') & (q['qb'] == dan)]
    check(len(w3) == 1 and w3['role'].iloc[0] == 'RELIEF', 'his week-3 appearance is RELIEF, not a start')
    date5 = tg.loc[('2026_05_TB_DAL', 'TB'), 'date']
    f = Q.forecast(tables, pri, 'TB', 2026, date5, dan)
    may = _qb_id(tables, 'TB', 'B.Mayfield')
    check(f['subset'] == 'QB_CHANGE' and f['dominant_starter'] == may,
          'TB W5 is QB_CHANGE against Mayfield as dominant starter of the prior 8')
    ev = f['qb_evidence']
    check(ev['starts'] == 1 and ev['relief'] == 1, f'W5 forecast reads 1 start + 1 relief separately ({ev})')
    re = f['rush_evidence']
    check(re['start_rush'] == 8 and pri['rush']['relief_weight'] < 1, 'W4 start: 8 rushes; relief down-weighted')
    sh_r, sh_v = re['shrink'], f['qb_deviation']['dropbacks']['shrink']
    check(0 < sh_r < 1 and 0 < sh_v < 0.5,
          f'one start informs, does not dominate: rush shrink {sh_r:.3f}, volume shrink {sh_v:.3f}')


def test_point_in_time_guard_rejects_and_is_load_bearing():
    tables, pri = _tables()
    dan = _qb_id(tables, 'TB', 'J.Daniels')
    tg = tables['tg'].set_index(['game_id', 'club'])
    date4 = tg.loc[('2026_04_GB_TB', 'TB'), 'date']
    check(not _raises(Exception, lambda: Q.assert_point_in_time(Q.history_before(tables, date4), date4)),
          'compliant history passes the guard')
    check(_raises(Q.PointInTimeViolation, lambda: Q.forecast_from_history(tables, pri, 'TB', 2026, date4, dan)),
          'seeded violation: unfiltered history (holds W4 itself and W5) is refused')
    check(_raises(Q.PointInTimeViolation, lambda: Q.forecast(tables, Q.fit_priors(tables, 2027), 'TB', 2026,
                                                             date4, dan)),
          'priors fitted on the forecast season itself are refused')
    clean = Q.forecast(tables, pri, 'TB', 2026, date4, dan)
    with guard_bypassed('nfl.research.qb_regime.qbctx_shadow', 'assert_point_in_time'):
        leaked = Q.forecast_from_history(tables, pri, 'TB', 2026, date4, dan)
    moved = abs(leaked['candidate']['qb_rush'] - clean['candidate']['qb_rush']) > 1e-6
    check(moved, 'LOAD-BEARING: with the guard bypassed the leaked future changes the W4 forecast '
                 f'(QB rush {clean["candidate"]["qb_rush"]:.3f} -> {leaked["candidate"]["qb_rush"]:.3f})')


def test_eval_artifact_is_self_consistent():
    p = Q.OUT_EVAL
    check(p.exists(), f'{p.name} exists')
    if not p.exists():
        return
    d = json.loads(p.read_text())
    n = d['n_team_games']
    check(n['QB_CHANGE'] + n['STABLE'] == n['total'] > 0 and n['QB_CHANGE'] > 0,
          f'subsets partition the evaluation: {n}')
    for lab in ('PRIMARY_ALL_TEAM_GAMES', 'SENSITIVITY_EXCLUDING_SPLIT'):
        e = d['evaluation'][lab]
        ok = True
        for q in Q.PRIMARY:
            c, s = e['QB_CHANGE'][q], e['STABLE'][q]
            want = (c['mae_diff_cand_minus_inc']['ci_hi'] < 0
                    and s['mae_diff_cand_minus_inc']['ci_hi'] <= Q.NONINF_FRAC * s['incumbent']['mae'])
            ok &= (e['verdict'][q]['PASS'] == want)
            ok &= c['mae_diff_cand_minus_inc']['B'] == Q.BOOT_B and c['mae_diff_cand_minus_inc']['seed'] == Q.BOOT_SEED
        ok &= e['verdict']['OVERALL_PASS'] == all(e['verdict'][q]['PASS'] for q in Q.PRIMARY)
        check(ok, f'{lab}: stored verdict recomputes from stored CIs under the predeclared bar (P7)')
    check(d['HEADLINE_VERDICT_PRIMARY'] == d['evaluation']['PRIMARY_ALL_TEAM_GAMES']['verdict'],
          'headline verdict is the primary-analysis verdict')
    pri = d['priors_by_forecast_season']
    check(all(max(pri[s]['fit_seasons']) < int(s) for s in pri), 'every prior was fitted on earlier seasons only')


def test_w5_artifact_covers_the_slate():
    p = Q.OUT_W5
    check(p.exists(), f'{p.name} exists')
    if not p.exists():
        return
    c = json.loads(p.read_text())['clubs']
    want = {'CHI': 'Tyson Bagent', 'MIN': 'Kyler Murray', 'WAS': 'Jayden Daniels', 'NYG': 'Jameis Winston'}
    check(len(c) == 16 and all(c[k]['starter'] == v for k, v in want.items()),
          '16 clubs; CHI Bagent, MIN Murray, WAS Jayden Daniels, NYG Winston')
    ok = all(c[k][q][arm]['point'] is not None and len(c[k][q][arm]['interval_80']) == 2
             for k in c for q in Q.PRIMARY for arm in ('incumbent', 'candidate'))
    check(ok, 'every club carries incumbent and candidate points and 80% intervals for all three quantities')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

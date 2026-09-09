"""RBDEP: RB1 <-> RB2 teammate dependence, and the guards around measuring it.

Two things are under test. The ABLATION SWITCH in `p4c_build.gen_weights`,
which must change nothing unless it is asked for and must refuse rather than
silently ignore a malformed request. And the MEASUREMENT DISCIPLINE, because
B11's headline number was a within-team-game conditional correlation set beside
a between-team-game realised one, and nothing in the repository would have
caught that.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT,
           os.path.join(_ROOT, 'nfl', 'research', 'p1'),
           os.path.join(_ROOT, 'nfl', 'research', 'p2'),
           os.path.join(_ROOT, 'nfl', 'research', 'p3'),
           os.path.join(_ROOT, 'nfl', 'research', 'p4b'),
           os.path.join(_ROOT, 'nfl', 'research', 'p4c'),
           os.path.join(_ROOT, 'nfl', 'research', 'rbdep')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4c_build as CB                                            # noqa: E402
import rbdep_lib as L                                             # noqa: E402
import run_rbdep as RR                                            # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402
from sportsplatform.governance.outcome import (                   # noqa: E402
    Outcome, State)

PASSED = FAILED = 0
RES = os.path.join(_ROOT, 'nfl', 'research', 'rbdep', 'rbdep_results.json')
BASE = os.path.join(_ROOT, 'nfl', 'research', 'rbdep', 'rbdep_baseline.json')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _par(seed=7):
    rng = np.random.default_rng(seed)
    return {'add_pool': {'RB': rng.normal(0, .05, 4000).astype(np.float32),
                         'WR': rng.normal(0, .03, 3000).astype(np.float32)},
            'lr_pool': {}, 'sigma_lr': {}, 'sigma_lg': {}, 'q_zero': {},
            'prior': {}, 'mass_pool': np.full(50, .2, np.float32),
            'mass_mean': .2, 'alpha0': 5.0}


def _fixture(n_groups=6, per=4):
    n = n_groups * per
    rng = np.random.default_rng(3)
    C = np.abs(rng.normal(.15, .05, n)).astype(np.float32)
    pos = ['RB'] * n
    groups = np.repeat(np.arange(n_groups, dtype=np.int64), per)
    return C, pos, groups, n


# ---------------------------------------------------------------- A
def test_A_the_default_is_untouched():
    print('\nA. the ablation is opt-in and the default is unchanged')
    sig = inspect.signature(CB.gen_weights)
    check('gen_weights takes add_pool_groups',
          'add_pool_groups' in sig.parameters)
    check('  and its default is None, so production behaviour is the default',
          sig.parameters['add_pool_groups'].default is None)
    par = _par()
    C, pos, groups, n = _fixture()
    a = CB.gen_weights('C', C, pos, par, 'carries', n, 400,
                       np.random.default_rng(11))
    b = CB.gen_weights('C', C, pos, par, 'carries', n, 400,
                       np.random.default_rng(11), add_pool_groups=None)
    check('  omitting it and passing None are bit-identical',
          np.array_equal(a, b))
    s = CB.gen_weights('C', C, pos, par, 'carries', n, 400,
                       np.random.default_rng(11), add_pool_groups=groups)
    check('  and passing groups DOES change the draw, so the switch is real',
          not np.array_equal(a, s))


# ---------------------------------------------------------------- B
def test_B_the_shared_arm_shares_and_only_that():
    print('\nB. what the shared arm actually does')
    par = _par()
    C, pos, groups, n = _fixture()
    # The RESIDUAL is what is shared. `gen_weights` clips C + residual into
    # [0, 1] afterwards, and that clip can separate two team-mates whose C
    # differ, so the sharing property is asserted on the residual itself.
    r = CB._resample(par['add_pool'], pos, n, 400, np.random.default_rng(11),
                     par['add_pool']['RB'], groups=groups)
    ri = CB._resample(par['add_pool'], pos, n, 400, np.random.default_rng(11),
                      par['add_pool']['RB'], groups=None)
    check('team-mates in one team-game receive the SAME residual',
          all(np.allclose(r[g * 4], r[g * 4 + k], atol=1e-6)
              for g in range(len(groups) // 4) for k in (1, 2, 3)))
    check('  different team-games receive different residuals',
          not np.allclose(r[0], r[4], atol=1e-6))
    check('  the incumbent does NOT share them',
          not np.allclose(ri[0], ri[1], atol=1e-6))
    pool = np.round(np.sort(par['add_pool']['RB']), 6)
    check('  every shared draw is a member of the same pool, so the per-row '
          'MARGINAL law is unchanged',
          bool(np.isin(np.round(r[0], 6), pool).all()))
    check('  and so is every incumbent draw, from the same pool',
          bool(np.isin(np.round(ri[0], 6), pool).all()))
    check('  the two arms agree on the pooled residual mean to MC noise',
          abs(float(r.mean()) - float(ri.mean())) < 0.005,
          (float(r.mean()), float(ri.mean())))
    # and the clip is what separates team-mates in W, not the sharing
    W = CB.gen_weights('C', C, pos, par, 'carries', n, 400,
                       np.random.default_rng(11), add_pool_groups=groups)
    unclipped = (C[:, None] + r > 0) & (C[:, None] + r < 1)
    both = unclipped[0] & unclipped[1]
    check('  where the [0,1] clip does not bind, two team-mates differ by '
          'exactly their C, so only the residual was shared',
          bool(np.allclose((W[0] - W[1])[both], (C[0] - C[1]), atol=1e-5)),
          int(both.sum()))


# ---------------------------------------------------------------- C
def test_C_malformed_requests_are_refused_not_ignored():
    print('\nC. seeded violations of the switch contract')
    par = _par()
    C, pos, groups, n = _fixture()

    def raises(code, **kw):
        try:
            CB.gen_weights('C', C, pos, par, 'carries', n, 50,
                           np.random.default_rng(1), **kw)
        except ValueError as exc:
            return str(exc).startswith(code)
        return False

    check('a group vector of the wrong length is refused',
          raises('SHARED_ADD_POOL_GROUP_SHAPE', add_pool_groups=groups[:5]))
    check('a float group vector is refused',
          raises('SHARED_ADD_POOL_GROUP_SHAPE',
                 add_pool_groups=groups.astype(float)))
    check('a negative group id is refused',
          raises('SHARED_ADD_POOL_GROUP_NEGATIVE',
                 add_pool_groups=groups - 1))
    try:
        CB.gen_weights('D_dir', C, pos, par, 'carries', n, 50,
                       np.random.default_rng(1), add_pool_groups=groups)
        ok = False
    except ValueError as exc:
        ok = str(exc).startswith('SHARED_ADD_POOL_NOT_APPLICABLE')
    check('a system that does not draw from add_pool refuses the argument '
          'rather than accepting and ignoring it', ok)


# ---------------------------------------------------------------- D
def test_D_the_like_for_like_discipline_is_enforced_by_construction():
    print('\nD. the B11 measurement defect, as a regression test')
    # A team-game whose two backs COMPETE within a draw (negative conditional
    # dependence) but whose conditional MEANS move together across team-games
    # (a shared level). The within statistic and the between statistic then
    # carry opposite signs -- which is exactly the B11 situation.
    rng = np.random.default_rng(5)
    G, M = 200, 300
    level = rng.normal(20, 5, G)[:, None]
    u = rng.normal(0, 1, (G, M))
    N1 = np.maximum(level + u, 0.0)
    N2 = np.maximum(level - u, 0.0)          # anti-correlated WITHIN, shared level
    T = np.full((G, M), 30.0)
    d = L.dependence(N1, N2, T, N1[:, 0], N2[:, 0], np.full(G, 30.0))
    w = d['NOT_COMPARABLE_within_team_game_across_draws_counts']
    b = d['LIKE_FOR_LIKE_between_team_game_counts']['median']
    check('the within-team-game statistic is strongly NEGATIVE here', w < -0.8,
          w)
    check('  the between-team-game statistic is strongly POSITIVE here',
          b > 0.8, b)
    check('  so the two cannot be substituted, and the artifact names which '
          'is which', w * b < 0)
    check('  the comparable one is labelled LIKE_FOR_LIKE',
          'LIKE_FOR_LIKE_between_team_game_counts' in d)
    check('  the incomparable ones are labelled NOT_COMPARABLE / FORBIDDEN',
          'NOT_COMPARABLE_within_team_game_across_draws_counts' in d
          and 'FORBIDDEN_corr_of_predictive_means' in d)


# ---------------------------------------------------------------- E
def test_E_the_predeclaration_guard_is_load_bearing():
    print('\nE. the pre-registration hash guard')
    fh = tempfile.NamedTemporaryFile('w', suffix='.md', delete=False)
    fh.write('a pre-registration that does not match its pin\n')
    fh.close()
    try:
        assert_guard_is_load_bearing(
            run=lambda: RR.verify_predeclaration(fh.name, 'f' * 64),
            module_path='run_rbdep', attr='verify_predeclaration',
            caught=lambda o: o.state is State.FAIL,
            returns=Outcome.ok('STUB_NO_CHECK', value=True))
        ok, why = True, ''
    except AssertionError as exc:
        ok, why = False, str(exc)[:160]
    finally:
        os.unlink(fh.name)
    check('a moved pre-registration is refused, and bypassing the guard lets '
          'it through', ok, why)
    real = RR.verify_predeclaration()
    check('  the real pre-registration matches its pin',
          real.state is State.PASS, f'{real.code} {real.detail[:90]}')
    check('  and the pin is a full sha256',
          len(RR.PREDECLARATION_SHA256) == 64)


# ---------------------------------------------------------------- F
def test_F_the_future_season_guard_is_load_bearing():
    print('\nF. no 2026 outcome can enter this experiment')
    rows = [{'season': s} for s in (2020, 2021, 2022, 2023, 2024, 2025)]
    clean = L.assert_no_future_season(rows)
    check('a clean panel passes', clean.state is State.PASS, clean.code)
    check('  and 2020/2021 are recorded as never scored',
          clean.evidence['burn_in_never_scored'] == [2020, 2021])
    leaking = rows + [{'season': 2026}]
    try:
        assert_guard_is_load_bearing(
            run=lambda: L.assert_no_future_season(leaking),
            module_path='rbdep_lib', attr='assert_no_future_season',
            caught=lambda o: (o.state is State.FAIL
                              and o.code == 'RBDEP_FUTURE_SEASON_IN_PANEL'),
            returns=Outcome.ok('STUB_NO_CHECK', value=True))
        ok, why = True, ''
    except AssertionError as exc:
        ok, why = False, str(exc)[:160]
    check('a seeded 2026 row is REFUSED, not filtered, and the guard is what '
          'refuses it', ok, why)


# ---------------------------------------------------------------- G
def test_G_the_hard_gates_refuse_what_they_claim_to():
    print('\nG. allocation closure, negativity, cap repair')
    clean = {'G1_closure_violations': 0, 'G2_budget_violations': 0,
             'G3_negative_shares': 0, 'G3_negative_counts': 0,
             'G4_waterfill_bind': 0, 'G5_weight_floor_rate': 0.2}
    check('clean gate counts pass', L.gates_verdict(clean).state is State.PASS)
    for k in ('G1_closure_violations', 'G2_budget_violations',
              'G3_negative_shares', 'G3_negative_counts',
              'G4_waterfill_bind'):
        seeded = dict(clean, **{k: 1})
        o = L.gates_verdict(seeded)
        check(f'  a seeded {k} is refused',
              o.state is State.FAIL and o.code == 'RBDEP_HARD_GATE_FAILED',
              o.code)
    check('  a nonzero G5 floor rate alone is NOT a refusal -- the incumbent '
          'already floors, and a rate is not a pass',
          L.gates_verdict(dict(clean, G5_weight_floor_rate=0.9)).state
          is State.PASS)
    try:
        assert_guard_is_load_bearing(
            run=lambda: L.gates_verdict(dict(clean, G1_closure_violations=7)),
            module_path='rbdep_lib', attr='gates_verdict',
            caught=lambda o: (o.state is State.FAIL
                              and o.code == 'RBDEP_HARD_GATE_FAILED'),
            returns=Outcome.ok('STUB_NO_CHECK', value={}))
        ok, why = True, ''
    except AssertionError as exc:
        ok, why = False, str(exc)[:160]
    check('  and gates_verdict is what refuses a broken allocation -- with it '
          'bypassed the same counts pass', ok, why)


# ---------------------------------------------------------------- H
def test_H_the_shrink_frame_is_a_shrink_and_nothing_else():
    print('\nH. Frame L')
    starts = np.array([0, 3], dtype=np.int64)
    counts = np.array([3, 2])
    C = np.array([.4, .2, .1, .5, .1], np.float32)
    check('lambda = 1 returns C unchanged, so Frame H IS the incumbent frame',
          np.array_equal(L.shrink_C(C, starts, counts, 1.0), C))
    flat = L.shrink_C(C, starts, counts, 0.0)
    check('  lambda = 0 makes every back in a team-game equal',
          np.allclose(flat[:3], flat[0]) and np.allclose(flat[3:], flat[3]))
    for lam in (0.0, 0.25, 0.5, 0.75, 1.0):
        s = L.shrink_C(C, starts, counts, lam)
        check(f'  lambda={lam} preserves each team-game total (a shrink '
              f'toward the mean cannot move the sum)',
              abs(float(s[:3].sum() - C[:3].sum())) < 1e-5
              and abs(float(s[3:].sum() - C[3:].sum())) < 1e-5)


# ---------------------------------------------------------------- I
def test_I_the_artifacts_say_what_they_measured():
    print('\nI. the artifacts')
    if not os.path.exists(RES):
        check('rbdep_results.json exists', False,
              f'{RES} absent -- run nfl/research/rbdep/run_rbdep.py')
        return
    r = json.load(open(RES))
    check('rbdep_results.json exists and carries a verdict',
          bool(r.get('verdict')), r.get('verdict'))
    check('  it labels itself EXPLORATORY, because the evaluation seasons are '
          'the seasons the model was selected on',
          r.get('exploratory', '').startswith('EXPLORATORY'))
    check('  the pre-registration hash is recorded with the result',
          r['predeclaration']['evidence']['sha256']
          == RR.PREDECLARATION_SHA256)
    arms = r['arms']
    check('  both arms ran at every pre-declared lambda',
          len(arms) == 2 * len(L.LAMBDA_GRID), len(arms))
    bad = []
    for k, v in arms.items():
        g = v['gates']
        if any(g[q] for q in ('G1_closure_violations', 'G2_budget_violations',
                              'G3_negative_shares', 'G3_negative_counts',
                              'G4_waterfill_bind')):
            bad.append(k)
        if v['gate_verdict']['state'] != 'PASS':
            bad.append(k + ':verdict')
    check('  every arm reports exact closure, zero negatives, no cap repair',
          not bad, bad)
    for k, v in arms.items():
        if not k.endswith('lambda=1.0'):
            check(f'  {k} scores NO marginal quality (Frame L forbids it)',
                  v['marginals'].get('state') == 'NOT_APPLICABLE',
                  v['marginals'].get('state'))
    if os.path.exists(BASE):
        b = json.load(open(BASE))
        h = b['historical_half']['prior_weeks']
        check('  the baseline reproduces the realised historical dependence '
              'to within 0.06 of the -0.329 B11 quotes',
              abs(h['realised_between_team_game_counts'] + 0.329) < 0.06,
              h['realised_between_team_game_counts'])
        check('  and on the same frame the INCUMBENT is correctly signed, '
              'which is the whole finding',
              h['LIKE_FOR_LIKE_between_team_game_counts']['median'] < 0
              and h['LIKE_FOR_LIKE_between_team_game_counts']['p_gt_zero']
              <= 0.05)
        ph = b['production_half']
        if ph['outcome']['state'] == 'PASS':
            m = ph['measured']
            check('  a PASS production half CARRIES its measurement -- '
                  'as_dict() drops Outcome.value, so recording only the '
                  'outcome would claim a reproduction holding none of it',
                  m is not None and 'LIKE_FOR_LIKE_between_team_game_counts'
                  in m)
            check('    and it reproduces B11 +0.081 as a WITHIN statistic',
                  abs(m['NOT_COMPARABLE_within_team_game_across_draws_counts']
                      - 0.081) < 0.002,
                  m['NOT_COMPARABLE_within_team_game_across_draws_counts'])
            check('    while the comparable BETWEEN statistic is +0.113',
                  abs(m['LIKE_FOR_LIKE_between_team_game_counts']['median']
                      - 0.113) < 0.002,
                  m['LIKE_FOR_LIKE_between_team_game_counts']['median'])
        else:
            check('  the production half records WHY it could not be '
                  'reproduced, with a cause',
                  ph['outcome']['state'] == 'BLOCKED'
                  and bool(ph['outcome']['detail']),
                  ph['outcome']['code'])
    else:
        check('rbdep_baseline.json exists', False, f'{BASE} absent')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

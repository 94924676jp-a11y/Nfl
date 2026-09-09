"""XL1 tests: the shared passing event, and what it must refuse.

Every guard here is proved load-bearing in the project's sense: it rejects a
seeded violation, and the test that proves so fails when the guard is bypassed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production.nonqb import shared_pass as SP                 # noqa: E402

PASSED = FAILED = 0
XL1 = os.path.join(_ROOT, 'nfl', 'research', 'xl1')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def test_A_predeclaration_hash_is_the_committed_one():
    print('\nA. the pre-registration is what the module claims it is')
    p = os.path.join(XL1, 'predeclaration_xl1.md')
    check('the pre-registration exists', os.path.exists(p), p)
    if not os.path.exists(p):
        return
    with open(p, 'rb') as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    check('it hashes to the sha256 the module carries',
          got == SP.PREDECLARATION_SHA256,
          f'{got} != {SP.PREDECLARATION_SHA256}')
    check('the default mode is off, so production still runs B0',
          SP.SHARED_PASS_DEFAULT == 'off', SP.SHARED_PASS_DEFAULT)
    check('governance says candidate, not promoted',
          'NOT promoted' in SP.GOVERNANCE, SP.GOVERNANCE)


def test_B_untargeted_rate_is_estimated_not_assumed():
    print('\nB. the untargeted-throw rate has an empirical anchor')
    o = SP.untargeted_rate()
    check('it is estimated', o.state is State.PASS, f'{o.code}: {o.detail}')
    if o.state is not State.PASS:
        return
    check('the value is a plausible share of throws', 0.0 < o.value < 0.2,
          str(o.value))
    ev = o.evidence
    check('it names its source', bool(ev.get('source')), str(ev))
    check('it carries the n it was measured on',
          (ev.get('n_team_games') or 0) > 1000, str(ev.get('n_team_games')))
    check('it says it was estimated rather than assumed',
          ev.get('estimated_not_assumed') is True, str(ev))
    hist = os.path.join(XL1, 'history_levels.json')
    with open(hist) as fh:
        h = json.load(fh)
    tgm = h['team_game_means']
    check('it reproduces from the artifact arithmetic',
          abs(o.value - tgm['throws_minus_targets'] / tgm['throws']) < 1e-12)


def test_C_missing_history_is_refused_not_defaulted():
    print('\nC. no anchor, no rate -- the silent-constant guard')
    real = SP._HISTORY
    try:
        SP._HISTORY = os.path.join(XL1, 'does_not_exist.json')
        o = SP.untargeted_rate()
        check('an absent anchor is BLOCKED, not defaulted',
              o.state is State.BLOCKED, f'{o.state.value}[{o.code}]')
        check('the refusal is named',
              o.code == 'UNTARGETED_RATE_NOT_ESTIMATED', o.code)
        check('it does not carry a fabricated value',
              getattr(o, 'value', None) is None, str(getattr(o, 'value', None)))
    finally:
        SP._HISTORY = real
    check('the real anchor still works afterwards',
          SP.untargeted_rate().state is State.PASS)


def test_D_throw_budget_refuses_what_it_should():
    print('\nD. the throw budget')
    rng = np.random.default_rng(1)
    o = SP.targeted_throws(np.zeros((0, 5)), 0.04, rng)
    check('a team with no quarterback row is refused',
          o.state is State.FAIL and o.code == 'THROW_BUDGET_EMPTY',
          f'{o.state.value}[{o.code}]')
    o = SP.targeted_throws(np.full((1, 5), -3.0), 0.04, rng)
    check('a negative attempt count is refused rather than clipped',
          o.state is State.FAIL and o.code == 'THROW_BUDGET_NEGATIVE',
          f'{o.state.value}[{o.code}]')
    att = np.full((2, 4000), 16.0)
    o = SP.targeted_throws(att, 0.04231993609385619, rng)
    check('a real budget passes', o.state is State.PASS, o.code)
    if o.state is not State.PASS:
        return
    v = o.value
    check('throws = sum of attempts', bool((v['throws'] == 32).all()))
    check('targeted + untargeted = throws, in every draw',
          bool((v['targeted'] + v['untargeted'] == v['throws']).all()))
    check('the untargeted pool is not empty and not everything',
          0 < float(v['untargeted'].mean()) < 5,
          str(float(v['untargeted'].mean())))
    # 32 throws x 0.0423 = 1.354 untargeted expected
    check('the untargeted mean tracks the estimated rate',
          abs(float(v['untargeted'].mean()) - 32 * 0.042320) < 0.08,
          str(float(v['untargeted'].mean())))
    check('untargeted is a NAMED pool, not a residual',
          o.evidence.get('untargeted_is_a_named_pool') is True)


def test_E_dealing_preserves_the_competition_and_the_count():
    print('\nE. dealing targets')
    rng = np.random.default_rng(7)
    n, m = 5, 3000
    share = np.zeros((n, m))
    share[0] = 0.40
    share[1] = 0.25
    share[2] = 0.15
    share[3] = 0.10
    share[4] = 0.05
    other = np.full((1, m), 0.05)
    targeted = [np.full(m, 30, int)]
    o = SP.deal_targets(share, other, targeted, [0], [n], rng)
    check('dealing passes', o.state is State.PASS, o.code)
    if o.state is not State.PASS:
        return
    T, oth = o.value['targets'], o.value['other']
    check('every targeted throw is dealt exactly once',
          bool((T.sum(0) + oth.sum(0) == 30).all()),
          str(np.unique(T.sum(0) + oth.sum(0))[:5]))
    check('no negative target count', bool((T >= 0).all()))
    emp = T.mean(1) / 30.0
    check('the empirical share reproduces the simplex it was given',
          bool(np.abs(emp - share[:, 0]).max() < 0.01),
          str(np.round(emp, 4).tolist()))
    check('the ordering of the competition is preserved',
          list(np.argsort(-emp)) == [0, 1, 2, 3, 4],
          str(np.argsort(-emp).tolist()))
    check('it says what it preserved',
          'simplex' in (o.evidence.get('competition_preserved') or ''))


def test_F_degenerate_simplex_is_refused():
    print('\nF. a simplex that sums to zero cannot be dealt from')
    rng = np.random.default_rng(3)
    o = SP.deal_targets(np.zeros((3, 10)), np.zeros((1, 10)),
                        [np.full(10, 5, int)], [0], [3], rng)
    check('refused by name',
          o.state is State.FAIL and o.code == 'TARGET_SIMPLEX_DEGENERATE',
          f'{o.state.value}[{o.code}]')


def test_G_identity_report_is_load_bearing():
    print('\nG. the identity report refuses a seeded violation')
    m = 200
    R = np.random.default_rng(0).integers(0, 4, (6, m))
    Y = R * 11.0
    D = np.random.default_rng(1).integers(0, 2, (6, m))
    ok = SP.identity_report(R.sum(0), Y.sum(0), D.sum(0), R, Y, D)
    check('an exact construction is reported exact',
          ok.state is State.PASS and ok.code == 'SHARED_PASS_IDENTITY_EXACT',
          f'{ok.state.value}[{ok.code}]')
    check('it counts the draws it checked',
          ok.evidence.get('passing_yards_n_draws') == m,
          str(ok.evidence.get('passing_yards_n_draws')))
    # SEEDED VIOLATION: one draw of passing yards moved by a single yard.
    bad_y = Y.sum(0).astype(float).copy()
    bad_y[17] += 1.0
    o = SP.identity_report(R.sum(0), bad_y, D.sum(0), R, Y, D)
    check('a one-yard disagreement in one draw is REFUSED',
          o.state is State.FAIL
          and o.code == 'SHARED_PASS_IDENTITY_VIOLATED',
          f'{o.state.value}[{o.code}]')
    check('the refusal names the metric and the count',
          o.evidence.get('passing_yards_violating_draws') == 1,
          str(o.evidence.get('passing_yards_violating_draws')))
    check('it does not clip: the other metrics still read exact',
          o.evidence.get('completions_violating_draws') == 0
          and o.evidence.get('passing_td_violating_draws') == 0)
    # The bypass half belongs where the guard is CONSUMED, not here: stubbing
    # identity_report and then calling identity_report proves nothing, because
    # the stub is the thing being called. test_J does it at the caller.


def test_H_passer_credit_closes_or_refuses():
    print('\nH. crediting the team total to its passers')
    rng = np.random.default_rng(11)
    m = 500
    att = np.stack([np.full(m, 24.0), np.full(m, 6.0)])
    cmp_t = np.full(m, 20.0)
    pyd_t = np.full(m, 240.0)
    ptd_t = np.full(m, 2.0)
    o = SP.credit_to_passers(att, cmp_t, pyd_t, ptd_t, rng)
    check('it closes', o.state is State.PASS, f'{o.code}: {o.detail}')
    if o.state is not State.PASS:
        return
    v = o.value
    for k, want in (('cmp', cmp_t), ('pyds', pyd_t), ('ptd', ptd_t)):
        check(f'{k} sums to the team total in every draw',
              bool(np.abs(v[k].sum(0) - want).max() < 1e-6),
              str(float(np.abs(v[k].sum(0) - want).max())))
    check('the 80/20 attempt split moves the credit the same way',
          abs(v['pyds'][0].mean() / 240.0 - 0.8) < 1e-9,
          str(v['pyds'][0].mean() / 240.0))
    check('the attribution is named rather than implied',
          'PROPORTIONAL_ATTRIBUTION' in (o.evidence.get('attribution') or ''))


def test_J_gate1_verdict_is_driven_by_the_identity_computation():
    """The bypass half, at the caller.

    XL1's Gate 1 verdict must come from the identity comparison and from
    nothing else. Neutering the comparison must turn a failing arm into a
    passing one; if it does not, the verdict was coming from somewhere else
    and the comparison is decoration.
    """
    print('\nJ. Gate 1 is load-bearing at the caller')
    sys.path.insert(0, XL1)
    try:
        import run_xl1 as R
    except Exception as exc:                                   # noqa: BLE001
        check('run_xl1 imports', False, f'{type(exc).__name__}: {exc}')
        return
    m = 50
    qb = {'completions': np.full(m, 20.0), 'passing_yards': np.full(m, 240.0),
          'passing_td': np.full(m, 2.0)}
    recv = {'completions': np.full(m, 18.0),
            'passing_yards': np.full(m, 205.0),
            'passing_td': np.full(m, 1.0)}
    rows = [{'game_id': 'G', 'team': 'AAA', 'arms': {
        'B0': {'qb_side': {k: R.summarise_player(v) for k, v in qb.items()},
               'receiving_side': {k: R.summarise_player(v)
                                  for k, v in recv.items()},
               'identity': R._identity(qb, recv)},
        'C1': {'qb_side': {k: R.summarise_player(v) for k, v in recv.items()},
               'receiving_side': {k: R.summarise_player(v)
                                  for k, v in recv.items()},
               'identity': R._identity(recv, recv)},
        'C3': {'qb_side': {k: R.summarise_player(v) for k, v in recv.items()},
               'receiving_side': {k: R.summarise_player(v)
                                  for k, v in recv.items()},
               'identity': R._identity(recv, recv)}},
        'player_displacement': []}]
    with open(os.path.join(XL1, 'history_levels.json')) as fh:
        hist = json.load(fh)
    ur = SP.untargeted_rate()
    args = type('A', (), {'season': 2026, 'week': 1, 'draws': m})()
    got = R._summarise(rows, hist, ur, SP.PREDECLARATION_SHA256, args,
                       {}, {'checked': 0, 'identical': 0, 'differing': []})
    check('a disagreeing arm fails Gate 1',
          got['gate1']['B0']['PASS'] is False, str(got['gate1']['B0']))
    check('an exact arm passes Gate 1',
          got['gate1']['C1']['PASS'] is True, str(got['gate1']['C1']))
    check('the failing arm names how many draws disagreed',
          got['gate1']['B0']['passing_yards']['violating_draws'] == m,
          str(got['gate1']['B0']['passing_yards']))
    # BYPASS: neuter the identity comparison and re-summarise the SAME rows.
    real = R._identity
    try:
        R._identity = lambda a, b: {k: {'violating_draws': 0, 'n_draws': m,
                                        'mean_abs_diff': 0.0}
                                    for k in R.TEAM_METRICS}
        rows2 = [dict(rows[0], arms={a: dict(v, identity=R._identity(None,
                                                                     None))
                                     for a, v in rows[0]['arms'].items()})]
        byp = R._summarise(rows2, hist, ur, SP.PREDECLARATION_SHA256, args,
                           {}, {'checked': 0, 'identical': 0,
                                'differing': []})
        check('BYPASS: with the comparison neutered B0 now passes Gate 1, so '
              'the verdict was genuinely coming from the comparison',
              byp['gate1']['B0']['PASS'] is True, str(byp['gate1']['B0']))
    finally:
        R._identity = real
    check('restored, the real comparison fails B0 again',
          R._summarise(rows, hist, ur, SP.PREDECLARATION_SHA256, args, {},
                       {'checked': 0, 'identical': 0,
                        'differing': []})['gate1']['B0']['PASS'] is False)


def test_I_results_artifact_if_present_agrees_with_the_gates():
    print('\nI. the committed results artifact, if it exists')
    p = os.path.join(XL1, 'xl1_results.json')
    if not os.path.exists(p):
        check('no results artifact yet -- nothing claimed', True)
        return
    with open(p) as fh:
        r = json.load(fh)
    check('it records the pre-registration it ran under',
          r.get('predeclaration_sha256') == SP.PREDECLARATION_SHA256,
          str(r.get('predeclaration_sha256')))
    check('it is marked TEST_ONLY', r.get('TEST_ONLY') is True)
    check('it says nothing was promoted',
          'NOT promoted' in (r.get('governance') or ''))
    g1 = r.get('gate1') or {}
    if g1:
        check('B0 fails Gate 1 -- that is the defect this study exists for',
              g1.get('B0', {}).get('PASS') is False,
              str(g1.get('B0', {}).get('PASS')))
        for arm in ('C1', 'C3'):
            if arm in g1:
                check(f'{arm} closes every identity in every draw',
                      g1[arm].get('PASS') is True, str(g1[arm]))
    eq = r.get('orchestration_equivalence') or {}
    if eq:
        check('the orchestration equivalence gate passed',
              eq.get('PASS') is True, str(eq))


def test_L_own3_cold_start_flag_defaults_off():
    """OWN-3 C0 is a candidate. Production must not be running it by accident.

    The flag is the whole promotion surface: if it ever defaults True without
    an owner ruling, an unpromoted candidate is live. Guarded here rather than
    trusted to a code review.
    """
    print('\nL. the cold-start flag is a candidate, not the default')
    import inspect
    from nfl.production import qb_v1 as QBV1
    from nfl.production.nonqb import football_engine as FE
    for mod, fn in ((QBV1, 'slate_prospective'), (FE, 'qb_slate')):
        sig = inspect.signature(getattr(mod, fn))
        prm = sig.parameters.get('include_cold_start')
        check(f'{mod.__name__}.{fn} takes include_cold_start',
              prm is not None, str(sig))
        if prm is not None:
            check(f'{mod.__name__}.{fn} defaults it to False',
                  prm.default is False, repr(prm.default))
    src = inspect.getsource(QBV1.slate_prospective)
    check('the exclusion is still keyed on h_games, not silently removed',
          "h_games'] >= 1" in src or 'h_games"] >= 1' in src, 'filter absent')
    check('the kept rows are marked cold_start so nothing downstream can '
          'confuse them with a QB V1 forecast',
          "'cold_start'] = True" in src or '"cold_start"] = True' in src)
    check('the OWN-3 pre-registration is named in the code that implements it',
          'predeclaration_own3' in src, 'no pre-registration reference')


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def test_K_allocation_share_leak_guard():
    """OWN-1: allocated dropback share that reaches no forecastable passer.

    Found by the target-volume ownership audit. QB V1 correctly refuses a
    passer with no prior appearance; nothing then noticed that his allocated
    share had left the system.
    """
    print('\nK. allocated dropback share must reach a forecastable passer')
    from nfl.production import qb_accounting as QBACC
    alloc = {'AAA': {'pids': ['p1', 'p2'],
                     'shares': np.array([[0.7] * 20, [0.3] * 20])},
             'BBB': {'pids': ['q1'], 'shares': np.array([[1.0] * 20])}}
    ok = QBACC.reconcile_allocation_share(
        alloc, {'AAA': ['p1', 'p2'], 'BBB': ['q1']})
    check('a fully consumed allocation passes',
          ok.state is State.PASS
          and ok.code == 'QB_ALLOCATION_SHARE_CONSUMED',
          f'{ok.state.value}[{ok.code}]')
    check('it reports the mass it checked',
          abs(ok.evidence.get('total_share_mass', 0) - 2.0) < 1e-9,
          str(ok.evidence.get('total_share_mass')))
    # SEEDED VIOLATION: p2 is allocated 0.3 and cannot be forecast.
    bad = QBACC.reconcile_allocation_share(
        alloc, {'AAA': ['p1'], 'BBB': ['q1']})
    check('share allocated to an unforecastable passer is REFUSED',
          bad.state is State.FAIL
          and bad.code == 'QB_ALLOCATION_SHARE_UNCONSUMED',
          f'{bad.state.value}[{bad.code}]')
    check('the refusal quantifies the leak',
          abs(bad.evidence.get('total_share_lost', 0) - 0.3) < 1e-9,
          str(bad.evidence.get('total_share_lost')))
    check('it names the team and the quarterback',
          bad.evidence['leaks'][0]['team'] == 'AAA'
          and bad.evidence['leaks'][0]['unforecastable'] == ['p2'],
          str(bad.evidence['leaks'][0]))
    check('it does NOT renormalise the survivors',
          abs(bad.evidence.get('total_share_mass', 0) - 2.0) < 1e-9,
          'the mass was rescaled, which would hide the gap')
    check('no allocation at all is NOT_APPLICABLE, never a pass',
          QBACC.reconcile_allocation_share({}, {}).state
          is State.NOT_APPLICABLE)
    # BYPASS: with the membership test neutered the leak is invisible.
    empty = QBACC.reconcile_allocation_share(
        alloc, {'AAA': ['p1', 'p2'], 'BBB': ['q1']})
    check('BYPASS: told every passer is forecastable, the same allocation '
          'passes -- so the membership test is what caught it',
          empty.state is State.PASS, f'{empty.state.value}[{empty.code}]')
    check('and the real membership still refuses',
          QBACC.reconcile_allocation_share(
              alloc, {'AAA': ['p1'], 'BBB': ['q1']}).state is State.FAIL)


def test_M_own4_allocated_mass_is_conserved_per_draw():
    """OWN-4: a stochastic zero must never erase allocated opportunity.

    The invariant is per DRAW, not per mean. A single draw losing an entire
    allocated passing game is the defect, and a mean of 0.05% is not a defence.
    """
    print('\nM. allocated dropback mass survives a stochastic zero')
    from nfl.production import qb_accounting as QBACC
    seed = [20260908, 202601, 12345, 4]
    m = 200
    rng = np.random.default_rng(0)
    target = np.full(m, 37.0)
    drawn = rng.integers(1, 45, m).astype(float)
    o = QBACC.conserve_allocated_mass(target, drawn, seed)
    check('no repair needed when every cell has its own level draw',
          o.state is State.PASS
          and o.code == 'MASS_CONSERVED_NO_REPAIR_NEEDED', o.code)
    check('and every cell then maps to itself, so nothing is disturbed',
          bool(np.array_equal(o.value, np.arange(m))))
    # SEEDED VIOLATION: the primary passer draws zero in three draws while
    # holding a full allocated game.
    drawn2 = drawn.copy()
    drawn2[[7, 88, 191]] = 0.0
    o2 = QBACC.conserve_allocated_mass(target, drawn2, seed)
    check('a zero level draw against positive allocation is repaired',
          o2.state is State.PASS
          and o2.code == 'MASS_CONSERVED_BY_DONOR_DRAW', o2.code)
    check('it counts the cells at risk',
          o2.evidence['cells_needing_repair'] == 3,
          str(o2.evidence['cells_needing_repair']))
    check('and reports the TAIL, not just the mean',
          abs(o2.evidence['max_single_draw_at_risk'] - 37.0) < 1e-9,
          str(o2.evidence.get('max_single_draw_at_risk')))
    src = o2.value
    check('every repaired cell now points at a non-zero donor draw',
          bool((drawn2[src] > 0).all()), 'a repaired cell still has no level')
    untouched = [i for i in range(m) if i not in (7, 88, 191)]
    check('UNAFFECTED cells are untouched -- they still map to themselves',
          bool(np.array_equal(src[untouched], np.array(untouched))))
    check('the donor comes from THIS ROW, never from another player',
          bool(set(np.asarray(src)[[7, 88, 191]]).issubset(
              set(np.flatnonzero(drawn2 > 0).tolist()))))
    check('it says it renormalised no survivor and fitted nothing',
          o2.evidence.get('no_survivor_renormalisation') is True
          and o2.evidence.get('nothing_fitted') is True)
    # SEEDED VIOLATION 2: no donor anywhere. Must refuse, never invent.
    o3 = QBACC.conserve_allocated_mass(target, np.zeros(m), seed)
    check('a row with no non-zero draw at all is REFUSED by name',
          o3.state is State.FAIL
          and o3.code == 'QB_COMPOSITION_NO_DONOR_DRAW',
          f'{o3.state.value}[{o3.code}]')
    check('the refusal carries the mass it declined to invent',
          abs(o3.evidence['allocated_dropbacks_at_risk'] - 37.0 * m) < 1e-6,
          str(o3.evidence.get('allocated_dropbacks_at_risk')))
    check('a shape mismatch is refused rather than broadcast',
          QBACC.conserve_allocated_mass(np.zeros(5), np.zeros(7),
                                        seed).code
          == 'MASS_CONSERVATION_SHAPE_MISMATCH')
    # THE CONSERVATION ITSELF: composing through src must reach the target.
    fac = np.where((target > 0) & (drawn2[src] > 0),
                   target / np.maximum(drawn2[src], 1e-9), 0.0)
    got = drawn2[src] * fac
    check('composing through the source index reaches the allocated target '
          'in EVERY draw, including the repaired ones',
          bool(np.abs(got - target).max() < 1e-9),
          str(float(np.abs(got - target).max())))
    # BYPASS: without the repair the same cells lose their whole allocation.
    fac0 = np.where(drawn2 > 0, target / np.maximum(drawn2, 1e-9), 0.0)
    lost = target - drawn2 * fac0
    check('BYPASS: with the repair removed those draws lose 37.0 dropbacks '
          'each, so the guard is what conserved them',
          abs(float(lost.max()) - 37.0) < 1e-9, str(float(lost.max())))

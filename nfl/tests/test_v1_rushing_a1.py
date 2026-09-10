"""V1: the A1 single-owner rushing allocator, and every guard inside it.

THE STANDARD THIS FILE HOLDS ITSELF TO

A guard is not demonstrated because compliant data passes it. Every guard here
is shown to REJECT A SEEDED DEFECT, and where the guard is separable it is also
bypassed to prove the PASS came from the guard rather than from the input
happening to be clean.

The seeded defects are the real ones, not inventions:

*   A0's architecture -- designed QB rush drawn on its own, the rest
    partitioned separately -- which violated closure in 535,354 of 652,000
    draws in OWN-9. Reproduced here so the closure counter is shown to catch
    it.
*   clipping a negative budget instead of refusing it, which is the repair
    OWN-8 section 3 forbids by name.
*   silently rescaling a degenerate draw instead of naming it.
*   correlating per-team-game predictive MEANS against a realised series,
    which inflated a headline number in an accepted return and was withdrawn
    by OWN-10. This project has now found that defect class six times.
*   Python `hash()` in a seed vector, which made a declared seed fail to
    determine the draw in two production layers.
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
import textwrap

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'own9')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, State        # noqa: E402
from nfl.tests.bypass import guard_bypassed                       # noqa: E402
from nfl.production.nonqb import rushing_a1 as R                  # noqa: E402
import a1_lib as A                                                # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# --------------------------------------------------------------- fixtures
LEAGUE = dict(zip(R.CATEGORIES, (0.028, 0.075, 0.800, 0.042, 0.004, 0.006)))
TEAMS = ('ARI', 'LAC', 'ATL', 'PIT')


def _params(seed=11, resid_sd=0.02, n_hist=14):
    rng = np.random.default_rng(seed)
    return {
        'spec_version': R.SPEC_VERSION, 'season': 2026, 'week': 1,
        'history_cut_ord': 202601, 'categories': list(R.CATEGORIES),
        'k_shrink': R.K_SHRINK, 'ewma_halflife': R.EWMA_HALFLIFE,
        'league': dict(LEAGUE),
        'resid': {c: rng.normal(0.0, resid_sd, 400).astype(np.float32)
                  for c in R.CATEGORIES},
        'history': {
            t: {'n': n_hist,
                **{c: list(np.clip(rng.normal(v, 0.01, n_hist), 0, 1))
                   for c, v in LEAGUE.items()}}
            for t in TEAMS},
        'seasons_used': [2022, 2023, 2024, 2025], 'n_train': 3000,
    }


def _levels(m=200, seed=5, teams=TEAMS):
    rng = np.random.default_rng(seed)
    tc = {t: rng.integers(16, 36, m).astype(np.int64) for t in teams}
    scr = {t: rng.integers(0, 5, m).astype(np.int64) for t in teams}
    return tc, scr


def _run(m=200, seed=20260908, teams=TEAMS, par=None, **kw):
    tc, scr = _levels(m, teams=teams)
    return R.allocate(2026, 1, list(teams), tc, scr, m=m, seed=seed,
                      params=par or _params(), **kw), tc, scr


def _synthetic_frame(seasons=(2020, 2021, 2022, 2023, 2024), weeks=17,
                     teams=TEAMS, seed=3):
    """A frame with the same shape the pbp builder produces, closing exactly."""
    rng = np.random.default_rng(seed)
    out = []
    for s in seasons:
        for w in range(1, weeks + 1):
            for t in teams:
                tc = int(rng.integers(18, 38))
                scr = int(rng.integers(0, 5))
                budget = tc - scr
                p = np.array([LEAGUE[c] for c in R.CATEGORIES], float)
                cnt = rng.multinomial(budget, p / p.sum())
                row = {'season': s, 'week': w, 'team': t,
                       'ord': s * 100 + w, 'dropbacks': int(rng.integers(25, 45)),
                       'team_carries': tc, 'scramble': scr,
                       'rush_play_budget': budget,
                       **{c: int(cnt[j]) for j, c in enumerate(R.CATEGORIES)}}
                out.append(row)
    return A.attach_prior(out)


# ------------------------------------------------- 1. the frozen graph
def test_the_ownership_graph_is_the_one_own8_registered():
    print('\n1. the ownership graph is frozen, and the allocator is wired to it')
    o = R.predeclaration()
    check('the OWN-8 pre-registration is unmodified', o.state is State.PASS,
          f'{o.code} {o.detail[:120]}')
    check('the six carry-owned categories are exactly OWN-8\'s',
          tuple(R.CATEGORIES) == ('kneel', 'designed_qb', 'rb', 'wr', 'te',
                                  'fringe'), str(R.CATEGORIES))
    check('scrambles are NOT a partitioned category',
          'scramble' not in R.CATEGORIES and 'scramble' in R.DROPBACK_OWNED)
    check('kneel is an explicit modelled category, not a residual',
          'kneel' in R.CATEGORIES)
    check('fringe is a NAMED residual that exists',
          'fringe' in R.CATEGORIES)
    check('the estimator constants are a1_lib\'s, not re-chosen',
          R.K_SHRINK == A.K_SHRINK == 4.0
          and R.EWMA_HALFLIFE == A.EWMA_HALFLIFE == 2.0,
          f'{R.K_SHRINK} {R.EWMA_HALFLIFE}')
    check('the identity block declares nothing was fitted here',
          R.estimator_identity()['fitted_here'] == []
          and R.estimator_identity()['clipping'] == 'none')


def test_the_predeclaration_guard_is_load_bearing():
    """Seed a moved pre-registration and require the allocator to refuse."""
    print('\n1b. bypass: move the pre-registration hash, allocation must stop')
    real = R.PREDECLARATION_SHA256
    try:
        R.PREDECLARATION_SHA256 = '0' * 64
        o = R.predeclaration()
        check('a modified pre-registration is a named FAIL',
              o.state is State.FAIL and o.code == 'A1_PREDECLARATION_MODIFIED',
              o.code)
        bad, _, _ = _run()
        check('allocate refuses to run against a moved graph',
              bad.state is State.FAIL
              and bad.code == 'A1_PREDECLARATION_MODIFIED',
              f'{bad.state} {bad.code}')
    finally:
        R.PREDECLARATION_SHA256 = real
    ok, _, _ = _run()
    check('and it runs again once the graph is restored',
          ok.state is State.PASS, ok.code)


# ------------------------------------------------- 2. the hard requirements
def test_every_hard_requirement_is_counted_and_zero():
    print('\n2. the hard requirements, counted rather than asserted')
    o, tc, scr = _run(m=300)
    if not check('allocation passes', o.state is State.PASS,
                 f'{o.state} {o.code} {o.detail[:160]}'):
        return
    e = o.evidence
    for k in ('closure_violations', 'negative_allocations',
              'category_budget_overruns', 'ledger_violations',
              'carries_with_no_owner', 'carries_with_two_owners'):
        check(f'{k} == 0 across {e["draws"]} draw cells', e[k] == 0, str(e[k]))
    check('every carry has exactly one owner', e['every_carry_exactly_one_owner'])
    check('no clipping, no survivor renormalisation, no repair, no deletion',
          e['clipping_applied'] == 0
          and e['survivor_renormalisation_applied'] == 0
          and e['post_hoc_repairs'] == 0 and e['deleted_draws'] == 0)
    check('the degenerate counter is present and named',
          'degenerate_draws_named_and_given_to_fringe' in e)
    check('the share floor is counted rather than hidden',
          'share_floor_binds' in e, str(e.get('share_floor_binds')))
    # and the same thing measured OUTSIDE the allocator
    V = o.value
    bad = 0
    for t in TEAMS:
        tot = sum(V['carries'][(t, c)] for c in R.CATEGORIES)
        bad += int((tot != V['rush_play_budget'][t]).sum())
        bad += int((tot + V['scrambles'][t] != V['team_carries'][t]).sum())
    check('closure re-measured independently of the allocator', bad == 0,
          str(bad))


def test_the_closure_counter_rejects_the_A0_architecture():
    """Seed OWN-9's incumbent and require the counter to catch it.

    A0 drew designed QB rush on the DROPBACK denominator and partitioned the
    rest separately, so the two could not close. OWN-9 measured 535,354
    violations in 652,000 draws. If `verify_allocation` cannot see that, it is
    inert and the zeros above mean nothing.
    """
    print('\n2b. bypass: the A0 architecture must be counted as violating')
    rng = np.random.default_rng(4)
    m = 500
    budget = rng.integers(18, 34, m).astype(np.int64)
    tc = budget + 2
    scr = np.full(m, 2, np.int64)
    par = _params()
    rest = [c for c in R.CATEGORIES if c != 'designed_qb']
    p = np.array([par['league'][c] for c in rest], float)
    p = p / p.sum()
    alloc = {c: np.zeros(m, np.int64) for c in R.CATEGORIES}
    for j in range(m):
        d = rng.multinomial(int(budget[j]), p)
        for i, c in enumerate(rest):
            alloc[c][j] = d[i]
    alloc['designed_qb'] = rng.binomial(35, 0.055, m).astype(np.int64)
    cnt = R.verify_allocation(alloc, budget, tc, scr)
    check('A0 violates closure and the counter says so',
          cnt['closure_violations'] > 0, str(cnt))
    check('A0 double-owns carries and the counter says so',
          cnt['carries_with_two_owners'] > 0, str(cnt))
    check('A0 breaks the team-carry ledger and the counter says so',
          cnt['ledger_violations'] > 0, str(cnt))
    # and the SAME counter on the SAME budgets reports zero for a real A1
    # partition, so the violations above are the architecture and not the
    # counter being trigger-happy.
    a1, _, _ = R._partition(par, 'ARI', budget, np.random.default_rng([8]), m)
    clean = R.verify_allocation(a1, budget, tc, scr)
    check('the same counter reports zero on the A1 partition',
          clean['closure_violations'] == 0
          and clean['carries_with_two_owners'] == 0
          and clean['ledger_violations'] == 0, str(clean))


def test_a_nonzero_count_aborts_instead_of_being_repaired():
    """Stub the counter into reporting a violation; allocate must FAIL."""
    print('\n2c. bypass: a violation must abort, never be repaired')
    # The ORIGINAL is captured before the patch. Calling R.verify_allocation
    # from inside the replacement would call the replacement -- which is a
    # RecursionError, and the first version of this test hit it.
    _real = R.verify_allocation

    def _dirty(alloc, budget, team_carries, scrambles):
        c = dict(_real(alloc, budget, team_carries, scrambles))
        c['closure_violations'] = 7
        return c
    with guard_bypassed('nfl.production.nonqb.rushing_a1',
                        'verify_allocation', replacement=_dirty):
        o, _, _ = _run()
    check('a counted violation is a named FAIL',
          o.state is State.FAIL and o.code == 'A1_HARD_REQUIREMENT_VIOLATED',
          f'{o.state} {o.code}')
    check('the failure carries the count rather than a repaired number',
          o.evidence.get('closure_violations') == 7 * len(TEAMS),
          str(o.evidence.get('closure_violations')))
    clean, _, _ = _run()
    check('with the real counter in place the same call passes',
          clean.state is State.PASS, clean.code)


# ------------------------------------------------- 3. scrambles stay put
def test_scrambles_are_dropback_owned_and_never_touched():
    print('\n3. scrambles arrive as a level and leave unchanged')
    o, tc, scr = _run(m=250)
    if not check('allocation passes', o.state is State.PASS, o.code):
        return
    same = all(np.array_equal(o.value['scrambles'][t], scr[t]) for t in TEAMS)
    check('the scramble vectors are bit-identical to the input', same)
    check('the evidence says no scramble was redrawn',
          o.evidence['scrambles_redrawn'] == 0
          and o.evidence['scrambles_dropback_owned'] is True)
    ok = all(np.array_equal(
        o.value['qb_rush_opportunity'][t],
        scr[t] + o.value['carries'][(t, 'designed_qb')]) for t in TEAMS)
    check('qb_rush_opportunity is scramble + designed, by construction', ok)
    check('kneels are NOT inside qb_rush_opportunity',
          o.evidence['kneel_in_qb_rush_opportunity'] is False)
    src = textwrap.dedent(inspect.getsource(R._partition))
    check('the partition function draws no scramble of its own',
          'scramble' not in src.lower(), src[:200])


def test_a_negative_budget_is_refused_by_name_not_clipped():
    print('\n3b. bypass: clipping a negative budget must not be available')
    m = 120
    tc = {t: np.full(m, 20, np.int64) for t in TEAMS}
    scr = {t: np.full(m, 3, np.int64) for t in TEAMS}
    scr['ATL'] = np.full(m, 25, np.int64)          # more scrambles than carries
    o = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=1,
                   params=_params())
    check('scrambles exceeding team carries is a NAMED refusal',
          o.state is State.FAIL
          and o.code == 'A1_SCRAMBLES_EXCEED_TEAM_CARRIES', o.code)
    check('the refusal counts the offending cells rather than fixing them',
          o.evidence.get('n_cells') == m, str(o.evidence.get('n_cells')))
    # SEED THE FORBIDDEN REPAIR and require the ledger counter to reject it.
    budget = np.maximum(tc['ATL'] - scr['ATL'], 0)          # <- the clip
    par = _params()
    rng = np.random.default_rng([1, 2])
    alloc, _, _ = R._partition(par, 'ATL', budget, rng, m)
    cnt = R.verify_allocation(alloc, budget, tc['ATL'], scr['ATL'])
    check('clipping closes the partition but BREAKS the carry ledger',
          cnt['closure_violations'] == 0 and cnt['ledger_violations'] == m,
          str(cnt))


# ------------------------------------------------- 4. degenerate draws
def test_a_degenerate_draw_is_named_and_counted():
    print('\n4. a draw with every category weight zero is named, not rescaled')
    par = _params()
    par['league'] = {c: 0.0 for c in R.CATEGORIES}
    par['resid'] = {c: np.zeros(0, np.float32) for c in R.CATEGORIES}
    par['history'] = {}
    m = 80
    tc = {t: np.full(m, 24, np.int64) for t in TEAMS}
    scr = {t: np.full(m, 2, np.int64) for t in TEAMS}
    o = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=2, params=par)
    if not check('a degenerate slate still returns a closed partition',
                 o.state is State.PASS, f'{o.state} {o.code}'):
        return
    n = o.evidence['degenerate_draws_named_and_given_to_fringe']
    check(f'every degenerate draw is COUNTED ({n})', n == m * len(TEAMS),
          str(n))
    tot_fringe = sum(int(o.value['carries'][(t, 'fringe')].sum())
                     for t in TEAMS)
    tot_other = sum(int(o.value['carries'][(t, c)].sum())
                    for t in TEAMS for c in R.CATEGORIES if c != 'fringe')
    check('the mass goes to the NAMED residual and nowhere else',
          tot_other == 0 and tot_fringe == 22 * m * len(TEAMS),
          f'{tot_fringe} {tot_other}')
    check('closure still holds on the degenerate slate',
          o.evidence['closure_violations'] == 0)
    # the seeded defect: a silent rescale would report zero degenerate draws
    check('a silent rescale would have reported 0 here, and does not',
          n != 0)


# ------------------------------------------------- 5. levels are not ours
def test_a_continuous_level_is_refused_unless_the_caller_declares_rounding():
    print('\n5. turning a level into a count is a D1 decision, not A1\'s')
    m = 100
    rng = np.random.default_rng(6)
    tc = {t: rng.uniform(18, 34, m) for t in TEAMS}
    scr = {t: rng.uniform(0, 4, m) for t in TEAMS}
    o = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=3,
                   params=_params())
    check('a non-integer level is refused by name',
          o.state is State.FAIL and o.code == 'A1_LEVEL_NOT_INTEGER', o.code)
    o2 = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=3,
                    params=_params(), level_rounding='round_half_even')
    check('a DECLARED rounding is accepted', o2.state is State.PASS, o2.code)
    check('and the moved cells are counted, not silent',
          o2.evidence['level_cells_rounded'] > 0
          and o2.evidence['level_rounding'] == 'round_half_even',
          str(o2.evidence['level_cells_rounded']))
    o3 = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=3,
                    params=_params(), level_rounding='floor_it')
    check('an undeclared rounding mode is refused',
          o3.state is State.FAIL
          and o3.code == 'A1_LEVEL_ROUNDING_UNDECLARED', o3.code)


def test_shape_and_membership_of_the_inputs_are_checked():
    print('\n5b. a missing level is not a level of zero')
    m = 50
    tc, scr = _levels(m)
    tc2 = {k: v for k, v in tc.items() if k != 'PIT'}
    o = R.allocate(2026, 1, list(TEAMS), tc2, scr, m=m, seed=1,
                   params=_params())
    check('a missing team is a named FAIL',
          o.state is State.FAIL and o.code == 'A1_INPUT_TEAM_MISSING', o.code)
    tc3 = dict(tc); tc3['PIT'] = tc['PIT'][:10]
    o2 = R.allocate(2026, 1, list(TEAMS), tc3, scr, m=m, seed=1,
                    params=_params())
    check('a short draw vector is a named FAIL',
          o2.state is State.FAIL and o2.code == 'A1_DRAW_COUNT_MISMATCH',
          o2.code)
    o3 = R.allocate(2026, 1, [], tc, scr, m=m, seed=1, params=_params())
    check('an empty slate BLOCKS with a declared cause',
          o3.state is State.BLOCKED
          and o3.evidence.get('cause') == Cause.DEPENDENCY.value,
          f'{o3.state} {o3.evidence.get("cause")}')
    o4 = R.allocate(2026, 1, list(TEAMS), tc, scr, m=m, seed=1,
                    params={'league': {}})
    check('a partial parameter set is refused',
          o4.state is State.FAIL and o4.code == 'A1_PARAMS_MALFORMED', o4.code)


# ------------------------------------------------- 6. seeds
def test_no_python_hash_reaches_any_seed():
    print('\n6. the seed contract: sha256 everywhere, Python hash() nowhere')
    src = open(R.__file__).read()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'hash']
    check('rushing_a1 CALLS Python hash() nowhere',
          not calls, f'lines {[c.lineno for c in calls]}')
    # the scanner is not inert: it finds a seeded call
    seeded = ast.parse("rng = default_rng([seed, hash('carries') % 9973])")
    found = [n for n in ast.walk(seeded) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'hash']
    check('the AST scanner detects a seeded hash() call', len(found) == 1)
    c = R.seed_contract()
    check('the contract declares it uses no Python hash',
          c['uses_python_hash'] is False)
    check('the contract is versioned against seeds.py',
          c['seed_contract'] == 'nfl-stream-seed-v1', c['seed_contract'])
    d = R.registry_debt()
    check('the missing registry entry is a DEFERRED debt, not a silent default',
          d.state in (State.DEFERRED, State.PASS), f'{d.state} {d.code}')
    if d.state is State.DEFERRED:
        check('the debt names exactly what is owed',
              'seeds.py' in str(d.evidence.get('owed')),
              str(d.evidence.get('owed'))[:120])
    check('an undeclared A1 stream name is refused, never defaulted',
          R.stream_component('not_a_stream').code == 'A1_STREAM_UNDECLARED')
    check('a missing team id is refused, never defaulted',
          R.team_component('').code == 'A1_TEAM_ID_MISSING')


def test_the_stream_components_are_stable_across_processes():
    """The defect this closes: Python hash() is randomised per process."""
    print('\n6b. bypass: a randomised hash would move; sha256 does not')
    prog = (
        'import sys; sys.path.insert(0, %r)\n'
        'from nfl.production.nonqb import rushing_a1 as R\n'
        'print(R.stream_component().value, R.team_component("ARI").value, '
        'hash("ARI"))\n' % _ROOT)
    got = []
    for hs in ('0', '1'):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        r = subprocess.run([sys.executable, '-c', prog], capture_output=True,
                           text=True, cwd=_ROOT, env=env, timeout=180)
        if r.returncode != 0:
            check(f'subprocess PYTHONHASHSEED={hs} ran', False,
                  r.stderr[-300:])
            return
        got.append(r.stdout.split())
    check('the A1 stream component is identical across processes',
          got[0][0] == got[1][0], f'{got[0][0]} vs {got[1][0]}')
    check('the team component is identical across processes',
          got[0][1] == got[1][1], f'{got[0][1]} vs {got[1][1]}')
    check('and Python hash() of the same string is NOT -- the seeded defect',
          got[0][2] != got[1][2], f'{got[0][2]} vs {got[1][2]}')


def test_reproducibility_and_stream_separation():
    print('\n6c. same seed reproduces; different team and game do not collide')
    a, _, _ = _run(m=150)
    b, _, _ = _run(m=150)
    check('the same call reproduces bit for bit',
          all(np.array_equal(a.value['carries'][k], b.value['carries'][k])
              for k in a.value['carries']))
    same = all(np.array_equal(a.value['carries'][('ARI', c)],
                              a.value['carries'][('LAC', c)])
               for c in R.CATEGORIES)
    check('two teams on one slate do not share a stream', not same)
    g1, _, _ = _run(m=150, game_id='2026_01_ARI_LAC')
    g2, _, _ = _run(m=150, game_id='2026_01_ATL_PIT')
    check('two game ids do not produce identical draws',
          not np.array_equal(g1.value['carries'][('ARI', 'rb')],
                             g2.value['carries'][('ARI', 'rb')]))
    check('an unwired caller is visible in the evidence, not hidden',
          a.evidence['game_stream_separated'] is False
          and g1.evidence['game_stream_separated'] is True)
    c2, _, _ = _run(m=150, seed=20260909)
    check('a different declared seed changes the draw',
          not np.array_equal(a.value['carries'][('ARI', 'rb')],
                             c2.value['carries'][('ARI', 'rb')]))


# ------------------------------------------------- 7. reference equivalence
def test_the_production_partition_reproduces_a1_lib_bit_for_bit():
    """If this drifts, production is no longer the arm OWN-9 scored."""
    print('\n7. the production partition IS a1_lib.draw_a1')
    par = _params(seed=21)
    m = 400
    budget = 27
    hist = par['history']['ARI']
    row = {'rush_play_budget': budget, 'h_n': hist['n'],
           **{f'h_{c}': hist[c] for c in R.CATEGORIES}}
    ref, _deg = A.draw_a1(row, {'league': par['league'],
                                'resid': par['resid']},
                          np.random.default_rng([1, 2, 3]), m)
    got, floor, deg = R._partition(par, 'ARI', np.full(m, budget),
                                   np.random.default_rng([1, 2, 3]), m)
    check('every category is bit-identical to the reference implementation',
          all(np.array_equal(ref[c], got[c]) for c in R.CATEGORIES))
    check('the share floor is counted by production and was silent in research',
          floor >= 0 and isinstance(floor, int), str(floor))
    check('the reference and production agree on degenerate count',
          deg == _deg, f'{deg} {_deg}')
    check('the centre is a1_lib\'s shrinkage, not a reimplementation',
          abs(R._centre({'h_n': hist['n'],
                         **{f'h_{c}': hist[c] for c in R.CATEGORIES}},
                        'rb', par['league'])
              - A._centre(row, 'rb', {'league': par['league']})) < 1e-15)
    # cold start falls back to the league share, which is the family's own rule
    cold = R._centre({'h_n': 0, **{f'h_{c}': [] for c in R.CATEGORIES}},
                     'rb', par['league'])
    check('a team with no history gets the league share, not a zero',
          abs(cold - par['league']['rb']) < 1e-12, str(cold))


def test_a2_is_not_reopened():
    print('\n7b. OWN-10 rejected the latent; it must not reappear')
    check('the module declares the rejection', R.A2_LATENT_REJECTED is True)
    src = open(R.__file__).read()
    tree = ast.parse(src)
    names = {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    bad = sorted(x for x in names if x in ('tau', 'latent', 'u_latent'))
    check('no latent parameter is present anywhere in the allocator',
          not bad, str(bad))
    check('the evidence says so on every run', _run(m=40)[0]
          .evidence['a2_latent_present'] is False)


# ------------------------------------------------- 8. dependence, per draw
def test_dependence_is_per_draw_and_the_mean_based_statistic_is_refused():
    print('\n8. one draw per team-game; the mean-based statistic is inflated')
    rng = np.random.default_rng(12)
    n, m = 400, 300
    y = rng.integers(18, 38, n).astype(float)          # realised team carries
    X = rng.poisson(0.07 * y[:, None], (n, m)).astype(float)
    d = R.per_draw_dependence(X, y)
    check('the per-draw statistic PASSES and says it is comparable',
          d.state is State.PASS and d.evidence['comparable_with_realised']
          is True and d.evidence['mean_based'] is False, d.code)
    check('it is reported as a DISTRIBUTION over draws, not a point',
          {'per_draw_mean', 'per_draw_sd', 'p05', 'p95'} <= set(d.value),
          str(sorted(d.value)))
    mb = R.mean_based_dependence(X, y)
    check('the mean-based statistic is NEVER a PASS',
          mb.state is State.FAIL
          and mb.code == 'A1_MEAN_BASED_DEPENDENCE_NOT_COMPARABLE', mb.code)
    check('and its number is carried under a name saying it is not comparable',
          'value_not_comparable' in mb.evidence
          and mb.evidence['comparable_with_realised'] is False)
    # THE SEEDED DEFECT: averaging draws inflates the statistic. If it did not,
    # this whole guard would be pointless -- so the test measures the inflation.
    infl = mb.evidence['value_not_comparable'] - d.value['per_draw_mean']
    check(f'the mean-based number is materially larger ({infl:+.4f})',
          infl > 0.05,
          f'per-draw {d.value["per_draw_mean"]:.4f} vs mean-based '
          f'{mb.evidence["value_not_comparable"]:.4f}')
    check('a single draw cannot form a distribution and is refused',
          R.per_draw_dependence(X[:, :1], y).code
          == 'A1_DEPENDENCE_NEEDS_DRAWS')
    check('a mismatched shape is refused',
          R.per_draw_dependence(X, y[:10]).code == 'A1_DEPENDENCE_SHAPE')
    na = R.per_draw_dependence(X, np.ones(n))
    check('a constant realised series is NOT_APPLICABLE with a reason, '
          'never a zero',
          na.state is State.NOT_APPLICABLE and bool(na.detail), na.code)


# ------------------------------------------------- 9. the fit
def test_the_fit_is_chronological_and_says_what_it_consumed():
    print('\n9. parameters come from seasons strictly before the forecast')
    frame = _synthetic_frame()
    o = R.fit_frozen(2024, 0, frame=frame)
    if not check('a fit on a synthetic frame passes', o.state is State.PASS,
                 f'{o.state} {o.code} {o.detail[:140]}'):
        return
    check('training seasons are strictly earlier than the forecast season',
          max(o.value['seasons_used']) < 2024, str(o.value['seasons_used']))
    check('the history cut is strictly before the forecast ordinal',
          o.evidence['highest_history_ord'] < o.evidence['history_cut_ord'],
          f'{o.evidence["highest_history_ord"]} '
          f'{o.evidence["history_cut_ord"]}')
    check('the fit declares it consumed no outcome at or after the cut',
          o.evidence['consumed_outcome_at_or_after_cut'] is False)
    check('every category carries a residual pool',
          all(o.evidence['resid_pool_sizes'][c] > 0 for c in R.CATEGORIES),
          str(o.evidence['resid_pool_sizes']))
    mid = R.fit_frozen(2024, 9, frame=frame)
    check('a mid-season cut uses that season\'s completed weeks',
          mid.evidence['highest_history_ord'] == 202408,
          str(mid.evidence['highest_history_ord']))
    check('and never the week being forecast',
          mid.evidence['highest_history_ord']
          < mid.evidence['history_cut_ord'])
    burn = R.fit_frozen(2021, 1, frame=frame)
    check('a burn-in season is refused rather than fitted on nothing',
          burn.state is State.BLOCKED
          and burn.code == 'A1_SEASON_IS_BURN_IN', burn.code)
    check('the burn-in block declares a cause',
          burn.evidence.get('cause') == Cause.DATA.value)


def test_the_chronology_guard_is_load_bearing():
    """Seed leaked history and require the fit to refuse."""
    print('\n9b. bypass: leak a future ordinal into the history')
    frame = _synthetic_frame()
    _real = R._history_from_frame                 # captured before the patch

    def _leaky(fr, cut_ord):
        hist, _hi = _real(fr, cut_ord)
        return hist, cut_ord + 1                      # <- the seeded leak
    with guard_bypassed('nfl.production.nonqb.rushing_a1',
                        '_history_from_frame', replacement=_leaky):
        o = R.fit_frozen(2024, 5, frame=frame)
    check('leaked history is a named FAIL',
          o.state is State.FAIL and o.code == 'A1_CHRONOLOGY_VIOLATED',
          f'{o.state} {o.code}')
    clean = R.fit_frozen(2024, 5, frame=frame)
    check('the same fit passes with the leak removed',
          clean.state is State.PASS, clean.code)


def test_the_frame_must_close_in_the_data_before_any_model_runs():
    print('\n9c. bypass: a frame whose categories do not close is refused')
    frame = _synthetic_frame(seasons=(2020, 2021, 2022, 2023), weeks=6)
    bad_frame = [dict(r) for r in frame]
    bad_frame[3]['rb'] += 1                           # <- a carry from nowhere
    resid = [r['team_carries'] - r['scramble']
             - sum(r[c] for c in R.CATEGORIES) for r in bad_frame]
    check('the seeded frame really does not close',
          sum(1 for v in resid if v != 0) == 1, str(resid[:6]))
    check('a caller-supplied frame is checked too, not trusted',
          R.fit_frozen(2024, 0, frame=bad_frame).code
          == 'A1_FRAME_CATEGORIES_DO_NOT_CLOSE',
          R.fit_frozen(2024, 0, frame=bad_frame).code)
    check('and the clean frame it was copied from does fit',
          R.fit_frozen(2024, 0, frame=frame).state is State.PASS)
    saved_build = A.build_frame
    saved_attach = A.attach_prior
    try:
        A.build_frame = lambda files, pos: [dict(r) for r in bad_frame]
        A.attach_prior = lambda fr: fr
        b = R.build_frame(['x'], {})
        check('build_frame refuses a frame whose categories do not close',
              b.state is State.FAIL
              and b.code == 'A1_FRAME_CATEGORIES_DO_NOT_CLOSE', b.code)
        check('and it says how many team-games are broken',
              b.evidence.get('n_bad') == 1, str(b.evidence.get('n_bad')))
        A.build_frame = lambda files, pos: []
        e = R.build_frame(['x'], {})
        check('an empty frame BLOCKS rather than reading as a quiet season',
              e.state is State.BLOCKED and e.code == 'A1_FRAME_EMPTY', e.code)
    finally:
        A.build_frame = saved_build
        A.attach_prior = saved_attach


def test_an_absent_pbp_source_blocks_by_name_and_is_not_stubbed():
    print('\n9d. no play-by-play means BLOCKED with a cause, never a stub')
    saved = {k: os.environ.get(k) for k in R.PBP_GLOB_ENV}
    try:
        for k in R.PBP_GLOB_ENV:
            os.environ.pop(k, None)
        o = R.pbp_sources()
        check('an absent source BLOCKS', o.state is State.BLOCKED
              and o.code == 'A1_PBP_SOURCE_NOT_LOCATED', o.code)
        check('with cause DATA', o.evidence.get('cause') == Cause.DATA.value)
        check('and it names the exact fields it needs',
              'qb_kneel' in o.detail and 'qb_scramble' in o.detail)
        os.environ[R.PBP_GLOB_ENV[0]] = '/nonexistent-a1/pbp*.csv.gz'
        e = R.pbp_sources()
        check('a glob that matches nothing BLOCKS rather than reading as empty',
              e.state is State.BLOCKED
              and e.code == 'A1_PBP_GLOB_MATCHED_NOTHING', e.code)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_frozen_parameters_round_trip_and_refuse_the_wrong_season():
    print('\n9e. frozen parameters are readable, and season-checked')
    frame = _synthetic_frame()
    o = R.fit_frozen(2024, 0, frame=frame)
    if not check('fit passes', o.state is State.PASS, o.code):
        return
    js = R.params_to_json(o.value)
    back = R.params_from_json(js)
    check('the residual pools survive the round trip exactly',
          all(np.array_equal(np.asarray(o.value['resid'][c], np.float32),
                             back['resid'][c]) for c in R.CATEGORIES))
    check('the history survives the round trip',
          back['history'].keys() == o.value['history'].keys())
    m = 60
    tc, scr = _levels(m)
    a = R.allocate(2024, 1, list(TEAMS), tc, scr, m=m, seed=4,
                   params=o.value)
    b = R.allocate(2024, 1, list(TEAMS), tc, scr, m=m, seed=4, params=back)
    check('and a round-tripped parameter set draws identically',
          a.state is State.PASS and b.state is State.PASS
          and all(np.array_equal(a.value['carries'][k], b.value['carries'][k])
                  for k in a.value['carries']))
    import json as _json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'p.json')
        js2 = dict(js); js2['season'] = 2019
        open(p, 'w').write(_json.dumps(js2))
        R.cache_clear()
        got = R.params(2024, 0, path=p)
        check('a parameter file for the wrong season is refused',
              got.state is State.FAIL
              and got.code == 'A1_PARAMS_SEASON_MISMATCH', got.code)
        open(p, 'w').write(_json.dumps(js))
        R.cache_clear()
        good = R.params(2024, 0, path=p)
        check('and the right one loads with its provenance',
              good.state is State.PASS and good.evidence.get('sha256'),
              good.code)
    R.cache_clear()


# ------------------------------------------------- 10. distributional shape
def test_kneels_stay_explicit_and_the_shape_is_not_degenerate():
    print('\n10. kneels are their own category and carry real mass')
    o, _, _ = _run(m=600)
    if not check('allocation passes', o.state is State.PASS, o.code):
        return
    kn = np.concatenate([o.value['carries'][(t, 'kneel')] for t in TEAMS])
    fr = np.concatenate([o.value['carries'][(t, 'fringe')] for t in TEAMS])
    rb = np.concatenate([o.value['carries'][(t, 'rb')] for t in TEAMS])
    dq = np.concatenate([o.value['carries'][(t, 'designed_qb')] for t in TEAMS])
    check(f'kneels are drawn, not folded away (mean {kn.mean():.3f})',
          kn.sum() > 0)
    check('kneels and fringe are separately reported',
          not np.array_equal(kn, fr))
    check(f'RB carries dominate the budget (mean {rb.mean():.2f})',
          rb.mean() > 5 * (kn.mean() + dq.mean()) / 2)
    check('the evidence declares kneel an explicit category',
          o.evidence['kneel_is_an_explicit_category'] is True)
    check('no category is ever negative',
          all(int((o.value['carries'][(t, c)] < 0).sum()) == 0
              for t in TEAMS for c in R.CATEGORIES))

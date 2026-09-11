"""NFL-V1-R3 adversarial tests: the non-QB chain refuses rather than invents."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production.nonqb import accounting as ACC                # noqa: E402
from nfl.production.nonqb import eligibility as EL                # noqa: E402
from nfl.production.nonqb import inputs as IN                     # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402

PASSED = FAILED = 0
IDS = ['p1', 'p2', 'p3']
PAR = {'add_pool': {'WR': np.array([0.0, 0.01, -0.01], np.float32)},
       'mass_pool': np.array([0.01, 0.02], np.float32), 'mass_mean': 0.011}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    # Returned so a caller can stop rather than index into a shape it has just
    # recorded as unrecognised. `if not check(...)` was silently always true
    # while this returned None.
    return bool(ok)


def _appear(test_only=True, m=40):
    return Outcome.ok('APPEARANCE_OK',
                      value={i: np.ones(m, int) for i in IDS},
                      test_only=test_only)


# TEST-ONLY stand-ins for the frozen priors. They are the SHAPE the frozen
# fits return; the layers refuse anything that is not that shape, which is
# what `test_D_conversion_refuses_a_caller_supplied_prior` checks.
RECV_PRIORS = {'pos_catch_rate': {'WR': 0.63},
               'pos_yardage_pool': {'WR': np.array([3.0, 9.0, 14.0, -2.0,
                                                    27.0])},
               'own': {}, 'k_shrink': 4.0}
TD_PRIORS = {'B_pos': {'WR': 0.0489}, 'B_league': 0.0465,
             'pos_catch_rate': {'WR': 0.63}}
ORD = 202601


def _chain(m=40):
    ap = _appear(m=m)
    pa = LY.participation(ap, {'p1': 0.6, 'p2': 0.3, 'p3': 0.1}, m=m)
    tc = LY.targets_carries(pa, 'targets', [0.6, 0.3, 0.1],
                            ['WR', 'WR', 'WR'], ([0], [3]), IDS, PAR, m=m)
    T = tc.value['share'] * 30
    cv = LY.receiving_conversion(tc, T, RECV_PRIORS, IDS, ['WR'] * 3, ORD,
                                 m=m)
    td = LY.td_layer(cv, T, TD_PRIORS, IDS, ['WR'] * 3, ORD, m=m)
    return ap, pa, tc, cv, td


# ==========================================================================
def test_A_governance_is_authoritative():
    print('\nA. PATH_C_STATE governs, prose does not')
    o = EL.assert_no_stale_labels()
    check('no production string calls a non-production subsystem ACCEPTED',
          o.state is State.PASS, str(o.evidence.get('offences'))[:200])
    mx = EL.matrix()
    check('  nothing non-QB is publication eligible',
          not any(v['publication_eligible'] for v in mx.values()))
    for layer in ('targets_carries', 'receiving_conversion', 'td_layer'):
        check(f'  {layer} is NOT prospectively validated',
              mx[layer]['prospective_validation_state']
              == 'NOT_PROSPECTIVELY_VALIDATED')
    # seed a fake promotion and prove the guard catches it
    import pathlib, tempfile
    p = pathlib.Path(tempfile.mkdtemp()) / 'fake.py'
    p.write_text("SPEC = ('targets_carries', 'x', 'P4C system C ACCEPTED')\n")
    o2 = EL.assert_no_stale_labels([p])
    check('  and a seeded fake promotion IS caught',
          o2.state is State.FAIL and o2.code == 'STALE_GOVERNANCE_LABEL',
          o2.code)


def test_B_appearance_without_injuries_refuses():
    """SEEDED, because the world stopped supplying the condition.

    This used to call the real path and rely on the captured injuries feed
    being unusable. Once the feed became usable the call PASSED, and the test
    reported working inputs as a failure -- a test conditioned on an empty
    world rather than on the behaviour it means to protect.

    Worse, it was masking a real defect while it did so: readiness reports
    ENGINE_INPUTS_READY when nothing blocks, and layers.appearance compared
    against 'INJURIES_READY', so the slate-wide path deferred exactly when
    the inputs were ready. That is fixed; this now seeds the not-ready state
    directly and requires the refusal to name it.
    """
    print('\nB. appearance without a usable injuries feed emits nothing')
    real = LY.RD.report

    def _blocked(season, week, *a, **k):
        d = dict(real(season, week, *a, **k))
        d['overall_state'] = 'INJURIES_NOT_FILED'
        d['injuries'] = dict(d.get('injuries') or {},
                             reason='seeded: no club filed a report')
        return d

    LY.RD.report = _blocked
    try:
        o = LY.appearance(2026, 1, [{'gsis_id': 'x'}])
    finally:
        LY.RD.report = real
    check('the real path does not PASS', o.state is not State.PASS, o.code)
    check('  it names the exact condition, not a generic failure',
          'INJURIES' in o.code, o.code)
    check('  and emits no probabilities at all', o.value is None
          or not isinstance(o.value, dict) or not o.value, str(o.value)[:60])

    # AND THE OTHER SIDE OF IT: with the feed ready, the layer must actually
    # run. Without this, restoring the stale constant would pass the suite.
    ok = LY.appearance(2026, 1, [{'gsis_id': 'x'}])
    check('  while a READY feed lets the real mechanism run',
          ok.state is State.PASS, f'{ok.state.name}[{ok.code}]')


def test_C_fixture_quarantine():
    print('\nC. a fixture cannot reach a forecast artifact')
    o = IN.validate_appearance_inputs(
        {'practice_progression': 1, 'teammate_availability': 1}, 2026)
    check('an UNMARKED fixture is refused',
          o.state is State.FAIL and o.code == 'UNMARKED_FIXTURE', o.code)
    o2 = IN.validate_appearance_inputs({'_test_only': True}, 2026)
    check('  an incomplete fixture is refused',
          o2.state is State.FAIL and o2.code == 'FIXTURE_INCOMPLETE', o2.code)
    ap, pa, tc, cv, td = _chain()
    for nm, o3 in (('participation', pa), ('targets_carries', tc),
                   ('conversion', cv), ('td', td)):
        check(f'  test_only propagates through {nm}',
              o3.evidence.get('test_only') is True)
    g = LY.assert_publishable(pa, tc, cv, td)
    check('  and the publication gate REFUSES the tainted run',
          g.state is State.FAIL
          and g.code == 'TEST_ONLY_DATA_IN_PRODUCTION_PATH', g.code)
    clean = LY.assert_publishable(Outcome.ok('X', value=1))
    check('  while an untainted run passes the same gate',
          clean.state is State.PASS)


def test_D_upstream_gating():
    print('\nD. every layer refuses when its upstream is absent')
    # CONSTRUCT the blocked upstream instead of hoping the real one fails.
    #
    # This called LY.appearance and relied on it refusing because the captured
    # injuries feed was unusable. Once the feed became usable, appearance
    # PASSED, participation ran, and this test reported the cascade WORKING as
    # a failure. What it means to protect is downstream gating: given a
    # refused upstream, every layer below refuses and emits nothing. That is
    # deterministic, so seed it.
    blocked = Outcome.deferred(
        'INJURIES_NOT_FILED',
        'seeded upstream refusal: no club filed a report',
        owed={'source': 'injuries_2026'})
    pa = LY.participation(blocked, {})
    check('participation without appearance',
          pa.code == 'BLOCKED_UPSTREAM_APPEARANCE', pa.code)
    tc = LY.targets_carries(pa, 'targets', [], [], ([], []), [], PAR)
    check('  targets/carries without participation',
          tc.code == 'BLOCKED_UPSTREAM_APPEARANCE', tc.code)
    cv = LY.receiving_conversion(tc, [], {}, [], [], ORD)
    check('  conversion without opportunity',
          cv.code == 'BLOCKED_UPSTREAM_OPPORTUNITY', cv.code)
    td = LY.td_layer(cv, [], {}, [], [], ORD)
    check('  TD without conversion', td.code == 'BLOCKED_UPSTREAM_TD_INPUT',
          td.code)
    check('  and none of them produced a value',
          all(o.value is None for o in (pa, tc, cv, td)))


def test_E_allocation_accounting():
    print('\nE. allocation accounting: named residual, nothing clipped away')
    ap, pa, tc, cv, td = _chain(m=60)
    S, other = tc.value['share'], tc.value['other']
    check('no negative share', not bool((S < 0).any()))
    tot = S.sum(0) + other[0]
    check('  player shares + OTHER == 1 on every draw (simplex)',
          float(np.abs(tot - 1.0).max()) < 1e-5, float(np.abs(tot - 1).max()))
    check('  the OTHER residual is non-zero and therefore named, not hidden',
          float(other.mean()) > 0, float(other.mean()))
    check('  receptions <= targets on every draw',
          bool((cv.value['receptions'] <= np.rint(S[0] * 30) + 1e-9).all()))
    check('  TD <= receptions on every draw',
          bool((td.value['td'] <= cv.value['receptions']).all()))
    # NOT "no negative yards": RC1 resamples real per-catch gains and a
    # reception for a loss is ordinary football. The mechanical identity is
    # that catching nothing yields exactly nothing.
    R = cv.value['receptions']
    Y = cv.value['receiving_yards']
    check('  zero receptions yields exactly zero yards',
          not bool((np.abs(Y[R <= 0]) > 1e-9).any()))
    check('  and the yardage keeps its spread rather than collapsing to a '
          'per-catch constant',
          float(np.nanmax(np.where(R > 0, Y / np.maximum(R, 1), np.nan)))
          > float(np.nanmin(np.where(R > 0, Y / np.maximum(R, 1), np.nan))))


def test_F_a_player_without_appearance_is_refused():
    print('\nF. an allocation cannot be invented for an unknown player')
    ap = _appear()
    pa = LY.participation(ap, {'p1': 0.6, 'p2': 0.3, 'p3': 0.1})
    tc = LY.targets_carries(pa, 'targets', [0.6, 0.3, 0.1, 0.2],
                            ['WR'] * 4, ([0], [4]), IDS + ['ghost'], PAR)
    check('a player with no appearance draw REFUSES the allocation',
          tc.state is State.FAIL
          and tc.code == 'ALLOCATION_PLAYER_WITHOUT_APPEARANCE', tc.code)


def test_G_no_oracle_in_production():
    print('\nG. the realised-allocation oracle is structurally unreachable')
    import p4c_lib as L
    check("system E is not in ELIGIBLE_SYSTEMS",
          'E' not in L.ELIGIBLE_SYSTEMS, str(L.ELIGIBLE_SYSTEMS))
    check('  and is explicitly marked diagnostic-only',
          'E' in L.DIAGNOSTIC_ONLY)
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'layers.py')).read()
    check('  production requests system C by name and never E',
          "gen_weights('C'" in src and "gen_weights('E'" not in src)


def test_H_determinism_and_cross_draw():
    print('\nH. same seed identical, different seed different')
    def run(seed, m=40):
        return LY.targets_carries(
            LY.participation(_appear(m=m), {'p1': .6, 'p2': .3, 'p3': .1}, m=m),
            'targets', [.6, .3, .1], ['WR'] * 3, ([0], [3]), IDS, PAR,
            m=m, seed=seed)
    a, b, c = run(1), run(1), run(2)
    check('same seed -> identical', np.array_equal(a.value['share'],
                                                   b.value['share']))
    check('different seed -> different',
          not np.array_equal(a.value['share'], c.value['share']))
    # cross-draw mismatch: appearance at 40 draws, allocation asked for 200
    pa = LY.participation(_appear(m=40), {'p1': .6, 'p2': .3, 'p3': .1}, m=40)
    bad = LY.targets_carries(pa, 'targets', [.6, .3, .1], ['WR'] * 3,
                             ([0], [3]), IDS, PAR, m=200)
    check('  a draw-width mismatch is a NAMED refusal, not a numpy error',
          bad.state is State.FAIL
          and bad.code == 'CROSS_DRAW_INDEX_MISMATCH', bad.code)


def test_I_team_volume_cache_is_draw_equivalent():
    print('\nI. the per-slate cache changes no number')
    TV.cache_clear()
    a = TV.forecast(2026, 1, ['NE', 'SEA'], m=30)
    b = TV.forecast(2026, 1, ['NE', 'SEA'], m=30)          # warm
    check('cold and warm produce identical draws',
          all(np.array_equal(a.value[k], b.value[k]) for k in a.value))
    TV.cache_clear()
    c = TV.forecast(2026, 1, ['DAL', 'PHI'], m=30)
    TV.cache_clear()
    d = TV.forecast(2026, 1, ['DAL', 'PHI'], m=30)
    check('  and a different game is unaffected by cache state',
          all(np.array_equal(c.value[k], d.value[k]) for k in c.value))


def test_J_readiness_names_the_condition():
    print('\nJ. readiness reports a specific condition, never "failed"')
    r = RD.report(2026, 1)
    check('an overall state is reported', bool(r['overall_state']))
    check('  it is specific to injuries, not generic',
          'INJURIES' in r['overall_state'] or r['overall_state']
          == 'ENGINE_INPUTS_READY', r['overall_state'])
    check('  it names the blocking layer', r['blocking_layers'] == ['appearance']
          or not r['blocking_layers'], r['blocking_layers'])
    check('  it carries a next action', len(r['next_action']) > 20)
    check('  and column population is measured, not assumed',
          'report_status' in r['injuries'].get('column_population', {}))
    d = json.load(open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                                    'week2_data_debt.json')))
    check('  the week-2 debt names pbp_participation as needed from week 2',
          d['findings']['pbp_participation']['needed_from'] == 'WEEK 2')
    check('  and records that no source policy was changed',
          'NONE' in d['answers']['policy_change_made'])


def test_B_implementation_claims_are_checked():
    o = EL.assert_implementations_exist()
    check('every layer claiming a production implementation has one that '
          'imports', o.state is State.PASS,
          f'{o.state.value}[{o.code}] {o.detail[:200]}')
    m = EL.matrix({})
    check('  the matrix carries an implementation state per layer',
          all(v['production_implementation_state'] in
              ('IMPLEMENTED', 'NOT_IMPLEMENTED') for v in m.values()))
    check('  rushing_conversion is declared NOT_IMPLEMENTED rather than '
          'left blank',
          m['rushing_conversion']['production_implementation_state']
          == 'NOT_IMPLEMENTED')
    # A FALSE CLAIM MUST BE CAUGHT. Seed one.
    old = dict(EL.IMPLEMENTATION)
    try:
        EL.IMPLEMENTATION['td_layer'] = ('IMPLEMENTED',
                                         'nfl.production.nonqb.no_such_module')
        bad = EL.assert_implementations_exist()
        check('  a claimed module that does not exist is caught',
              bad.state is State.FAIL
              and bad.code == 'IMPLEMENTATION_CLAIM_UNSUPPORTED',
              f'{bad.state.value}[{bad.code}]')
    finally:
        EL.IMPLEMENTATION.clear()
        EL.IMPLEMENTATION.update(old)


def test_B_injuries_rows_for_the_wrong_season_or_week_are_dropped():
    """A stale or misaddressed injuries row must not reach the mechanism."""
    from nfl.production.nonqb import appearance_model as AM
    rows = [{'season': '2025', 'week': '1', 'team': 'NE', 'gsis_id': 'a',
             'report_status': '', 'practice_status': 'Full'},
            {'season': '2026', 'week': '1', 'team': 'NE', 'gsis_id': 'b',
             'report_status': 'Out', 'practice_status': 'Did Not Participate'},
            {'season': '2026', 'week': '1', 'team': '', 'gsis_id': 'c',
             'report_status': '', 'practice_status': 'Full'},
            {'season': '2026', 'week': '1', 'team': 'NE', 'gsis_id': '',
             'report_status': '', 'practice_status': 'Full'}]
    got = AM.parse_injuries_rows(rows, 2026)
    check('a prior-season injuries row is not consumed as this season\'s',
          (2025, 1, 'NE', 'a') not in got)
    check('  a row with no team is dropped', not any(k[2] == '' for k in got))
    check('  a row with no gsis_id is dropped',
          not any(k[3] == '' for k in got))
    check('  and the one legitimate row survives',
          list(got) == [(2026, 1, 'NE', 'b')], list(got))


def test_B_participation_prior_is_prior_only():
    from nfl.production.nonqb import participation_prior as PPX
    o = PPX.share_prior(2026, 1, [{'gsis_id': 'nobody', 'position': 'WR'}])
    check('a player with no history falls back to the DECLARED positional '
          'mean, never zero', o.state is State.PASS
          and o.evidence['n_on_positional_mean'] == 1,
          f'{o.state.value}[{o.code}]')
    check('  and the fallback is a real number, not a silent zero',
          o.value['nobody'] > 0.0, o.value.get('nobody'))
    o2 = PPX.share_prior(2026, 1, [{'position': 'WR'}])
    check('  a player with no gsis_id is refused',
          o2.state is State.FAIL
          and o2.code == 'PARTICIPATION_IDENTITY_UNRESOLVED',
          f'{o2.state.value}[{o2.code}]')
    o3 = PPX.share_prior(2026, 1, [{'gsis_id': 'q', 'position': 'K'}])
    check('  and a slate with no modelled position is refused, not emptied',
          o3.state is State.FAIL and o3.code == 'PARTICIPATION_PRIOR_EMPTY',
          f'{o3.state.value}[{o3.code}]')
    # The week-2 debt named this refusal; here it is, firing.
    o4 = PPX.share_prior(2026, 2, [{'gsis_id': 'x', 'position': 'WR'}])
    check('  week 2 without any 2026 participation history REFUSES',
          o4.state is State.BLOCKED
          and o4.code == 'PARTICIPATION_HISTORY_STALE',
          f'{o4.state.value}[{o4.code}]')
    check('  and it names the missing source',
          o4.evidence.get('missing_source') == 'pbp_participation_2026',
          o4.evidence.get('missing_source'))
    debt = json.load(open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                                       'week2_data_debt.json')))
    check('  which is exactly the refusal the week-2 debt promised',
          'PARTICIPATION_HISTORY_STALE'
          in debt['findings']['pbp_participation']['exact_refusal'])


# ---------------------------------------------------------------- G
def _clean(n=4, m=20, g=2):
    """A draw set that satisfies every non-QB identity by construction."""
    rng = np.random.default_rng(7)
    starts, counts = [0, 2], [2, 2]
    S = rng.dirichlet(np.ones(n // g + 1), size=(g, m))
    share = np.zeros((n, m), np.float64)
    other = np.zeros((g, m), np.float64)
    for k, (a, c) in enumerate(zip(starts, counts)):
        share[a:a + c] = S[k][:, :c].T
        other[k] = S[k][:, c]
    V = np.full((g, m), 30.0)
    T = share * np.repeat(V, counts, axis=0)
    A = np.ones((n, m))
    R = np.rint(T * 0.6)
    D = np.minimum(R, 1.0)
    Y = R * 11.0
    return dict(share=share, other=other, team_volume=V,
                player_opportunity=T, appearance=A, starts=starts,
                counts=counts, receptions=R, receiving_td=D,
                receiving_yards=Y)


def test_g_nonqb_accounting_is_load_bearing():
    """Every identity must REJECT a seeded violation. A guard that accepts
    one is not a guard, and a suite that never seeds one has not tested it."""
    base = _clean()
    ok = ACC.reconcile_nonqb(**base)
    check('a clean non-QB draw set reconciles', ok.state is State.PASS,
          f'{ok.code}: {ok.detail[:120]}')
    check('  and it says how many cells it actually examined',
          ok.evidence.get('n_cells_checked', 0) > 0)
    check('  and every declared identity is named in the evidence',
          set(ok.evidence.get('identities_checked', ())) ==
          set(ACC.IDENTITY_NAMES))

    # THE VACUOUS CASE. Zero cells is not a pass.
    v = ACC.reconcile_nonqb(np.zeros((0, 0)), np.zeros((0, 0)),
                            np.zeros((0, 0)), np.zeros((0, 0)),
                            np.zeros((0, 0)), [], [])
    check('an empty draw set FAILS rather than passing vacuously',
          v.state is State.FAIL and v.code == 'NONQB_ACCOUNTING_VACUOUS',
          f'{v.state.value}[{v.code}]')

    seeds = {}
    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['other'] = b['other'] + 0.05
    seeds['share_simplex_closure'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['share'][0, 0] = -0.01
    seeds['share_non_negative'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['player_opportunity'][1, 3] += 2.0
    seeds['player_opportunity_within_team'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['receptions'] = b['receptions'] + 99.0
    seeds['receptions_within_targets'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['receiving_td'] = b['receptions'] + 1.0
    seeds['receiving_td_within_receptions'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['receptions'] = b['receptions'].copy()
    b['receptions'][2, 2] = 0.0
    b['receiving_yards'][2, 2] = 14.0        # yards with nothing caught
    seeds['zero_receptions_implies_zero_yards'] = b

    b = {k: (x.copy() if hasattr(x, 'copy') else x) for k, x in base.items()}
    b['appearance'][0, :] = 0.0        # did not play, still allocated
    seeds['allocation_only_when_available'] = b

    check('every declared identity has a seeded violation',
          set(seeds) == set(ACC.IDENTITY_NAMES),
          str(set(ACC.IDENTITY_NAMES) - set(seeds)))
    for name, kw in seeds.items():
        o = ACC.reconcile_nonqb(**kw)
        hit = [x['identity'] for x in (o.evidence.get('violations') or ())]
        check(f'  {name}: the seeded violation is rejected',
              o.state is State.FAIL and name in hit,
              f'{o.state.value}[{o.code}] hit={hit}')

    # It must not CLIP. A failing run reports the worst cell, not a repair.
    o = ACC.reconcile_nonqb(**seeds['share_simplex_closure'])
    check('  a violation is reported with its worst cell, never clipped',
          any(x['worst'] > 0 for x in o.evidence['violations']))


def test_g_accounting_refuses_a_mismatched_draw_index():
    base = _clean()
    b = dict(base)
    b['appearance'] = np.ones((4, 19))          # one draw short
    o = ACC.reconcile_nonqb(**b)
    check('a cross-layer draw-width mismatch is a NAMED refusal',
          o.state is State.FAIL and o.code == 'CROSS_DRAW_INDEX_MISMATCH',
          f'{o.state.value}[{o.code}]')


def test_g_chain_accounting_is_not_applicable_when_nothing_ran():
    bad = Outcome.blocked('BLOCKED_UPSTREAM_APPEARANCE', 'x',
                          cause=__import__(
                              'sportsplatform.governance.outcome',
                              fromlist=['Cause']).Cause.DEPENDENCY)
    good = Outcome.ok('OK', value=1)
    o = ACC.reconcile_chain(good, bad, bad, bad, bad, bad)
    check('accounting over a chain that did not run is NOT_APPLICABLE, '
          'not PASS', o.state is State.NOT_APPLICABLE
          and o.code == 'NONQB_ACCOUNTING_NOT_REACHED',
          f'{o.state.value}[{o.code}]')
    check('  and it names which stages were absent',
          any('appearance' in a for a in o.evidence['absent']))
    o2 = ACC.reconcile_chain(good, good, good, good, good, good)
    check('  a fully-executed chain is PASS', o2.state is State.PASS)


def test_g_accounting_test_fails_when_the_guard_is_bypassed():
    """The second half of the G0A standard: removing the guard must break the
    test. A test that would still pass with the guard deleted tests nothing."""
    from nfl.tests import bypass as BP
    base = _clean()
    base['appearance'] = base['appearance'].copy()
    base['appearance'][0, :] = 0.0        # allocated while not appearing
    caught = ACC.reconcile_nonqb(**base)
    check('with the guard in place the violation is caught',
          caught.state is State.FAIL)
    with BP.guard_bypassed('nfl.production.nonqb.accounting',
                           'reconcile_nonqb',
                           replacement=lambda *a, **k: Outcome.ok(
                               'STUB', value={})):
        import importlib
        m = importlib.import_module('nfl.production.nonqb.accounting')
        missed = m.reconcile_nonqb(**base)
    check('  with it bypassed the SAME violation goes undetected',
          missed.state is State.PASS,
          f'{missed.state.value}[{missed.code}]')
    check('  so the check above is load-bearing rather than decorative',
          caught.state is State.FAIL and missed.state is State.PASS)


def test_g_negative_receiving_yards_are_reported_not_refused():
    """A reception for a loss is ordinary football. The identity that once
    forbade it was a property of the placeholder conversion layer."""
    base = _clean()
    base['receiving_yards'] = base['receiving_yards'].copy()
    base['receiving_yards'][0, 0] = -8.0
    o = ACC.reconcile_nonqb(**base)
    check('a negative receiving-yard cell does NOT fail accounting',
          o.state is State.PASS, f'{o.state.value}[{o.code}] {o.detail[:120]}')
    check('  it is counted and reported instead',
          o.evidence.get('n_negative_yard_cells') == 1,
          o.evidence.get('n_negative_yard_cells'))
    check('  and the minimum is carried',
          abs(float(o.evidence.get('min_receiving_yards')) + 8.0) < 1e-9)


# ---------------------------------------------------------------- L
def test_l_real_slate_chain_refuses_without_a_fixture():
    from nfl.production.nonqb import slate_rehearsal as SL
    players = [{'gsis_id': 'x1', 'position': 'WR', 'team': 'NE'}]
    ch = SL.nonqb_chain(2026, 1, players)
    check('the real-input chain covers every gated layer',
          tuple(ch) == SL.CHAIN, str(tuple(ch)))
    check('  appearance does not PASS without a legitimate source',
          ch['appearance'].state is not State.PASS,
          ch['appearance'].state.value)
    check('  and it emits no probability at all',
          ch['appearance'].evidence.get('value') is None
          and not isinstance(ch['appearance'].value, dict)
          if ch['appearance'].state is not State.PASS else False)
    for k in SL.CHAIN[1:]:
        check(f'  {k} is blocked upstream, not silently empty',
              ch[k].state is State.BLOCKED
              and ch[k].code.startswith('BLOCKED_UPSTREAM'),
              f'{ch[k].state.value}[{ch[k].code}]')
    for k, v in ch.items():
        check(f'  {k} names its refusal specifically',
              v.code not in ('ERROR', 'FAILED', 'UNKNOWN') and len(v.code) > 6,
              v.code)


def test_l_slate_stage_state_is_never_inferred_from_absence():
    from nfl.production.nonqb import slate_rehearsal as SL
    g = {'stages': [{'stage': 'qb_layer', 'state': 'PASS',
                     'code': 'QB_LAYER_OK'}], 'failures': []}
    check('a reported stage keeps its own code',
          SL._code(None, g, 'qb_layer') == 'PASS[QB_LAYER_OK]')
    check('an UNREPORTED stage is ABSENT, never PASS',
          SL._code(None, g, 'td_layer').startswith('ABSENT'),
          SL._code(None, g, 'td_layer'))


def test_l_recorded_slate_rehearsal_is_real_and_refused():
    f = os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                     'slate_rehearsal.json')
    if not os.path.exists(f):
        check('the recorded real-slate rehearsal exists', False, f)
        return
    r = json.load(open(f))
    check('the recorded real-slate rehearsal used NO fixture',
          r['TEST_ONLY'] is False and 'NONE' in r['fixtures_used'])
    check('  it ran every game on the slate', r['n_games'] == 16, r['n_games'])

    # SCHEMA IS CHECKED, NOT ASSUMED. This read g['layers'] directly. The
    # producer (slate_rehearsal.build) writes the non-QB states under
    # g['nonqb'] with 'team_environment' and 'qb_layer' as siblings, so the
    # committed artifact had drifted off the shape the test asserted, and
    # re-running the producer surfaced it as a KeyError.
    #
    # The raise is the point: this function died on its third assertion, so
    # the checks below it never ran and the module's own tally reported ZERO
    # failing checks. Only run_suite's separate RAISED counter caught it.
    # A shape mismatch is now a NAMED failing check.
    def _layers(g):
        if 'nonqb' in g:
            d = dict(g['nonqb'])
            for k in ('team_environment', 'qb_layer'):
                if k in g:
                    d[k] = g[k]
            return d
        return g.get('layers') or {}

    bad_shape = [g['game_id'] for g in r['games']
                 if 'nonqb' not in g and 'layers' not in g]
    if not check('  every game carries a recognised layer-state shape',
                 not bad_shape,
                 f'REHEARSAL_SCHEMA_UNRECOGNISED: {bad_shape[:3]}'):
        return
    check('  team environment executed on every game',
          all(_layers(g).get('team_environment', '').startswith('PASS')
              for g in r['games']),
          [_layers(g).get('team_environment') for g in r['games'][:3]])
    check('  no non-QB modelling layer produced a forecast',
          all(not v.startswith('PASS') for g in r['games']
              for k, v in _layers(g).items()
              if k not in ('team_environment', 'qb_layer')),
          [v for g in r['games'] for k, v in _layers(g).items()
           if k not in ('team_environment', 'qb_layer')
           and v.startswith('PASS')][:3])
    check('  and no player record was emitted',
          r.get('n_player_records', 0) == 0, r.get('n_player_records'))
    check('  publication remains refused',
          'NFL1_NOT_AUTHORIZED' in r['publication'], r['publication'])
    check('  and G0A is still recorded as 11/12',
          r['gates']['G0A'] == '11/12', r['gates'])


# ---------------------------------------------------------------- frozen fits
def test_D_conversion_refuses_a_caller_supplied_prior():
    """A layer that accepts any prior is not an implementation of RC1."""
    ap = _appear(m=20)
    pa = LY.participation(ap, {'p1': 0.6, 'p2': 0.3, 'p3': 0.1}, m=20)
    tc = LY.targets_carries(pa, 'targets', [0.6, 0.3, 0.1],
                            ['WR', 'WR', 'WR'], ([0], [3]), IDS, PAR, m=20)
    T = tc.value['share'] * 30
    o = LY.receiving_conversion(tc, T, {'catch_rate': 0.62,
                                        'yards_per_reception': 11.0},
                                IDS, ['WR'] * 3, ORD, m=20)
    check('a caller-supplied conversion prior is refused',
          o.state is State.FAIL and o.code == 'CONVERSION_PRIOR_NOT_FROZEN',
          f'{o.state.value}[{o.code}]')
    t = LY.td_layer(_ok_conv(20), T, {'td_per_opportunity': 0.05}, IDS,
                    ['WR'] * 3, ORD, m=20)
    check('  and a caller-supplied TD rate is refused',
          t.state is State.FAIL and t.code == 'TD_PRIOR_NOT_FROZEN',
          f'{t.state.value}[{t.code}]')
    bad = dict(TD_PRIORS, B_pos={'WR': 0.9})
    t2 = LY.td_layer(_ok_conv(20), T, bad, IDS, ['WR'] * 3, ORD, m=20)
    check('  a per-reception rate above one is refused, never clipped',
          t2.state is State.FAIL and t2.code == 'TD_RATE_ABOVE_ONE',
          f'{t2.state.value}[{t2.code}]')


def _ok_conv(m):
    ap = _appear(m=m)
    pa = LY.participation(ap, {'p1': 0.6, 'p2': 0.3, 'p3': 0.1}, m=m)
    tc = LY.targets_carries(pa, 'targets', [0.6, 0.3, 0.1],
                            ['WR', 'WR', 'WR'], ([0], [3]), IDS, PAR, m=m)
    return LY.receiving_conversion(tc, tc.value['share'] * 30, RECV_PRIORS,
                                   IDS, ['WR'] * 3, ORD, m=m)


def test_D_conversion_is_a_distribution_not_a_point():
    """The point-for-a-distribution defect, the fourth time it has appeared in
    this project. A constant yards-per-reception collapses a tail a Normal
    already understates thirteenfold."""
    cv = _ok_conv(200)
    Y, R = cv.value['receiving_yards'], cv.value['receptions']
    per = np.where(R > 0, Y / np.maximum(R, 1), np.nan)
    check('per-catch yardage varies within a player',
          float(np.nanstd(per[0])) > 0.0, float(np.nanstd(per[0])))
    check('  and the pool\'s negative gains survive into the draws',
          bool((per < 0).any() or (Y < 0).any()))
    a = _ok_conv(50).value['receptions']
    b = _ok_conv(50).value['receptions']
    check('  the same seed reproduces the same draws exactly',
          bool((a == b).all()))


def test_D_p4c_params_refuse_a_leaked_panel():
    from nfl.production.nonqb import p4c_params as P4
    check('the P4C production params name a frozen spec',
          P4.SPEC_VERSION.startswith('p4c-'), P4.SPEC_VERSION)
    o = P4.params('not_a_class', 2026)
    check('  an unknown allocation class is refused',
          o.state is State.FAIL and o.code == 'UNKNOWN_CLASS',
          f'{o.state.value}[{o.code}]')


def test_D_appearance_walk_matches_the_research_walk():
    """The production feature walk exists only because stage_a.build loads its
    own panel. If it ever diverges, production is running a different
    mechanism under an accepted name."""
    from nfl.production.nonqb import appearance_model as AM
    o = AM.assert_walk_matches_research()
    check('the production walk is identical to the research walk',
          o.state is State.PASS, f'{o.state.value}[{o.code}] {o.detail[:160]}')
    check('  over a non-trivial number of comparisons',
          int(o.evidence.get('n_comparisons') or 0) > 100000,
          o.evidence.get('n_comparisons'))


def test_D_appearance_refuses_an_unidentified_player():
    from nfl.production.nonqb import appearance_model as AM
    o = AM.predict(2026, 1, [{'position': 'WR', 'team': 'NE'}],
                   [{'season': '2026', 'week': '1', 'team': 'NE',
                     'gsis_id': 'x', 'report_status': '',
                     'practice_status': 'Full'}])
    check('a player with no gsis_id is refused, never name-matched',
          o.state is State.FAIL
          and o.code == 'APPEARANCE_IDENTITY_UNRESOLVED',
          f'{o.state.value}[{o.code}]')
    o2 = AM.predict(2026, 1, [{'gsis_id': 'x', 'position': 'WR',
                               'team': 'NE'}], [])
    check('  and an empty injuries feed defers rather than predicting',
          o2.state is State.DEFERRED, f'{o2.state.value}[{o2.code}]')


def test_K_recorded_engine_rehearsal_is_quarantined():
    """Updated for the R4 artifact schema. The PROPERTIES asserted are the
    same or stronger: R3 required every layer to execute, and R4 requires that
    too EXCEPT for rushing conversion, which must carry exactly the named
    deferral -- a stricter statement than 'every layer passed', because it
    pins which layer may not and why."""
    f = os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                     'engine_rehearsal.json')
    if not os.path.exists(f):
        check('the recorded engine rehearsal exists', False, f)
        return
    r = json.load(open(f))
    check('the engine rehearsal is marked TEST_ONLY', r['TEST_ONLY'] is True)
    check('  it names the ONE stubbed input',
          'injuries' in r['stubbed_input'] and 'ONLY' in r['stubbed_input'],
          r['stubbed_input'])
    check('  it carries fixture provenance',
          len(r['fixture_provenance']) > 60)
    check('  every game refuses publication',
          all(g.get('publication_gate', '').startswith('FAIL')
              for g in r['games'] if 'publication_gate' in g))
    bad = [(k, v) for g in r['games'] for k, v in g['layers'].items()
           if not v.startswith('PASS') and k != 'rushing_conversion']
    check('  every layer except rushing conversion executed on every game',
          not bad, bad[:3])
    rc = {v for g in r['games'] for k, v in g['layers'].items()
          if k == 'rushing_conversion'}
    check('  and rushing conversion carries exactly the named deferral',
          rc == {'DEFERRED[RUSHING_CONVERSION_CONTROL_UNDEFINED]'}, rc)
    a = r['accounting']
    check('  receiving accounting reconciled every game',
          a['receiving_ok'] == a['n_games'], a)
    check('  every receiving identity violation count is zero',
          all(v == 0 for k, v in a['violations'].items()
              if k.endswith('_violations')), a['violations'])
    check('  over a non-trivial number of cells',
          a['total_cells_checked'] > 100000, a['total_cells_checked'])
    check('  rushing accounting fails ONLY on the named QB gap',
          a['rushing_ok'] == 0
          and a['violations'].get('rushing_td_within_carries_violations') == 0,
          a['violations'])
    check('  and it cannot satisfy G0A', 'NONE' in r['g0a_effect'])


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

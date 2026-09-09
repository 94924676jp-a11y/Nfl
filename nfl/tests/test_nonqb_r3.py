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


def _appear(test_only=True, m=40):
    return Outcome.ok('APPEARANCE_OK',
                      value={i: np.ones(m, int) for i in IDS},
                      test_only=test_only)


def _chain(m=40):
    ap = _appear(m=m)
    pa = LY.participation(ap, {'p1': 0.6, 'p2': 0.3, 'p3': 0.1}, m=m)
    tc = LY.targets_carries(pa, 'targets', [0.6, 0.3, 0.1],
                            ['WR', 'WR', 'WR'], ([0], [3]), IDS, PAR, m=m)
    cv = LY.receiving_conversion(tc, tc.value['share'][0] * 30,
                                 {'catch_rate': 0.62,
                                  'yards_per_reception': 11.0}, m=m)
    td = LY.td_layer(cv, cv.value['receptions'],
                     {'td_per_opportunity': 0.05}, m=m)
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
    print('\nB. appearance without a usable injuries feed emits nothing')
    o = LY.appearance(2026, 1, [{'gsis_id': 'x'}])
    check('the real path does not PASS', o.state is not State.PASS, o.code)
    check('  it names the exact condition, not a generic failure',
          'INJURIES' in o.code, o.code)
    check('  and emits no probabilities at all', o.value is None
          or not isinstance(o.value, dict) or not o.value, str(o.value)[:60])


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
    blocked = Outcome.blocked('UPSTREAM', 'x', cause=None) if False else \
        LY.appearance(2026, 1, [{'gsis_id': 'x'}])
    pa = LY.participation(blocked, {})
    check('participation without appearance',
          pa.code == 'BLOCKED_UPSTREAM_APPEARANCE', pa.code)
    tc = LY.targets_carries(pa, 'targets', [], [], ([], []), [], PAR)
    check('  targets/carries without participation',
          tc.code == 'BLOCKED_UPSTREAM_APPEARANCE', tc.code)
    cv = LY.receiving_conversion(tc, [], {})
    check('  conversion without opportunity',
          cv.code == 'BLOCKED_UPSTREAM_OPPORTUNITY', cv.code)
    td = LY.td_layer(cv, [], {})
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
    check('  no negative receiving yards',
          not bool((cv.value['receiving_yards'] < 0).any()))


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
    b['receiving_yards'][2, 2] = -1.0
    seeds['receiving_yards_non_negative'] = b

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
    check('  team environment executed on every game',
          all(g['team_environment'].startswith('PASS') for g in r['games']))
    check('  the QB layer executed on every game',
          all(g['qb_layer'].startswith('PASS') for g in r['games']))
    check('  no non-QB layer produced a forecast',
          all(not v.startswith('PASS')
              for g in r['games'] for v in g['nonqb'].values()))
    check('  non-QB accounting is NOT_APPLICABLE, never PASS',
          all(g['nonqb_accounting'].startswith('NOT_APPLICABLE')
              for g in r['games']))
    check('  publication remains refused',
          'NFL1_NOT_AUTHORIZED' in r['publication'], r['publication'])
    check('  and G0A is still recorded as 11/12',
          r['gates']['G0A'] == '11/12', r['gates'])


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

"""An intercepted throw is not available to be caught.

C3 builds the targeted-throw budget from the quarterbacks' attempts and RC1
converts every one of those throws to a possible catch. Nothing removed the
ones the interception draw had already spent, so a team draw could catch more
balls than there were non-intercepted attempts to throw, and
`credit_passing_line` refused -- correctly, and after the fact.

SC2 reserves them before the catches are drawn. Two claims, and they are
different:

  1. COHERENCE. `receptions <= attempts - interceptions`, per team per draw,
     by construction and not by a guard.
  2. THE LEVEL DOES NOT MOVE. Removing throws from the pool without restoring
     the rate would cut about 0.51 receptions per team-game. The rate is taken
     conditional on not having been intercepted, `c / (1 - pi)`, so
     E[R] = T c exactly as before. A test that checked only (1) would pass on
     a construction that quietly lowered every receiver's catches, which is
     the failure mode SC2's own pre-registration named before it was built.

The constant is MEASURED and this file is what stops it drifting: `pi` in code
must equal the share in `SC2_SECTION3_MEASUREMENT.json`, which was computed on
2,718 REG team-games.
"""
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PASSED, FAILED, BLOCKED = 0, 0, 0
_F = []


def ck(name, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        _F.append(name)
    print(('PASS ' if cond else 'FAIL ') + name
          + ((' :: ' + detail) if detail else ''))


def blocked(name, detail):
    global BLOCKED
    BLOCKED += 1
    print(f'BLOCKED {name} cause=DATA :: {detail} BLOCKED is not a pass.')


def test_the_constant_is_the_measured_one():
    from nfl.production.nonqb import shared_pass as SP
    f = REPO / 'nfl' / 'research' / 'sc2' / 'SC2_SECTION3_MEASUREMENT.json'
    if not f.exists():
        blocked('SC2_MEASUREMENT_ABSENT',
                'the section-3 measurement artifact is not in the tree, so '
                'the constant has nothing to be checked against.')
        return
    a = json.loads(f.read_text())
    ck('pick_share_in_code_matches_the_measurement',
       abs(SP.INTERCEPTION_SHARE_OF_TARGETS
           - a['interceptions_as_share_of_targets']) < 5e-7,
       f"code {SP.INTERCEPTION_SHARE_OF_TARGETS} "
       f"artifact {a['interceptions_as_share_of_targets']}")
    # The two independent routes to the conditional rate must agree, or the
    # identity the whole construction rests on is not the right one.
    direct = a['m2_catch_rate_on_targets_minus_interceptions']
    derived = (a['m2_catch_rate_on_targets']
               / (1.0 - a['interceptions_as_share_of_targets']))
    ck('the_conditional_rate_identity_holds_in_the_measurement',
       abs(direct - derived) < 1e-5,
       f'measured directly {direct:.6f} against c/(1-pi) {derived:.6f}')
    ck('the_measurement_frame_is_recorded',
       int(a.get('n_team_games', 0)) > 2000, str(a.get('n_team_games')))


def test_the_reservation_closes_and_never_exceeds_targets():
    from nfl.production.nonqb import shared_pass as SP
    rng = np.random.default_rng(11)
    T = rng.integers(0, 9, (6, 500))
    team_int = [np.minimum(rng.poisson(0.9, 500), T[:3].sum(0)),
                np.minimum(rng.poisson(0.9, 500), T[3:].sum(0))]
    o = SP.deal_interceptions(T, [0, 3], [3, 3], team_int, rng)
    ck('the_reservation_runs', o.state.name == 'PASS', o.code)
    if o.state.name != 'PASS':
        return
    INT = o.value
    ck('no_receiver_is_picked_more_often_than_he_was_targeted',
       bool((INT <= T).all()))
    for k, (s0, c) in enumerate(zip([0, 3], [3, 3])):
        ck(f'team{k}_reservation_closes_exactly',
           bool((INT[s0:s0 + c].sum(0) == team_int[k]).all()),
           'a hypergeometric draw sums to nsample by construction')


def test_a_pick_that_exceeds_the_named_targets_is_reported_not_absorbed():
    from nfl.production.nonqb import shared_pass as SP
    T = np.array([[1], [0]])
    o = SP.deal_interceptions(T, [0], [2], [np.array([5])],
                              np.random.default_rng(0))
    ck('the_shortfall_is_counted',
       bool(o.evidence.get('team_draws_with_more_picks_than_named_targets')),
       'a team draw with more picks than named targets is a DIFFERENT gap '
       'and must be visible rather than silently truncated')


def test_the_level_does_not_move():
    """E[R] = T c, before and after. The claim SC2 would fail on quietly."""
    from nfl.production.nonqb import shared_pass as SP
    from nfl.production.nonqb import layers as LY
    from sportsplatform.governance.outcome import Outcome

    m, n = 20000, 2
    pi = SP.INTERCEPTION_SHARE_OF_TARGETS
    T = np.full((n, m), 8.0)
    priors = {'k_shrink': 1.0, 'own': {}, 'pos_yardage_pool': {'WR': [10.0]},
              'pos_catch_rate': {'WR': 0.675155}}
    tc = Outcome.ok('T', value=None)
    ids, pos = ['a', 'b'], ['WR', 'WR']
    base = LY.receiving_conversion(tc, T, priors, ids, pos, 202602,
                                   m=m, seed=5)
    ck('the_unreserved_call_still_runs', base.state.name == 'PASS', base.code)
    # Reserve at exactly the expected rate, which is what the engine's
    # hypergeometric delivers in expectation.
    rng = np.random.default_rng(3)
    INT = rng.binomial(T.astype(int), pi)
    res = LY.receiving_conversion(tc, T, priors, ids, pos, 202602, m=m,
                                  seed=5, intercepted=INT, pick_share=pi)
    ck('the_reserved_call_runs', res.state.name == 'PASS', res.code)
    if not (base.state.name == 'PASS' and res.state.name == 'PASS'):
        return
    b = float(base.value['receptions'].mean())
    r = float(res.value['receptions'].mean())
    want = 8.0 * 0.675155
    # Monte Carlo error on a mean of n*m Bernoulli-ish counts; 4 sd is the
    # tolerance and it is derived, not picked to fit.
    sd = float(np.sqrt(8 * 0.675 * 0.325 / (n * m)))
    ck('the_unreserved_mean_is_T_times_c', abs(b - want) < 4 * sd,
       f'{b:.4f} against {want:.4f}, 4sd = {4 * sd:.4f}')
    ck('the_reserved_mean_is_ALSO_T_times_c', abs(r - want) < 4 * sd,
       f'{r:.4f} against {want:.4f}, 4sd = {4 * sd:.4f}')
    # And the failure mode the pre-registration named: the rate NOT restored.
    naive = LY.receiving_conversion(tc, T, priors, ids, pos, 202602, m=m,
                                    seed=5, intercepted=INT, pick_share=0.0)
    if naive.state.name == 'PASS':
        nm = float(naive.value['receptions'].mean())
        ck('and_the_UNrestored_rate_would_have_lowered_it',
           nm < want - 4 * sd,
           f'{nm:.4f} against {want:.4f} -- this is the level change SC2 '
           f'exists to avoid, reproduced on purpose')


def test_half_a_reservation_is_refused():
    from nfl.production.nonqb import layers as LY
    from sportsplatform.governance.outcome import Outcome
    T = np.full((1, 4), 5.0)
    priors = {'k_shrink': 1.0, 'own': {}, 'pos_yardage_pool': {'WR': [10.0]},
              'pos_catch_rate': {'WR': 0.7}}
    o = LY.receiving_conversion(Outcome.ok('T', value=None), T, priors,
                                ['a'], ['WR'], 202602, m=4, seed=1,
                                intercepted=np.zeros((1, 4)))
    ck('picks_without_a_share_refuse',
       o.state.name == 'FAIL' and o.code == 'SC2_RESERVATION_HALF_SUPPLIED',
       f'{o.state.name}[{o.code}]')
    o = LY.receiving_conversion(Outcome.ok('T', value=None), T, priors,
                                ['a'], ['WR'], 202602, m=4, seed=1,
                                intercepted=np.full((1, 4), 9.0),
                                pick_share=0.02)
    ck('more_picks_than_targets_refuse_rather_than_clip',
       o.state.name == 'FAIL'
       and o.code == 'SC2_RESERVATION_EXCEEDS_TARGETS',
       f'{o.state.name}[{o.code}]')


def test_the_frozen_arms_do_not_move():
    from nfl.production import candidate_mode as CM
    for name in ('V1_CANDIDATE_R9_W1P', 'V1_CANDIDATE_R9_W1P_G',
                 'V1_CANDIDATE_R9_W1P_GA'):
        o = CM.resolve(getattr(CM, name))
        ck(f'{name}_does_not_reserve',
           not o.value['flags'].get('reserve_interceptions'),
           'a closure change may never be an edit to a frozen arm')
    for name in ('V1_CANDIDATE_R9_W1P_GS', 'V1_CANDIDATE_R9_W1P_GSV',
                 'V1_CANDIDATE_R9_W1P_GSP', 'V1_CANDIDATE_R9_W1P_GSVP'):
        o = CM.resolve(getattr(CM, name))
        ck(f'{name}_resolves', o.state.name == 'PASS', o.code)
        ck(f'{name}_reserves',
           bool(o.value['flags'].get('reserve_interceptions')))
        ck(f'{name}_is_not_promoted', not o.value.get('promoted'))
        ck(f'{name}_carries_SC2',
           any(c.get('component') == 'SC2'
               for c in o.value['components']))
        ck(f'{name}_carries_the_ablation_note',
           bool(o.value.get('ablation', {}).get('what_it_cannot_separate')))


def test_the_arms_differ_in_exactly_what_they_declare():
    from nfl.production import candidate_mode as CM
    f = {n: CM.resolve(getattr(CM, f'V1_CANDIDATE_R9_W1P_{n}')).value['flags']
         for n in ('GS', 'GSV', 'GSP', 'GSVP')}
    keys = set().union(*[set(v) for v in f.values()])

    def diff(a, b):
        return {k for k in keys if f[a].get(k) != f[b].get(k)}

    ck('A1_only_differs_from_the_baseline_in_availability_alone',
       diff('GS', 'GSV') == {'availability_feed'}, str(diff('GS', 'GSV')))
    ck('A2_only_differs_in_the_panel_AND_the_mechanism',
       diff('GS', 'GSP') == {'appearance_panel_2026', 'appearance_r8'},
       'both, which is why it is never reported as the panel effect alone: '
       + str(diff('GS', 'GSP')))
    ck('A1_plus_A2_is_exactly_the_union',
       diff('GS', 'GSVP') == diff('GS', 'GSV') | diff('GS', 'GSP'),
       str(diff('GS', 'GSVP')))


def test_an_injected_population_is_compared_against_the_fitted_one():
    """The one line that would have caught the week-1 survivorship filter.

    A model's coefficients mean something only against the population they
    were fitted on. R8 moves w = n_cur/(n_cur+k) of its weight off the depth
    listing the moment a player has ONE current-season game, and it learned
    what that trade is worth on week-1 rows that are about half non-appearers.
    The 2026 week-1 rows come from the snap-count file, where almost everyone
    appeared -- so `n_cur = 1` at serve time is not the `n_cur = 1` the fit
    saw, and adding the observation that a starter PLAYED moved him DOWN.

    This does not assert the defect is fixed. It asserts the comparison is
    made and the gap is visible, because the failure mode is silence.
    """
    from nfl.production.nonqb import appearance_r7 as R7
    from nfl.production.nonqb import appearance_panel_2026 as AP

    fr = R7.build_frame()
    if fr.state.name != 'PASS':
        blocked('W1_FRAME_UNAVAILABLE',
                f'the R7 frame is {fr.state.name}[{fr.code}], so there is no '
                f'fitted population to compare against.')
        return
    hist = [r for r in fr.value if r['w'] == 1]
    if not hist:
        blocked('W1_FRAME_NO_WEEK_ONE', 'the frame holds no week-1 row.')
        return
    fitted = sum(r['appeared'] for r in hist) / len(hist)
    ex = AP.as_r8_frame_rows(2026, 1)
    if ex.state.name != 'PASS':
        blocked('W1_PANEL_UNAVAILABLE',
                f'the 2026 week-1 panel is {ex.state.name}[{ex.code}].')
        return
    served = sum(r['appeared'] for r in ex.value) / len(ex.value)
    gap = abs(served - fitted)
    # 10pp is a judgement about when a population difference stops being
    # noise and starts being a different question, stated here rather than
    # discovered after a board looked wrong.
    ck('the_injected_week1_population_matches_the_fitted_one',
       gap <= 0.10,
       f'fitted base rate {fitted:.4f} on {len(hist)} week-1 frame row(s) '
       f'against injected {served:.4f} on {len(ex.value)} row(s), gap '
       f'{gap:.4f}. KNOWN OPEN: the panel is built from snap counts and the '
       f'frame from the panel UNION the depth chart, so a healthy scratch has '
       f'a row in one and none in the other. See '
       f'nfl/research/sc2/W1_PANEL_SURVIVORSHIP.md')
    ck('the_arms_that_consume_it_carry_the_warning', _panel_arms_warn(),
       'GSP and GSVP must name the skew in their own component declaration, '
       'so it cannot be read off a board without it')


def _panel_arms_warn():
    from nfl.production import candidate_mode as CM
    for name in ('V1_CANDIDATE_R9_W1P_GSP', 'V1_CANDIDATE_R9_W1P_GSVP'):
        o = CM.resolve(getattr(CM, name))
        a2 = [c for c in o.value['components']
              if c.get('component') == 'A2_PANEL']
        if not a2 or 'survivorship' not in a2[0]:
            return False
    return True


def test_zz_every_check_passed():
    # THE TRIPWIRE, AND IT IS RECOGNISED BY SHAPE. `run_suite.tally_tripwires`
    # counts a function that calls anything beyond print/AssertionError as a
    # real test, so a `', '.join(...)` in here turned this into a ZERO-CHECK
    # function -- one that ran, measured nothing, and said nothing. The failed
    # names are printed by `ck` as they happen and again in `main`.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for fn in sorted(n for n in globals()
                     if n.startswith('test_') and n != 'test_zz_every_check_passed'):
        print(f'--- {fn} ---')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    if _F:
        print('FAILED: ' + ', '.join(_F))
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())

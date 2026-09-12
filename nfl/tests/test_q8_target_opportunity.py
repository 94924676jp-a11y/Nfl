"""Q8: the attribution audit, the one licensed repair, and the artefact.

WHAT THESE TESTS PROTECT.

  * THE ATTRIBUTION ADDS UP. Exact Shapley over all 32 subsets; the five
    component values must sum to the total movement, or the ranking is not a
    decomposition of anything.

  * THE BIAS IS PARTLY A SELECTION ARTEFACT. The same model, same draws, is
    biased by two yards on the outcome-selected population and near-unbiased
    on the population it forecasts. That gap is the finding, and it is
    asserted on the emitted artifact.

  * THE BUDGET CARRIES ITS PREDICTIVE SPREAD. A point budget with no spread
    would under-disperse every player's targets and hand the whole inflation
    to the BUDGET oracle. The residual pool must be a pool.

  * ONE CHANGE. The two arms differ in the budget and in nothing else, and the
    shrinkage slope is fitted on strictly earlier seasons.

  * A GAIN IN COVERAGE OR BIAS IS NOT SUPPORT. `decide` refuses it, because
    the audit has already shown bias on that population is largely mechanical.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.q8 import audit as AUD                          # noqa: E402
from nfl.research.q8 import repair as REP                         # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _audit():
    p = AUD.HERE / 'Q8_ATTRIBUTION_AUDIT.json'
    return json.loads(p.read_text()) if p.exists() else None


def _results():
    return json.loads(REP.RESULTS.read_text()) if REP.RESULTS.exists() else None


# ================================================== the attribution audit
def test_a_the_attribution_is_an_exact_decomposition():
    a = _audit()
    if a is None:
        check('the audit artifact exists', False)
        return
    check('all 32 subsets were evaluated', a['n_subsets'] == 32,
          str(a['n_subsets']))
    check('no repair was built in the audit', a['no_repair_built'] is True)
    for name, att in a['attribution'].items():
        check(f'{name}: the five values sum to the total movement',
              att['adds_up'] is True,
              f"{att['sum_of_shapley_values']} vs {att['total_movement']}")
        check(f'  and every component is ranked', 
              len(att['ranked_by_absolute_contribution']) == 5)
        check(f'  each carrying its oracle kind',
              all(att['components'][c]['kind'] in ('REALISATION', 'PARAMETER')
                  for c in AUD.COMPONENTS))
    check('the two kinds of oracle are distinguished in prose too',
          'REALISATION' in a['oracle_kinds_note']
          and 'PARAMETER' in a['oracle_kinds_note'])


def test_b_the_share_machinery_is_measured_at_near_zero():
    a = _audit()
    if a is None:
        check('the audit artifact exists', False)
        return
    for name in ('receiving_yard_bias', 'player_target_crps'):
        att = a['attribution'][name]
        tot = abs(att['total_movement'])
        for c in ('CLASS', 'SHRINK', 'REDIST'):
            share = abs(att['components'][c]['shapley']) / tot if tot else 0.0
            check(f'{name}: {c} carries under 10% of the movement',
                  share < 0.10, f'{100 * share:.2f}%')
    check('the ranking names a winner for bias and for CRPS separately',
          a['headline']['bias_is_dominated_by']
          != a['headline']['target_crps_is_dominated_by'],
          f"{a['headline']['bias_is_dominated_by']} vs "
          f"{a['headline']['target_crps_is_dominated_by']}")


def test_c_the_bias_is_largely_a_selection_artefact():
    a = _audit()
    if a is None:
        check('the audit artifact exists', False)
        return
    sel = a['attribution']['receiving_yard_bias']['baseline']
    full = a['attribution']['receiving_yard_bias_full_frame']['baseline']
    check('the outcome-selected population shows a large bias',
          abs(sel) > 1.0, f'{sel:+.4f}')
    check('the forecast population shows a small one',
          abs(full) < 0.5, f'{full:+.4f}')
    check('  and they differ by more than a yard',
          abs(sel - full) > 1.0, f'{abs(sel - full):.4f}')
    check('the population rule is stated, not assumed',
          'at least one prior appeared game' in a['population_note'])


def test_d_the_budget_carries_its_predictive_spread():
    a = _audit()
    if a is None:
        check('the audit artifact exists', False)
        return
    for f in a['fit_log']:
        check(f"{f['eval_season']}: the budget residual pool is a pool",
              f['budget_residual_pool'] > 100, str(f['budget_residual_pool']))
        check(f"  with a real spread", f['budget_residual_sd'] > 1.0,
              str(f['budget_residual_sd']))
    check('a point budget would have been the defect, and is named as such',
          'POINT BUDGET IS NOT WHAT PRODUCTION DOES'
          in AUD.budget_model.__doc__)


# =============================================================== the repair
def test_e_the_repair_changes_the_budget_and_nothing_else():
    denom = AUD.load_denom()
    arms, ev = REP.budget_arms(denom, 2024)
    b_point, b_res = arms['BASELINE']
    s_point, s_res = arms['Q8_BUDGET_SHRINK']
    check('the slope is fitted on strictly earlier seasons',
          ev['basis'] == 'OLS_SLOPE_ON_STRICTLY_EARLIER_SEASONS', ev['basis'])
    check('  and it is below one, which is the defect it fixes',
          0.0 < ev['beta'] < 1.0, str(ev['beta']))
    check('the shrunk point differs from the frozen point',
          any(abs(s_point[k] - b_point[k]) > 1e-9 for k in b_point))
    check('  and it shrinks TOWARD the league mean, never away',
          all(abs(s_point[k] - ev['league_mean'])
              <= abs(b_point[k] - ev['league_mean']) + 1e-9
              for k in b_point))
    check('the residual pool is recomputed around the new centre',
          abs(ev['residual_sd_shrunk'] - ev['residual_sd_baseline']) > 1e-6,
          f"{ev['residual_sd_baseline']} vs {ev['residual_sd_shrunk']}")
    check('the frozen P4B estimator is read, not re-chosen',
          ev['estimator'] in ('ewma', 'coach_prior', 'league_mean',
                              'team_expanding', 'last_game', 'roll3', 'roll5',
                              'prev_season'), ev['estimator'])
    check('only two arms exist', REP.ARMS == ('BASELINE', 'Q8_BUDGET_SHRINK'))


def test_f_the_repair_calibrates_the_budget_it_aimed_at():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    b = r['team_budget']
    s0 = b['BASELINE']['calibration']['slope']
    s1 = b['Q8_BUDGET_SHRINK']['calibration']['slope']
    check('the baseline budget slope is well below 1', s0 < 0.8, str(s0))
    check('  and the repair moves it toward 1', abs(1 - s1) < abs(1 - s0),
          f'{s0} -> {s1}')
    check('the budget CRPS improves', 
          b['Q8_BUDGET_SHRINK']['crps'] < b['BASELINE']['crps'],
          f"{b['BASELINE']['crps']} -> {b['Q8_BUDGET_SHRINK']['crps']}")
    check('  significantly, on the team-game bootstrap',
          b['Q8_BUDGET_SHRINK']['block_bootstrap_by_team_game']
          ['excludes_zero'] is True)
    check('the budget RMSE improves too',
          b['Q8_BUDGET_SHRINK']['rmse'] < b['BASELINE']['rmse'])


def test_g_the_boundary_is_reported_rather_than_averaged_away():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    d = r['decision']
    check('the decision names strata that improved and that worsened',
          'strata_significantly_better' in d
          and 'strata_significantly_worse' in d)
    check('both lists are non-empty, which IS the finding',
          d['strata_significantly_better'] and d['strata_significantly_worse'],
          f"{len(d['strata_significantly_better'])} better, "
          f"{len(d['strata_significantly_worse'])} worse")
    reg = r['by_target_regime']
    hi = [k for k in reg if k in ('3-5', '6-9', '10+')]
    lo = [k for k in reg if k in ('0', '1-2')]
    check('every high-target regime improves',
          all(reg[k]['Q8_BUDGET_SHRINK']['improves'] for k in hi), str(hi))
    check('every low-target regime worsens',
          all(not reg[k]['Q8_BUDGET_SHRINK']['improves'] for k in lo), str(lo))
    check('each stratum is reported season-independently with its own n',
          all('n' in reg[k]['Q8_BUDGET_SHRINK'] for k in reg))


def test_h_a_gain_in_coverage_or_bias_is_never_support():
    def mk(delta, sig=False, worse=(), better=(0,)):
        # `better` marks a stratum whose improvement survives the bootstrap.
        # The rule requires one, and the OVERALL delta's significance is a
        # different flag -- conflating them was a fixture bug, not a code one.
        strata = {f's{i}': {'Q8_BUDGET_SHRINK': {
            'improves': i not in worse, 'n': 200,
            'block_bootstrap_by_team_game': {
                'excludes_zero': (i in worse) or (i in better)}}}
            for i in range(4)}
        return {'overall': {'Q8_BUDGET_SHRINK': {
            'paired_target_crps_delta': {
                'delta_mean': delta, 'delta_pct': 100 * delta,
                'block_bootstrap_by_team_game': {'excludes_zero': sig}},
            'paired_rec_yard_crps_delta': {
                'delta_mean': -0.1,
                'block_bootstrap_by_team_game': {'excludes_zero': False}}}},
            'by_position': strata, 'by_role_class': {},
            'by_target_regime': {}, 'by_appearance_certainty': {}}
    d = REP.decide(mk(+0.01))
    check('no proper-score gain -> REJECT', d['decision'] == 'REJECT',
          d['decision'])
    check('  and it says coverage and bias cannot rescue it',
          d['coverage_or_bias_cannot_rescue'] is True
          and 'cannot rescue' in d['why'])
    d = REP.decide(mk(-0.01, sig=True))
    check('broad improvement with a significant one -> SUPPORT',
          d['decision'] == 'SUPPORT', d['decision'])
    d = REP.decide(mk(-0.01, sig=True, worse=(3,), better=(0,)))
    check('a significantly worse stratum -> REJECT',
          d['decision'] == 'REJECT', d['decision'])
    check('the rule travels in the artifact',
          'SUPPORT' in d['rule'] and 'REJECT' in d['rule']
          and 'selection artefact' in d['rule'])


def test_i_the_held_fixed_layers_are_named_and_the_artifacts_are_clean():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    joined = ' '.join(r['held_fixed']).lower()
    for layer in ('r8', 'class-level', 'shrinkage', 'redistribution',
                  'efficiency', 'touchdown'):
        check(f'{layer} is declared held fixed', layer in joined)
    check('exactly one change is declared',
          'shrunk toward' in r['the_one_change'])
    check('nothing is promoted', r['promoted'] is False)
    check('no market input is recorded as used', r['market_inputs_used'] == [])
    check('no 2026 row was used', r['live_2026_rows_used'] == 0)
    check('the evaluation seasons are all historical',
          max(r['eval_seasons']) <= 2025, str(r['eval_seasons']))
    check('the decision is one of the three states',
          r['decision']['decision'] in ('SUPPORT', 'WEAK_SUPPORT', 'REJECT'),
          r['decision']['decision'])
    check('intervals are clustered on team-games',
          'team-game' in r['clustering'])
    b = r['overall']['Q8_BUDGET_SHRINK']['paired_target_crps_delta'][
        'block_bootstrap_by_team_game']
    check('  with fewer clusters than rows',
          b['n_clusters'] < b['n_rows'], f"{b['n_clusters']}/{b['n_rows']}")


def test_j_no_rc2_repair_arm_is_reopened():
    spec = (AUD.HERE / 'Q8_REPAIR_SPEC.md').read_text()
    check('the repair spec names the RC2 arms it is NOT',
          'draw-centring' in spec and 'zero-mass' in spec
          and 'variance calibration' in spec)
    check('  and says which layer it acts on instead',
          'team target budget' in spec)
    check('the scope question is stated rather than resolved quietly',
          'scope question' in spec.lower())
    r = _results()
    if r:
        check('the repair acts on the budget, not on receiving yards',
              'team-target point' in r['the_one_change'])


def test_k_the_downstream_and_supporting_measures_are_reported():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for arm in REP.ARMS:
        o = r['overall'][arm]
        check(f'{arm}: zero-target probability is measured against the '
              f'realised rate',
              o['zero_target_probability']['predicted'] is not None
              and o['zero_target_probability']['observed'] is not None,
              f"{o['zero_target_probability']}")
        check(f'{arm}: target-share calibration is a slope, not a bias alone',
              (o['target_share_calibration'] or {}).get('slope') is not None)
        check(f'{arm}: interval coverage is reported at four levels',
              len(o['coverage']) == 4)
        check(f'{arm}: the RC2-comparable population is carried beside the '
              f'full one', 'rc2_population' in o)
    check('starter dilution is reported per class',
          all(rc in r['starter_dilution']['BASELINE']
              for rc in ('starter', 'rotational', 'fringe')))
    check('replacement is measured only where a starter was absent',
          'starter was absent' in r['replacement']['reads']
          and r['replacement']['n_team_games_with_an_absent_starter'] > 0)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

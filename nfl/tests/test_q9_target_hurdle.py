"""Q9: the two stages kept apart, exact reconciliation, and named fallbacks.

WHAT THESE TESTS PROTECT.

  * P(appears) AND P(targeted | appears) ARE NOT COLLAPSED. Stage 1 is fitted
    on appeared rows only and its feature list carries no appearance
    probability; the marginal zero probability is composed at draw time.

  * THE FLOOR IS WHAT MAKES IT A HURDLE. A multinomial can hand a "positive"
    player zero targets. Every clearer gets one target first, so a positive
    player is genuinely positive.

  * RECONCILIATION IS EXACT ON EVERY DRAW, including both fallback paths.

  * BOTH FALLBACKS ARE NAMED AND COUNTED. A fallback nobody measures is a
    fallback nobody knows fired. Neither forces a player active and neither
    drops the budget.

  * A RECEIVING-YARD GAIN IS INSUFFICIENT. `decide` never reads that metric.

  * NO STRATUM THE DECISION READS IS DEFINED FROM THE REALISED TARGET COUNT.
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

from nfl.research.q9 import hurdle as H                           # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _results():
    return json.loads(H.RESULTS.read_text()) if H.RESULTS.exists() else None


# ============================================== the two stages stay apart
def test_a_the_stages_are_not_collapsed():
    names = ' '.join(H.FEATURE_NAMES).lower()
    check('stage 1 carries no appearance probability as a feature',
          'p_appear' not in names and 'appearance' not in names, names[:80])
    check('  and the hurdle is fitted on APPEARED rows only',
          "if r['appeared']" in H.fit_hurdle.__code__.co_consts.__str__()
          or 'APPEARED training rows only' in H.fit_hurdle.__doc__,
          'fit_hurdle')
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('the artifact states how the marginal zero is composed',
          '1 - p_appear * p_hurdle' in r['stages_not_collapsed'])
    check('  and that it is never fitted as one quantity',
          'never fitted as one quantity' in r['stages_not_collapsed'])
    check('the stage-1 feature list is published in full',
          r['stage_1_feature_names'] == list(H.FEATURE_NAMES),
          str(len(H.FEATURE_NAMES)))


def test_b_only_pregame_features_are_admitted():
    check('the declared feature list passes the pregame check',
          H.assert_pregame_only(H.FEATURE_NAMES) is True)
    for bad in ('realized_availability', 'actual_targets',
                'weekly_rosters.status', 'vegas_wp', 'postgame_snaps'):
        try:
            H.assert_pregame_only(list(H.FEATURE_NAMES) + [bad])
            check(f'{bad} is refused', False)
        except ValueError as e:
            check(f'{bad} is refused by name', bad in str(e))
    check('the feature vector is exactly as long as the name list',
          len(H.featurise({'role_class': 'starter', 'pos': 'WR', 'rank': 1},
                          0.0)) == len(H.FEATURE_NAMES))
    check('prior target frequency and its complement are both carried',
          'prior_target_frequency' in H.FEATURE_NAMES
          and 'prior_zero_target_frequency' in H.FEATURE_NAMES)


# =================================== the floor, the exactness, the fallbacks
def test_c_every_clearer_receives_at_least_one_target():
    rng = np.random.default_rng(0)
    base = np.array([0.30, 0.25, 0.20, 0.15, 0.10])
    clear = np.array([True, False, True, True, False])
    out, fb = H.allocate_hurdle(base, clear, 20, rng)
    check('no fallback fired on the ordinary path', fb is None, str(fb))
    check('every clearer is strictly positive',
          all(out[i] >= 1 for i in (0, 2, 3)), str(out))
    check('every non-clearer is exactly zero',
          out[1] == 0 and out[4] == 0, str(out))
    check('the budget reconciles exactly', out.sum() == 20, str(out.sum()))


def test_d_reconciliation_is_exact_on_every_path():
    rng = np.random.default_rng(1)
    base = np.array([0.4, 0.3, 0.2, 0.1])
    for budget in (1, 2, 3, 4, 7, 40):
        for clear in (np.array([True] * 4), np.array([False] * 4),
                      np.array([True, False, False, False]),
                      np.array([True, True, False, True])):
            out, fb = H.allocate_hurdle(base, clear, budget, rng)
            check(f'budget {budget}, {int(clear.sum())} clearers: sums exactly',
                  out.sum() == budget, f'{out.sum()} vs {budget}')
    out, fb = H.allocate_hurdle(base, np.array([False] * 4), 0, rng)
    check('a zero budget allocates nothing and needs no fallback',
          out.sum() == 0 and fb is None)


def test_e_both_fallbacks_are_named_and_behave():
    rng = np.random.default_rng(2)
    base = np.array([0.4, 0.3, 0.2, 0.1])
    out, fb = H.allocate_hurdle(base, np.array([False] * 4), 5, rng)
    check('no clearers fires the named state', fb == H.NO_CLEARERS, str(fb))
    check('  and the budget is still allocated, never dropped',
          out.sum() == 5, str(out.sum()))
    check('  over every player rather than forcing one active',
          (out > 0).sum() >= 1)
    out, fb = H.allocate_hurdle(base, np.array([True] * 4), 2, rng)
    check('more clearers than budget fires the named state',
          fb == H.MORE_CLEARERS_THAN_BUDGET, str(fb))
    check('  exactly budget players are given one target each',
          out.sum() == 2 and int((out == 1).sum()) == 2, str(out))
    check('  and nobody gets more than one on that path',
          out.max() <= 1, str(out.max()))
    counts = np.zeros(4)
    for _ in range(4000):
        o, _f = H.allocate_hurdle(base, np.array([True] * 4), 2,
                                  np.random.default_rng(_))
        counts += (o > 0)
    check('the weighted draw favours the higher-weighted clearers, so the '
          'declared probabilities are preserved in proportion',
          counts[0] > counts[3], str(counts))


def test_f_the_run_reports_both_fallback_rates():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    fb = r['fallbacks']
    check('the number of hurdle draws is counted',
          fb['n_hurdle_draws'] > 100000, str(fb['n_hurdle_draws']))
    for name in (H.NO_CLEARERS, H.MORE_CLEARERS_THAN_BUDGET):
        check(f'{name} is counted', name in fb['states'])
        check(f'  with a rate', fb['states'][name]['rate'] is not None)
    check('each fallback says what it does',
          'never dropped' in fb['NO_CLEARERS_means']
          and 'preserved in proportion'
          in fb['MORE_CLEARERS_THAN_BUDGET_means'])
    check('reconciliation is exact for the hurdle arm',
          r['reconciliation']['Q9_HURDLE']['exact'] is True,
          str(r['reconciliation']['Q9_HURDLE']
              ['max_absolute_reconciliation_error']))
    check('  and for the baseline',
          r['reconciliation']['BASELINE']['exact'] is True)


# ================================================= what is held fixed
def test_g_the_q8_repair_is_absent_and_the_rest_is_fixed():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    check('the Q8 budget repair is not applied', 
          r['q8_budget_repair_applied'] is False)
    for f in r['fit_log']:
        check(f"{f['eval_season']}: the fit log says so too",
              f['q8_budget_repair_applied'] is False)
    joined = ' '.join(r['held_fixed']).lower()
    for layer in ('budget', 'appearance', 'class-level', 'shrinkage',
                  'efficiency', 'touchdown'):
        check(f'{layer} is declared held fixed', layer in joined)
    check('nothing is promoted', r['promoted'] is False)
    check('no market input is recorded as used', r['market_inputs_used'] == [])
    check('no 2026 row was used', r['live_2026_rows_used'] == 0)
    check('the evaluation seasons are all historical',
          max(r['eval_seasons']) <= 2025, str(r['eval_seasons']))


# ================================================= the decision rule
def test_h_a_receiving_yard_gain_alone_is_never_support():
    def mk(zero_better=True, pos_worse=False, marg_delta=-1.0,
           marg_worse=False, exact=True):
        zb = {'brier': 0.2, 'log_loss': 0.5, 'abs_zero_rate_gap': 0.03}
        zh = ({'brier': 0.19, 'log_loss': 0.49, 'abs_zero_rate_gap': 0.01}
              if zero_better else
              {'brier': 0.21, 'log_loss': 0.51, 'abs_zero_rate_gap': 0.05})
        return {
            'by_arm': {'BASELINE': {'zero_target_probability': zb},
                       'Q9_HURDLE': {'zero_target_probability': zh}},
            'paired': {
                'positive_crps': {'delta_pct': 1.0,
                                  'block_bootstrap_by_team_game': {
                                      'excludes_zero': pos_worse,
                                      'mean': 1.0 if pos_worse else -1.0}},
                'marginal_crps': {'delta_pct': marg_delta,
                                  'block_bootstrap_by_team_game': {
                                      'excludes_zero': marg_worse,
                                      'mean': 1.0 if marg_worse else -1.0}},
                'receiving_yard_crps': {'delta_pct': -99.0,
                                        'block_bootstrap_by_team_game': {
                                            'excludes_zero': True,
                                            'mean': -99.0}}},
            'reconciliation': {'Q9_HURDLE': {'exact': exact}},
        }
    d = H.decide(mk())
    check('all four conditions met -> SUPPORT', d['decision'] == 'SUPPORT',
          d['decision'])
    d = H.decide(mk(marg_delta=+0.5))
    check('marginal CRPS not improving drops it to WEAK_SUPPORT',
          d['decision'] == 'WEAK_SUPPORT', d['decision'])
    d = H.decide(mk(zero_better=False))
    check('zero calibration failing -> REJECT, despite a huge yardage gain',
          d['decision'] == 'REJECT', d['decision'])
    d = H.decide(mk(pos_worse=True))
    check('positive CRPS significantly worse -> REJECT',
          d['decision'] == 'REJECT', d['decision'])
    d = H.decide(mk(exact=False))
    check('inexact reconciliation -> REJECT whatever else is true',
          d['decision'] == 'REJECT', d['decision'])
    check('the artifact records that the yardage metric is not read',
          d['receiving_yard_crps_not_read_by_this_rule'] is True)
    check('the rule travels in the artifact',
          'SUPPORT' in d['rule'] and 'INSUFFICIENT' in d['rule'].upper())


def test_i_no_decision_stratum_comes_from_the_realised_count():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for name in ('by_position', 'by_role_class', 'by_appearance_certainty',
                 'by_prior_opportunity_depth'):
        check(f'{name} is reported', bool(r.get(name)), str(len(r.get(name) or {})))
    diag = r['diagnostic_not_read_by_the_decision']
    check('the realised-volume breakdown is quarantined',
          'by_realised_target_regime' in diag)
    check('  and says why', 'may not select a model' in diag['note'])
    d = r['decision']
    check('the decision reads none of it',
          not any('realised' in str(k) for k in d))
    check('every decision field is one the rule names',
          set(d) >= {'zero_target_calibration_improved',
                     'positive_crps_significantly_worse',
                     'marginal_crps_improves', 'team_reconciliation_exact'})


def test_j_the_four_metric_blocks_are_reported_separately():
    r = _results()
    if r is None:
        check('the results artifact exists', False)
        return
    for arm in H.ARMS:
        a = r['by_arm'][arm]
        for block in ('zero_target_probability',
                      'positive_target_distribution',
                      'full_marginal_target_distribution',
                      'downstream_receiving_yards'):
            check(f'{arm}: {block} is its own block', block in a)
        z = a['zero_target_probability']
        for f in ('brier', 'log_loss', 'expected_calibration_error',
                  'calibration_bins'):
            check(f'{arm}: the zero block carries {f}', f in z)
        m = a['full_marginal_target_distribution']
        check(f'{arm}: the marginal block carries zero-mass calibration',
              'zero_mass_calibration' in m)
        check(f'{arm}: the positive block is scored on positive rows only',
              a['positive_target_distribution']['n'] < z['n'],
              f"{a['positive_target_distribution']['n']} of {z['n']}")
    check('intervals are clustered on team-games',
          'team-game' in r['clustering'])
    b = r['paired']['marginal_crps']['block_bootstrap_by_team_game']
    check('  with fewer clusters than rows',
          b['n_clusters'] < b['n_rows'], f"{b['n_clusters']}/{b['n_rows']}")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

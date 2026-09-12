"""Q9B: identifiability, the plain-family test, fallbacks, parity, freeze.

WHAT THESE TESTS PROTECT.

  * THE ORACLE IS A PARAMETER ORACLE. pi* is the player's season-average share,
    never that game's own share -- which would predict a zero-target player's
    zero with certainty and prove nothing.

  * THE DM ARM IS REFUSED FOR A MEASURED REASON. The dispersion threshold was
    fixed in code before the number was read, and the arm list must match the
    verdict rather than the literature.

  * Q9 IS FROZEN. The comparison calls `nfl.research.q9.hurdle.allocate_hurdle`
    rather than reimplementing it, so it cannot drift from the supported
    candidate.

  * THE PLAIN FAMILY IS THE TEST OF THE MECHANISM. MNL_PLUS gets the hurdle's
    own covariates; if it matched, the hurdle would be a reparameterisation.

  * PARITY IS BIT-FOR-BIT, and the TEST_ONLY mark propagating is the
    production guard working, not a defect.

  * THE FREEZE CONSUMES NO FUTURE OUTCOME.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.q9 import hurdle as Q9                          # noqa: E402
from nfl.research.q9b import family as FAM                        # noqa: E402
from nfl.research.q9b import identify as IDN                      # noqa: E402
from nfl.research.q9b import production_parity as PAR             # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _load(name):
    p = IDN.HERE / name
    return json.loads(p.read_text()) if p.exists() else None


# ============================================== the identifiability audit
def test_a_the_zero_mass_is_decomposed_exactly():
    a = _load('Q9B_IDENTIFIABILITY.json')
    if a is None:
        check('the identifiability artifact exists', False)
        return
    o = a['overall']
    check('the three components reconstruct the observation',
          abs((o['multinomial_sampling_zero'] + o['structural_excess'])
              - o['observed_zero_rate']) < 1e-6,
          f"{o['multinomial_sampling_zero']} + {o['structural_excess']} "
          f"vs {o['observed_zero_rate']}")
    check('the production share\'s implied zero is the baseline plus its '
          'mis-estimation',
          abs((o['multinomial_sampling_zero']
               + o['mis_estimated_share_component'])
              - o['implied_zero_production_share']) < 1e-6)
    check('most of the zero mass is ordinary multinomial sampling',
          o['multinomial_sampling_zero'] / o['observed_zero_rate'] > 0.75,
          f"{100 * o['multinomial_sampling_zero'] / o['observed_zero_rate']:.1f}%")
    check('the oracle is a PARAMETER oracle and says so',
          'never that game' in a['oracle_kind'])
    check('the identification rule was fixed before the numbers',
          'fixed before the numbers were read'
          in a['verdict']['predeclared_rule'])


def test_b_the_exact_multinomial_zero_mass_is_what_it_claims():
    """(1-pi)^N, checked against a direct simulation rather than asserted."""
    rng = np.random.default_rng(0)
    pi = np.array([0.4, 0.35, 0.25])
    N = 6
    implied = IDN._implied_zero(pi, np.full(200, N))
    draws = rng.multinomial(N, pi, size=40000)
    emp = (draws == 0).mean(axis=0)
    check('the closed form matches a direct multinomial simulation',
          float(np.abs(implied - emp).max()) < 0.01,
          f'max gap {float(np.abs(implied - emp).max()):.4f}')
    check('a larger budget produces less zero mass',
          float(IDN._implied_zero(pi, np.full(10, 20))[0])
          < float(IDN._implied_zero(pi, np.full(10, 3))[0]))


def test_c_the_dirichlet_arm_is_refused_for_a_measured_reason():
    a = _load('Q9B_IDENTIFIABILITY.json')
    f = _load('Q9B_FAMILY_RESULTS.json')
    if a is None or f is None:
        check('both artifacts exist', False)
        return
    d = a['dispersion_audit']
    check('the dispersion threshold was pre-declared',
          d['predeclared_threshold'] == 1.25, str(d['predeclared_threshold']))
    check('the ratio is measured at the CORRECT share, not the fitted one',
          'CORRECT share' in d['reads'])
    check('the verdict matches the measurement',
          (d['verdict'] == 'OVERDISPERSED_DM_JUSTIFIED')
          == (d['variance_ratio_median'] >= d['predeclared_threshold']),
          f"{d['variance_ratio_median']} -> {d['verdict']}")
    check('the arm list matches the verdict, not the literature',
          f['dirichlet_multinomial_arm']['included']
          is (d['verdict'] == 'OVERDISPERSED_DM_JUSTIFIED'))
    check('  and the reason quotes the measurement',
          '1.193' in f['dirichlet_multinomial_arm']['reason']
          or '1.25' in f['dirichlet_multinomial_arm']['reason'])
    check('only the three registered arms ran',
          set(f['arms']) == {'BASELINE', 'MNL_PLUS', 'Q9_HURDLE'},
          str(f['arms']))


# =============================================== the plain-family test
def test_d_q9_is_called_not_reimplemented():
    src = FAM.run.__doc__ or ''
    import inspect
    body = inspect.getsource(FAM.run)
    check('the comparison calls the frozen allocator',
          'Q9.allocate_hurdle' in body)
    check('  and does not define its own',
          'def allocate' not in inspect.getsource(FAM))
    f = _load('Q9B_FAMILY_RESULTS.json')
    if f:
        check('the artifact states the freeze',
              'imported from nfl.research.q9.hurdle' in f['q9_is_frozen'])


def test_e_the_plain_family_gets_the_hurdles_own_covariates():
    r = {'role_class': 'starter', 'pos': 'WR', 'rank': 1}
    base = Q9.featurise(r, 0.0)
    mnl = FAM.mnl_features(r, 0.2, 0.0)
    check('MNL_PLUS carries every stage-1 feature',
          mnl[:len(base)] == base)
    check('  plus the log production share, and nothing else',
          len(mnl) == len(base) + 1, f'{len(mnl)} vs {len(base) + 1}')
    check('a bigger production share raises that feature',
          FAM.mnl_features(r, 0.4, 0.0)[-1]
          > FAM.mnl_features(r, 0.1, 0.0)[-1])


def test_f_the_falsifiable_check_is_reported_either_way():
    f = _load('Q9B_FAMILY_RESULTS.json')
    if f is None:
        check('the family artifact exists', False)
        return
    fc = f['falsifiable_check']
    check('the baseline shortfall is stated', 'baseline_zero_shortfall' in fc)
    for arm in ('MNL_PLUS', 'Q9_HURDLE'):
        check(f'{arm} reports the fraction it closed',
              fc['by_arm'][arm]['fraction_of_shortfall_closed'] is not None,
              str(fc['by_arm'][arm]['fraction_of_shortfall_closed']))
    mnl = fc['by_arm']['MNL_PLUS']['fraction_of_shortfall_closed']
    hur = fc['by_arm']['Q9_HURDLE']['fraction_of_shortfall_closed']
    check('the hurdle closes more of the shortfall than the plain family',
          hur > mnl, f'{hur} vs {mnl}')
    check('  and the plain family is measurably not a substitute',
          fc['by_arm']['MNL_PLUS']['abs_gap']
          > fc['by_arm']['Q9_HURDLE']['abs_gap'],
          f"{fc['by_arm']['MNL_PLUS']['abs_gap']} vs "
          f"{fc['by_arm']['Q9_HURDLE']['abs_gap']}")
    check('every arm reconciles exactly',
          all(v['max_absolute_error'] == 0.0
              for v in f['reconciliation'].values()),
          str(f['reconciliation']))


# ===================================================== the fallback audit
def test_g_the_fallback_is_located_and_its_effect_measured():
    fb = _load('Q9_FALLBACK_AUDIT.json')
    if fb is None:
        check('the fallback audit exists', False)
        return
    m = fb.get('more_clearers_than_budget')
    check('the more-clearers state is characterised', bool(m))
    if not m:
        return
    check('it is concentrated in very low team target budgets',
          m['concentrated_in_low_budgets'] is True,
          f"mean drawn budget {m['mean_team_budget_drawn']}")
    check('  and every event sits in the lowest budget band',
          set(m['by_budget_band']) == {'<25'}, str(m['by_budget_band']))
    check('  with more clearers than targets by construction',
          m['mean_n_clearers'] > m['mean_team_budget_drawn'])
    sd = fb.get('selection_distortion') or {}
    check('the selection rates are measured against the declared probability',
          bool(sd.get('by_declared_hurdle_probability')))
    check('  and the note names what would count as distortion',
          'weighting is by the base share' in sd.get('note', ''))
    c = fb.get('contribution') or {}
    check('the effect on CRPS is measured, not assumed',
          'marginal_crps_affected' in c and 'marginal_crps_elsewhere' in c)
    check('the no-clearers state is reported whatever its rate',
          Q9.NO_CLEARERS in fb['states'])


def test_h_the_pit_deterioration_is_located():
    f = _load('Q9B_FAMILY_RESULTS.json')
    if f is None:
        check('the family artifact exists', False)
        return
    p = f['pit_diagnosis']
    check('PIT is declared diagnosed and not optimised',
          'read by no decision' in p['note'])
    band = p['by_actual_target_band']
    worse = [k for k, v in band.items()
             if isinstance(v, dict) and v.get('worsens')]
    better = [k for k, v in band.items()
              if isinstance(v, dict) and v.get('worsens') is False]
    check('some bands worsen and some improve, so it is located not pooled',
          worse and better, f'worse {worse} better {better}')
    depth = p['by_prior_depth']
    check('the cold-start cell is measured',
          '0' in depth and 'chi2_per_row_delta' in depth['0'])
    check('  and it is the worst of the depth cells',
          depth['0']['chi2_per_row_delta'] == max(
              v['chi2_per_row_delta'] for v in depth.values()
              if isinstance(v, dict) and 'chi2_per_row_delta' in v),
          str(depth['0']['chi2_per_row_delta']))


# ================================================== parity and the freeze
def test_i_parity_is_bit_for_bit_and_the_guard_fires():
    p = _load('Q9_PRODUCTION_PARITY.json')
    if p is None:
        check('the parity artifact exists', False)
        return
    check('every invariant is checked',
          set(p['invariants']) == set(PAR.INVARIANTS),
          str(sorted(p['invariants'])))
    for k, v in p['invariants'].items():
        check(f'{k} holds', v is True)
    check('the status matches the invariants',
          (p['status'] == 'PARITY_HOLDS') == all(p['invariants'].values()))
    check('no mismatch was recorded', p['mismatches'] == [],
          str(p['mismatches'][:2]))
    check('the real production interfaces were exercised',
          'nfl.production.nonqb.layers.appearance'
          in p['interfaces_exercised'])
    check('the TEST_ONLY mark propagated, which is the guard working',
          all(g['upstream_test_only'] for g in p['games'])
          and 'produces no artifact' in p['test_only_note'])
    check('more than one game was tested', p['n_games_tested'] > 1,
          str(p['n_games_tested']))


def test_j_the_freeze_records_identity_and_consumes_no_future():
    fz = _load('Q9_PROSPECTIVE_FREEZE.json')
    if fz is None:
        check('the freeze artifact exists', False)
        return
    check('no future outcome was consumed',
          fz['no_future_outcome_consumed'] is True)
    check('  and the artifact says why that matters',
          'post-hoc description' in fz['consumption_note'])
    ci = fz['candidate_identity']
    check('the mechanism spec version is recorded',
          ci['mechanism_spec_version'] == Q9.SPEC_VERSION)
    check('every executing module is hashed',
          len(ci['module_source_sha16']) >= 4
          and all(len(v) == 16 for v in ci['module_source_sha16'].values()))
    fs = fz['feature_schema']
    check('the feature schema is recorded in order',
          fs['stage_1_features_in_order'] == list(Q9.FEATURE_NAMES))
    check('  with its own hash', len(fs['schema_sha16']) == 16)
    ph = fz['parameter_hashes']
    for k in ('hurdle_coefficients_sha16', 'class_prior_sha16',
              'budget_residual_pool_sha16'):
        check(f'{k} is recorded', len(ph[k]) == 16)
    check('the training seasons are all historical',
          max(ph['training_seasons']) < fz['frozen_at_season'],
          str(ph['training_seasons']))
    check('the Q8 repair is recorded as absent',
          ph['q8_budget_repair_applied'] is False)
    check('the production interface version is recorded',
          len(fz['production_interface']['version_sha16']) == 16)
    check('the fallback counters are frozen with it',
          Q9.MORE_CLEARERS_THAN_BUDGET in fz['fallback_counters_at_freeze'])
    check('the decision metrics are frozen with it',
          'marginal_crps_delta_pct' in fz['decision_metrics_at_freeze'])
    check('the plan says what would falsify it',
          'falsify' in ' '.join(fz['prospective_plan']).lower()
          or fz['prospective_plan'].get('what_would_falsify'))
    check('a refit is declared a different candidate',
          'different candidate' in fz['prospective_plan']['refit_policy'])
    check('nothing is promoted', fz['promoted'] is False)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

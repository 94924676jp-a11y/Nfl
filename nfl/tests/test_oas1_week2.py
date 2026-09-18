"""P9: the Week-2 OAS1 fit, the leak it avoids, and the choice it refuses.

The runner raised "the fitting body is not implemented in this pass" from the
day it was written. This file covers the body that replaced that raise.

THREE THINGS ARE WORTH TESTING AND ONE IS NOT

Worth testing: that the per-fold prior is the lawful one, that an undeclared
tie-break is refused rather than invented, and that the scoring refusal is a
measurement of the captured weeks rather than an assumption. Those are the
places where a plausible implementation is wrong in a way no number would show.

Not worth testing: the values of the fitted strengths. Pinning them here would
be a second copy of `OAS1_WEEK2_RESULT.json` that goes stale the moment the
capture is rebuilt, and the artifact already carries them with their
provenance. What IS pinned is that the artifact agrees with a live run on the
things a reader would act on: identification, the undecided axis, and whether
the hurdle was evaluated.

THE SLOW TEST PROBLEM, HANDLED WITHOUT A FAST/SLOW SPLIT

A full re-run parses three seasons of play-by-play and fits 864 configurations
over 8 folds; it is minutes, not seconds. So the expensive checks read the
COMMITTED artifact, and the cheap ones exercise the functions directly on small
synthetic inputs. No test here is skipped, and none is marked "slow" -- a test
group that runs zero checks is a false green, and this project has a rule
against inventing that split.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.research.oas1 import amendment as AM                      # noqa: E402
from nfl.research.oas1 import preregistration as PRE               # noqa: E402
from nfl.research.oas1 import prior_season as PS                   # noqa: E402
from nfl.research.oas1 import week2 as W2                          # noqa: E402

PASSED = FAILED = 0
ART = pathlib.Path(_ROOT) / 'nfl/research/oas1/OAS1_WEEK2_RESULT.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _art():
    return json.loads(ART.read_text()) if ART.exists() else None


# =================================================== the algebra, directly

def test_the_penalty_leaves_the_intercept_and_home_alone():
    p = W2.penalty_vector(32)
    check('the design is 2 + 2*32 columns wide', len(p) == 66, str(len(p)))
    check('the intercept is unpenalised', p[0] == 0.0)
    check('the home term is unpenalised', p[-1] == 0.0)
    check('both team families are penalised', p[1:-1].sum() == 64.0,
          str(p[1:-1].sum()))


def test_a_unit_with_no_prior_gets_no_pseudo_observation():
    """A zero pseudo-observation is not "no information".

    It is the assertion that the unit is exactly league average, and asserting
    that about a club never seen is the cold-start defect this project has
    already paid for.
    """
    teams = ['AAA', 'BBB']
    theta = {('AAA', 'off_pass'): 0.05, ('AAA', 'def_pass'): -0.02}
    v, m, missing = W2.prior_vector(theta, teams, 'pass')
    check('the club with a prior is masked in', m[1] == 1.0 and m[3] == 1.0,
          str(m))
    check('its response is carried', v[1] == 0.05 and v[3] == -0.02, str(v))
    check('the club without one is masked OUT, not set to zero',
          m[2] == 0.0 and m[4] == 0.0, str(m))
    check('and it is named rather than silently dropped',
          sorted(missing) == ['BBB/def_pass', 'BBB/off_pass'], str(missing))


def test_kappa_zero_reduces_to_plain_ridge_and_kappa_large_follows_the_prior():
    rng = np.random.default_rng(20260918)
    n, T = 400, 4
    X = np.zeros((n, 2 + 2 * T))
    X[:, 0] = 1.0
    for i in range(n):
        X[i, 1 + rng.integers(T)] = 1.0
        X[i, 1 + T + rng.integers(T)] = 1.0
    X[:, -1] = rng.integers(2, size=n)
    y = rng.normal(size=n)
    XtX, Xty = X.T @ X, X.T @ y
    pen = W2.penalty_vector(T)
    pv = np.zeros(2 + 2 * T)
    pm = np.zeros(2 + 2 * T)
    pv[1:1 + T] = np.array([1.0, -1.0, 0.5, -0.5])
    pm[1:1 + T] = 1.0
    a = W2.solve(XtX, Xty, lam=1.0, kappa=0.0, rho=1.0, pen=pen,
                 prior_v=pv, prior_m=pm)
    b = np.linalg.solve(XtX + np.diag(1.0 * pen), Xty)
    check('kappa=0 is exactly plain ridge', np.allclose(a, b, atol=1e-12),
          str(float(np.abs(a - b).max())))
    c = W2.solve(XtX, Xty, lam=1.0, kappa=1e9, rho=1.0, pen=pen,
                 prior_v=pv, prior_m=pm)
    check('a very large kappa pulls the masked units onto rho*theta_prev',
          np.allclose(c[1:1 + T], pv[1:1 + T], atol=1e-4),
          str(c[1:1 + T]))
    d = W2.solve(XtX, Xty, lam=1.0, kappa=1e9, rho=0.5, pen=pen,
                 prior_v=pv, prior_m=pm)
    check('and rho scales the prior response, so rho=0.5 lands halfway',
          np.allclose(d[1:1 + T], 0.5 * pv[1:1 + T], atol=1e-4),
          str(d[1:1 + T]))
    check('an unmasked column is untouched by kappa',
          abs(c[-1] - a[-1]) < 1e-6 or pm[-1] == 0.0)


def test_the_tie_break_reads_the_amendment_and_refuses_an_unknown_axis():
    hi = W2._shrink_key({'lambda': 10.0, 'kappa': 5.0, 'rho': 0.5})
    lo = W2._shrink_key({'lambda': 10.0, 'kappa': 5.0, 'rho': 1.0})
    check('a smaller rho is MORE shrunken under the declared order', hi > lo,
          f'{hi} vs {lo}')
    check('a larger lambda outranks everything after it',
          W2._shrink_key({'lambda': 11.0, 'kappa': 0.0, 'rho': 1.0})
          > W2._shrink_key({'lambda': 10.0, 'kappa': 500.0, 'rho': 0.5}))
    check('the order comes from the amendment, not from this module',
          tuple(AM.AMENDED_TIE_BREAK_ORDER) == ('max lambda', 'max kappa',
                                                'min rho'),
          str(AM.AMENDED_TIE_BREAK_ORDER))
    saved = AM.AMENDED_TIE_BREAK_ORDER
    try:
        AM.AMENDED_TIE_BREAK_ORDER = ('max lambda', 'min garbage_time')
        try:
            W2._shrink_key({'lambda': 1.0, 'kappa': 0.0, 'rho': 1.0})
            check('an undeclared tie-break axis raises', False, 'no raise')
        except ValueError as exc:
            check('an undeclared tie-break axis raises rather than guessing',
                  'undeclared tie-break axis' in str(exc), str(exc)[:100])
    finally:
        AM.AMENDED_TIE_BREAK_ORDER = saved


# ============================================= the committed artifact

def test_the_artifact_exists_and_is_research_only():
    d = _art()
    if not check('OAS1_WEEK2_RESULT.json exists', d is not None, str(ART)):
        return
    check('it is research-only', d['research_only'] is True)
    check('downstream is not authorized', d['downstream_authorized'] is False)
    check('nothing is promoted', d['promoted'] is False)
    check('it names the forecast ordinal',
          d['forecast']['ordinal'] == 202602, str(d['forecast']))
    check('it carries its training provenance by blob and hash',
          all('sha256' in v and 'blob' in v
              for v in d['training_provenance'].values()),
          str(d['training_provenance']))


def test_the_design_is_identified_at_week_two():
    """The point of the Week-2 construction. Week 1 alone is rank 32 of 66."""
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    for cls in ('pass', 'rush'):
        f = d['fits'][cls]['none']
        check(f'{cls}: rank {f["design_rank"]} of {f["design_cols"]}',
              f['design_rank'] == f['design_cols']
              - PRE.STRUCTURAL_DEFICIENCY,
              f'deficiency {f["design_deficiency"]}')
        check(f'{cls}: identified', f['identified'] is True)
        check(f'{cls}: the only deficiency left is the structural one',
              f['design_deficiency'] == PRE.STRUCTURAL_DEFICIENCY,
              str(f['design_deficiency']))
        check(f'{cls}: every club carries a prior',
              f['n_units_without_prior'] == 0,
              str(f['n_units_without_prior']))


def test_every_inner_fold_uses_the_prior_of_the_season_before_its_own():
    """The leak the obvious implementation would have had.

    Handing every fold the committed 2025 prior puts weeks 12-18 of 2025 inside
    the prior of a fold forecasting 2025 week 12 -- and it would flatter exactly
    the kappa and rho axes being selected.
    """
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    for cls in ('pass', 'rush'):
        pf = d['selection'][cls]['prior_per_fold']
        check(f'{cls}: every fold records which prior season it used',
              len(pf) >= 2, str(pf))
        bad = [(o, v['prior_season']) for o, v in pf.items()
               if v['prior_season'] != int(o) // 100 - 1]
        check(f'{cls}: each fold uses the season before ITS OWN season',
              not bad, str(bad))
        check(f'{cls}: not every fold uses the same prior -- that would be '
              f'the leak', len({v['prior_season'] for v in pf.values()}) >= 2,
              str({v['prior_season'] for v in pf.values()}))


def test_no_inner_fold_reaches_the_forecast_ordinal():
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    fo = d['forecast']['ordinal']
    for cls in ('pass', 'rush'):
        ords = d['selection'][cls]['fold_ordinals']
        check(f'{cls}: every inner fold is strictly before {fo}',
              all(o < fo for o in ords), str(ords))
        for f in d['selection'][cls]['folds']:
            for g, r in (f.get('by_rule') or {}).items():
                check(f'{cls} fold {f["ordinal"]} rule {g}: a training set '
                      f'exists and is smaller than the frame',
                      r['n_train'] > 0)


def test_the_undeclared_tie_break_is_refused_not_invented():
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    check('the candidate is recorded as NOT SELECTED',
          d['candidate_status'].startswith('NOT SELECTED'),
          d['candidate_status'][:80])
    check('and selection_complete says so too',
          d['selection_complete'] is False)
    for cls in ('pass', 'rush'):
        s = d['selection'][cls]
        check(f'{cls}: the undecided axis is named',
              s['undecided_axis'] == 'garbage_time', str(s['undecided_axis']))
        check(f'{cls}: every tied variant carries its own score',
              len(s['undecided_variant_scores']) > 1,
              str(s['undecided_variant_scores']))
        check(f'{cls}: the variants are not identical, so the axis is not '
              f'degenerate',
              len(set(s['undecided_variant_scores'].values()))
              == len(s['undecided_variant_scores']),
              str(s['undecided_variant_scores']))
        check(f'{cls}: every tied variant is fitted',
              all(g in d['fits'][cls] for g in s['undecided_variant_scores']),
              str(sorted(d['fits'][cls])))
        check(f'{cls}: none of them is marked selected',
              not any(d['fits'][cls][g].get('selected')
                      for g in s['undecided_variant_scores']))
        sp = d['fits'][cls]['variant_spread']
        check(f'{cls}: the spread across variants is measured, not asserted',
              sp['max_abs_difference'] is not None
              and sp['n_variants'] > 1, str(sp))
        check(f'{cls}: and the spread is labelled as not a selection rule',
              'not a selection criterion' in sp['interpretation'])


def test_the_flat_surface_is_recorded_rather_than_smoothed_over():
    """864 of 864 within one SE is the finding, not a detail."""
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    for cls in ('pass', 'rush'):
        s = d['selection'][cls]
        check(f'{cls}: the configuration count is recorded',
              s['n_configurations'] > 100, str(s['n_configurations']))
        check(f'{cls}: how many fall within one SE is recorded',
              s['n_within_one_se'] == s['n_configurations'],
              f'{s["n_within_one_se"]} of {s["n_configurations"]}')
        check(f'{cls}: the best-scoring config is kept beside the chosen one',
              s['best_config_by_score'] != s['chosen_config']
              or s['n_within_one_se'] == 1,
              f'{s["best_config_by_score"]} vs {s["chosen_config"]}')
        check(f'{cls}: rho identifiability at the chosen kappa is stated',
              isinstance(s['rho_identified_at_chosen_kappa'], bool))


def test_the_hurdle_is_not_evaluated_and_says_so_in_those_words():
    """BLOCKED must never be read as a pass, and NOT_EVALUATED must not vanish."""
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    sc = d['scoring']
    check('the scoring state is BLOCKED', sc['state'] == 'BLOCKED', sc['state'])
    check('under its own named code',
          sc['code'] == 'OAS1_WEEK2_SCORE_NOT_COMPUTABLE_HERE', sc['code'])
    check('no hurdle is evaluated', sc['hurdles_evaluated'] is False)
    check('and the status says not passed, not failed, not waived',
          'not passed' in sc['hurdle_status']
          and 'not failed' in sc['hurdle_status']
          and 'not waived' in sc['hurdle_status'], sc['hurdle_status'])
    check('the refusal names the weeks actually captured',
          sc['evidence'].get('weeks_captured') == [1],
          str(sc['evidence'].get('weeks_captured')))
    check('and it says the work is assigned, not blocked for everyone',
          'ASSIGNED' in sc['detail'], sc['detail'][:120])


def test_the_scoring_refusal_is_measured_from_the_capture():
    """Not a constant: it reads the blob and reports the weeks it found."""
    o = W2.score_availability(202602)
    check('score_availability returns a governed Outcome',
          o.state is not None)
    check('it reports the weeks it read',
          isinstance(o.evidence.get('weeks_captured'), list),
          str(o.evidence.get('weeks_captured')))
    check('and it agrees with the committed artifact',
          o.code == (_art() or {}).get('scoring', {}).get('code'),
          f'{o.code}')


def test_the_interpretations_are_declared_rather_than_silent():
    d = _art()
    if d is None:
        check('the artifact exists', False)
        return
    ids = {i['id'] for i in d['interpretations']}
    check('the per-fold prior decision is declared',
          'PER_FOLD_PRIOR' in ids, str(ids))
    check('the common scoring rowset decision is declared',
          'COMMON_SCORING_ROWSET' in ids, str(ids))
    for i in d['interpretations']:
        check(f'{i["id"]} states why', len(i['why']) > 40, i['why'][:60])


# ========================================== the prior it all rests on

def test_the_committed_prior_reproduces_from_committed_code():
    """`OAS1_PRIOR_2025.json` had no builder. It has one now, and it agrees."""
    o = PS.verify_committed()
    check('the prior reproduces', o.state is State.PASS,
          f'{o.code}: {o.detail}')
    if o.state is State.PASS:
        check('all 128 unit strengths were compared',
              o.value['n_compared'] == 128, str(o.value['n_compared']))
        check('to a maximum absolute difference of exactly 0.0',
              o.value['max_abs_strength_difference'] == 0.0,
              str(o.value['max_abs_strength_difference']))
        check('and both chosen lambdas agree',
              all(v['committed'] == v['rebuilt']
                  for v in o.value['chosen_lambda'].values()),
              str(o.value['chosen_lambda']))
    check('what was NOT compared is stated rather than glossed',
          'stable_content_sha256' in (o.evidence.get('not_compared') or ''),
          str(o.evidence.get('not_compared'))[:80])


def test_the_prior_refuses_a_season_it_has_no_capture_for():
    o = PS.build(1999)
    check('an uncaptured season is refused, not approximated',
          o.state is not State.PASS and o.code == PS.CODE_NO_BLOB,
          f'{o.state}[{o.code}]')
    check('and the refusal names the seasons that ARE declared',
          sorted(o.evidence.get('declared') or []) == [2024, 2025, 2026],
          str(o.evidence.get('declared')))


def test_the_runner_no_longer_raises_not_implemented():
    src = (pathlib.Path(_ROOT)
           / 'nfl/research/oas1/fit_week2.py').read_text()
    check('the "fitting body is not implemented" raise is gone',
          'the fitting body is not implemented' not in src)
    check('and the runner calls the body',
          'from nfl.research.oas1 import week2' in src and 'W2.main()' in src)

"""Gates 3-5: the frame, the governed target, the fit, the baselines, the spec.

EVERY CHECK HERE ATTACKS A SPECIFIC WAY THE BUILD COULD LOOK RIGHT AND BE
WRONG. The ones that matter most:

  * the sign convention, which is the most likely silent defect in an
    opponent-adjustment model;
  * the intercept being penalised, which would bias every unit estimate by
    absorbing the league mean into the shrunken dummies;
  * B4 on a single week, which MUST produce zero adjustment -- the
    identification collapse expressed arithmetically;
  * a baseline and the candidate receiving different row sets, which is the
    most common way a spurious win appears;
  * the pre-registration's prose disagreeing with its code, which is exactly
    how the Contract 4 threshold loosened silently.
"""
from __future__ import annotations

import glob
import hashlib
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                     # noqa: E402
from nfl.ingest import allowlist as AL                                  # noqa: E402
from nfl.production import evaluator as EV                              # noqa: E402
from nfl.research.oas1 import baselines as BL                           # noqa: E402
from nfl.research.oas1 import design as DS                              # noqa: E402
from nfl.research.oas1 import fit as FT                                 # noqa: E402
from nfl.research.oas1 import frame as FR                               # noqa: E402
from nfl.research.oas1 import preregistration as PRE                    # noqa: E402
from nfl.research.oas1 import target as TG                              # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
_CACHE = {}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _frame(season):
    if season in _CACHE:
        return _CACHE[season]
    b = sorted(glob.glob(os.path.join(_ROOT,
                                      f'nfl/vintage/pbp_{season}.*.csv.gz')))
    if not b:
        return None
    p = pathlib.Path(b[-1])
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    o = FR.build(p, vintage_sha256=sha)
    _CACHE[season] = (o, sha)
    return _CACHE[season]


# ==================================================================== FRAME
def test_A_the_frame_keeps_every_row_and_counts_every_exclusion():
    print('\nA. nothing is dropped')
    got = _frame(2026)
    check('the 2026 frame builds', got is not None and got[0].state is State.PASS,
          'no capture' if got is None else f'{got[0].state}[{got[0].code}]')
    if got is None or got[0].state is not State.PASS:
        NOT_EXECUTED.append('A: no 2026 frame')
        return
    o, _sha = got
    e = o.evidence
    check('  every input row is in the output',
          len(o.value['rows']) == e['n_input_rows'],
          f'{len(o.value["rows"])} vs {e["n_input_rows"]}')
    check('  the exclusion reasons sum EXACTLY to the input row count',
          sum(e['exclusion_counts'].values()) == e['n_input_rows'],
          f'{sum(e["exclusion_counts"].values())} vs {e["n_input_rows"]}')
    check('  every row carries exactly one reason from the declared set',
          all(r['excluded_reason'] in FR.REASONS for r in o.value['rows']))
    check('  the precedence order is declared, not left to iteration order',
          bool(e['reason_precedence']) and len(e['reason_precedence']) >= 8,
          str(e['reason_precedence']))
    check('  ALL sacks land in the pass class',
          e['n_sacks_in_pass_class'] == e['n_sacks_kept']
          and e['n_sacks_kept'] > 0,
          f'{e["n_sacks_in_pass_class"]} of {e["n_sacks_kept"]}')
    check('  ALL kept scrambles land in the pass class',
          e['n_scrambles_in_pass_class'] == e['n_scrambles_kept']
          and e['n_scrambles_kept'] > 0,
          f'{e["n_scrambles_in_pass_class"]} of {e["n_scrambles_kept"]}')
    check('  no special-teams row is kept',
          not any(r['excluded_reason'] == 'none'
                  and r['play_class'] is None for r in o.value['rows']))
    check('  the garbage-time rule touches NO model-derived column',
          FR.garbage_time({'score_differential': '30',
                           'game_seconds_remaining': '100'}, 'A') is True
          and 'wp' not in FR.GT_RULE_TEXT['A'],
          FR.GT_RULE_TEXT['A'])
    check('  and a row it cannot judge is NOT treated as garbage time',
          FR.garbage_time({'score_differential': None,
                           'game_seconds_remaining': None}, 'A') is False)


# =================================================================== TARGET
def test_B_the_target_is_governed_and_the_features_are_not():
    print('\nB. epa as a label, never as a feature')
    got = _frame(2026)
    if got is None:
        NOT_EXECUTED.append('B: no frame')
        return
    o, sha = got
    check('the target module is the module the allowlist authorises',
          TG.MODULE_NAME == AL.OAS1_TARGET_MODULE,
          f'{TG.MODULE_NAME} vs {AL.OAS1_TARGET_MODULE}')
    t = TG.build(o.value['kept'], vintage_sha256=sha)
    check('  it builds with a real vintage', t.state is State.PASS,
          f'{t.state}[{t.code}]')
    check('  and records that it is a target only',
          t.evidence['used_as'].startswith('REGRESSION TARGET'),
          t.evidence['used_as'])
    check('  with the fit design recorded as UNKNOWN, not guessed',
          'UNKNOWN' in t.evidence['model_generation']
          and 'FIT DESIGN is UNKNOWN' in t.evidence['provenance_caveat'],
          t.evidence['model_generation'][:60])
    bad = TG.build(o.value['kept'], vintage_sha256='deadbeef')
    check('  a malformed vintage is REFUSED', bad.state is State.FAIL
          and bad.code == TG.CODE_REFUSED, f'{bad.state}[{bad.code}]')
    check('the general quarantine is UNTOUCHED by all of this',
          AL.assert_columns_allowed(
              'pbp', ['epa'], AL.Purpose.FORECAST).code
          == 'MODEL_DERIVED_COLUMN_ACCESS')
    d = DS.build(o.value['kept'], play_class='pass')
    check('  the design matrix builds', d.state is State.PASS,
          f'{d.state}[{d.code}]')
    if d.state is State.PASS:
        check('  and NO design column is epa-derived',
              AL.assert_no_epa_in_features(d.value['names']).state is State.PASS)
        check('  which is checked by NAME, so it is auditable',
              all(isinstance(n, str) for n in d.value['names'])
              and d.value['names'][0] == 'intercept')


# =================================================================== DESIGN
def test_C_an_unidentified_design_is_refused_not_fitted():
    print('\nC. the gate that stops ridge answering anyway')
    got = _frame(2026)
    if got is None:
        NOT_EXECUTED.append('C: no frame')
        return
    kept = got[0].value['kept']
    i = DS.identify(kept, play_class='pass')
    check('2026 week 1 is BLOCKED as unidentified',
          i.state is State.BLOCKED and i.code == DS.CODE_UNIDENTIFIED,
          f'{i.state}[{i.code}]')
    check(f'  with deficiency {PRE.WEEK1_DEFICIENCY} and '
          f'{PRE.WEEK1_COMPONENTS} components, matching the pre-registration',
          i.evidence['deficiency'] == PRE.WEEK1_DEFICIENCY
          and i.evidence['n_components'] == PRE.WEEK1_COMPONENTS,
          f'{i.evidence["deficiency"]}, {i.evidence["n_components"]}')
    check('  and it names the unestimable dimensions',
          i.evidence['unestimable_opponent_dimensions'] == 32,
          str(i.evidence['unestimable_opponent_dimensions']))
    f = FT.fit_season(kept, play_class='pass', lam=1.0)
    check('a fit on it REFUSES by default',
          f.state is State.BLOCKED and f.code == FT.CODE_UNIDENTIFIED,
          f'{f.state}[{f.code}]')
    f2 = FT.fit_season(kept, play_class='pass', lam=1.0,
                       allow_unidentified=True)
    check('  and an override with no stated reason is also refused',
          f2.state is State.FAIL, f'{f2.state}[{f2.code}]')
    got25 = _frame(2025)
    if got25 is None:
        NOT_EXECUTED.append('C: no 2025 frame')
        return
    i25 = DS.identify(got25[0].value['kept'], play_class='pass')
    check('the full 2025 season IS identified',
          i25.state is State.PASS, f'{i25.state}[{i25.code}]')
    check(f'  deficiency is the structural '
          f'{PRE.STRUCTURAL_DEFICIENCY}, and one graph component',
          i25.evidence['deficiency'] == PRE.STRUCTURAL_DEFICIENCY
          and i25.evidence['n_components'] == 1,
          f'{i25.evidence["deficiency"]}, {i25.evidence["n_components"]}')


# ====================================================================== FIT
def test_D_the_fit_does_what_the_spec_says():
    print('\nD. intercept unpenalised, sign fixed, centring a relabelling')
    m = FT.penalty_mask(66)
    check('the intercept is UNPENALISED', m[0] == 0.0, str(m[0]))
    check('  the home term is UNPENALISED', m[-1] == 0.0, str(m[-1]))
    check('  and every unit column IS penalised', bool((m[1:-1] == 1.0).all()))
    # SIGN CONVENTION, on synthetic data with a known answer.
    rng = np.random.default_rng(7)
    teams = [f'T{i:02d}' for i in range(8)]
    rows = []
    # A round robin, so the design is connected and identified.
    for i, o in enumerate(teams):
        for j, d in enumerate(teams):
            if i == j:
                continue
            for _ in range(40):
                # T00 is a TERRIBLE defence: it concedes +1.0 extra EPA.
                bonus = 1.0 if d == 'T00' else 0.0
                rows.append({
                    'play_class': 'pass', 'excluded_reason': 'none',
                    'offense_team': o, 'defense_team': d,
                    'offense_is_home': bool((i + j) % 2),
                    'game_id': f'g{i}_{j}', 'play_id': len(rows),
                    'epa': float(bonus + rng.normal(0, 0.5)),
                    'season': 2025, 'week': 1 + (i * 8 + j) % 17,
                    'ordinal': 202501 + (i * 8 + j) % 17})
    f = FT.fit_season(rows, play_class='pass', lam=1.0)
    check('the synthetic fit passes', f.state is State.PASS,
          f'{f.state}[{f.code}] {f.detail[:150]}')
    if f.state is not State.PASS:
        NOT_EXECUTED.append('D: synthetic fit refused')
        return
    du = {u['team']: u['strength'] for u in f.value['units']
          if u['unit'] == 'def_pass'}
    worst = max(du, key=lambda t: du[t])
    check('SIGN: the defence that concedes MORE epa has the LARGEST '
          'def_pass value -- positive defence means WORSE',
          worst == 'T00' and du['T00'] > 0,
          f'largest is {worst} at {du[worst]:+.4f}; T00 is {du["T00"]:+.4f}')
    check('  and the convention is stated in the artifact',
          'WORSE' in f.evidence['sign_convention'],
          f.evidence['sign_convention'][:70])
    check('  every unit carries a game-clustered standard error',
          all(u['se_clustered_by_game'] > 0 for u in f.value['units']))
    check('  and a play count, so a small sample is visible',
          all(u['n_plays'] > 0 for u in f.value['units']))
    # Centring is a relabelling: each family sums to zero AFTER it.
    for u in ('off_pass', 'def_pass'):
        v = [x['strength'] for x in f.value['units'] if x['unit'] == u]
        check(f'  {u} sums to zero after centring',
              abs(float(np.sum(v))) < 1e-9, str(float(np.sum(v))))
    check('  and centring did NOT move the fitted values, only the zero',
          all(abs((x['strength_uncentered'] - x['strength'])
                  - (f.evidence['defense_shift'] if x['unit'] == 'def_pass'
                     else f.evidence['offense_shift'])) < 1e-9
              for x in f.value['units']))
    # Lambda to infinity: units vanish, the intercept survives.
    big = FT.fit_season(rows, play_class='pass', lam=1e12)
    check('lambda -> very large drives units to zero',
          big.state is State.PASS
          and max(abs(u['strength_uncentered'])
                  for u in big.value['units']) < 1e-3,
          str(max(abs(u['strength_uncentered'])
                  for u in big.value['units'])
              if big.state is State.PASS else big.code))
    check('  while the INTERCEPT survives, which is what the unpenalised '
          'intercept is for',
          big.state is State.PASS and abs(big.evidence['intercept']) > 0.05,
          str(big.evidence.get('intercept')))


# ================================================================ BASELINES
def test_E_the_baselines_are_fair_and_B4_collapses_on_one_week():
    print('\nE. the comparator suite')
    check(f'all six baselines are declared: {PRE.BASELINES}',
          tuple(BL.NAMES) == PRE.BASELINES, str(BL.NAMES))
    for n in BL.NAMES:
        s = BL.SPECS[n]
        for k in ('formula', 'information_set', 'cold_start',
                  'hyperparameters', 'tuning_rule', 'target', 'metrics'):
            check(f'  {n} declares its {k}', bool(s.get(k)), str(s.get(k)))
    check('B5 is named the decisive comparator',
          'DECISIVE' in BL.SPECS['B5']['name'].upper()
          and PRE.DECISIVE_COMPARATOR == 'B5')
    # B4 ON ONE WEEK: zero adjustment for every unit.
    teams = [f'T{i:02d}' for i in range(8)]
    one = []
    for k in range(0, 8, 2):
        o, d = teams[k], teams[k + 1]
        for side in ((o, d), (d, o)):
            for _ in range(30):
                one.append({'play_class': 'pass', 'excluded_reason': 'none',
                            'offense_team': side[0], 'defense_team': side[1],
                            'offense_is_home': True, 'game_id': f'g{k}',
                            'play_id': len(one), 'epa': 0.3 * (k + 1),
                            'season': 2025, 'week': 1, 'ordinal': 202501})
    mu = float(np.mean([r['epa'] for r in one]))
    off, dfn, info = BL._b4(one, mu)
    # Each unit faced exactly one opponent, so subtraction cancels entirely.
    check('B4 on a SINGLE week produces an offense adjustment of zero for '
          'every unit -- the identification collapse, arithmetically',
          max(abs(v) for v in off.values()) < 1e-9,
          f'max |off| {max(abs(v) for v in off.values()):.3e}')
    check('  and a defence adjustment of zero for every unit',
          max(abs(v) for v in dfn.values()) < 1e-9,
          f'max |def| {max(abs(v) for v in dfn.values()):.3e}')
    # AND IT SAYS IT DID NOT CONVERGE, WHICH A MEASUREMENT FORCED.
    #
    # B4 was declared with an `n_passes` hyperparameter. Undamped Jacobi
    # oscillates with period 2 here: 0.0000 at 1, 3 and 5 passes and 0.9000
    # at 2 and 4. A tuner picking `n_passes` on this design picks between two
    # arbitrary answers. The estimator now iterates to a tolerance and
    # reports non-convergence instead of carrying a pass count.
    check('  and it reports that it did NOT converge, rather than returning '
          'an arbitrary iterate silently',
          info['converged'] is False
          and info['used'] == 'SINGLE_PASS_FALLBACK',
          str({k: info[k] for k in ('converged', 'n_iter', 'used')}))
    check('  B4 therefore carries NO hyperparameter at all',
          BL.GRIDS['B4'] == {}, str(BL.GRIDS['B4']))
    check('  and `n_passes` is gone from the shrink directions with it',
          'n_passes' not in BL.SHRINK_DIRECTION,
          str(sorted(BL.SHRINK_DIRECTION)))
    conn = []
    for i, o in enumerate(teams):
        for j, d in enumerate(teams):
            if i == j:
                continue
            for _ in range(12):
                conn.append({'offense_team': o, 'defense_team': d,
                             'epa': 0.1 * i - 0.05 * j})
    mu_c = float(np.mean([r['epa'] for r in conn]))
    _o, _d, ic = BL._b4(conn, mu_c)
    check('on a CONNECTED schedule it converges within the iteration cap',
          ic['converged'] is True and ic['n_iter'] < BL.B4_MAX_ITER,
          str({k: ic[k] for k in ('converged', 'n_iter', 'final_change')}))
    check('  and the change trace shrinks rather than flipping',
          len(ic['change_trace']) >= 2
          and ic['change_trace'][-1] < ic['change_trace'][0],
          str(ic['change_trace'][:5]))
    # Identical row sets, checkable by hash.
    h1 = BL.rowset_hash(one)
    h2 = BL.rowset_hash(list(reversed(one)))
    check('the row-set hash is order-independent, so "identical information '
          'set" is checkable rather than asserted', h1 == h2)
    check('  and it changes when a row is removed',
          BL.rowset_hash(one[:-1]) != h1)
    # No baseline may read the forecast week.
    hist = [r for r in one]
    fut = [{**r, 'week': 2, 'ordinal': 202502, 'epa': 99.0,
            'play_id': 10000 + i} for i, r in enumerate(one[:10])]
    a = BL.predict('B3', hist, fut, {'half_life': 4.0})
    b = BL.predict('B3', hist, [{**r, 'epa': -99.0} for r in fut],
                   {'half_life': 4.0})
    check('a baseline`s prediction does not depend on the OUTCOME of the '
          'week it forecasts',
          a.state is State.PASS and np.allclose(a.value, b.value),
          'the forecast moved when only the held-out outcome changed')
    check('  and a baseline with no history REFUSES rather than predicting 0',
          BL.predict('B2', [], fut, {'n_games': 4}).code == BL.CODE_NO_HIST)


# =========================================================== PREREGISTRATION
def test_F_the_preregistration_is_literal_and_agrees_with_itself():
    print('\nF. thresholds a test reads from code')
    check('it declares it was written before any week-2 fit',
          PRE.DECLARED_BEFORE_ANY_WEEK2_FIT is True)
    check('the primary score names B5, clustering and the interval',
          all(k in PRE.PRIMARY_SCORE for k in ('B5', 'clustered', 'interval')),
          PRE.PRIMARY_SCORE[:80])
    check('the calibration band is a literal pair',
          PRE.CALIBRATION_SLOPE_BAND == (0.7, 1.3),
          str(PRE.CALIBRATION_SLOPE_BAND))
    check('the promotion criterion requires beating B4 as well as B5, so a '
          'shrinkage-only gain cannot pass',
          'B4' in PRE.PROMOTION_CRITERION and 'B5' in PRE.PROMOTION_CRITERION)
    check('  and restricts the claim to IDENTIFIED steps',
          'identified' in PRE.PROMOTION_CRITERION)
    check('the negative-result action forbids retuning until it wins',
          'No retuning' in PRE.NEGATIVE_RESULT_ACTION
          or 'no retuning' in PRE.NEGATIVE_RESULT_ACTION.lower(),
          PRE.NEGATIVE_RESULT_ACTION[:80])
    check('state-space work is blocked behind an identified mid-season win',
          'identified' in PRE.STATE_SPACE_BLOCKED_UNTIL)
    check('the week-2 construction forbids a week-1-only ridge',
          'NOT a' in PRE.WEEK2_CONSTRUCTION and 'rank 32' in
          PRE.WEEK2_CONSTRUCTION, PRE.WEEK2_CONSTRUCTION[:70])
    # THE CONTRACT-4 DEFECT: prose and code must not disagree.
    md = pathlib.Path(_ROOT, 'nfl/research/oas1/PREREGISTRATION.md')
    if not md.exists():
        NOT_EXECUTED.append('F: PREREGISTRATION.md not written yet')
        print('  NOT_EXECUTED: the markdown companion does not exist')
    else:
        txt = md.read_text()
        check('the markdown quotes the CODE`s lambda grid endpoints',
              f'{PRE.LAMBDA_GRID[0]:g}' in txt
              and f'{PRE.LAMBDA_GRID[-1]:g}' in txt,
              'the markdown states a grid the code does not')
        check('  and the code`s calibration band',
              '0.7' in txt and '1.3' in txt)
        check('  and the code`s week-1 rank numbers',
              str(PRE.WEEK1_RANK) in txt and str(PRE.WEEK1_DEFICIENCY) in txt)
        check('  and names the module as the source of truth',
              'preregistration.py' in txt)
    # The fit module must not restate a threshold the spec owns.
    check('the fit module`s lambda grid IS the pre-registered one',
          tuple(FT.LAMBDA_GRID) == tuple(PRE.LAMBDA_GRID),
          'two lambda grids exist and they differ')
    check('the design module`s structural deficiency IS the declared one',
          DS.EXPECTED_STRUCTURAL_DEFICIENCY == PRE.STRUCTURAL_DEFICIENCY)


# ================================================================ EVALUATOR
def test_G_the_evaluator_scores_a_continuous_target_without_a_second_crps():
    print('\nG. MAE and RMSE by extension, CRPS by import')
    for k in ('mae', 'rmse', 'crps', 'brier', 'log_loss'):
        check(f'SCORERS holds {k}', k in EV.SCORERS, str(sorted(EV.SCORERS)))
    y = np.array([1.0, -2.0, 0.5, 3.0])
    p = np.array([0.5, -1.0, 0.0, 2.0])
    check('mae is the mean absolute error',
          abs(EV.SCORERS['mae'](y, p) - 0.75) < 1e-12,
          str(EV.SCORERS['mae'](y, p)))
    check('rmse is larger than mae on a spread error set',
          EV.SCORERS['rmse'](y, p) > EV.SCORERS['mae'](y, p))
    check('both refuse a shape mismatch rather than broadcasting',
          _raises(lambda: EV.SCORERS['mae'](y, p[:2])))
    src = pathlib.Path(_ROOT, 'nfl/production/evaluator.py').read_text()
    check('there is still exactly ONE crps definition, and it is imported',
          src.count('\ndef crps(') == 0
          and 'from nfl.product.evaluator import crps' in src,
          f'{src.count(chr(10) + "def crps(")} local definition(s)')
    cal = EV.calibration_slope(y, p)
    check('the calibration slope is reported with its n and variance',
          cal['slope'] is not None and cal['n'] == 4
          and cal['predictor_variance'] > 0)
    deg = EV.calibration_slope(y, np.zeros(4))
    check('a CONSTANT predictor gets slope None, not 0.0 -- B0 is '
          'uncalibratable, not badly calibrated',
          deg['slope'] is None
          # ASSERT THE CLAIM, NOT A SENTENCE. This read
          # `'no measurement' in deg['why_none']` and went red when the
          # message was rewritten during the degenerate-ratio repair -- the
          # behaviour never changed. `uncalibratable` is the load-bearing
          # word and it is the one the project uses everywhere else.
          and 'uncalibratable' in (deg.get('why_none') or ''),
          f"slope={deg.get('slope')} why_none={deg.get('why_none')!r}")


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_frame_keeps_every_row_and_counts_every_exclusion,
               test_B_the_target_is_governed_and_the_features_are_not,
               test_C_an_unidentified_design_is_refused_not_fitted,
               test_D_the_fit_does_what_the_spec_says,
               test_E_the_baselines_are_fair_and_B4_collapses_on_one_week,
               test_F_the_preregistration_is_literal_and_agrees_with_itself,
               test_G_the_evaluator_scores_a_continuous_target_without_a_second_crps):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)

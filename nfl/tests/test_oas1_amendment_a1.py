"""Amendment A1: an amendment may only remove, and the ground must still hold.

Two axes were in the Week-2 search space with no declared path into the
objective. Leaving them in would have meant selecting over configurations that
cannot change a score -- 12,960 declared points over 864 distinct ones -- and
resolving one-standard-error ties on axes that do nothing.

These checks exist so the amendment cannot quietly become the opposite of what
it is: a route to widening a grid after seeing a result.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.oas1 import amendment as AM                        # noqa: E402
from nfl.research.oas1 import preregistration as PRE                 # noqa: E402
from sportsplatform.governance.outcome import State                  # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_it_validates_and_only_removes():
    o = AM.validate()
    check('A the amendment validates', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A-C amendment assertions')
        return
    check('A exactly half_life and min_plays come out',
          o.evidence['removed_axes'] == ['half_life', 'min_plays'],
          str(o.evidence['removed_axes']))
    check('A nothing is added and no grid is widened',
          o.evidence['removal_only'] is True
          and set(o.value) < set(AM.declared_space()),
          str(sorted(o.value)))
    check('A the four surviving axes are the live ones',
          sorted(o.value) == sorted(AM.LIVE_AXES), str(sorted(o.value)))


def test_B_the_duplication_is_exactly_fifteenfold():
    o = AM.validate()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('B duplication')
        return
    check('B 12,960 declared configurations, 864 distinct',
          o.evidence['declared_configurations'] == 12960
          and o.evidence['effective_configurations'] == 864,
          f"{o.evidence['declared_configurations']} / "
          f"{o.evidence['effective_configurations']}")
    check('B which is 5 half_life values times 3 min_plays values',
          o.evidence['duplication_factor']
          == len(PRE.HALF_LIFE_GRID) * len(PRE.MIN_PLAYS_GRID) == 15,
          str(o.evidence['duplication_factor']))


def test_C_the_tie_break_loses_its_dead_keys():
    check('C half_life and min_plays are struck from the tie-break',
          AM.AMENDED_TIE_BREAK_ORDER
          == ('max lambda', 'max kappa', 'min rho'),
          str(AM.AMENDED_TIE_BREAK_ORDER))
    check('C the surviving keys keep their declared order',
          list(AM.AMENDED_TIE_BREAK_ORDER)
          == [k for k in PRE.TIE_BREAK_ORDER
              if k in AM.AMENDED_TIE_BREAK_ORDER],
          str(PRE.TIE_BREAK_ORDER))


def test_D_the_frozen_preregistration_is_not_rewritten():
    """The amendment is additive. The original grids stay on disk as declared."""
    check('D HALF_LIFE_GRID is untouched in the preregistration',
          PRE.HALF_LIFE_GRID == (2.0, 4.0, 8.0, 16.0, float('inf')),
          str(PRE.HALF_LIFE_GRID))
    check('D MIN_PLAYS_GRID is untouched',
          PRE.MIN_PLAYS_GRID == (0, 20, 50), str(PRE.MIN_PLAYS_GRID))
    check('D and the config still declares both, so the removal is visible',
          {'half_life', 'min_plays'} <= set(AM.declared_space()),
          str(sorted(AM.declared_space())))
    check('D the amendment says the preregistration is unmodified',
          json.loads(AM.PATH.read_text())['preregistration_is_unmodified']
          is True)


def test_E_an_amendment_that_widened_would_be_refused():
    """The one thing this mechanism must never become."""
    real = AM.effective_space
    try:
        AM.effective_space = lambda: {**real(), 'lambda': list(PRE.LAMBDA_GRID)
                                      + [99999.0]}
        o = AM.validate()
        check('E adding a lambda point is refused',
              o.state is State.FAIL and o.code == AM.CODE_BAD,
              f'{o.state}[{o.code}]')
        check('E and the refusal names the added value',
              any('99999' in str(w) for w in o.evidence.get('widened', [])),
              str(o.evidence.get('widened')))
        AM.effective_space = lambda: {**real(),
                                      'a_new_axis_nobody_declared': [1, 2]}
        o2 = AM.validate()
        check('E inventing a new axis is refused',
              o2.state is State.FAIL
              and o2.evidence['added_axes'] == ['a_new_axis_nobody_declared'],
              f'{o2.state}[{o2.code}] {o2.evidence.get("added_axes")}')
    finally:
        AM.effective_space = real
    check('E and the real amendment still validates afterwards',
          AM.validate().state is State.PASS)


def test_F_the_ground_the_removal_rests_on_is_recorded():
    """half_life comes out because week 2 has one current-season week."""
    d = AM.REMOVED['half_life']['degeneracy_evidence']
    check('F the training set carries one current-season ordinal',
          d['current_season_ordinals_in_training'] == [202601],
          str(d['current_season_ordinals_in_training']))
    check('F every current-season play is zero games back, weight 1',
          d['games_back_for_every_current_season_play'] == 0
          and d['weight_for_every_half_life'] == 1.0, str(d))
    check('F reinstatement requires a further amendment, declared first',
          'before any fit' in AM.REMOVED['half_life']['reinstatement'])
    check('F min_plays is retained as reporting, fixed at 0, not deleted',
          AM.REMOVED['min_plays']['retained_as']['fixed_value'] == 0
          and AM.REMOVED['min_plays']['retained_as']['role'] == 'reporting',
          str(AM.REMOVED['min_plays']['retained_as']))


def test_G_the_candidate_is_fitted_but_promoted_by_nothing():
    """SUPERSEDES `test_G_the_candidate_is_still_not_fitted`, 2026-09-18.

    The old check asserted that no Week-2 result artifact exists. That was the
    right guard when it was written: it stopped the A1 amendment commit from
    quietly fitting a candidate while claiming only to remove two dead axes.

    The candidate has now been fitted deliberately, in its own commit, under
    P9, by `nfl/research/oas1/week2.py`. So "no artifact exists" is an obsolete
    contract and is replaced rather than suppressed -- and the replacement is
    STRONGER, because the thing the old check was really protecting was not
    the absence of a file. It was that nothing gets promoted and that A1's
    ground still holds. Both are asserted here against the fit that actually
    ran, which the old check could not do because there was nothing to read.
    """
    chain = json.loads(
        (_REPO/'nfl/research/oas1/OAS1_BASELINE_CHAIN.json').read_text())
    check('G the baseline chain still carries candidate_fitted=False -- the '
          'baselines were built BEFORE the candidate and that does not change',
          chain.get('candidate_fitted') is False,
          str(chain.get('candidate_fitted')))
    art = _REPO / 'nfl/research/oas1/OAS1_WEEK2_RESULT.json'
    if not art.exists():
        check('G the Week-2 artifact is present to be checked', False,
              str(art))
        return
    d = json.loads(art.read_text())
    check('G the fitted candidate is research-only',
          d.get('research_only') is True, str(d.get('research_only')))
    check('G no downstream consumer is authorized',
          d.get('downstream_authorized') is False)
    check('G nothing is promoted', d.get('promoted') is False)
    check('G the hurdle is not evaluated, so nothing can be read as a win',
          d['scoring']['hurdles_evaluated'] is False
          and d['scoring']['state'] == 'BLOCKED',
          str(d['scoring']['state']))
    # A1 REMOVED half_life ON THE GROUND THAT THE TRAINING SET CARRIES ONE
    # CURRENT-SEASON WEEK. Now that a fit exists, that ground is checkable
    # against the fit rather than against the amendment's own note.
    ords = set()
    for cls in ('pass', 'rush'):
        for f in d['selection'][cls]['folds']:
            ords.add(f['ordinal'])
    cur = sorted(o for o in ords
                 if o >= d['forecast']['season'] * 100)
    check('G the fitted chain reaches exactly one current-season ordinal, '
          'which is the ground A1 rests on',
          cur == [d['forecast']['season'] * 100 + 1], str(cur))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_it_validates_and_only_removes,
               test_B_the_duplication_is_exactly_fifteenfold,
               test_C_the_tie_break_loses_its_dead_keys,
               test_D_the_frozen_preregistration_is_not_rewritten,
               test_E_an_amendment_that_widened_would_be_refused,
               test_F_the_ground_the_removal_rests_on_is_recorded,
               test_G_the_candidate_is_fitted_but_promoted_by_nothing):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)

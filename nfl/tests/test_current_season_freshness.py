"""Freshness must REFUSE, and it must refuse for the right reason.

THE DEFECT THIS EXISTS FOR. `qb_allocation.panel_freshness` already detected
that panel_p3 stopped at ordinal 202518, `allocate()` already recorded that
verdict on the artifact -- and the board published anyway, because nothing
refused. A detector that nothing consults is documentation.

THE SCOPE IS THE DESIGN. The same input must PASS for a DET-BUF board reading
only DET and BUF, and REFUSE for a league-wide fit missing DEN and KC. A rule
with one threshold either blocks the first or admits the second.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State            # noqa: E402
from nfl.production import freshness as F                             # noqa: E402
from nfl.prospective import artifact as A                             # noqa: E402

PASSED = FAILED = 0

CLUBS32 = ('ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL',
           'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV',
           'MIA', 'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF',
           'TB', 'TEN', 'WAS')
FIXTURE = ('BUF', 'DET')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def test_A_the_same_input_passes_fixture_local_and_refuses_league_wide():
    print('\nA. one input, two scopes, two correct answers at once')
    loc = F.check_input('panel_p3', 2026, 2, scope=F.FIXTURE_LOCAL,
                        newest_ordinal=202601, expected_clubs=FIXTURE,
                        present_clubs=FIXTURE)
    check('FIXTURE_LOCAL on {BUF, DET} PASSES',
          loc.state is State.PASS and loc.code == F.CODE_FRESH,
          f'{loc.state}[{loc.code}]')
    wide = F.check_input('panel_p3', 2026, 2, scope=F.LEAGUE_WIDE,
                         newest_ordinal=202601, expected_clubs=CLUBS32,
                         present_clubs=[c for c in CLUBS32
                                        if c not in ('DEN', 'KC')])
    check('  the SAME input at LEAGUE_WIDE with 30 of 32 is BLOCKED',
          wide.state is State.BLOCKED and wide.code == F.CODE_INCOMPLETE,
          f'{wide.state}[{wide.code}]')
    check('    and it NAMES the missing clubs rather than counting them',
          wide.evidence['missing_clubs'] == ['DEN', 'KC'],
          str(wide.evidence['missing_clubs']))
    check('    with cause DATA', wide.evidence.get('cause') == Cause.DATA.value)
    # NO QUORUM. 31 of 32 is still a refusal.
    almost = F.check_input('panel_p3', 2026, 2, scope=F.LEAGUE_WIDE,
                           newest_ordinal=202601, expected_clubs=CLUBS32,
                           present_clubs=[c for c in CLUBS32 if c != 'KC'])
    check('  31 of 32 is ALSO blocked -- there is no majority rule',
          almost.state is State.BLOCKED, f'{almost.state}[{almost.code}]')


def test_B_stale_and_incomplete_are_different_codes():
    print('\nB. two failures, two codes -- never one flag for two conditions')
    stale = F.check_input('panel_p3', 2026, 2, scope=F.FIXTURE_LOCAL,
                          newest_ordinal=202518, expected_clubs=FIXTURE,
                          present_clubs=FIXTURE)
    check('an old ordinal with full coverage is _STALE',
          stale.code == F.CODE_STALE, stale.code)
    inc = F.check_input('panel_p3', 2026, 2, scope=F.FIXTURE_LOCAL,
                        newest_ordinal=202601, expected_clubs=FIXTURE,
                        present_clubs=('BUF',))
    check('  a current ordinal with a missing club is _INCOMPLETE',
          inc.code == F.CODE_INCOMPLETE, inc.code)
    check('  and they are not the same code',
          F.CODE_STALE != F.CODE_INCOMPLETE)


def test_C_the_week_one_exemption_is_named_not_passed():
    print('\nC. a season opener is EXEMPT, and exemption is not freshness')
    o = F.check_input('panel_p3', 2026, 1, scope=F.FIXTURE_LOCAL,
                      newest_ordinal=202518, expected_clubs=FIXTURE,
                      present_clubs=FIXTURE)
    check('week 1 is NOT_APPLICABLE', o.state is State.NOT_APPLICABLE,
          f'{o.state}[{o.code}]')
    check('  coded NOT_APPLICABLE_AT_A_SEASON_OPENER, never FRESH',
          o.code == F.CODE_OPENER and o.code != F.CODE_FRESH, o.code)


def test_D_expected_clubs_are_supplied_never_inferred():
    print('\nD. the check cannot mark its own homework')
    o = F.check_input('panel_p3', 2026, 2, scope=F.FIXTURE_LOCAL,
                      newest_ordinal=202601, expected_clubs=None,
                      present_clubs=FIXTURE)
    check('omitting the expected set is a REFUSAL, not a pass on what is there',
          o.state is State.FAIL
          and o.code == 'FRESHNESS_EXPECTED_CLUBS_NOT_SUPPLIED',
          f'{o.state}[{o.code}]')
    # THE TAUTOLOGY TEST: if expected were inferred from present, this would
    # pass while covering nothing.
    o2 = F.check_input('panel_p3', 2026, 2, scope=F.LEAGUE_WIDE,
                       newest_ordinal=202601, expected_clubs=CLUBS32,
                       present_clubs=())
    check('  zero present against 32 expected is BLOCKED, not vacuously fresh',
          o2.state is State.BLOCKED and len(o2.evidence['missing_clubs']) == 32,
          f'{o2.state}[{o2.code}] missing {o2.evidence["n_missing"]}')


def test_E_an_unmentioned_registered_input_is_a_refusal():
    print('\nE. a gate satisfiable by silence is not a gate')
    o = F.check_all(2026, 2, {'panel_p3': dict(
        scope=F.FIXTURE_LOCAL, newest_ordinal=202601,
        expected_clubs=FIXTURE, present_clubs=FIXTURE)})
    check('supplying one of three registered inputs BLOCKS',
          o.state is State.BLOCKED, f'{o.state}[{o.code}]')
    check('  and names every input that refused',
          set(o.evidence['blocking_inputs'])
          == {'denom_panel', 'team_volume_history'},
          str(o.evidence['blocking_inputs']))
    check('  an unknown input id is REFUSED rather than skipped',
          F.check_input('not_registered', 2026, 2, expected_clubs=FIXTURE,
                        present_clubs=FIXTURE,
                        newest_ordinal=202601).code == F.CODE_UNDECLARED)


def test_F_denom_panel_is_blocked_by_declaration_and_says_why():
    print('\nF. denom_panel: stale by declaration, and the block is not blunt')
    o = F.check_input('denom_panel', 2026, 2, scope=F.LEAGUE_WIDE,
                      newest_ordinal=202601, expected_clubs=CLUBS32,
                      present_clubs=CLUBS32)
    check('it BLOCKS even with a current ordinal and full coverage',
          o.state is State.BLOCKED and o.code == F.CODE_STALE,
          f'{o.state}[{o.code}]')
    check('  naming the source problem rather than a coverage number',
          o.evidence.get('declared_blocked') == 'CURRENT_SEASON_SOURCE_UNVERIFIED',
          str(o.evidence.get('declared_blocked')))
    # THE MEASUREMENT THAT MAKES THE BLOCK HONEST. Four of five team-volume
    # metrics use history-only estimators and are unaffected; exactly one,
    # team_targets, is an EWMA that cannot see week 1.
    check('  and separating which consumers are RECENCY-sensitive',
          o.evidence.get('recency_sensitive') == ['team_targets (ewma)'],
          str(o.evidence.get('recency_sensitive')))
    check('    from the four that are history-only and unaffected',
          len(o.evidence.get('history_only') or []) == 4,
          str(o.evidence.get('history_only')))


def test_G_it_is_registered_HARD_and_evaluated_before_publication():
    print('\nG. registered as a HARD invariant, not a recorded opinion')
    check('`current_season_input_freshness` is in artifact.INVARIANTS',
          'current_season_input_freshness' in A.INVARIANTS)
    check('  and its class is HARD',
          'current_season_input_freshness' in A.HARD_INVARIANTS)
    spec = A.INVARIANTS['current_season_input_freshness']
    check('  pointing at the real evaluator',
          spec['evaluator'] == 'nfl.production.freshness.check_all',
          spec['evaluator'])
    check('  and the class is READ from the table, not supplied by a caller',
          A.verdict('current_season_input_freshness',
                    F.check_input('panel_p3', 2026, 2, scope=F.FIXTURE_LOCAL,
                                  newest_ordinal=202601,
                                  expected_clubs=FIXTURE,
                                  present_clubs=FIXTURE))['class'] == A.HARD)


def test_H_ordinals_not_wall_clock():
    print('\nH. a touched file cannot become fresh')
    src = open(F.__file__).read()
    check('the module never reads a filesystem mtime',
          'getmtime' not in src and 'st_mtime' not in src)
    check('  and never reads a wall clock',
          'datetime.now' not in src and 'time.time' not in src)
    check('  the required ordinal is arithmetic on (season, week)',
          F.required_ordinal(2026, 2) == 202601
          and F.required_ordinal(2026, 12) == 202611,
          str(F.required_ordinal(2026, 2)))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_same_input_passes_fixture_local_and_refuses_league_wide,
               test_B_stale_and_incomplete_are_different_codes,
               test_C_the_week_one_exemption_is_named_not_passed,
               test_D_expected_clubs_are_supplied_never_inferred,
               test_E_an_unmentioned_registered_input_is_a_refusal,
               test_F_denom_panel_is_blocked_by_declaration_and_says_why,
               test_G_it_is_registered_HARD_and_evaluated_before_publication,
               test_H_ordinals_not_wall_clock):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)

"""The incumbency panel must be able to see the forecast week's previous game.

WHAT WENT WRONG WITHOUT THIS. `previous_primary_detail` takes the most recent
ordinal strictly before the cut. That is correct and it is not enough: it has
no way to notice the most recent ordinal is nine months old. Measured
2026-09-17, `panel_p3.csv.gz` holds 2020-2025 with a maximum ordinal of 202518
and ZERO rows for 2026, so a 2026 WEEK 2 forecast gave all 32 clubs a 2025
week-18 previous primary and classed all 32 a season opener. Nothing refused,
because nothing asked.

THE LABEL NAMED ONE CONDITION AND FIRED ON TWO. `is_season_opener` is true
both when the forecast really is an opener and when the panel simply cannot
reach the current season. Calling the second a "week1 specification defect"
is what let it hide.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State           # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def test_A_a_stale_panel_is_blocked_by_name():
    print('\nA. a week-2 forecast on a panel that stops last season is BLOCKED')
    o = QA.panel_freshness(2026, 2)
    check('2026 week 2 is BLOCKED, not answered silently',
          o.state is State.BLOCKED, f'{o.state}[{o.code}]')
    check('  and the code names STALE CURRENT-SEASON STATE, not a boundary',
          o.code == 'PANEL_STALE_CURRENT_SEASON_STATE', o.code)
    # `cause` is carried in the evidence as a string, not as an attribute --
    # checked the way the governance type actually exposes it.
    check('  with cause DATA', o.evidence.get('cause') == Cause.DATA.value,
          str(o.evidence.get('cause')))
    ev = o.evidence
    check('  the newest panel ordinal is reported, not just asserted stale',
          isinstance(ev.get('newest_panel_ordinal'), int),
          str(ev.get('newest_panel_ordinal')))
    check('  and the ordinal it needed is reported beside it',
          ev.get('forecast_ordinal') == 202602, str(ev.get('forecast_ordinal')))
    print(f'       newest panel ordinal {ev.get("newest_panel_ordinal")}, '
          f'seasons {ev.get("seasons_in_panel")}')


def test_B_a_real_season_opener_is_not_a_staleness_finding():
    print('\nB. week 1 crosses a boundary by definition and is NOT stale')
    o = QA.panel_freshness(2026, 1)
    check('2026 week 1 PASSES', o.state is State.PASS, f'{o.state}[{o.code}]')
    check('  and says why it does not apply rather than claiming freshness',
          o.code == 'PANEL_FRESHNESS_NOT_APPLICABLE_AT_A_SEASON_OPENER', o.code)


def test_C_an_in_season_week_the_panel_covers_passes():
    print('\nC. a week the panel actually covers is FRESH')
    o = QA.panel_freshness(2025, 10)
    check('2025 week 10 PASSES as FRESH', o.state is State.PASS
          and o.code == 'PANEL_FRESH', f'{o.state}[{o.code}]')
    check('  the trail allowance is ONE week and is declared, not implicit',
          QA.PANEL_MAX_TRAIL_WEEKS == 1, str(QA.PANEL_MAX_TRAIL_WEEKS))
    # BEHAVIOURAL: the boundary of the rule, not the rule's happy path. The
    # panel's newest ordinal is 202518, so week 19 is exactly reachable and
    # week 20 is exactly one week too far.
    a, b = QA.panel_freshness(2025, 19), QA.panel_freshness(2025, 20)
    check('  week 19 (newest+1) is still FRESH', a.state is State.PASS,
          f'{a.state}[{a.code}]')
    check('  week 20 (newest+2) is BLOCKED -- the rule bites at the boundary',
          b.state is State.BLOCKED, f'{b.state}[{b.code}]')


def test_D_the_two_boundary_causes_are_named_apart():
    print('\nD. `is_season_opener` conflated two conditions; they are split')
    trip = [('p1', 1, 0), ('p2', 2, 0)]
    d = {'pid': 'x', 'ordinal': 202518, 'is_season_opener': True}
    w1 = QA.qb3_configuration(trip, d, season=2026, week=1)
    w2 = QA.qb3_configuration(trip, d, season=2026, week=2)
    old = QA.qb3_configuration(trip, d)
    check('a real week-1 opener keeps QB3_WEEK1_SEASON_BOUNDARY',
          w1['defect_id'] == 'QB3_WEEK1_SEASON_BOUNDARY', str(w1['defect_id']))
    check('  and is caused SEASON_OPENER',
          w1['boundary_cause'] == 'SEASON_OPENER', str(w1['boundary_cause']))
    check('a week-2 room is QB_STALE_CURRENT_SEASON_STATE, not a "week1" defect',
          w2['defect_id'] == 'QB_STALE_CURRENT_SEASON_STATE',
          str(w2['defect_id']))
    check('  and is caused STALE_CURRENT_SEASON_STATE',
          w2['boundary_cause'] == 'STALE_CURRENT_SEASON_STATE',
          str(w2['boundary_cause']))
    check('a caller that cannot say which week keeps the old id and says so',
          old['defect_id'] == 'QB3_WEEK1_SEASON_BOUNDARY'
          and old['boundary_cause'] == 'UNDETERMINED', str(old['boundary_cause']))
    # EVERY SEALED ARTIFACT KEEPS THE ID IT RECORDED.
    for c in (w1, w2, old):
        check('  the legacy id is preserved beside the new one',
              c['defect_id_legacy'] == 'QB3_WEEK1_SEASON_BOUNDARY',
              str(c.get('defect_id_legacy')))
    check('  and the declared causes are the ones the module names',
          set(QA.BOUNDARY_CAUSES) == {'SEASON_OPENER',
                                      'STALE_CURRENT_SEASON_STATE',
                                      'UNDETERMINED'},
          str(QA.BOUNDARY_CAUSES))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_stale_panel_is_blocked_by_name,
               test_B_a_real_season_opener_is_not_a_staleness_finding,
               test_C_an_in_season_week_the_panel_covers_passes,
               test_D_the_two_boundary_causes_are_named_apart):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)

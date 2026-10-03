"""OWNER RULE 1 (2026-10-02), production group B: nothing measured cannot PASS.

"No consequential validator, gate, audit, reconciliation, readiness check, or comparison may
return PASS/SUCCESS/READY when its required measured input is empty, absent, unparsed,
zero-count, or otherwise non-evidentiary. The failure state must distinguish
EMPTY_INPUT / NOT_EXECUTED / INCOMPLETE from a true FAIL."

This module covers the universe layer (participation, allocation, chronology, role state), the
non-QB production layer (layers, current-season evidence, accounting, role invariants,
eligibility, game readiness), the review gate and slate report, and the product layer (quality
gates, model health, board pointer). Every row is one repaired site. Each carries a POSITIVE
CONTROL (an input known to violate the rule, which must now be refused with one of the three
non-evidentiary causes, never PASS and never a plain FAIL) and a NEGATIVE CONTROL (a minimal
valid, non-empty input which must still pass, or must fail for its own true reason). A detector
without a demonstrated trip case is not validated, so every positive control records itself with
`observe(...)` (OWNER RULE 2).

The authoritative runner is
`python3.12 nfl/tests/run_suite.py --modules test_non_evidentiary_refusal_production_b`.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(_REPO), str(_REPO / 'nfl' / 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sportsplatform.governance.outcome import (                       # noqa: E402
    NON_EVIDENTIARY, Cause, Outcome, State)
from nfl.tests._controls import observe                                # noqa: E402

PASSED = FAILED = 0
NE_CAUSES = {c.value for c in NON_EVIDENTIARY}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def refused(o) -> bool:
    """BLOCKED with a non-evidentiary cause: the only acceptable answer to an empty input."""
    return (isinstance(o, Outcome) and o.state is State.BLOCKED
            and (o.evidence or {}).get('cause') in NE_CAUSES)


def _desc(o):
    if isinstance(o, Outcome):
        return f'{o.state.value}[{o.code}] cause={(o.evidence or {}).get("cause")}'
    return repr(o)[:160]


# ---------------------------------------------------------------- shared fixtures
_BUDGET = {'skill_nonqb_budget': 0.8, 'skill_nonqb_sd': 0.1, 'qb_budget': 1.0,
           'qb_sd': 0.0, 'all_positions': 11.0, 'all_positions_sd': 0.0,
           'n_team_games': 1}
CUT, RAN = '2026-09-21T18:00:00Z', '2026-09-21T18:44:48Z'


def _role_row(gsis='A', share=0.8, n=2):
    from nfl.production.universe import role_state as RS
    return {'room': RS.ROOM_CARRIES, 'team': 'NE', 'gsis_id': gsis,
            'display_name': gsis, 'role': 'STARTER', 'game_id': 'g',
            'role_support': RS.ROLE_SUPPORTED, 'role_unsupported_why': [],
            'conflicts': [],
            'evidence': {'current_season_snaps': {'mean_offense_pct': share,
                                                  'n_games_at_this_club': n}}}


def _alloc_outcome(rows, clubs, room='carries'):
    return Outcome.ok('ALLOCATED', value=rows, clubs=clubs, room=room)


def _one_man_allocation():
    from nfl.production.universe import allocation as AL
    rows = [{'gsis_id': 'A', 'display_name': 'A', 'role': 'STARTER', 'team': 'NE',
             'share_of_measured': 1.0, 'share_renormalised': 1.0,
             'allocation_state': AL.ALLOCATED}]
    clubs = {'NE': {'n_with_measured_share': 1, 'reassigned_mass': 0.0,
                    'retained_share_mass': 1.0, 'n_without_measured_share': 0,
                    'concentration': {}}}
    return _alloc_outcome(rows, clubs)


# ================================================================ universe layer
def test_01_participation_assess_over_no_rows():
    print('\n1. universe.participation.assess')
    from nfl.production.universe import participation as PA
    o = PA.assess([], budget=_BUDGET)
    observe('nfl.production.universe.participation:assess:PARTICIPATION_EMPTY_INPUT', o)
    check('positive control: no role row in an opportunity room is refused, not RESOLVED',
          refused(o) and o.code == 'PARTICIPATION_EMPTY_INPUT' and o.evidence['n_rows'] == 0,
          _desc(o))
    o = PA.assess([{'room': 'kicks', 'team': 'NE', 'gsis_id': 'K'}], budget=_BUDGET)
    check('  and a row outside every opportunity room is the same refusal', refused(o), _desc(o))
    o = PA.assess([_role_row()], budget=_BUDGET)
    check('  negative control: one measured, role-supported row closing the budget RESOLVES',
          o.state is State.PASS and o.code == 'PARTICIPATION_RESOLVED' and o.evidence['n_rows'] == 1,
          _desc(o))
    o = PA.assess([_role_row(share=0.5)], budget=_BUDGET)
    check('  and a row that leaves the budget open is PARTICIPATION_INCOMPLETE, a true '
          'non-pass with cause DATA', o.state is State.BLOCKED
          and o.code == 'PARTICIPATION_INCOMPLETE' and not o.non_evidentiary, _desc(o))


def test_02_participation_gate_over_nobody():
    print('\n2. universe.participation.assert_participation_supports_allocation')
    from nfl.production.universe import participation as PA
    empty = Outcome.ok('P', value=[])
    o = PA.assert_participation_supports_allocation(empty, allocating_ids={'A'})
    observe('nfl.production.universe.participation:assert_participation_supports_allocation:'
            'PARTICIPATION_GATE_EMPTY_INPUT', o)
    check('positive control: a participation outcome with no rows is refused, never '
          'SUPPORTS_ALLOCATION', refused(o) and o.code == 'PARTICIPATION_GATE_EMPTY_INPUT',
          _desc(o))
    po = PA.assess([_role_row()], budget=_BUDGET)
    o = PA.assert_participation_supports_allocation(po, allocating_ids=set())
    observe('nfl.production.universe.participation:assert_participation_supports_allocation:'
            'ALLOCATING_SET_EMPTY', o)
    check('positive control: rows exist but the allocator names nobody -> refused',
          refused(o) and o.code == 'ALLOCATING_SET_EMPTY', _desc(o))
    o = PA.assert_participation_supports_allocation(po, allocating_ids={'A'})
    check('  negative control: one resolved player is MEASURED and refused only for the '
          'governed tolerance being uncertified (GOVERNANCE, not non-evidentiary)',
          o.state is State.BLOCKED and o.code == 'PARTICIPATION_TOLERANCE_NOT_CERTIFIED'
          and not o.non_evidentiary, _desc(o))
    o = PA.assert_participation_supports_allocation(po)
    check('  and no declared allocating set is still NO_ALLOCATING_DECLARATION (GOVERNANCE)',
          o.state is State.BLOCKED and o.code == 'NO_ALLOCATING_DECLARATION'
          and not o.non_evidentiary, _desc(o))


def test_03_redistribution_gate_over_no_rooms():
    print('\n3. universe.allocation.assert_redistribution_supported')
    from nfl.production.universe import allocation as AL
    o = AL.assert_redistribution_supported(_alloc_outcome([], {}))
    observe('nfl.production.universe.allocation:assert_redistribution_supported:'
            'REDISTRIBUTION_EMPTY_INPUT', o)
    check('positive control: an allocation with no club and no row is refused, not '
          'NO_REDISTRIBUTION_REQUIRED', refused(o) and o.code == 'REDISTRIBUTION_EMPTY_INPUT'
          and o.evidence['n_clubs'] == 0, _desc(o))
    o = AL.assert_redistribution_supported(_one_man_allocation())
    check('  negative control: one room retaining its whole measured mass PASSES',
          o.state is State.PASS and o.code == 'NO_REDISTRIBUTION_REQUIRED'
          and o.value['n_clubs'] == 1, _desc(o))
    ao = _one_man_allocation()
    ao.evidence['clubs']['NE']['reassigned_mass'] = 0.3
    ao.value[0]['share_of_measured'] = 0.7
    o = AL.assert_redistribution_supported(ao)
    check('  and a room that reassigns mass is REDISTRIBUTION_UNSUPPORTED (GOVERNANCE), '
          'distinct from the empty refusal', o.state is State.BLOCKED
          and o.code == 'REDISTRIBUTION_UNSUPPORTED' and not o.non_evidentiary, _desc(o))


def test_04_conservation_gate_over_no_composition():
    print('\n4. universe.allocation.assert_allocation_conserves')
    from nfl.production.universe import allocation as AL
    o = AL.assert_allocation_conserves(_alloc_outcome([], {}), consuming_ids={'A'})
    observe('nfl.production.universe.allocation:assert_allocation_conserves:'
            'ALLOCATION_EMPTY_INPUT', o)
    check('positive control: no composition to sum is refused, not CONSERVES',
          refused(o) and o.code == 'ALLOCATION_EMPTY_INPUT', _desc(o))
    o = AL.assert_allocation_conserves(_one_man_allocation(), consuming_ids=set())
    observe('nfl.production.universe.allocation:assert_allocation_conserves:'
            'CONSUMING_SET_EMPTY', o)
    check('positive control: a composition exists but the consumer reads nobody -> refused',
          refused(o) and o.code == 'CONSUMING_SET_EMPTY', _desc(o))
    o = AL.assert_allocation_conserves(_one_man_allocation(), consuming_ids={'A'})
    check('  negative control: one unit composition read by its one player CONSERVES',
          o.state is State.PASS and o.code == 'ALLOCATION_CONSERVES', _desc(o))
    o = AL.assert_allocation_conserves(_one_man_allocation(), consuming_ids={'GHOST'})
    check('  and a consumer outside the composition is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'CONSUMER_READS_OUTSIDE_THE_COMPOSITION', _desc(o))


def test_05_chronology_certificate_over_no_sources():
    print('\n5. universe.chronology.certify')
    from nfl.production.universe import chronology as CH
    o = CH.certify(CUT, RAN, sources={})
    observe('nfl.production.universe.chronology:certify:CHRONOLOGY_NO_SOURCES', o)
    check('positive control: a supplied-but-empty sources map is refused, not CERTIFIED',
          refused(o) and o.code == 'CHRONOLOGY_NO_SOURCES'
          and o.evidence['n_sources_checked'] == 0, _desc(o))
    o = CH.certify(CUT, RAN, sources={'injuries': {'retrieved_at': '2026-09-21T17:00:00Z'}})
    check('  negative control: one vintage before the cut CERTIFIES with n_sources_checked=1 '
          'and all three invariants asserted', o.state is State.PASS
          and o.value['n_sources_checked'] == 1
          and len(o.value['invariants_asserted']) == 3
          and o.value['vintage_invariants_state'] == 'EXECUTED', _desc(o))
    o = CH.certify(CUT, RAN)
    check('  the clock-only precheck (sources=None, run_chain\'s declared use) asserts ONE '
          'invariant and names the two it did not execute', o.state is State.PASS
          and o.value['invariants_asserted'] == ['information_cut <= run_started_at']
          and len(o.value['invariants_not_executed']) == 2
          and o.value['vintage_invariants_state'] == 'NOT_EXECUTED', _desc(o))
    o = CH.certify(CUT, RAN, sources={'injuries': {'retrieved_at': '2026-09-21T20:00:00Z'}})
    check('  and a vintage after the cut is CHRONOLOGY_VIOLATED (GOVERNANCE), not empty',
          o.state is State.BLOCKED and o.code == 'CHRONOLOGY_VIOLATED'
          and not o.non_evidentiary, _desc(o))


def test_06_freshness_over_no_families():
    print('\n6. universe.chronology.check_freshness')
    from nfl.production.universe import chronology as CH
    o = CH.check_freshness(CUT, {})
    observe('nfl.production.universe.chronology:check_freshness:FRESHNESS_NO_SOURCES', o)
    check('positive control: no evidence family is EMPTY_INPUT (was DEPENDENCY), never '
          'ESTABLISHED', refused(o) and o.code == 'FRESHNESS_NO_SOURCES'
          and o.evidence['cause'] == Cause.EMPTY_INPUT.value, _desc(o))
    o = CH.check_freshness(CUT, {'injuries': {'retrieved_at': '2026-09-21T17:00:00Z'}})
    check('  negative control: one family is MEASURED (PASS, or refused for its own reason '
          'such as an uncertified requirement), never non-evidentiary',
          not o.non_evidentiary and (o.evidence or {}).get('n_families') == 1, _desc(o))


def test_07_role_state_gate_over_nobody():
    print('\n7. universe.role_state.assert_role_state_supported')
    from nfl.production.universe import role_state as RS
    o = RS.assert_role_state_supported([], publishable_ids={'A'})
    observe('nfl.production.universe.role_state:assert_role_state_supported:'
            'ROLE_STATE_EMPTY_INPUT', o)
    check('positive control: no role row is refused, not SUPPORTED_FOR_PUBLISHABLE_SET',
          refused(o) and o.code == 'ROLE_STATE_EMPTY_INPUT', _desc(o))
    o = RS.assert_role_state_supported([_role_row()], publishable_ids=set())
    observe('nfl.production.universe.role_state:assert_role_state_supported:'
            'PUBLISHABLE_SET_EMPTY', o)
    check('positive control: an explicitly empty publishable set certifies nobody -> refused',
          refused(o) and o.code == 'PUBLISHABLE_SET_EMPTY', _desc(o))
    o = RS.assert_role_state_supported([_role_row()], publishable_ids={'A'})
    check('  negative control: one supported player in a one-man set PASSES',
          o.state is State.PASS and o.code == 'ROLE_STATE_SUPPORTED_FOR_PUBLISHABLE_SET'
          and o.value['n_publishable'] == 1, _desc(o))
    bad = _role_row()
    bad['role_support'] = RS.ROLE_UNSUPPORTED
    bad['role_unsupported_why'] = ['no measured participation']
    o = RS.assert_role_state_supported([bad], publishable_ids={'A'})
    check('  and an unsupported player in the set is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'ROLE_UNSUPPORTED_PLAYER_IN_PUBLISHABLE_SET', _desc(o))
    o = RS.assert_role_state_supported([_role_row()])
    check('  and no declared set at all is NO_PUBLISHABLE_SET_DECLARED (GOVERNANCE)',
          o.state is State.BLOCKED and o.code == 'NO_PUBLISHABLE_SET_DECLARED'
          and not o.non_evidentiary, _desc(o))


# ================================================================ non-QB production layer
def test_08_publishable_gate_over_no_layer_outcomes():
    print('\n8. nonqb.layers.assert_publishable')
    from nfl.production.nonqb import layers as LY
    o = LY.assert_publishable()
    observe('nfl.production.nonqb.layers:assert_publishable:NO_TEST_ONLY_DATA_EMPTY_INPUT', o)
    check('positive control: a gate handed no layer outcome is refused, not NO_TEST_ONLY_DATA',
          refused(o) and o.code == 'NO_TEST_ONLY_DATA_EMPTY_INPUT', _desc(o))
    o = LY.assert_publishable(Outcome.ok('X', value=1))
    check('  negative control: one clean layer outcome PASSES with n_measured=1',
          o.state is State.PASS and o.evidence['n_measured'] == 1, _desc(o))
    o = LY.assert_publishable(Outcome.ok('X', value=1, test_only=True))
    check('  and a TEST-ONLY fixture is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'TEST_ONLY_DATA_IN_PRODUCTION_PATH', _desc(o))


def test_09_point_in_time_over_no_rows():
    print('\n9. nonqb.current_season_evidence.assert_pit')
    from nfl.production.nonqb import current_season_evidence as CSE
    o = CSE.assert_pit([], before_week=3)
    observe('nfl.production.nonqb.current_season_evidence:assert_pit:'
            'CURRENT_SEASON_EVIDENCE_PIT_EMPTY_INPUT', o)
    check('positive control: no usage row is refused, not IS_POINT_IN_TIME',
          refused(o) and o.code == 'CURRENT_SEASON_EVIDENCE_PIT_EMPTY_INPUT'
          and o.evidence['n_rows'] == 0, _desc(o))
    o = CSE.assert_pit([(1, 'NYG', 'Y'), (2, 'NYG', 'Y')], before_week=3)
    check('  negative control: two weeks strictly before the forecast week PASS',
          o.state is State.PASS and o.value['max_week_used'] == 2, _desc(o))
    o = CSE.assert_pit([(3, 'NYG', 'Y')], before_week=3)
    check('  and a leaked week is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD', _desc(o))


def test_10_nonqb_accounting_over_zero_cells():
    print('\n10. nonqb.accounting.reconcile_nonqb')
    from nfl.production.nonqb import accounting as ACC
    z = np.zeros((0, 0))
    o = ACC.reconcile_nonqb(z, z, z, z, z, [], [])
    observe('nfl.production.nonqb.accounting:reconcile_nonqb:NONQB_ACCOUNTING_VACUOUS', o)
    check('positive control: an empty draw set is BLOCKED/EMPTY_INPUT (was a FAIL), never OK',
          refused(o) and o.code == 'NONQB_ACCOUNTING_VACUOUS'
          and o.evidence['n_cells_checked'] == 0, _desc(o))
    S = np.array([[.5, .5, .5], [.3, .3, .3]])
    O = np.array([[.2, .2, .2]])
    V = np.array([[10., 10., 10.]])
    o = ACC.reconcile_nonqb(S, O, V, S * V, np.ones_like(S), [0], [2])
    check('  negative control: six coherent cells in one group are OK',
          o.state is State.PASS and o.evidence['n_cells_checked'] == 6, _desc(o))
    o = ACC.reconcile_nonqb(S, O + 0.5, V, S * V, np.ones_like(S), [0], [2])
    check('  and a broken simplex is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'NONQB_DRAW_ACCOUNTING_VIOLATED', _desc(o))


def test_11_rushing_accounting_over_zero_cells():
    print('\n11. nonqb.accounting.reconcile_rushing')
    from nfl.production.nonqb import accounting as ACC
    z = np.zeros((0, 0))
    o = ACC.reconcile_rushing(z, z, z, z, [], [])
    observe('nfl.production.nonqb.accounting:reconcile_rushing:NONQB_ACCOUNTING_VACUOUS', o)
    check('positive control: an empty carry draw set is BLOCKED/EMPTY_INPUT, never OK',
          refused(o) and o.code == 'NONQB_ACCOUNTING_VACUOUS', _desc(o))
    S = np.array([[.6, .6], [.3, .3]])
    O = np.array([[.1, .1]])
    V = np.array([[20., 20.]])
    o = ACC.reconcile_rushing(S, O, V, S * V, [0], [2])
    check('  negative control: four coherent carry cells are OK',
          o.state is State.PASS and o.evidence['n_cells_checked'] == 4, _desc(o))


def test_12_qb_carry_containment_over_zero_draws():
    print('\n12. nonqb.accounting.assert_no_double_counted_qb_carries')
    from nfl.production.nonqb import accounting as ACC
    o = ACC.assert_no_double_counted_qb_carries(
        np.zeros((2, 0)), np.zeros((1, 0)), np.zeros((1, 0)), np.zeros((1, 0)))
    observe('nfl.production.nonqb.accounting:assert_no_double_counted_qb_carries:'
            'QB_CARRY_CONTAINMENT_EMPTY_INPUT', o)
    check('positive control: zero draws is refused rather than reporting a NaN excess as '
          'MEASURED', refused(o) and o.code == 'QB_CARRY_CONTAINMENT_EMPTY_INPUT'
          and o.evidence['n_measured'] == 0, _desc(o))
    m = 5
    rb, team = np.full((2, m), 9.0), np.full((1, m), 27.0)
    o = ACC.assert_no_double_counted_qb_carries(rb, 0.2 * team, team, np.full((1, m), 5.0))
    check(f'  negative control: {m} draws are MEASURED with n_measured={m}',
          o.state is State.PASS and o.code == 'QB_CARRY_CONTAINMENT_MEASURED'
          and o.evidence['n_measured'] == m and np.isfinite(o.value['mean_excess_if_summed']),
          _desc(o))


def test_13_role_ordering_over_no_pairs():
    print('\n13. nonqb.role_invariants.check')
    from nfl.production.nonqb import role_invariants as RI
    o = RI.check({}, {}, n_draws=100, teams={}, label='nothing')
    observe('nfl.production.nonqb.role_invariants:check:ROLE_ORDERING_INPUT_INCOMPLETE', o)
    check('positive control: no probabilities is BLOCKED/EMPTY_INPUT (was a FAIL)',
          refused(o) and o.code == RI.CODE_INPUT and o.evidence['n_players'] == 0, _desc(o))
    o = RI.check({'buf': 0.37, 'det': 0.05}, {'buf': (3, 'RB'), 'det': (4, 'RB')},
                 n_draws=100, teams={'buf': 'BUF', 'det': 'DET'}, label='two clubs')
    observe('nfl.production.nonqb.role_invariants:check:ROLE_ORDERING_NO_COMPARABLE_PAIRS', o)
    check('positive control: ranks from two clubs form no pair -> refused, not CONSISTENT',
          refused(o) and o.code == RI.CODE_NO_PAIRS and o.evidence['n_ordered_pairs'] == 0,
          _desc(o))
    depth = {'a': (1, 'RB'), 'b': (2, 'RB')}
    teams = {'a': 'BUF', 'b': 'BUF'}
    o = RI.check({'a': 0.10, 'b': 0.30}, depth, n_draws=100, teams=teams, label='one room')
    check('  negative control: one ordered pair in one room, no inversion, is CONSISTENT',
          o.state is State.PASS and o.code == RI.CODE_OK and o.evidence['n_ordered_pairs'] == 1,
          _desc(o))
    o = RI.check({'a': 0.60, 'b': 0.20}, depth, n_draws=100, teams=teams, label='inverted')
    check('  and a real inversion is a TRUE FAIL', o.state is State.FAIL
          and o.code == RI.CODE_INVERSION, _desc(o))
    o = RI.check({'a': 0.1}, {'a': (1, 'RB')}, n_draws=100, teams={}, label='no club')
    check('  and a ranked player with no club is a TRUE FAIL under CODE_INPUT, distinct '
          'from the empty refusal', o.state is State.FAIL and o.code == RI.CODE_INPUT
          and not o.non_evidentiary, _desc(o))


def test_14_stale_label_scan_over_no_file():
    print('\n14. nonqb.eligibility.assert_no_stale_labels')
    from nfl.production.nonqb import eligibility as EL
    o = EL.assert_no_stale_labels([_REPO / 'nfl/production/DOES_NOT_EXIST.py'])
    observe('nfl.production.nonqb.eligibility:assert_no_stale_labels:'
            'NO_STALE_GOVERNANCE_LABELS_EMPTY_INPUT', o)
    check('positive control: a path list whose file does not exist scanned nothing and is '
          'refused, not NO_STALE_GOVERNANCE_LABELS', refused(o)
          and o.code == 'NO_STALE_GOVERNANCE_LABELS_EMPTY_INPUT'
          and o.evidence['n_files_scanned'] == 0, _desc(o))
    o = EL.assert_no_stale_labels()
    check('  negative control: the real run_forecast.py is scanned (PASS or a true FAIL) with '
          'a positive line count', not o.non_evidentiary and o.state in (State.PASS, State.FAIL)
          and (o.state is State.FAIL or o.evidence['n_measured'] > 0), _desc(o))


def test_15_implementation_claims_over_no_layers():
    print('\n15. nonqb.eligibility.assert_implementations_exist')
    from nfl.production.nonqb import eligibility as EL
    saved = dict(EL.IMPLEMENTATION)
    try:
        EL.IMPLEMENTATION.clear()
        o = EL.assert_implementations_exist()
        observe('nfl.production.nonqb.eligibility:assert_implementations_exist:'
                'IMPLEMENTATIONS_PRESENT_EMPTY_INPUT', o)
        check('positive control: a table with no layer imported nothing and is refused, not '
              'IMPLEMENTATIONS_PRESENT', refused(o)
              and o.code == 'IMPLEMENTATIONS_PRESENT_EMPTY_INPUT', _desc(o))
    finally:
        EL.IMPLEMENTATION.clear()
        EL.IMPLEMENTATION.update(saved)
    o = EL.assert_implementations_exist()
    check('  negative control: the real table imports its claimed modules and PASSES with '
          'n_measured>0', o.state is State.PASS and o.evidence['n_measured'] > 0, _desc(o))


def test_16_game_readiness_over_no_games():
    print('\n16. nonqb.readiness.game_readiness')
    from nfl.production.nonqb import readiness as RD
    g = RD.game_readiness(2026, 1, games=[], written_at='2026-09-01T00:00:00Z')
    observe('nfl.production.nonqb.readiness:game_readiness:GAME_READINESS_NOT_EXECUTED', g)
    check('positive control: an empty game list is GAME_READINESS_NOT_EXECUTED with cause '
          'EMPTY_INPUT and n_games=0, never a slate with nothing blocking',
          g.get('state') == 'GAME_READINESS_NOT_EXECUTED' and g.get('cause') == 'EMPTY_INPUT'
          and g['n_games'] == 0 and g['n_executable'] == 0, str(g)[:200])
    from nfl.capture import coverage as C
    p = C.load_week_plan(2026, 1)
    if p.state is not State.PASS:
        check('  negative control needs the 2026 week-1 plan on disk: it did not load, so '
              'this control is NOT_EXECUTED here (named, not passed)', False, _desc(p))
        return
    c = sorted(p.value, key=lambda x: x.game_id)[0]
    g = RD.game_readiness(2026, 1, games=[(c.game_id, c.kickoff_utc)])
    check(f'  negative control: one real game ({c.game_id}) is judged, with a declared state',
          g.get('state') is None and g['n_games'] == 1
          and g['games'][0]['state'] in RD.GAME_STATES, str(g.get('state_counts')))


# ================================================================ review layer
def test_17_review_gate_over_no_dossiers_is_a_proposal_not_a_patch():
    print('\n17. review.gate.evaluate -- PROTECTED path: proposed, not applied')
    # nfl/production/review/gate.py is in contracts.PROTECTED_PATHS (propose only). The rule-1
    # repair for "zero dossiers and no conflict -> PLAYER_REVIEW_PASS" is recorded as a patch for
    # the owner at coordination/EVIDENCE/proposals/2026-10-02_review_gate_rule1.patch and in
    # docs/AGENT_OUTBOX.md. Until ratified the defect stands, and this check says so by name
    # rather than pretending the gate refuses.
    from nfl.production.review import gate as G
    from coordination.orchestrator import contracts as C
    check('review/gate.py is a PROTECTED path, so an agent may not patch it',
          any('nfl/production/review/gate.py' == x for x in C.PROTECTED_PATHS))
    prop = _REPO / 'coordination/EVIDENCE/proposals/2026-10-02_review_gate_rule1.patch'
    check('  the proposed patch exists and names PLAYER_REVIEW_NO_DOSSIERS',
          prop.exists() and 'PLAYER_REVIEW_NO_DOSSIERS' in prop.read_text(), str(prop))
    rep = {'conflicts': [], 'projection_source': {'digests': {}}, 'coverage': {}}
    o = G.evaluate(rep)
    check('  KNOWN DEFECT, OWNER-GATED: today a report with no dossier and no conflict still '
          'returns PLAYER_REVIEW_PASS (this check flips when the owner applies the proposal)',
          o.state is State.PASS and o.code == 'PLAYER_REVIEW_PASS', _desc(o))


def test_18_review_completeness_over_no_dossiers():
    print('\n18. review.slate_report.assert_player_review_complete')
    from nfl.production.review import slate_report as SR
    o = SR.assert_player_review_complete({})
    observe('nfl.production.review.slate_report:assert_player_review_complete:'
            'PLAYER_REVIEW_COMPLETE_EMPTY_INPUT', o)
    check('positive control: an empty report is refused, never PLAYER_REVIEW_COMPLETE',
          refused(o) and o.code == 'PLAYER_REVIEW_COMPLETE_EMPTY_INPUT'
          and o.evidence['n_universe'] == 0, _desc(o))
    o = SR.assert_player_review_complete(
        {'coverage': {'n_universe': 0, 'n_publishable': 0, 'publishable_coverage': 0.0,
                      'publishable_without_dossier': []}, 'conflicts': []})
    check('  and a report that says it covered zero players is the same refusal',
          refused(o) and o.code == 'PLAYER_REVIEW_COMPLETE_EMPTY_INPUT', _desc(o))
    rep = {'coverage': {'n_universe': 1, 'n_publishable': 1, 'publishable_coverage': 1.0,
                        'publishable_without_dossier': []}, 'conflicts': []}
    o = SR.assert_player_review_complete(rep)
    check('  negative control: one reviewed player with no missing dossier is COMPLETE',
          o.state is State.PASS and o.code == 'PLAYER_REVIEW_COMPLETE', _desc(o))
    rep['coverage']['publishable_without_dossier'] = ['GHOST']
    o = SR.assert_player_review_complete(rep)
    check('  and a publishable player with no dossier is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'PLAYER_REVIEW_INCOMPLETE', _desc(o))


# ================================================================ product layer
def _temp_board(t, players):
    t = pathlib.Path(t)
    raw = b'not-a-real-npz-but-bytes-that-hash'
    (t / 'player_draws.npz').write_bytes(raw)
    (t / 'board.json').write_text(json.dumps({
        'run_id': 'r', 'game_id': 'g', 'players': players, 'n_players': len(players),
        'draws_sha256': hashlib.sha256(raw).hexdigest(), 'draw_content_digest': 'd'}))
    (t / 'player_draws_manifest.json').write_text(json.dumps({
        'run_id': 'r', 'game_id': 'g', 'content_digest': 'd',
        'layers': {'receiving': {'row_axis': 'gsis_id',
                                 'row_ids': [p['gsis_id'] for p in players] or ['A']}}}))
    return t


def test_19_quality_gates_evaluate_with_zero_findings():
    print('\n19. product.quality_gates.evaluate')
    from nfl.product import quality_gates as QG
    saved = (QG._HARD_GATES, QG._SOFT_GATES, QG.gate_authoritative_inactive)
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        np.savez(t / 'player_draws.npz', **{'receiving__targets': np.zeros((1, 4))})
        (t / 'board.json').write_text(json.dumps({'run_id': 'r', 'game_id': 'g',
                                                  'players': [{'gsis_id': 'A'}]}))
        (t / 'player_draws_manifest.json').write_text(json.dumps({
            'run_id': 'r', 'layers': {'receiving': {'row_axis': 'gsis_id', 'row_ids': ['A']}}}))
        try:
            # Drive the detector: a gate set that produces no finding at all. The real
            # gates cannot be made to return nothing over a loadable board (each emits
            # INSUFFICIENT_EVIDENCE rather than silence), so the gate tuple is emptied
            # for this one call, the same way test_non_evidentiary_refusal empties
            # verdict.GATE_SCOPE to reach PRODUCT_VERDICT_EMPTY_INPUT.
            QG._HARD_GATES, QG._SOFT_GATES = (), ()
            QG.gate_authoritative_inactive = lambda *a, **k: []
            o = QG.evaluate(t)
            observe('nfl.product.quality_gates:evaluate:QUALITY_GATES_EVALUATED_NOTHING', o)
            check('positive control: zero findings is BLOCKED/EMPTY_INPUT under '
                  'QUALITY_GATES_EVALUATED_NOTHING (was a FAIL), never EVALUATED',
                  refused(o) and o.code == 'QUALITY_GATES_EVALUATED_NOTHING'
                  and o.evidence['n_findings'] == 0, _desc(o))
        finally:
            QG._HARD_GATES, QG._SOFT_GATES, QG.gate_authoritative_inactive = saved
        o = QG.evaluate(t)
        check('  negative control: the real gates over the same board EVALUATE with findings, '
              'and the verdict is INSUFFICIENT_EVIDENCE (no inactive list), not PRELIMINARY',
              o.state is State.PASS and o.code == 'QUALITY_GATES_EVALUATED'
              and o.evidence['verdict']['counts']['findings'] > 0
              and o.evidence['verdict']['board_state'] != QG.PRELIMINARY, _desc(o))


def test_20_quality_verdict_over_no_findings():
    print('\n20. product.quality_gates.verdict')
    from nfl.product import quality_gates as QG
    v = QG.verdict([])
    observe('nfl.product.quality_gates:verdict:QUALITY_VERDICT_EMPTY_INPUT', v)
    check('positive control: a verdict composed over zero findings is '
          'QUALITY_VERDICT_EMPTY_INPUT / EMPTY_INPUT and the board is WITHHELD, not PRELIMINARY',
          v.get('state') == 'QUALITY_VERDICT_EMPTY_INPUT' and v.get('cause') == 'EMPTY_INPUT'
          and v['board_state'] == QG.WITHHELD and v['counts']['findings'] == 0, str(v)[:200])
    f = QG._finding(next(iter(QG.GATES)), QG.ROW, 'A/x', 'PASS', 'fine')
    v = QG.verdict([f])
    check('  negative control: one evaluated, non-firing HARD finding composes PRELIMINARY',
          v['board_state'] == QG.PRELIMINARY and v.get('state') is None
          and v['counts']['findings'] == 1, str(v.get('board_state')))
    f = QG._finding(next(iter(QG.GATES)), QG.ROW, 'A/x', QG.FIRED, 'bad')
    v = QG.verdict([f])
    check('  and one FIRED finding is a true WITHHELD with the gate named',
          v['board_state'] == QG.WITHHELD and v.get('cause') is None
          and v['counts']['hard_fired'] == 1, str(v.get('hard_fired'))[:120])


def test_21_ranking_admission_with_no_health_row():
    print('\n21. product.model_health.assert_ranking_admissible')
    from nfl.product import model_health as MH
    rows = [{'metric': 'rushing/carries', 'delta': 40.0}]
    kept, blocked = MH.assert_ranking_admissible(rows, [])
    flag = blocked[0]['blocked_by_health'][0] if blocked else 'KEPT'
    observe('nfl.product.model_health:assert_ranking_admissible:HEALTH_NOT_MEASURED', flag)
    check('positive control: an empty health table admits nobody; the row leaves the ranking '
          'as HEALTH_NOT_MEASURED with cause EMPTY_INPUT', kept == [] and len(blocked) == 1
          and flag == MH.HEALTH_NOT_MEASURED and blocked[0]['blocked_cause'] == 'EMPTY_INPUT',
          f'kept={kept} blocked={blocked}')
    health = [{'metric': 'receiving/targets', 'ranking_eligible': True, 'warnings': []}]
    kept, blocked = MH.assert_ranking_admissible(rows, health)
    check('  and a metric absent from a non-empty health table is blocked the same way',
          kept == [] and blocked and blocked[0]['blocked_by_health'] == [MH.HEALTH_NOT_MEASURED],
          f'kept={kept}')
    health = [{'metric': 'rushing/carries', 'ranking_eligible': True, 'warnings': []}]
    kept, blocked = MH.assert_ranking_admissible(rows, health)
    check('  negative control: a measured, eligible metric is KEPT', len(kept) == 1
          and blocked == [], f'kept={kept} blocked={blocked}')
    health = [{'metric': 'rushing/carries', 'ranking_eligible': False,
               'warnings': ['DIRECTIONAL_SKEW']}]
    kept, blocked = MH.assert_ranking_admissible(rows, health)
    check('  and a measured warning blocks with the WARNING named, not the absence',
          kept == [] and blocked[0]['blocked_by_health'] == ['DIRECTIONAL_SKEW']
          and 'blocked_cause' not in blocked[0], f'blocked={blocked}')


def test_22_single_version_board_over_no_rows():
    print('\n22. product.board_pointer._no_mixed_versions')
    from nfl.product import board_pointer as BP
    with tempfile.TemporaryDirectory() as t:
        d = _temp_board(t, [])
        o = BP._no_mixed_versions(d)
        observe('nfl.product.board_pointer:_no_mixed_versions:SINGLE_VERSION_BOARD_EMPTY_INPUT', o)
        check('positive control: a board with zero player rows is refused, not SINGLE_VERSION',
              refused(o) and o.code == 'SINGLE_VERSION_BOARD_EMPTY_INPUT'
              and o.evidence['n_players'] == 0, _desc(o))
    with tempfile.TemporaryDirectory() as t:
        d = _temp_board(t, [{'gsis_id': 'A'}])
        o = BP._no_mixed_versions(d)
        check('  negative control: one row joined to one manifest of one run is SINGLE_VERSION',
              o.state is State.PASS and o.code == 'SINGLE_VERSION_BOARD'
              and o.evidence['n_players'] == 1, _desc(o))
        man = json.loads((d / 'player_draws_manifest.json').read_text())
        man['run_id'] = 'other'
        (d / 'player_draws_manifest.json').write_text(json.dumps(man))
        o = BP._no_mixed_versions(d)
        check('  and a manifest from another run is a TRUE FAIL', o.state is State.FAIL
              and o.code == 'MIXED_VERSION_ROWS', _desc(o))


def test_99_quality_gates_with_no_board_to_evaluate():
    print('\n99. product.quality_gates.evaluate over a board directory that does not exist')
    import tempfile as _tf
    from nfl.product import quality_gates as QG
    o = QG.evaluate(pathlib.Path(_tf.mkdtemp()) / 'no_such_board')
    observe('nfl.product.quality_gates:evaluate:QUALITY_GATES_INPUT_MISSING', o)
    check('positive control: a missing board is BLOCKED QUALITY_GATES_INPUT_MISSING, never EVALUATED',
          o.state is State.BLOCKED and o.code == 'QUALITY_GATES_INPUT_MISSING', _desc(o))
    check('  negative control: the live board evaluation is driven by test_quality_gates', True)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items()
                           if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)

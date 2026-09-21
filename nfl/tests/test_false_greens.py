"""The five false-green paths found in dd2ca76, each pinned so it cannot return.

Every one of these was a gate that returned PASS while the property it is
named after was not established. They are grouped here rather than scattered
across the modules they came from, because the FAILURE MODE is the same in all
five and a reader who finds one should see the other four beside it.

  1. A freshness gate that tested whether an age could be CALCULATED.
  2. An artifact that claimed an information cut it had not reached.
  3. A tolerance supplied by the caller who wanted to pass it.
  4. A gate whose test population was built out of the answer.
  5. Conservation read as validity: the shares summed, so the allocation was
     called good.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import verdict as V                            # noqa: E402
from nfl.production.universe import allocation as AL               # noqa: E402
from nfl.production.universe import chronology as CH               # noqa: E402
from nfl.production.universe import governed_thresholds as GT      # noqa: E402
from nfl.production.universe import participation as PA            # noqa: E402
from nfl.production.universe import player_universe as PU          # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.universe import support_state as S             # noqa: E402
from nfl.production.universe import usage_vintage as UV            # noqa: E402
from nfl.prospective import artifact as ART                        # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T19:02:49Z'
GAME = '2026_02_NYG_LA'
RAN = '2026-09-21T19:05:49Z'
_C = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _ctx():
    if 'uni' not in _C:
        _C['uni'] = PU.build(2026, 2, GAME, CUT)
        u = UV.usage_season(2026, CUT, before_week=2)
        _C['usage'] = u.value if u.state is State.PASS else {}
        _C['role'] = RS.assign(_C['uni'].value, season=2026, week=2,
                               usage_rows=_C['usage'])
        s = RS.load_snaps(2026, 2)
        b = PA.measure_budget(s.value)
        _C['part'] = PA.assess(_C['role'].value, budget=b.value)
    return _C


# --- 1. FRESHNESS ----------------------------------------------------------
def test_freshness_tests_freshness_and_not_the_existence_of_a_clock():
    src_fresh = {'injuries': {'retrieved_at': '2026-09-21T18:00:00Z'}}
    src_stale = {'injuries': {'retrieved_at': '2026-09-20T16:07:00Z'}}
    src_none = {'injuries': {'retrieved_at': None}}
    src_future = {'injuries': {'retrieved_at': '2026-09-21T23:00:00Z'}}
    src_unknown_family = {'transactions': {'retrieved_at':
                                           '2026-09-21T18:00:00Z'}}

    stale = CH.check_freshness(CUT, src_stale)
    ok(stale.state is State.FAIL,
       f'a 27-hour injury capture FAILS against a 6-hour requirement: '
       f'{stale.state.name}[{stale.code}]')
    row = stale.evidence['families'][0]
    ok(row['state'] == CH.STALE and row['age_hours'] > 24,
       f'and is named STALE with its measured age: {row["age_hours"]:.2f}h')

    fut = CH.check_freshness(CUT, src_future)
    ok(fut.state is State.FAIL
       and fut.evidence['families'][0]['state'] == CH.FUTURE_DATED,
       'a capture retrieved after the cut is FUTURE_DATED, which is worse '
       'than stale rather than fresher')

    unk = CH.check_freshness(CUT, src_none)
    ok(unk.state is not State.PASS
       and unk.evidence['families'][0]['state'] == CH.AGE_UNKNOWN,
       'an uncalculable age does not pass -- which is the exact inversion of '
       'the defect, where a calculable age DID pass')

    nofam = CH.check_freshness(CUT, src_unknown_family)
    ok(nofam.state is not State.PASS
       and nofam.evidence['families'][0]['state'] == CH.NO_REQUIREMENT,
       'a family with no governed requirement cannot be certified fresh; '
       'absence refuses rather than passes')

    # AND THE PART THAT MATTERS MOST: being inside the requirement is not
    # enough while the requirement itself is only CANDIDATE.
    fresh = CH.check_freshness(CUT, src_fresh)
    ok(fresh.state is not State.PASS,
       f'a capture well inside its proposed maximum still does not certify, '
       f'because the maximum is CANDIDATE: {fresh.code}')
    r = fresh.evidence['families'][0]
    ok(r['state'] == CH.REQUIREMENT_UNCERTIFIED
       and r['within_candidate_requirement'] is True,
       'the row separates "within the proposed requirement" from "certified '
       'fresh", which are different claims')
    ok(GT.freshness_requirement('injuries')['max_age_hours'] == 6.0,
       'the requirement is a real number, not a placeholder')
    ok(CH.check_freshness(CUT, {}).state is State.BLOCKED,
       'an empty source set is not a passing check')


# --- 2. CHRONOLOGY ---------------------------------------------------------
def test_a_run_cannot_claim_a_cut_it_has_not_reached():
    # The exact numbers from the committed artifact.
    bad = CH.certify('2026-09-21T19:52:00Z', '2026-09-21T18:44:48Z')
    ok(bad.state is State.BLOCKED and bad.code == 'CHRONOLOGY_VIOLATED',
       f'the dd2ca76 artifact\'s own timestamps are refused: {bad.code}')
    v = bad.evidence['violations'][0]
    ok(v['kind'] == 'CUT_AFTER_RUN' and v['seconds_into_the_future'] > 4000,
       f'and the violation is named with its size: '
       f'{v["seconds_into_the_future"]:.0f}s into the future')

    good = CH.certify(CUT, RAN)
    ok(good.state is State.PASS and good.code == 'CHRONOLOGY_CERTIFIED',
       f'a cut before its run certifies: {good.code}')
    ok(good.value['cut_is_before_run_by_seconds'] > 0,
       'and the certificate carries the margin')
    ok(len(good.value['invariants_asserted']) == 3,
       'three invariants are asserted by name, not implied')

    after = CH.certify(CUT, RAN, sources={
        'injuries': {'retrieved_at': '2026-09-21T20:00:00Z'}})
    ok(after.state is State.BLOCKED
       and after.evidence['violations'][0]['kind'] == 'VINTAGE_AFTER_CUT',
       'a vintage retrieved after the cut is evidence the run was not '
       'entitled to see, and blocks')
    pub = CH.certify(CUT, RAN, sources={
        'depth_charts': {'retrieved_at': '2026-09-21T18:00:00Z',
                         'published_at': '2026-09-21T21:00:00Z'}})
    ok(pub.state is State.BLOCKED,
       'the publication clock is checked too, not only retrieval')
    ok(CH.certify('nonsense', RAN).state is State.BLOCKED,
       'an unreadable clock blocks rather than being skipped')

    # The real run, end to end.
    c = _ctx()
    live = CH.certify(CUT, RAN, sources=c['uni'].evidence['sources'])
    ok(live.state is State.PASS,
       f'the corrected Monday chain certifies: {live.code}')


# --- 3. TOLERANCE ----------------------------------------------------------
def test_the_caller_does_not_get_to_set_what_passes():
    c = _ctx()
    po = c['part']
    rows = po.value or (po.evidence or {}).get('value') or []
    alloc = {r['gsis_id'] for r in rows
             if r['participation_state'] == PA.RESOLVED}
    g = PA.assert_participation_supports_allocation(
        po, allocating_ids=alloc, max_unresolved_fraction=0.25)
    ok(g.state is not State.PASS,
       f'the 25% figure that passed this board on 2026-09-21 no longer does: '
       f'{g.state.name}[{g.code}]')
    ok(g.evidence.get('applied_max_unresolved_fraction') == 0.05,
       f'the governed 5% applied instead: '
       f'{g.evidence.get("applied_max_unresolved_fraction")}')
    ok(g.evidence.get('caller_proposal_was_not_applied') is True,
       'and the outcome says the caller\'s number was not used')
    ok(GT.summary()['n_production_certified'] == 0,
       'no threshold anywhere in the system is production-certified')
    for item in GT.summary()['items']:
        ok(item['certification'] in GT.CERTIFICATION_STATES,
           f'{item["name"]} carries a declared certification state: '
           f'{item["certification"]}')


# --- 4. POPULATION ---------------------------------------------------------
def test_the_gate_population_is_not_built_from_the_answer():
    c = _ctx()
    uni, ro = c['uni'], c['role']
    pop = RS.downstream_population(uni.value)
    ok(pop, f'the universe defines a population: {len(pop)} player(s)')

    # It is defined WITHOUT role: every member is justified by support_state
    # and position alone.
    by_id = {r['gsis_id']: r for r in uni.value}
    ok(all(by_id[p]['support_state'] in S.EXPECTED_TO_PLAY for p in pop),
       'every member is there because the universe expects him to play')
    unsupported = {r['gsis_id'] for r in ro.value
                   if r['role_support'] == RS.ROLE_UNSUPPORTED}
    ok(unsupported & pop,
       f'and role-unsupported players are INSIDE it, not filtered out first: '
       f'{len(unsupported & pop)} of {len(unsupported)}')

    # The old, self-selecting population.
    old = {r['gsis_id'] for r in ro.value
           if r['role_support'] == RS.ROLE_SUPPORTED
           and r['role'] in RS.WORKLOAD_BEARING}
    ok(not (old & unsupported),
       'the old population contained no unsupported player by construction, '
       'which is why it always passed')
    ok(len(pop) > len(old),
       f'the independent population is larger: {len(pop)} vs {len(old)}')

    g_old = RS.assert_role_state_supported(ro.value, publishable_ids=old)
    g_new = RS.assert_role_state_supported(ro.value, universe_rows=uni.value)
    ok(g_old.state is State.PASS,
       'the self-selected population passes, as it always did')
    ok(g_new.state is State.FAIL,
       f'the independent population does not: {g_new.code}')
    ok(g_new.evidence['population_source']
       == 'player_universe.EXPECTED_TO_PLAY_in_a_room',
       'and the outcome records where the population came from')
    ok(len(g_new.evidence['offending']) == len(unsupported & pop),
       f'every unsupported player in the population is named: '
       f'{len(g_new.evidence["offending"])}')

    # A caller cannot narrow it: a supplied set is folded IN, not swapped in.
    g_both = RS.assert_role_state_supported(
        ro.value, publishable_ids=old, universe_rows=uni.value)
    ok(g_both.state is State.FAIL,
       'passing the old narrow set alongside the universe cannot rescue it')
    ok(RS.assert_role_state_supported(ro.value).state is State.BLOCKED,
       'supplying neither blocks rather than certifying nothing')


# --- 5. CONSERVATION IS NOT VALIDITY ---------------------------------------
def test_conservation_does_not_certify_where_the_mass_went():
    c = _ctx()
    for room in (RS.ROOM_CARRIES, RS.ROOM_TARGETS):
        ao = AL.allocate(c['part'], c['usage'], room=room)
        cons = AL.assert_allocation_conserves(
            ao, consuming_ids={r['gsis_id'] for r in ao.value
                               if r['allocation_state'] == AL.ALLOCATED})
        red = AL.assert_redistribution_supported(ao)
        ok(cons.state is State.PASS,
           f'{room}: the shares still conserve, which is true and is not '
           f'enough')
        ok(red.state is State.BLOCKED
           and red.code == 'REDISTRIBUTION_UNSUPPORTED',
           f'{room}: and the separate gate refuses, because no model says '
           f'where the reassigned mass went: {red.code}')
        off = red.evidence['offending']
        ok(off, f'{room}: the offending clubs are named: '
                f'{[o["club"] for o in off]}')
        for o in off:
            top = o['players_whose_share_the_assumption_inflates'][0]
            ok(top['renormalised_share'] > top['measured_share'],
               f'{o["club"]} {room}: the most inflated player is named with '
               f'both numbers -- {top["display_name"]} '
               f'{top["measured_share"]:.1%} -> '
               f'{top["renormalised_share"]:.1%}')
            ok(abs(o['reassigned_mass']) > 0,
               f'{o["club"]} {room}: with the mass that moved '
               f'({o["reassigned_mass"]:+.1%})')

    ok(GT.REDISTRIBUTION_MODEL['model'] is None,
       'there is no redistribution model, and the registry says so')
    ok(GT.REDISTRIBUTION_MODEL[
        'max_reassigned_fraction_without_a_model'] == 0.0,
       'so the only fraction involving no unvalidated claim is zero')


# --- 6. AND THE ONE THE FORECAST ITSELF FOUND ------------------------------
def test_the_invariant_the_forecast_emits_is_declared():
    ok('draw_contract' in ART.INVARIANTS,
       'the draw_contract invariant P0-A emits is declared in the table')
    ok('draw_contract' in ART.HARD_INVARIANTS,
       'as HARD, because it is what catches a silently absent layer')
    spec = ART.INVARIANTS['draw_contract']
    ok(spec['evaluator'].startswith('nfl.production.contracts'),
       f'and names its evaluator: {spec["evaluator"]}')
    ok('why_hard' in spec and 'artifact_sealing' in spec['why_hard'],
       'with the failure that justified it written down')


def test_the_verdict_requires_the_new_gates():
    req = set(V.required_gates('football'))
    for g in ('CHRONOLOGY_CERTIFIED', 'REDISTRIBUTION_PLAUSIBILITY',
              'DATA_FRESHNESS', 'PARTICIPATION_COMPLETENESS',
              'ROLE_PLAUSIBILITY', 'OPPORTUNITY_CONSERVATION'):
        ok(g in req, f'{g} is a required football gate')
    ok(set(V.required_gates('dfs_product')) > req,
       'and the product scopes inherit all of them')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_freshness_tests_freshness_and_not_the_existence_of_a_clock,
              test_a_run_cannot_claim_a_cut_it_has_not_reached,
              test_the_caller_does_not_get_to_set_what_passes,
              test_the_gate_population_is_not_built_from_the_answer,
              test_conservation_does_not_certify_where_the_mass_went,
              test_the_invariant_the_forecast_emits_is_declared,
              test_the_verdict_requires_the_new_gates):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())

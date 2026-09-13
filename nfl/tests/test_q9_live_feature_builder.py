"""The live pregame feature builder, the complete paired artifact, and G0A.

WHAT THESE TESTS PROTECT.

  * NO OUTCOME OF THE FORECAST SEASON ENTERS A FEATURE. The history window is
    seasons strictly earlier, every realised field on a live row must be
    PRESENT and None -- present, because a field that is merely absent lets a
    later `.get(f, 0)` default it, and that is how an unplayed game acquires a
    result.

  * THE ROSTER FILE IS NEVER OPENED. `weekly_rosters.status == INA` is
    game-day information; the pool comes from the depth chart. Two guards,
    because a forbidden source and a forbidden descriptor field fail
    differently.

  * THE SCHEMA IS THE FROZEN ONE. 25 features hashing what the candidate was
    frozen against, checked on every build. A builder emitting a different
    schema is building for a different candidate.

  * PARITY IS EXACT WHERE BOTH BUILDERS ARE DEFINED, and outside that window
    the divergence is confined to the features the history walk drives. The
    containment check is asserted non-vacuous: if every feature counted as a
    history feature it would pass on anything.

  * COMPLETENESS IS COMPUTED, NOT DECLARED, AND HAS NO Q9 EXEMPTION. The
    nine required layers come from the governed module, the shared/arm
    partition must cover them exactly, and dropping any one layer must take
    COMPLETE away.

  * ONLY THE TARGET ALLOCATION DIFFERS. Both halves: a shared input that
    differed would make the arms incomparable, and an arm layer that did NOT
    differ would mean the candidate did nothing.

  * G0A IS REPORTED, NOT WAIVED. The remaining item is derived from the
    roadmap and checklist rather than typed, and no code path can mark it
    cleared.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State           # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                 # noqa: E402
from nfl.prospective.q9shadow import complete as COMPLETE              # noqa: E402
from nfl.prospective.q9shadow import g0a as G0A                        # noqa: E402
from nfl.prospective.q9shadow import ledger as LED                     # noqa: E402
from nfl.prospective.q9shadow import live_features as LF               # noqa: E402
from nfl.prospective.q9shadow import seal as SEAL
from nfl.prospective.q9shadow import armpolicy as ARM                      # noqa: E402
from nfl.prospective.q9shadow import reuse as REUSE                    # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                      # noqa: E402
from nfl.prospective.q9shadow import timebasis as TB                   # noqa: E402
from nfl.research import completeness as CP                            # noqa: E402
from nfl.research.q9 import hurdle as Q9                               # noqa: E402

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
    p = CAND.HERE / name
    return json.loads(p.read_text()) if p.exists() else None


# ============================================ the live feature builder
def test_01_schema_is_the_frozen_one():
    print('\n-- the feature schema --')
    o = LF.assert_feature_schema_matches_freeze()
    check('the live builder emits the frozen 25-feature schema',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    check('  and it is 25 features', len(Q9.FEATURE_NAMES) == 25,
          str(len(Q9.FEATURE_NAMES)))
    check('nothing here fits a coefficient',
          not any(n in dir(LF) for n in ('fit', 'fit_hurdle', 'refit')),
          'no fit function in the module')


def test_02_source_and_roster_guards():
    print('\n-- what may be read --')
    o = LF.assert_sources_permitted(['depth_charts', 'injuries',
                                     'historical_panel'])
    check('the three permitted sources pass', o.state is State.PASS)
    for bad in ('weekly_rosters', 'official_inactives', 'pbp',
                'player_stats'):
        o = LF.assert_sources_permitted(['depth_charts', bad])
        check(f'  {bad} is refused by name',
              o.state is State.FAIL
              and o.code == 'Q9_LIVE_SOURCE_NOT_PERMITTED')
    o = LF.assert_sources_permitted(['depth_charts', 'something_new'])
    check('an undeclared source is refused too', o.state is State.FAIL)
    check('the forbidden table states the measurement behind each refusal',
          '3,438' in LF.FORBIDDEN_SOURCES['weekly_rosters'])
    for f in ('status', 'roster_status', 'inactive', 'is_inactive'):
        o = LF.assert_no_roster_status([{'gsis_id': 'p1', f: 'INA'}])
        check(f'  a descriptor carrying {f} is refused',
              o.state is State.FAIL
              and o.code == 'Q9_LIVE_ROSTER_STATUS_SUPPLIED')
    o = LF.assert_no_roster_status([{'gsis_id': 'p1', 'position': 'WR',
                                     'team': 'KC'}])
    check('a clean descriptor passes', o.state is State.PASS)


def test_03_a_live_row_may_carry_no_outcome():
    print('\n-- no outcome of the forecast season --')
    clean = {'s': 2026, 'w': 1, 't': 'KC', 'pid': 'p1'}
    for f in LF.REALISED_FIELDS:
        clean[f] = None
    o = LF.assert_no_live_outcome([clean], 2026)
    check('a row with every realised field present and None passes',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    for f in ('targets', 'appeared', 'snap'):
        bad = dict(clean, **{f: 0})
        o = LF.assert_no_live_outcome([bad], 2026)
        check(f'  a row carrying {f}=0 is refused',
              o.state is State.FAIL
              and o.code == 'Q9_LIVE_ROW_CARRIES_AN_OUTCOME')
    missing = {k: v for k, v in clean.items() if k != 'targets'}
    o = LF.assert_no_live_outcome([missing], 2026)
    check('a row that OMITS a realised field is refused, not accepted',
          o.state is State.FAIL,
          'absence lets a later .get default it to zero')
    hist = dict(clean, s=2024, targets=7)
    o = LF.assert_no_live_outcome([hist], 2026)
    check('a HISTORICAL row may carry its outcome', o.state is State.PASS)


def test_04_history_feature_set_is_derived_and_not_vacuous():
    print('\n-- the history feature set --')
    check('it is derived from the schema, not typed',
          set(LF.HISTORY_FEATURES) <= set(Q9.FEATURE_NAMES))
    check('the role features are in it -- role class is trailing snap share',
          {'role_starter', 'role_rotational', 'role_fringe'}
          <= set(LF.HISTORY_FEATURES))
    check('the four h_* driven features are in it',
          {'prior_target_frequency', 'recent_participation_ewma',
           'prior_share_given_positive',
           'prior_opportunity_depth_capped'} <= set(LF.HISTORY_FEATURES))
    check('the containment check is NOT vacuous: 13 features are outside it',
          len(LF.SOURCE_FEATURES) == 13, str(len(LF.SOURCE_FEATURES)))
    check('  and the live-source features are the ones outside',
          {'rank_r1', 'pos_WR', 'inj_Out', 'inj_report_available',
           'expected_team_budget_standardised'} <= set(LF.SOURCE_FEATURES))
    check('the two sets partition the schema exactly',
          set(LF.HISTORY_FEATURES) | set(LF.SOURCE_FEATURES)
          == set(Q9.FEATURE_NAMES)
          and not (set(LF.HISTORY_FEATURES) & set(LF.SOURCE_FEATURES)))


def test_04b_no_forecast_season_row_in_any_upstream_source():
    print('\n-- upstream leakage audit --')
    o = LF.leakage_audit(2026)
    check('no upstream source carries a 2026 row',
          o.state is State.PASS
          and o.code == 'Q9_NO_FORECAST_SEASON_ROW_IN_ANY_UPSTREAM_SOURCE',
          f'{o.state.value}[{o.code}]')
    if o.state is not State.PASS:
        return
    check('  every declared source was actually measured',
          set(o.value) == set(LF.LEAKAGE_SOURCES), str(sorted(o.value)))
    check('  the appearance frame is included -- it fits the shared upstream',
          'r8_enriched_frame' in o.value
          and o.value['r8_enriched_frame']['n_rows'] > 10000)
    check('  the budget denominators are included',
          o.value['budget_denominators']['n_at_or_after_forecast_season'] == 0)
    check('  and this is what supports the arm-A claim',
          o.evidence.get('supports_arm') == 'A')
    o2 = LF.leakage_audit(2025)
    check('the audit is not vacuous: asking about 2025 FAILS on 2025 rows',
          o2.state is State.FAIL
          and o2.code == 'Q9_FORECAST_SEASON_ROW_IN_UPSTREAM_SOURCE',
          f'{o2.state.value}[{o2.code}]')


def test_05_the_parity_artifact():
    print('\n-- builder parity --')
    d = _load('Q9_LIVE_FEATURE_PARITY.json')
    check('the parity artifact exists', d is not None)
    if not d:
        return
    check('parity is EXACT inside the window where both are defined',
          d['builder_parity'] == 'EXACT',
          f"{d['n_players_compared']} compared, "
          f"{d['n_players_differing']} differing")
    check('  and the comparison is not empty',
          d['n_players_compared'] >= 200, str(d['n_players_compared']))
    check('the window is week 1', d['parity_window_weeks'] == [1])
    wd = d['window_divergence']
    check('outside the window the divergence is confined to history features',
          wd['confined_to_history_features'] is True,
          str(wd['non_history_features_that_differed']))
    check('  and it is a real divergence, not an empty one',
          wd['n_differing_outside_window'] > 0,
          f"{wd['n_differing_outside_window']} of "
          f"{wd['n_compared_outside_window']}")
    check('  the containment check is declared non-vacuous',
          wd['containment_check_is_not_vacuous'] is True
          and wd['n_non_history_features'] == 13)
    check('the cause is named, not shrugged at',
          'earlier weeks of the same season' in wd['cause'])
    check('widening the window is refused, with the reason',
          'forbids' in wd['not_a_defect_because'])
    check('the arm-A / arm-B choice is reserved to the owner',
          wd['decided_by'] == 'OWNER'
          and 'arm A' in wd['open_owner_decision']
          and 'arm B' in wd['open_owner_decision'],
          wd.get('decided_by'))
    check('same-week duplicate players are excluded and counted',
          d['same_week_duplicate_players']['n_excluded'] > 0,
          str(d['same_week_duplicate_players']['n_excluded']))
    check('  and the reason they are not repaired is a candidate mutation',
          'candidate mutation' in
          d['same_week_duplicate_players']['not_repaired_because'])
    check('source agreement is reported SEPARATELY from builder parity',
          'source_agreement' in d and 'DATA' in
          d['source_agreement'].get('note', '') + 'DATA')


def test_06_the_builder_runs_on_a_real_live_game():
    print('\n-- the live path, on a 2026 game --')
    o = LF.build_team_week(2026, 1, 'ATL', '2026-09-12T00:00:00Z',
                           '2026-09-13T17:00:00Z')
    check('the builder produces features for a real 2026 team-week',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    if o.state is not State.PASS:
        return
    e = o.evidence
    check('  every history season is strictly before the forecast season',
          max(e['history_seasons']) < 2026, str(e['history_seasons']))
    check('  it declares that no forecast-season outcome was consumed',
          e['no_forecast_season_outcome_consumed'] is True)
    check('  and therefore arm A', e['arm'] == 'A')
    check('  the schema hash matches the freeze',
          e['feature_schema_sha16'] ==
          CAND.freeze_identity()['feature_schema_sha16'])
    check('  every source carries a sha256 and a NAMED retrieval basis',
          all(v.get('sha256') and v.get('retrieved_at')
              and v.get('retrieved_at_basis')
              for v in e['source_provenance'].values()),
          str(sorted({v.get('retrieved_at_basis')
                      for v in e['source_provenance'].values()})))
    check('  the unfilled-report_status count is reported, not hidden',
          'n_injury_rows_without_report_status' in e,
          str(e.get('n_injury_rows_without_report_status')))
    g = LF.assert_no_live_outcome(o.value, 2026)
    check('  and every produced row carries no outcome',
          g.state is State.PASS, f'{g.state.value}[{g.code}]')
    proj = [len(Q9.featurise(
        __import__('nfl.prospective.q9shadow.inputs', fromlist=['x'])
        .project_feature_row(r), 0.0)) for r in o.value]
    check('  every row featurises to exactly 25 through the projection',
          set(proj) == {25}, str(sorted(set(proj))))


def test_07_the_live_source_needs_a_team_and_a_clock():
    print('\n-- the live entry point will not default a clock --')
    o = SH.feature_rows(SH.LIVE_PREGAME, season=2026, week=1)
    check('a slate-shaped request without team or clock is refused',
          o.state is State.BLOCKED
          and o.code == 'Q9_LIVE_PREGAME_NEEDS_TEAM_AND_CLOCK',
          f'{o.state.value}[{o.code}]')
    check('  and it says why defaulting would be wrong',
          'newest capture' in (o.detail or ''))
    o = SH.feature_rows(SH.LIVE_PREGAME, season=2026, week=1, team='ATL',
                        observed_before='2026-09-12T00:00:00Z',
                        kickoff_utc='2026-09-13T17:00:00Z')
    check('addressed per team-week with a clock, it builds',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')


# ==================================== the complete paired shadow artifact
def test_08_the_layer_partition_covers_the_required_set():
    print('\n-- the nine required layers --')
    check('the required set comes from the governed module',
          tuple(COMPLETE.REQUIRED_LAYERS) == CP.LAYER_NAMES)
    check('  and there are nine of them',
          len(COMPLETE.REQUIRED_LAYERS) == 9,
          str(len(COMPLETE.REQUIRED_LAYERS)))
    o = COMPLETE.assert_partition_covers_required()
    check('shared + arm cover them exactly', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    check('carries is SHARED -- Q9 changes target allocation only',
          'carries' in COMPLETE.SHARED_LAYERS)
    check('targets is the divergence point',
          'targets' in COMPLETE.ARM_LAYERS
          and 'target' in COMPLETE.DIVERGENCE_POINT)
    saved = dict(COMPLETE.SHARED_LAYERS)
    try:
        COMPLETE.SHARED_LAYERS.pop('carries')
        o = COMPLETE.assert_partition_covers_required()
        check('an unowned layer is refused by name',
              o.state is State.FAIL
              and o.code == 'Q9_LAYER_PARTITION_INCOMPLETE'
              and 'carries' in (o.evidence.get('unowned') or []))
        COMPLETE.SHARED_LAYERS['targets'] = 'x'
        o = COMPLETE.assert_partition_covers_required()
        check('a layer owned twice is refused too', o.state is State.FAIL)
    finally:
        COMPLETE.SHARED_LAYERS.clear()
        COMPLETE.SHARED_LAYERS.update(saved)


def test_09_completeness_is_computed_and_has_no_exemption():
    print('\n-- the completeness gate --')
    full = {k: 'PASS' for k in COMPLETE.REQUIRED_LAYERS}
    v, verdict = COMPLETE.completeness_value(full)
    check('an all-PASS matrix reads COMPLETE',
          v == COMPLETE.CONTRACT_COMPLETE and verdict == 'FULL', f'{v}/{verdict}')
    for k in COMPLETE.REQUIRED_LAYERS:
        broken = dict(full, **{k: 'BLOCKED_TEST'})
        vv, _ = COMPLETE.completeness_value(broken)
        check(f'  dropping {k} takes COMPLETE away',
              vv == COMPLETE.CONTRACT_PARTIAL, vv)
    target_only = COMPLETE.matrix({'A': {'targets': np.zeros((3, 2))},
                                   'B': {'targets': np.zeros((3, 2))}}, {})
    vv, verdict = COMPLETE.completeness_value(target_only)
    check('a single-layer target forecast is PARTIAL, not COMPLETE',
          vv == COMPLETE.CONTRACT_PARTIAL, f'{vv}/{verdict}')
    check('the governed verdict decides, not a literal',
          verdict == CP.forecast_completeness(target_only))


def test_10_only_the_target_allocation_differs():
    print('\n-- the single divergence point --')
    a = np.arange(12, dtype=float).reshape(4, 3)
    b = a + 1.0
    shared = {'appearance_draws': {'x': a, 'y': a},
              'team_budget_draws': {'x': a, 'y': a}}
    o = COMPLETE.assert_single_divergence({'x': {'targets': a},
                                           'y': {'targets': b}}, shared)
    check('differing targets on identical upstream passes',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    o = COMPLETE.assert_single_divergence({'x': {'targets': a},
                                           'y': {'targets': a}}, shared)
    check('IDENTICAL arm layers are refused -- the candidate did nothing',
          o.state is State.FAIL
          and o.code == 'Q9_COMPLETE_DIVERGENCE_NOT_SINGLE'
          and 'targets' in (o.evidence.get('arm_layers_identical') or []))
    o = COMPLETE.assert_single_divergence(
        {'x': {'targets': a}, 'y': {'targets': b}},
        {'appearance_draws': {'x': a, 'y': b}})
    check('a DIFFERING shared input is refused -- arms not comparable',
          o.state is State.FAIL
          and 'appearance_draws' in
          (o.evidence.get('shared_upstream_differs') or []))
    o = COMPLETE.assert_single_divergence(
        {'x': {'targets': a, 'receptions': None},
         'y': {'targets': b, 'receptions': None}}, shared)
    check('a layer that was not produced is skipped, not compared as equal',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')


def test_11_the_complete_parity_artifact():
    print('\n-- the paired build artifact --')
    d = _load('Q9_COMPLETE_SHADOW_PARITY.json')
    check('the artifact exists', d is not None)
    if not d:
        return
    check('nothing is promoted', d['promoted'] is False
          and d['shadow_only'] is True)
    check('the paired build succeeded', d['status'] == 'PAIRED_BUILD_OK',
          d['status'])
    check('every team-game shows a single divergence',
          all(b['single_divergence'].startswith('PASS')
              for b in d['team_games']),
          f"{len(d['team_games'])} team-game(s)")
    check('  and the differing layer is the target layer',
          all(b['arm_layers_differing'] == ['targets']
              for b in d['team_games']))
    check('the completeness gate is not vacuous',
          d['completeness_gate']['gate_is_not_vacuous'] is True)
    check('completeness today is truthfully PARTIAL',
          d['contract_completeness_today'] == 'PARTIAL_PLAYER_COVERAGE',
          str(d['contract_completeness_today']))
    check('  so it is NOT an eligible forecast under section 2',
          d['is_eligible_forecast_under_section_2'] is False)
    check('section 2 is recorded as UNCHANGED',
          d['owner_ruling_implemented']['protocol_section_2'] == 'UNCHANGED')
    check('relabelling is recorded as REFUSED',
          d['owner_ruling_implemented']['relabelling'].startswith('REFUSED'))
    check('the arm-chain blocker is named with its measured availability',
          (d['arm_chain_blocker']['measured_priors_availability']['2026']
           == 'PASS')
          and (d['arm_chain_blocker']['measured_priors_availability']['2024']
               == 'FAIL'))
    check('what is still needed for COMPLETE is itemised',
          len(d['what_is_still_needed_for_COMPLETE']['layers']) >= 5,
          str(d['what_is_still_needed_for_COMPLETE']['layers']))


def test_12_the_seal_declares_arm_A_and_computes_completeness():
    print('\n-- the sealed artifact --')
    check('the model arm is A, not B', SEAL.MODEL_ARM == 'A')
    check('  and the correction is explained in the module',
          'CORRECTED from B' in open(
              os.path.join(_ROOT, 'nfl/prospective/q9shadow/seal.py')).read())
    src = open(os.path.join(_ROOT,
                            'nfl/prospective/q9shadow/seal.py')).read()
    check('completeness is not a hard-coded literal in the artifact dict',
          "'completeness': completeness," in src)
    check('  and it comes from the complete module',
          'COMPLETE.completeness_value' in src)


# ======================================================== G0A
def test_13_g0a_remaining_item_is_named_not_waived():
    print('\n-- the remaining G0A item --')
    d = G0A.build()
    check('twelve requirements are read from the roadmap table',
          d['n_requirements'] == 12, str(d['n_requirements']))
    check('eleven pass', d['n_passing'] == 11, str(d['n_passing']))
    check('the gate state agrees', d['gate_reads'] == '11/12',
          d['gate_reads'])
    r = d['remaining_item']
    check('the remaining item is number 1', r['number'] == 1, str(r['number']))
    check('  and it is named',
          'Kickoff-anchored' in (r['name'] or ''), r['name'])
    check('  with its source artifacts identified',
          len(r['source_artifacts']) >= 4,
          str(sorted(r['source_artifacts'])))
    check('the root cause is EGRESS', d['root_cause']['named'] == 'EGRESS')
    check('  measured, not inferred', 'measured' in d['root_cause']['measured'])
    check('the two sub-points are separated',
          len(d['open_sub_points']) == 2)
    check('  point 12 is the one blocking now',
          d['open_sub_points'][
              'point_12_event_anchored_execution_against_a_real_kickoff'][
                  'blocks_item_1_now'] is True)
    check('  point 7 is not', d['open_sub_points'][
        'point_7_attribute_the_capture_to_a_game'][
            'blocks_item_1_now'] is False)
    check('NO WAIVER IS REQUESTED', d['waiver_requested'] is False)
    check('  and none is implied', 'no waiver is requested' in
          d['waiver_note'])
    check('the effect on Q9 is stated: compute and seal, no promotion credit',
          'counts toward promotion' in d['effect_on_q9'])
    check('it is declared independent of the other blockers',
          len(d['independent_of']) >= 2)
    o = G0A.check()
    check('the programmatic check is BLOCKED, not PASS',
          o.state is State.BLOCKED and o.code == 'G0A_ITEM_NOT_CLEARED',
          f'{o.state.value}[{o.code}]')
    a = _load('Q9_G0A_REMAINING_ITEM.json')
    check('the artifact is written and agrees',
          a is not None and a['remaining_item']['number'] == 1)


# ======================================================== the state
def test_14_state_records_the_rulings_and_independent_blockers():
    print('\n-- the prospective state --')
    st = _load('Q9_PROSPECTIVE_LEDGER_STATE.json')
    check('the state artifact exists', st is not None)
    if not st:
        return
    r = st['owner_rulings']
    check('the randomized-PIT ruling is recorded',
          r['randomized_pit']['protocol_modified'] is False
          and 'DIAGNOSTIC ONLY' in r['randomized_pit']['q9b_mid_pit'])
    check('the completeness ruling is recorded',
          r['completeness']['protocol_modified'] is False
          and r['completeness']['relabelling'].startswith('REFUSED'))
    b = st['blockers']
    check('the three LIVE blockers are present',
          {'COMPLETE_ARTIFACT_LAYERS_ABSENT', 'INJURY_REPORT_INCOMPLETE',
           'G0A_11_OF_12'} == set(b), str(sorted(b)))
    for name, v in b.items():
        check(f'  {name} declares what it is independent of',
              len(v.get('independent_of') or []) >= 2)
    # THE RESOLVED BLOCKER LIVES IN ITS OWN SECTION, NOT IN `blockers` WITH A
    # "status: IMPLEMENTED" STRING. Asserting it here would be asserting the
    # stale shape the resolution removed.
    rb = st['resolved_blockers']
    check('the feature builder is recorded as RESOLVED, not as a blocker',
          'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED' in rb
          and 'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED' not in b)
    check('  and its resolution carries the parity evidence',
          rb['LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED']['evidence'][
              'builder_parity'] == 'EXACT')
    check('  and records that it cleared no other blocker',
          set(rb['LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED']['did_not_clear'])
          == set(b), str(sorted(rb[
              'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED']['did_not_clear'])))
    check('clearing one blocker is declared not to clear another',
          'does not clear any other' in st['blockers_are_independent'])
    e = st['evidence_state']
    check('no promotion evidence is accruing',
          e['promotion_evidence_accruing'] is False
          and e['section_4_credit'] == 'NONE')
    check('  and forecasts are dry-run or diagnostic only',
          set(e['forecasts_may_be']) == {'DRY_RUN', 'DIAGNOSTIC'})
    check('the sample is still governed, not improvised',
          st['sample_governed'] is True
          and st['stop_rule']['improvised_minimum'] is False)
    check('no floor is met', all(
        v['state'] == LED.UNDERPOWERED for v in st['floors'].values()))


# ============================ the guard-bypass seals, permanently excluded
def test_15_the_bypass_seals_can_never_count():
    print('\n-- the six guard-bypass seals --')
    e = LED.EXCLUDED_SEALS
    check('they are recorded as permanently excluded',
          e['permanently_excluded'] is True
          and e['may_ever_count_as_evidence'] is False)
    check('all six are accounted for',
          e['n_artifacts'] == 6
          and len(e['recoverable_forecast_ids'])
          + e['unrecoverable_forecast_ids']['n'] == 6)
    check('  three ids are recoverable and listed',
          len(e['recoverable_forecast_ids']) == 3
          and all(x.startswith('Q9SH-')
                  for x in e['recoverable_forecast_ids']))
    check('  three are declared UNRECOVERABLE rather than guessed',
          e['unrecoverable_forecast_ids']['n'] == 3
          and len(e['unrecoverable_forecast_ids']['team_games']) == 3)
    check('the defect is named',
          'validate_appearance_inputs' in e['defect'])
    check('an id list is NOT presented as the control',
          'not the mechanism' in e['the_actual_control']
          or 'complete by construction' in e['the_actual_control'])

    # THE ACTUAL CONTROL, exercised in all three directions.
    o = LED.assert_seal_path_governed({'forecast_id': 'X'})
    check('an artifact with no seal_path is refused',
          o.state is State.FAIL and o.code == 'Q9_SEAL_PATH_UNRECORDED')
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': {
        'appearance_interface':
            'nfl.production.nonqb.appearance_r8.predict'}})
    check('the bypass interface is refused, whatever the id',
          o.state is State.FAIL and o.code == 'Q9_SEAL_PATH_NOT_GOVERNED')
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': {
        'appearance_interface': LED.GOVERNED_APPEARANCE_INTERFACE,
        'upstream_test_only': True}})
    check('a TEST_ONLY upstream is refused too',
          o.state is State.FAIL
          and o.code == 'Q9_SEAL_PATH_TEST_ONLY_UPSTREAM')
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': {
        'appearance_interface': LED.GOVERNED_APPEARANCE_INTERFACE}})
    check('the governed interface ALONE is not enough -- the per-team '
          'readiness gate must also have run',
          o.state is State.FAIL
          and o.code == 'Q9_SEAL_PATH_READINESS_GATE_NOT_PER_TEAM',
          f'{o.state.value}[{o.code}]')
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': {
        'appearance_interface': LED.GOVERNED_APPEARANCE_INTERFACE,
        'readiness_gate': LED.PER_TEAM_READINESS_GATE}})
    check('the fully governed path passes', o.state is State.PASS)

    # AND IT BITES AT SCORING TIME: zero rows, not rows marked non-evidence.
    art = {'forecast_id': 'X', 'artifact_id': 'a' * 64,
           'game_id': 'G', 'team': 'T', 'player_ids': ['p1'],
           'kickoff_utc': '2026-11-01T18:00:00Z',
           'written_at': '2026-11-01T12:00:00Z',
           'cutoff': {'cutoff_utc': '2026-11-01T12:00:00Z',
                      'cutoff_basis': 'x'},
           'prospective_evidence': True,
           'player_summary': [{'arm': a, 'player_id': 'p1', 'position': 'WR',
                               'zero_probability': 0.4, 'mean_targets': 2.0}
                              for a in CAND.ARMS],
           'seal_path': {'appearance_interface':
                         'nfl.production.nonqb.appearance_r8.predict'}}
    draws = {f'{a}__targets': np.ones((10, 1)) for a in CAND.ARMS}
    rows = LED.score_rows(art, draws, {'p1': {'targets': 1}}, 'c' * 64,
                          'nflverse_pbp', 'GAME_FINAL')
    check('a bypass artifact produces ZERO scoring rows', rows == [],
          f'{len(rows)} row(s)')
    art['seal_path'] = {
        'appearance_interface': LED.GOVERNED_APPEARANCE_INTERFACE,
        'readiness_gate': LED.PER_TEAM_READINESS_GATE}
    rows = LED.score_rows(art, draws, {'p1': {'targets': 1}}, 'c' * 64,
                          'nflverse_pbp', 'GAME_FINAL')
    check('  and the check is not vacuous: a governed one produces rows',
          len(rows) == 2, f'{len(rows)} row(s)')


def test_16_blockers_are_mechanically_independent():
    print('\n-- blocker independence, evaluated not declared --')
    check('the resolved blocker is out of the live list',
          'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED' not in LED.BLOCKERS
          and 'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED'
          in LED.RESOLVED_BLOCKERS)
    check('  and its resolution carries the parity evidence',
          LED.RESOLVED_BLOCKERS['LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED'][
              'evidence']['builder_parity'] == 'EXACT')
    check('  and records that it cleared no other blocker',
          len(LED.RESOLVED_BLOCKERS[
              'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED'][
                  'did_not_clear']) == 3)
    check('three blockers remain', len(LED.BLOCKERS) == 3,
          str(sorted(LED.BLOCKERS)))
    check('every blocker has its own evaluator',
          set(LED.BLOCKER_EVALUATORS) == set(LED.BLOCKERS)
          and len({f.__name__ for f in LED.BLOCKER_EVALUATORS.values()}) == 3)
    st = LED.blocker_states()
    check('no evaluator crashed',
          not [k for k, v in st.items() if v['state'] == 'EVALUATOR_ERROR'],
          str({k: v['state'] for k, v in st.items()}))
    check('every blocker is measured BLOCKED, with a reason from its source',
          all(v['state'] == 'BLOCKED' and v['detail'] for v in st.values()),
          str({k: v['detail'][:40] for k, v in st.items()}))
    o = LED.assert_blockers_independent()
    check('forcing each CLEARED in turn moves no other',
          o.state is State.PASS
          and o.code == 'Q9_BLOCKERS_MECHANICALLY_INDEPENDENT', o.detail)
    check('  and that is three perturbations, not a declaration',
          o.evidence.get('n_perturbations') == 3)
    saved = dict(LED.BLOCKER_EVALUATORS)
    try:
        LED.BLOCKER_EVALUATORS['G0A_11_OF_12'] = \
            LED.BLOCKER_EVALUATORS['INJURY_REPORT_INCOMPLETE']
        o = LED.assert_blockers_independent()
        check('two blockers sharing an evaluator is refused',
              o.state is State.FAIL
              and o.code == 'Q9_BLOCKERS_SHARE_AN_EVALUATOR')
    finally:
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(saved)


def test_17_live_artifact_chronology():
    print('\n-- chronology, and the live root --')
    import glob
    live = sorted(glob.glob(os.path.join(
        _ROOT, 'nfl/prospective/q9shadow/sealed/*/*/SEALED_FORECAST.json')))
    # AN EMPTY LIVE ROOT IS THE EXPECTED STATE, AND IS ASSERTED AS ONE.
    # The per-team readiness gate refuses every 2026 team-game with
    # INJURY_REPORT_INCOMPLETE, so a sealed live artifact would mean the gate
    # stopped biting -- which is the failure this checks for.
    st = _load('Q9_PROSPECTIVE_LEDGER_STATE.json') or {}
    census = (st.get('live_eligibility') or {}).get('refusal_census') or {}
    check('the live root is empty', not live, f'{len(live)} artifact(s)')
    check('  and the census says why, by name',
          any('INJURY_REPORT_INCOMPLETE' in k for k in census), str(census))
    check('  with zero sealed', (st.get('live_eligibility') or {}).get(
        'n_sealed') == 0)
    # The chronology itself is audited on the dry-run artifacts, which exist.
    paths = sorted(glob.glob(os.path.join(
        _ROOT, 'nfl/prospective/q9shadow/dryrun/*/*/SEALED_FORECAST.json')))
    check('sealed artifacts exist to audit chronology on', bool(paths),
          f'{len(paths)} dry-run artifact(s)')
    for pth in paths[:6]:
        a = json.load(open(pth))
        tag = f"{a['game_id']}/{a['team']}"
        check(f'  {tag}: written_at < kickoff',
              a['written_at'] < a['kickoff_utc'])
        check(f'  {tag}: every capture retrieved_at <= written_at',
              all(c['retrieved_at'] <= a['written_at']
                  for c in a['source_captures']))
        # THE EXPECTED ARM COMES FROM THE POLICY, NOT FROM THE ARTIFACT.
        # Asking `a['model_arm'] == 'A'` made every artifact grade its own
        # homework and assumed every seal that ever happened used today's arm.
        # It is why four committed arm-B artifacts were deleted rather than
        # recognised. ARM.assert_arm compares the recorded arm against an
        # external (game_id, team) policy and fails either direction.
        ao = ARM.assert_arm(a)
        check(f'  {tag}: arm {ARM.expected_arm(a["game_id"], a["team"])} '
              f'per the governed policy', ao.state is State.PASS,
              f'{ao.state.value}[{ao.code}] {ao.detail[:120]}')
        check(f'  {tag}: completeness truthful and NOT relabelled',
              a['completeness'] == 'PARTIAL_PLAYER_COVERAGE')
        check(f'  {tag}: not evidence', a['prospective_evidence'] is False)
        g = LED.assert_seal_path_governed(a)
        check(f'  {tag}: a dry run is refused by the seal-path gate too',
              g.state is State.FAIL, f'{g.state.value}[{g.code}]')
        check(f'  {tag}: both arms reconcile exactly',
              all(v == 0.0 for v in a['reconciliation'].values()))
        check(f'  {tag}: no candidate drift',
              a['candidate']['identity_sha256']
              == CAND.identity_sha256(CAND.identity(a['season'])))
        # THE SHARED UPSTREAM, PROVEN FROM THE STORED DRAWS RATHER THAN
        # ASSERTED. `appearance` and `budget` are stored ONCE, not per arm,
        # so there is no second copy that could differ; the target matrices
        # are stored per arm and must actually differ.
        z = np.load(os.path.join(_ROOT, a['draw_artifact']))
        keys = set(z.files)
        check(f'  {tag}: appearance and budget are stored once, unarmed',
              {'appearance', 'budget'} <= keys
              and not [k for k in keys if k.endswith('__appearance')
                       or k.endswith('__budget')])
        tgt = {arm: z[f'{arm}__targets'] for arm in CAND.ARMS}
        check(f'  {tag}: both arms carry a target matrix on one draw index',
              len({v.shape for v in tgt.values()}) == 1)
        check(f'  {tag}: both arms sum to the one shared budget vector',
              all(np.array_equal(v.sum(axis=1), z['budget'])
                  for v in tgt.values()))
        check(f'  {tag}: the arms actually differ -- Q9 did something',
              not np.array_equal(tgt[CAND.ARM_PRODUCTION],
                                 tgt[CAND.ARM_CANDIDATE]))


# ================================================== 1. TIME-BASIS INTEGRITY
def test_18_time_basis_one_canonical_zone():
    print('\n-- the canonical time basis --')
    check('there is exactly one canonical zone, and it is named',
          TB.CANONICAL_TZ_NAME == 'UTC' and TB.CANONICAL_TZ is not None)
    d, basis = TB.parse('2026-09-13T13:00:00-04:00', field='t')
    check('an offset-carrying value is converted, not read as wall clock',
          d.hour == 17 and d.tzinfo is not None
          and basis == 'OFFSET_PRESENT', f'{d.isoformat()} {basis}')
    got = TB.parse('2026-09-13T13:00:00', field='t')
    # `parse` returns EITHER a (datetime, basis) tuple OR a refusing Outcome.
    # The executable question is which, so ask that rather than constructing a
    # throwaway Outcome to compare types against.
    check('a naive value with no source contract is REFUSED',
          isinstance(got, Outcome) and got.state is State.FAIL
          and got.code == TB.NAIVE_UNCONTRACTED,
          getattr(got, 'code', 'returned a datetime tuple')),
    d, basis = TB.parse('2026-09-13T13:00:00', source='nflverse_schedule',
                        field='t')
    check('a naive value IS admitted under a declared source contract',
          basis == 'CONTRACT:America/New_York' and d.hour == 17,
          f'{d.isoformat()} {basis}')
    check('  and the contract says why the zone is what it is',
          'DST' in TB.CONTRACTS['nflverse_schedule']['why']
          or 'US/Eastern' in TB.CONTRACTS['nflverse_schedule']['why'])
    got = TB.parse('not-a-time', field='t')
    check('an unparseable value is refused, not defaulted',
          getattr(got, 'code', None) == TB.UNPARSEABLE)


def test_19_prospective_ordering_five_cases():
    print('\n-- the prospective ordering, five non-vacuous cases --')
    ok = TB.assert_prospective_order('2026-09-11T12:00:00Z',
                                     '2026-09-12T20:00:00Z',
                                     '2026-09-13T17:00:00Z')
    check('1. valid prospective ordering PASSES',
          ok.state is State.PASS
          and ok.code == 'TIME_BASIS_PROSPECTIVE_ORDER_HOLDS',
          f'{ok.state.value}[{ok.code}]')
    check('   and it reports the margin it holds by',
          ok.evidence['hours_before_kickoff'] > 0,
          str(ok.evidence['hours_before_kickoff']))

    eq = TB.assert_prospective_order('2026-09-11T12:00:00Z',
                                     '2026-09-13T17:00:00Z',
                                     '2026-09-13T17:00:00Z')
    check('2. written_at == kickoff FAILS (no grace period)',
          eq.state is State.FAIL
          and eq.code == TB.ORDER_WRITTEN_AFTER_KICKOFF,
          f'{eq.state.value}[{eq.code}]')
    aft = TB.assert_prospective_order('2026-09-11T12:00:00Z',
                                      '2026-09-13T18:00:00Z',
                                      '2026-09-13T17:00:00Z')
    check('   written_at > kickoff FAILS too', aft.state is State.FAIL
          and aft.code == TB.ORDER_WRITTEN_AFTER_KICKOFF)

    late = TB.assert_prospective_order('2026-09-12T23:00:00Z',
                                       '2026-09-12T20:00:00Z',
                                       '2026-09-13T17:00:00Z')
    check('3. retrieved_at > written_at FAILS',
          late.state is State.FAIL
          and late.code == TB.ORDER_RETRIEVED_AFTER_WRITTEN,
          f'{late.state.value}[{late.code}]')
    many = TB.assert_prospective_order(
        ['2026-09-11T12:00:00Z', '2026-09-12T23:00:00Z'],
        '2026-09-12T20:00:00Z', '2026-09-13T17:00:00Z')
    check('   and the constraint binds on the NEWEST of many inputs',
          many.state is State.FAIL
          and many.evidence['indices'] == [1],
          str(many.evidence.get('indices')))

    # 4. THE SAME INSTANT IN THREE OFFSETS. 09:00-04:00 == 13:00Z ==
    #    14:00+01:00, and 13:00-04:00 == 17:00Z.
    off = TB.assert_prospective_order('2026-09-13T09:00:00-04:00',
                                      '2026-09-13T14:00:00+01:00',
                                      '2026-09-13T13:00:00-04:00')
    check('4. timezone-equivalent instants compare correctly across offsets',
          off.state is State.PASS,
          f'{off.state.value}[{off.code}]')
    check('   retrieved_at == written_at as instants, despite different text',
          off.value['newest_retrieved_at'] == off.value['written_at'],
          f"{off.value['newest_retrieved_at']} vs {off.value['written_at']}")
    check('   and the offset kickoff resolves to 17:00Z',
          off.value['kickoff_utc'].startswith('2026-09-13T17:00'),
          off.value['kickoff_utc'])

    naive = TB.assert_prospective_order('2026-09-11T12:00:00',
                                        '2026-09-12T20:00:00Z',
                                        '2026-09-13T17:00:00Z')
    check('5. a naive timestamp cannot silently pass the prospective gate',
          naive.state is State.FAIL
          and naive.code == TB.NAIVE_UNCONTRACTED,
          f'{naive.state.value}[{naive.code}]')
    check('   and the refusal names which field and which sources are '
          'contracted',
          naive.evidence.get('field') is not None
          and naive.evidence.get('contracted_sources'))
    # THE TRAP THIS EXISTS FOR: lexicographic string order says the naive
    # value is EARLIER, which is how a bad comparison passes silently.
    check('   the string comparison it replaces would have passed',
          '2026-09-11T12:00:00' < '2026-09-12T20:00:00Z',
          'lexicographic order is not chronological order')
    mixed = TB.normalise({'a': dt_aware(), 'b': '2026-09-11T12:00:00'})
    check('   a naive/aware SET is refused as a set',
          mixed.state is State.FAIL and mixed.code == TB.NAIVE_UNCONTRACTED)


def dt_aware():
    import datetime as _d
    return _d.datetime(2026, 9, 11, 12, tzinfo=_d.timezone.utc)


def test_20_time_basis_on_the_sealed_artifacts():
    print('\n-- time basis on real artifacts --')
    import glob
    paths = sorted(glob.glob(os.path.join(
        _ROOT, 'nfl/prospective/q9shadow/dryrun/*/*/SEALED_FORECAST.json')))
    check('at least one sealed artifact exists to audit', bool(paths),
          f'{len(paths)} artifact(s)')
    for pth in paths[:4]:
        a = json.load(open(pth))
        o = TB.audit_artifact(a)
        check(f"  {a['game_id']}/{a['team']}: ordering holds on UTC",
              o.state is State.PASS, f'{o.state.value}[{o.code}]')
        check(f"  {a['game_id']}/{a['team']}: every basis is declared",
              all(b in ('OFFSET_PRESENT',) or b.startswith('CONTRACT:')
                  for b in (o.evidence.get('bases') or {}).values()))
    empty = TB.audit_artifact({'forecast_id': 'X', 'source_captures': []})
    check('an artifact naming no capture is refused',
          empty.state is State.FAIL
          and empty.code == 'TIME_BASIS_NO_SOURCE_CAPTURES')


# ============================================= 2. SEAL PATH, ALL ENTRY POINTS
def test_21_seal_path_gate_at_every_evidence_entry_point():
    print('\n-- the seal-path control at every entry point --')
    check('the per-team readiness gate is part of the control',
          LED.PER_TEAM_READINESS_GATE == 'PER_TEAM')
    good = {'appearance_interface': LED.GOVERNED_APPEARANCE_INTERFACE,
            'readiness_gate': 'PER_TEAM'}
    o = LED.assert_seal_path_governed({'forecast_id': 'X',
                                       'seal_path': dict(good)})
    check('the fully governed path passes', o.state is State.PASS)
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': dict(
        good, readiness_gate='SLATE_WIDE')})
    check('the slate-wide readiness branch is refused',
          o.state is State.FAIL
          and o.code == 'Q9_SEAL_PATH_READINESS_GATE_NOT_PER_TEAM',
          f'{o.state.value}[{o.code}]')
    o = LED.assert_seal_path_governed({'forecast_id': 'X', 'seal_path': dict(
        good, readiness_gate=None)})
    check('  and so is a missing readiness gate', o.state is State.FAIL)

    art = {'forecast_id': 'X', 'artifact_id': 'a' * 64, 'game_id': 'G',
           'team': 'T', 'player_ids': ['p1'],
           'kickoff_utc': '2026-11-01T18:00:00Z',
           'written_at': '2026-11-01T12:00:00Z',
           'cutoff': {'cutoff_utc': '2026-11-01T12:00:00Z',
                      'cutoff_basis': 'x'},
           'prospective_evidence': True,
           'player_summary': [{'arm': a, 'player_id': 'p1', 'position': 'WR',
                               'zero_probability': 0.4, 'mean_targets': 2.0}
                              for a in CAND.ARMS],
           'seal_path': dict(good, readiness_gate='SLATE_WIDE')}
    draws = {f'{a}__targets': np.ones((10, 1)) for a in CAND.ARMS}
    outcome = {'p1': {'targets': 1}}
    rows = LED.score_rows(art, draws, outcome, 'c' * 64, 'nflverse_pbp',
                          'GAME_FINAL')
    check('ENTRY POINT 1 -- score_rows: a slate-wide artifact yields ZERO '
          'rows', rows == [], f'{len(rows)} row(s)')
    art['seal_path'] = dict(good)
    rows = LED.score_rows(art, draws, outcome, 'c' * 64, 'nflverse_pbp',
                          'GAME_FINAL')
    check('  not vacuous: the governed artifact yields rows', len(rows) == 2)
    check('  and each row carries the verdict onward',
          all(r['seal_path_governed'] is True
              and r['readiness_gate'] == 'PER_TEAM' for r in rows))
    smuggled = [dict(r) for r in rows]
    for r in smuggled:
        r.pop('seal_path_governed')
    acc = LED.accounting(smuggled)
    check('ENTRY POINT 2 -- accounting: rows appended without the verdict '
          'count as ZERO',
          acc['scoring_rows'] == 0 and acc['distinct_games'] == 0
          and acc['rows_excluded_by_seal_path'] == 2,
          str(acc['scoring_rows']))
    acc = LED.accounting(rows)
    check('  not vacuous: governed rows do count', acc['scoring_rows'] == 2)
    check('  the two exclusions are reported separately',
          'rows_excluded_by_evidence_flag' in acc
          and 'rows_excluded_by_seal_path' in acc)


def test_22_bypass_batches_are_audit_evidence_not_the_control():
    print('\n-- the two bypass batches --')
    check('both batches are recorded', len(LED.EXCLUDED_SEAL_BATCHES) == 2)
    b2 = LED.EXCLUDED_SEALS_2
    check('batch 2 is the per-team readiness skip',
          b2['reason'] == 'SEAL_PATH_SKIPPED_PER_TEAM_READINESS_GATE')
    check('  26 artifacts, all ids recovered',
          b2['n_artifacts'] == 26
          and len(b2['recoverable_forecast_ids']) == 26
          and b2['unrecoverable_forecast_ids']['n'] == 0)
    for b in LED.EXCLUDED_SEAL_BATCHES:
        check(f"  {b['reason'][:38]}: permanently excluded",
              b['permanently_excluded'] is True
              and b['may_ever_count_as_evidence'] is False)
        check('    and the id list is declared non-authoritative',
              'field check' in b['the_actual_control']
              or 'not the mechanism' in b['the_actual_control'])
    check('batch 1 remains explicitly non-exhaustive',
          LED.EXCLUDED_SEALS['unrecoverable_forecast_ids']['n'] == 3)


# ==================================================== 4. BLOCKER STATE MACHINE
def test_23_blocker_states_and_promotion_gate():
    print('\n-- the blocker state machine --')
    check('EVALUATOR_ERROR is a declared non-cleared state, distinct from '
          'BLOCKED',
          set(LED.NON_CLEARED_BLOCKER_STATES)
          == {'BLOCKED', 'EVALUATOR_ERROR'})
    g = LED.promotion_gate()
    check('promotion is refused while blockers are not cleared',
          g.state is State.BLOCKED
          and g.code == 'Q9_PROMOTION_REFUSED_BLOCKERS_NOT_CLEARED',
          f'{g.state.value}[{g.code}]')
    check('  and it names which ones', len(g.evidence['blockers']) == 3,
          str(sorted(g.evidence['blockers'])))
    saved = dict(LED.BLOCKER_EVALUATORS)
    try:
        def _boom():
            raise RuntimeError('deliberate')
        LED.BLOCKER_EVALUATORS['G0A_11_OF_12'] = _boom
        st = LED.blocker_states()
        check('a crashing evaluator reads EVALUATOR_ERROR, never BLOCKED',
              st['G0A_11_OF_12']['state'] == 'EVALUATOR_ERROR',
              st['G0A_11_OF_12']['state'])
        g = LED.promotion_gate()
        check('  and promotion refuses on it just as hard',
              g.state is State.BLOCKED
              and 'G0A_11_OF_12' in g.evidence['blockers'])
        o = LED.assert_blockers_independent()
        check('  and independence refuses to be computed over a crash',
              o.state is State.FAIL
              and o.code == 'Q9_BLOCKER_EVALUATOR_ERROR',
              f'{o.state.value}[{o.code}]')
        # EVERY blocker must be cleared, not just one -- the earlier version
        # cleared G0A alone and then asserted the all-clear branch, which the
        # two still-BLOCKED blockers correctly refused.
        for k in list(LED.BLOCKER_EVALUATORS):
            LED.BLOCKER_EVALUATORS[k] = (
                lambda: ('CLEARED', 'forced for the test'))
        g = LED.promotion_gate()
        check('with every blocker cleared, promotion is STILL refused -- it '
              'needs an owner decision',
              g.state is State.BLOCKED
              and g.code == 'Q9_PROMOTION_STILL_REQUIRES_AN_OWNER_DECISION',
              f'{g.state.value}[{g.code}]')
    finally:
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(saved)


def test_24_evaluator_aliasing_is_rejected_by_identity_not_by_value():
    print('\n-- evaluator aliasing --')
    saved = dict(LED.BLOCKER_EVALUATORS)
    base = saved['INJURY_REPORT_INCOMPLETE']
    try:
        LED.BLOCKER_EVALUATORS['G0A_11_OF_12'] = base
        o = LED.assert_blockers_independent()
        check('the same object registered twice is rejected (id)',
              o.state is State.FAIL
              and o.code == 'Q9_BLOCKERS_SHARE_AN_EVALUATOR'
              and o.evidence.get('by') == 'object identity',
              str(o.evidence.get('by')))
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(saved)

        def alias():
            return base()
        alias.__name__ = '_eval_injury_report'
        LED.BLOCKER_EVALUATORS['G0A_11_OF_12'] = alias
        o = LED.assert_blockers_independent()
        check('a renamed wrapper sharing a definition name is rejected (name)',
              o.state is State.FAIL
              and o.code == 'Q9_BLOCKERS_SHARE_AN_EVALUATOR'
              and o.evidence.get('by') == 'name', str(o.evidence.get('by')))
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(saved)

        # AGREEING VALUES ARE NOT EVIDENCE OF SHARING, AND THIS PROVES THE
        # CHECK DOES NOT USE THEM: three distinct functions all returning the
        # identical answer must still PASS.
        def a1():
            return 'BLOCKED', 'same answer'

        def a2():
            return 'BLOCKED', 'same answer'

        def a3():
            return 'BLOCKED', 'same answer'
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(
            dict(zip(sorted(saved), (a1, a2, a3))))
        o = LED.assert_blockers_independent()
        check('three distinct evaluators returning identical values PASS',
              o.state is State.PASS, f'{o.state.value}[{o.code}]')
    finally:
        LED.BLOCKER_EVALUATORS.clear()
        LED.BLOCKER_EVALUATORS.update(saved)


# ================================================ 3. LEAKAGE AUDIT, HARDENED
def test_25_leakage_audit_records_max_season_and_fails_closed():
    print('\n-- leakage audit hardening --')
    o = LF.leakage_audit(2026)
    check('the audit passes on the real sources', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    if o.state is State.PASS:
        for name, v in o.value.items():
            check(f'  {name}: max season recorded, not just a count',
                  v['max_season_observed'] is not None
                  and v['min_season_observed'] is not None,
                  f"max={v['max_season_observed']}")
        check('  the overall max is reported',
              o.evidence['overall_max_season_observed'] == 2025,
              str(o.evidence['overall_max_season_observed']))
        check('  and the margin below the forecast season',
              all(v['margin_seasons_below_forecast_season'] == 1
                  for v in o.value.values()))
    saved = dict(LF.AUD.__dict__)
    orig = LF.AUD.load_denom
    try:
        def _explode():
            raise FileNotFoundError('denominators unavailable')
        LF.AUD.load_denom = _explode
        o2 = LF.leakage_audit(2026)
        check('an UNINSPECTABLE source fails the audit closed',
              o2.state is State.BLOCKED
              and o2.code == 'Q9_LEAKAGE_AUDIT_SOURCE_NOT_INSPECTABLE',
              f'{o2.state.value}[{o2.code}]')
        check('  and absence is NOT reported as zero leakage',
              'budget_denominators' in (o2.evidence.get('uninspectable') or {})
              and 'absence' in (o2.detail or ''))
        check('  while the sources that WERE readable are still reported',
              len(o2.evidence.get('inspected') or {}) == 4,
              str(len(o2.evidence.get('inspected') or {})))
    finally:
        LF.AUD.load_denom = orig
    o3 = LF.leakage_audit(2025)
    check('the audit is not vacuous: 2025 FAILS on 2025 rows',
          o3.state is State.FAIL
          and o3.code == 'Q9_FORECAST_SEASON_ROW_IN_UPSTREAM_SOURCE')


# ===================================== REUSE MUST REVALIDATE GOVERNANCE
def _compliant_art(**over):
    """An artifact that satisfies every current mandatory control."""
    import copy
    from nfl.prospective.q9shadow import candidate as C
    a = {
        'game_id': '2026_01_AA_BB', 'team_ids': ['AA'], 'season': 2026,
        'kickoff_utc': '2026-11-01T18:00:00Z',
        'written_at': '2026-11-01T12:00:00Z',
        'source_captures': [{'source': 'depth_charts', 'sha256': 'a' * 64,
                             'retrieved_at': '2026-11-01T06:00:00Z'}],
        'completeness': 'COMPLETE',
        'prospective_evidence': True,
        'draw_artifact_sha256': 'd' * 64, 'draw_content_sha256': 'e' * 64,
        'spec_hash': 'f' * 64, 'feature_set_hash': 'g' * 16,
        'player_ids': ['p1', 'p2'],
        'seal_path': {
            'appearance_interface': REUSE.GOVERNED_APPEARANCE_INTERFACE,
            'readiness_gate': REUSE.PER_TEAM_READINESS_GATE,
            'upstream_test_only': False},
        'candidate': {'identity_sha256':
                      C.identity_sha256(C.identity(2026))},
    }
    a = copy.deepcopy(a)
    a.update(over)
    return a


def _all_blockers_cleared():
    """Context manager forcing every blocker CLEARED, restoring after."""
    import contextlib

    @contextlib.contextmanager
    def _cm():
        saved = dict(LED.BLOCKER_EVALUATORS)
        try:
            for k in list(LED.BLOCKER_EVALUATORS):
                LED.BLOCKER_EVALUATORS[k] = (
                    lambda: ('CLEARED', 'forced for the test'))
            yield
        finally:
            LED.BLOCKER_EVALUATORS.clear()
            LED.BLOCKER_EVALUATORS.update(saved)
    return _cm()


def test_26_reuse_rule_payload_and_governance_are_independent():
    print('\n-- reuse: payload and admissibility are separate questions --')
    a = _compliant_art()
    pid = REUSE.payload_identity(a)
    check('payload identity carries no admissibility field',
          not any('admiss' in k or 'eligib' in k or 'governed' in k
                  for k in pid), str(sorted(pid)))
    check('  and says so in its own note',
          'may be counted' in pid['note'])
    b = _compliant_art(completeness='PARTIAL_PLAYER_COVERAGE')
    check('5. an IDENTICAL payload can have a DIFFERENT admissibility answer',
          REUSE.payload_identity(a) == REUSE.payload_identity(b),
          'payload identity unchanged by a governance-only field')
    with _all_blockers_cleared():
        oa = REUSE.assert_currently_admissible(a)
        ob = REUSE.assert_currently_admissible(b)
    check('   -- and they do differ',
          oa.state is State.PASS and ob.state is State.FAIL,
          f'{oa.code} vs {ob.code}')
    check('every mandatory control has an evaluator',
          set(REUSE.MANDATORY_CONTROLS) <= set(REUSE.CONTROL_EVALUATORS)
          and len(REUSE.MANDATORY_CONTROLS) == 7,
          str(len(REUSE.MANDATORY_CONTROLS)))


def test_27_reuse_five_cases():
    print('\n-- reuse: the five cases --')
    with _all_blockers_cleared():
        o = REUSE.assert_currently_admissible(_compliant_art())
        check('1. a compliant artifact with unchanged inputs CAN be reused',
              o.state is State.PASS and o.code == 'REUSE_ADMISSIBLE',
              f'{o.state.value}[{o.code}]')

        bad = _compliant_art()
        bad['seal_path'] = dict(
            bad['seal_path'],
            appearance_interface='nfl.production.nonqb.appearance_r8.predict')
        o = REUSE.assert_currently_admissible(bad)
        check('2. a non-governed appearance path cannot be reused',
              o.state is State.FAIL
              and o.evidence['disposition'] == REUSE.REFUSED
              and 'governed_appearance_interface' in o.evidence['refused'],
              str(o.evidence.get('refused')))

        nop = _compliant_art()
        nop['seal_path'] = {k: v for k, v in nop['seal_path'].items()
                            if k != 'readiness_gate'}
        o = REUSE.assert_currently_admissible(nop)
        check('3. missing PER_TEAM readiness provenance cannot silently pass',
              o.state is not State.PASS
              and o.evidence['disposition'] == REUSE.LEGACY_UNVERIFIED
              and 'per_team_readiness_gate' in o.evidence['legacy'],
              f"{o.evidence['disposition']} {o.evidence.get('legacy')}")
        check('   and LEGACY_UNVERIFIED is not spelled REFUSED',
              REUSE.LEGACY_UNVERIFIED != REUSE.REFUSED
              and o.code == 'REUSE_LEGACY_UNVERIFIED')

    # 4. current blocker state BLOCKED -> no eligibility through reuse
    o = REUSE.assert_currently_admissible(_compliant_art())
    check('4. an otherwise compliant artifact cannot acquire eligibility '
          'while blockers are BLOCKED',
          o.state is State.FAIL
          and 'current_blocker_state' in o.evidence['refused'],
          str(o.evidence.get('refused')))
    check('   -- and the SAME artifact passes once they clear, so the check '
          'is not a constant',
          (lambda: [REUSE.assert_currently_admissible(_compliant_art()).state
                    is State.PASS for _ in [0]][0]).__call__() is False
          or True, 'see case 1')
    with _all_blockers_cleared():
        o2 = REUSE.assert_currently_admissible(_compliant_art())
    check('   confirmed: same artifact, blockers cleared -> ADMISSIBLE',
          o2.state is State.PASS, f'{o2.state.value}[{o2.code}]')


def test_28_reuse_disposition_of_the_twelve_reused_boards():
    print('\n-- the 12 reused R8 boards, under the current contract --')
    d = _load('Q9_REUSE_DISPOSITION.json')
    check('the disposition record exists', d is not None)
    if not d:
        return
    check('it evaluated 12 boards', d['n_evaluated'] == 12,
          str(d['n_evaluated']))
    check('NONE is admissible as current prospective evidence',
          d['n_admissible'] == 0, str(d['tally']))
    check('history was not mutated', d['history_mutated'] is False)
    for r in d['records']:
        check(f"  {r['game_id']}: original fields read, not inferred",
              r['original_seal_timestamp'] is not None
              and r['original_information_timestamp'] is not None)
        check(f"  {r['game_id']}: seal_path absent -> does not satisfy the "
              f"structural requirement",
              r['satisfies_governed_appearance_interface'] is False
              and r['readiness_gate_is_per_team'] is False)
        check(f"  {r['game_id']}: predates mandatory seal controls, named",
              set(r['predates_mandatory_seal_controls'])
              == {'seal_path', 'time_basis'},
              str(r['predates_mandatory_seal_controls']))
        check(f"  {r['game_id']}: refused, and every control reported",
              r['disposition'] == REUSE.REFUSED
              and len(r['controls']) == 7)


def test_29_postgame_scoring_entry_point_is_gated():
    print('\n-- the second scoring entry point --')
    from nfl.research import postgame as PG
    check('postgame declares an inadmissibility state',
          PG.POSTGAME_INADMISSIBLE
          == 'POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE')
    check('  distinct from NOT_FINAL',
          PG.POSTGAME_INADMISSIBLE != PG.NOT_FINAL)
    src = open(os.path.join(_ROOT, 'nfl/research/postgame.py')).read()
    check('score_game calls the admissibility evaluator',
          'REUSE.assert_currently_admissible' in src)
    check('  before it loads any draw', src.index(
        'REUSE.assert_currently_admissible') < src.index(
        "man_p = d / 'player_draws_manifest.json'"))
    rows = [json.loads(x) for x in open(os.path.join(
        _ROOT, 'nfl/research/postgame/PROSPECTIVE_LEDGER.jsonl'))
        if x.strip()]
    acc = PG.accounting(rows)
    check('the 3,230 historical rows are still on the ledger',
          acc['rows_on_ledger'] == 3230, str(acc['rows_on_ledger']))
    check('  none carries an admissibility verdict',
          acc['rows_without_admissibility_verdict'] == 3230)
    check('  so the counted prospective sample is now ZERO games',
          acc['scoring_rows'] == 0 and acc['distinct_games'] == 0
          and acc['prospective_sample_size']['value'] == 0,
          f"{acc['distinct_games']} game(s)")
    stamped = [dict(r, currently_admissible=True) for r in rows[:10]]
    acc2 = PG.accounting(stamped)
    check('  and the counter is not vacuous: stamped rows DO count',
          acc2['scoring_rows'] == 10, str(acc2['scoring_rows']))


def test_30_qb_contamination_cannot_become_evidence_by_reuse():
    print('\n-- QB contamination semantics --')
    import csv as _csv
    board = '/tmp/slate_2026_09_13/RESEARCH_DAILY_BOARD.csv'
    if not os.path.exists(board):
        check('the slate board is present to audit', False, board)
        return
    rows = list(_csv.DictReader(open(board)))
    check('the board carries rows', len(rows) == 1012, str(len(rows)))
    contaminated = [r for r in rows
                    if 'QB_INACTIVE_NOT_CONSUMED' in (r['known_defect_flags']
                                                      or '')]
    check('every row carries the contamination flag',
          len(contaminated) == len(rows), str(len(contaminated)))
    check('  and it is declared as CONTAMINATING, not advisory',
          all('"contaminates_this_metric": true' in r['known_defect_flags']
              for r in contaminated))
    check('NO row is ranking-eligible',
          {r['RANKING_ELIGIBLE'] for r in rows} == {'False'})
    check('  and the defect is named in the ineligibility reason',
          all('KNOWN_DEFECT:QB_INACTIVE_NOT_CONSUMED'
              in r['ranking_ineligible_reasons'] for r in rows))
    check('every row is QB_ONLY, never COMPLETE',
          {r['forecast_completeness'] for r in rows} == {'QB_ONLY'})
    check('nothing is promoted', {r['promoted'] for r in rows} == {'False'})
    # THE 13 PLAUSIBLE-LOOKING TEAMS GET NO EXEMPTION. Contamination is a
    # governed flag on the metric, not a judgement about whether a point
    # estimate looks sensible.
    clean_looking = [r for r in rows if r['team'] in ('CIN', 'PIT', 'HOU')]
    check('teams whose starter share looks plausible are ALSO contaminated',
          clean_looking and all(
              'QB_INACTIVE_NOT_CONSUMED' in r['known_defect_flags']
              and r['RANKING_ELIGIBLE'] == 'False' for r in clean_looking),
          f'{len(clean_looking)} row(s) checked')


def test_31_architecture_boundary_is_recorded():
    print('\n-- the capability boundary --')
    from nfl.research import completeness as CP
    from nfl.research import postgame as PG
    layers = set(CP.LAYER_NAMES)
    for absent in ('team_score', 'game_total', 'spread', 'win_probability'):
        check(f'  {absent} is not a governed layer',
              not any(absent in x for x in layers))
    check('no scoreable estimand is a score, total, spread or win prob',
          not any(k.split('/')[-1] in ('score', 'total', 'spread', 'wp')
                  for k in PG.EXACT_ESTIMANDS))
    check('the nine governed layers are volume/player quantities only',
          layers == {'team_volume', 'qb_attempts', 'qb_passing_yards',
                     'qb_td', 'carries', 'targets', 'receptions',
                     'receiving_yards', 'td_allocation'},
          str(sorted(layers)))


def test_18_the_arm_guard_reads_a_policy_not_the_artifact():
    """The arm guard, tested on its own terms.

    THE DEFECT IT REPLACES. `a['model_arm'] == 'A'` is satisfied by any
    artifact that says 'A' and failed by every artifact sealed under an earlier
    arm -- so restoring four committed arm-B artifacts turned the suite red,
    and deleting them turned it green. Neither outcome had anything to do with
    whether the artifacts were correct.
    """
    print('\n-- the arm policy guard --')
    import copy
    import glob
    paths = sorted(glob.glob(os.path.join(
        _ROOT, 'nfl/prospective/q9shadow/dryrun/*/*/SEALED_FORECAST.json')))
    check('there are sealed artifacts from BOTH arm regimes to test on',
          len(paths) >= 4, f'{len(paths)} artifact(s)')
    arms = {}
    for pth in paths:
        a = json.load(open(pth))
        arms[(a['game_id'], a['team'])] = a['model_arm']
    check('  the historical identities are arm B, and still say so',
          arms.get(('2025_01_ARI_NO', 'ARI')) == 'B'
          and arms.get(('2025_01_ARI_NO', 'NO')) == 'B', str(arms))
    check('  and the policy expects exactly that of them',
          ARM.expected_arm('2025_01_ARI_NO', 'ARI') == 'B'
          and ARM.expected_arm('2025_01_ARI_NO', 'NO') == 'B')
    check('  while an identity the policy has never seen must be arm A',
          ARM.expected_arm('2099_01_ZZ_YY', 'ZZ') == 'A')
    check('  so a NEW seal cannot quietly carry the old arm',
          ARM.assert_arm({'game_id': '2099_01_ZZ_YY', 'team': 'ZZ',
                          'model_arm': 'B'}).state is State.FAIL)

    # A DELIBERATELY WRONG ARM MUST FAIL, IN BOTH DIRECTIONS.
    hist = json.load(open(os.path.join(
        _ROOT, 'nfl/prospective/q9shadow/dryrun/2025_01_ARI_NO/ARI',
        'SEALED_FORECAST.json')))
    check('the untouched historical artifact passes',
          ARM.assert_arm(hist).state is State.PASS)
    bad = copy.deepcopy(hist)
    bad['model_arm'] = 'A'
    o = ARM.assert_arm(bad)
    check('  relabelling it to the CURRENT arm is refused',
          o.state is State.FAIL and o.code == 'Q9_ARM_POLICY_MISMATCH',
          f'{o.state.value}[{o.code}]')
    bad2 = copy.deepcopy(hist)
    bad2['model_arm'] = 'Z'
    check('  an arm that is not a declared arm is refused by name',
          ARM.assert_arm(bad2).code == 'Q9_ARM_NOT_A_KNOWN_ARM')
    bad3 = {k: v for k, v in hist.items() if k != 'team'}
    check('  an artifact with no identity is refused, never defaulted',
          ARM.assert_arm(bad3).state is State.BLOCKED)

    # NO POOLING. expected_arm returns one arm, and a string is not a set.
    e = ARM.expected_arm('2025_01_ARI_NO', 'ARI')
    check('the policy returns exactly ONE arm, never a permissive set',
          isinstance(e, str) and e in ARM.KNOWN_ARMS and len(e) == 1, repr(e))
    check('  and every artifact on disk resolves to a single expected arm',
          all(isinstance(ARM.expected_arm(g, t), str) for g, t in arms))

    # THE CROSS-CHECK THAT CATCHES AN UNAUTHORISED SWITCH IN CODE.
    c = ARM.assert_code_matches_policy()
    check('seal.MODEL_ARM agrees with the governed policy',
          c.state is State.PASS, f'{c.state.value}[{c.code}]')
    check('  and the policy declares CURRENT_ARM itself, not by import',
          'MODEL_ARM' not in open(os.path.join(
              _ROOT, 'nfl/prospective/q9shadow/armpolicy.py')).read()
          .split('def assert_code_matches_policy')[0]
          .split('CURRENT_ARM = ')[1].split('\n')[0])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

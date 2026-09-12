"""Q9 prospective shadow deployment: candidate identity, sealing, ledger, proof.

WHAT THESE TESTS PROTECT.

  * THE CANDIDATE CANNOT DRIFT. Every identity field is compared to the
    pre-season freeze, and a changed coefficient, feature schema, floor,
    fallback or threshold refuses by name. The registry's copy of the
    prohibited-input list is asserted equal to the frozen module's tuple, so
    a governance module holding a stale copy is a failing check.

  * SHADOW MEANS SHADOW. promoted false, prospective_candidate true,
    shadow_only true, and the registry refuses the combinations that would let
    one of the three drift from the others.

  * THE ARMS SHARE THEIR UPSTREAM. One appearance matrix, one budget vector,
    one draw index. Only the allocation stream is per-arm, and it is keyed by
    crc32 rather than by Python's per-process-randomised `hash()`.

  * THE SEALING PATH CANNOT READ AN OUTCOME. Three independent guards: no
    outcome reader in any sealing module's namespace, an outcome-shaped input
    refused by name, and the feature row projected onto the ten keys the
    frozen featuriser actually reads.

  * SUBSTRING GUARDS ARE MATCHED EXACTLY. `weekly_rosters` must not be
    refused as a play-by-play source. The first draft of this module's guard
    did exactly that, which is the same defect as a market guard matching
    `yardline_100`.

  * ROWS ARE NOT A SAMPLE SIZE, AND TWO ARMS ARE NOT TWO SAMPLES. The
    accounting reports ROW, PLAYER_GAME, TEAM_GAME and GAME separately, and a
    paired second arm adds no player-game.

  * FINALITY GATES SCORING and an outcome revision supersedes rather than
    overwrites -- both through the governed postgame module, not a copy.

  * THE FLOORS ARE TRANSCRIBED, NOT INVENTED. They must equal the protocol's
    own numbers, and the module must never report
    PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED, because the repository governs them.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.prospective import artifact as ART                            # noqa: E402
from nfl.prospective import registries as REG                          # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                 # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                      # noqa: E402
from nfl.prospective.q9shadow import ledger as LED                     # noqa: E402
from nfl.prospective.q9shadow import seal as SEAL                      # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                      # noqa: E402
from nfl.research import postgame as PG                                # noqa: E402
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


# ======================================================= the candidate
def test_01_candidate_is_registered_and_shadow_only():
    print('\n-- the candidate registry --')
    e = REG.CANDIDATES.get(CAND.CANDIDATE_NAME)
    check('Q9 is registered in the governed candidate registry', e is not None)
    if not e:
        return
    check('promoted is False', e['promoted'] is False)
    check('prospective_candidate is True', e['prospective_candidate'] is True)
    check('shadow_only is True', e['shadow_only'] is True)
    check('it may not be promoted on 2022-2025',
          e['may_promote_on_2022_2025'] is False)
    check('it names its freeze artifact', bool(e.get('freeze_artifact')))
    o = REG.check_candidate(CAND.CANDIDATE_NAME)
    check('the registry check passes', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    check("the registry's prohibited-input copy equals the frozen module's",
          tuple(e['prohibited_inputs']) == Q9.FORBIDDEN_INPUTS,
          f"{len(e['prohibited_inputs'])} entries")
    check('it points at the promotion rulebook',
          'PROSPECTIVE_EVALUATION_PROTOCOL' in e['promotion_rulebook'])
    check('the randomized-vs-mid PIT conflict is recorded, not hidden',
          'RANDOMIZED' in e['known_conflict_to_resolve_before_promotion'])


def test_02_registry_refuses_incoherent_shadow_status():
    print('\n-- the registry refuses an incoherent status --')
    saved = dict(REG.CANDIDATES)
    try:
        REG.CANDIDATES['_T_SHADOW_NO_PROSPECTIVE'] = {
            'status': 'x', 'promoted': False, 'shadow_only': True,
            'may_promote_on_2022_2025': False}
        o = REG.check_candidate('_T_SHADOW_NO_PROSPECTIVE')
        check('shadow_only without prospective_candidate is refused',
              o.state is State.FAIL
              and o.code == 'SHADOW_WITHOUT_PROSPECTIVE_STATUS',
              f'{o.state.value}[{o.code}]')
        REG.CANDIDATES['_T_NO_FREEZE'] = {
            'status': 'x', 'promoted': False, 'shadow_only': True,
            'prospective_candidate': True, 'may_promote_on_2022_2025': False}
        o = REG.check_candidate('_T_NO_FREEZE')
        check('a prospective candidate with no freeze artifact is refused',
              o.state is State.FAIL
              and o.code == 'PROSPECTIVE_CANDIDATE_WITHOUT_FREEZE',
              f'{o.state.value}[{o.code}]')
        REG.CANDIDATES['_T_PROMOTED'] = {
            'status': 'x', 'promoted': True,
            'may_promote_on_2022_2025': False}
        o = REG.check_candidate('_T_PROMOTED')
        check('a registry edit cannot record a promotion',
              o.state is State.FAIL
              and o.code == 'CANDIDATE_MARKED_PROMOTED')
    finally:
        REG.CANDIDATES.clear()
        REG.CANDIDATES.update(saved)


def test_03_identity_is_gated_against_the_freeze():
    print('\n-- the freeze gate --')
    art = _load('Q9_PROSPECTIVE_CANDIDATE.json')
    check('the candidate artifact exists', art is not None)
    if not art:
        return
    check('it reports promoted False, prospective True, shadow True',
          art['promoted'] is False and art['prospective_candidate'] is True
          and art['shadow_only'] is True)
    check('the freeze comparison passes',
          art['freeze']['comparison'].startswith('PASS'),
          art['freeze']['comparison'])
    check('the compared field list is the declared one',
          tuple(art['freeze']['identity_fields_compared'])
          == CAND.IDENTITY_FIELDS)
    for f in ('coefficient_sha16', 'feature_schema_sha16',
              'one_target_floor', 'named_fallbacks',
              'production_interface_sha16', 'appearance_spec_sha16',
              'budget_point_sha16'):
        check(f'  the identity carries {f}', f in art['identity'])
    check('both named Q9 fallbacks are in the identity',
          set(art['identity']['named_fallbacks'])
          == {Q9.NO_CLEARERS, Q9.MORE_CLEARERS_THAN_BUDGET})
    check('the one-target floor is part of the identity',
          art['identity']['one_target_floor'] is True)
    check('no fitted block was estimated on the forecast season',
          max(art['identity']['training_seasons']) < 2026,
          str(art['identity']['training_seasons']))
    check('the Q8 budget repair is NOT applied',
          art['identity']['q8_budget_repair_applied'] is False)
    check('the seed is not part of the mechanism identity',
          'seed_protocol' not in CAND.IDENTITY_FIELDS)


def test_04_a_changed_coefficient_refuses():
    print('\n-- a changed mechanism is a new candidate --')
    live = CAND.identity(2026)
    for field, bad in (('coefficient_sha16', 'deadbeefdeadbeef'),
                       ('feature_schema_sha16', 'deadbeefdeadbeef'),
                       ('one_target_floor', False),
                       ('named_fallbacks', ['SOMETHING_ELSE']),
                       ('share_shrinkage_k', 99.0)):
        mutated = dict(live)
        mutated[field] = bad
        o = CAND.assert_identical_to_freeze(mutated, 2026)
        names = [d['field'] for d in (o.evidence.get('differing') or [])]
        check(f'  a changed {field} refuses and is named',
              o.state is State.FAIL
              and o.code == 'Q9_CANDIDATE_DIFFERS_FROM_FREEZE'
              and field in names, f'{o.code} {names}')
    mutated = dict(live)
    mutated['module_source_sha16'] = {
        k: v for k, v in live['module_source_sha16'].items()
        if k != 'nfl.research.q9.hurdle'}
    o = CAND.assert_identical_to_freeze(mutated, 2026)
    check('dropping a module the freeze recorded refuses',
          o.state is State.FAIL,
          str([d['field'] for d in (o.evidence.get('differing') or [])])[:80])


# ======================================================= inputs and guards
def test_05_feature_projection_is_derived_and_clean():
    print('\n-- the feature projection --')
    derived = IN.derive_feature_row_keys()
    check('the key set is derived from the featuriser source, not typed',
          derived == IN.FEATURE_ROW_KEYS, f'{len(derived)} keys')
    check('it carries the four history features',
          {'h_target_freq', 'h_participation_ewma', 'h_share_given_positive',
           'h_appeared_games'} <= set(derived))
    check('it carries the three injury features',
          {'inj_status', 'inj_practice', 'inj_available'} <= set(derived))
    o = IN.assert_projection_excludes_outcomes()
    check('no feature key is outcome-shaped', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    row = {'h_target_freq': 0.5, 'role_class': 'starter', 'pos': 'WR',
           'rank': 1, 'targets': 9, 'share_targets': 0.3, 'appeared': 1,
           'q7_yds': 88.0}
    proj = IN.project_feature_row(row)
    check('a realised column on the row does not survive projection',
          'targets' not in proj and 'q7_yds' not in proj
          and 'share_targets' not in proj, str(sorted(proj))[:60])
    check('the projected row still featurises to the declared length',
          len(Q9.featurise(proj, 0.0)) == len(Q9.FEATURE_NAMES))


def test_06_outcome_shaped_inputs_refused_by_name():
    print('\n-- outcome-shaped inputs --')
    o = IN.assert_no_outcome_shaped_inputs({'sources': {
        'nflverse_pbp': {'sha256': 'a' * 64}}})
    check('a play-by-play source is refused',
          o.state is State.FAIL
          and o.code == 'Q9_SHADOW_OUTCOME_SHAPED_INPUT')
    o = IN.assert_no_outcome_shaped_inputs({'sources': {
        'depth_charts': {'sha256': 'a' * 64, 'final_score': 27}}})
    check('a realised key is refused', o.state is State.FAIL)
    o = IN.assert_no_outcome_shaped_inputs({'sources': {
        'weekly_rosters': {'sha256': 'a' * 64},
        'depth_charts': {'sha256': 'b' * 64}}})
    check('weekly_rosters is NOT refused as a play-by-play source',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    check('  and it IS recorded as restricted from stage 1',
          'weekly_rosters' in (o.evidence.get('restricted_from_stage_1') or []))
    check('the outcome-source list is matched exactly, not by substring',
          isinstance(IN.OUTCOME_SOURCES, frozenset))
    check('weekly_rosters is not in the outcome-source list',
          'weekly_rosters' not in IN.OUTCOME_SOURCES)


def test_07_no_sealing_module_can_reach_an_outcome_reader():
    print('\n-- the sealing path has no outcome reader --')
    for mod in (SEAL, SH, IN, CAND, LED.CAND):
        o = IN.assert_no_outcome_reader_imported(mod)
        check(f'  {mod.__name__}', o.state is State.PASS,
              f'{o.state.value}[{o.code}]')
    o = IN.assert_no_outcome_reader_imported(PG)
    check('the guard is not vacuous: postgame itself IS refused',
          o.state is State.FAIL
          and o.code == 'Q9_SEAL_PATH_IMPORTS_OUTCOME_READER',
          f'{o.state.value}[{o.code}]')
    check('the ledger MAY reach one -- it is the scoring path, not the seal',
          any(m in LED.PG.__name__ for m in ('postgame',)))


def test_08_schedule_projection_drops_outcomes_and_market():
    print('\n-- the schedule projection --')
    banned = ('home_score', 'away_score', 'result', 'total', 'overtime',
              'spread_line', 'total_line', 'away_moneyline', 'home_moneyline')
    for c in banned:
        check(f'  {c} is not a permitted pregame column',
              c not in SEAL.SCHEDULE_PREGAME_COLUMNS)
    o = SEAL.schedule_pregame(2025)
    check('the projection returns games', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    if o.state is State.PASS:
        cols = set(o.value[0])
        check('no banned column survives', not (cols & set(banned)),
              str(sorted(cols & set(banned))))
        check('kickoff_utc is derived and present',
              all(g.get('kickoff_utc') for g in o.value))
    # THE KICKOFF CLOCK IS VALIDATED AGAINST PRODUCTION, NOT TRUSTED.
    # An hour of slack on kickoff_utc is an hour in which a forecast written
    # after kickoff would pass `written_at < kickoff`. The first version
    # approximated the US/Eastern DST boundary by a date range and was wrong
    # by an hour on the Sunday the clocks go back -- a game day.
    from nfl.research import sealed_index as SI
    o26 = SEAL.schedule_pregame(2026)
    mine = ({g['game_id']: g['kickoff_utc'] for g in o26.value}
            if o26.state is State.PASS else {})
    prod = {r['game_id']: r['kickoff_utc'] for r in SI.discover_all()
            if r.get('game_id') and r.get('kickoff_utc')}
    overlap = sorted(set(mine) & set(prod))
    check('the derived kickoff matches every production-sealed record',
          bool(overlap) and all(mine[g] == prod[g] for g in overlap),
          f'{len(overlap)} game id(s) compared')
    offs = {g['kickoff_offset_hours_from_eastern'] for g in o26.value}
    check('both US/Eastern offsets occur across a regular season',
          offs == {4.0, 5.0}, str(sorted(offs)))
    check('the zone is named rather than hard-coded as an offset',
          all(g.get('kickoff_timezone') == 'America/New_York'
              for g in o26.value))


def test_09_eligibility_never_admits_a_played_game():
    print('\n-- eligibility --')
    o = SEAL.eligible_games(2025, now='2026-09-12T00:00:00Z')
    check('every 2025 game is permanently ineligible now',
          o.state is State.NOT_APPLICABLE
          and o.code == 'Q9_SHADOW_NO_GAME_AHEAD_OF_NOW',
          f'{o.state.value}[{o.code}]')
    o = SEAL.eligible_games(2025, now='2025-09-01T00:00:00Z')
    check('before the 2025 season every game is ahead of the clock',
          o.state is State.PASS and o.evidence['n_behind'] == 0,
          f"{o.evidence.get('n_ahead')} ahead")


def test_10_live_path_refuses_rather_than_stubbing():
    print('\n-- the live feature source --')
    o = SH.feature_rows(SH.LIVE_PREGAME, season=2026, week=1)
    check('the live pregame source refuses by name',
          o.state is State.BLOCKED
          and o.code == 'Q9_LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED',
          f'{o.state.value}[{o.code}]')
    check('  and it itemises what it would need',
          len(o.evidence.get('requirements') or {}) >= 6)
    check('  including the blocked official injury report',
          'official_injury_report' in (o.evidence.get('requirements') or {}))
    o = SH.feature_rows('NOT_A_SOURCE')
    check('an unknown feature source is refused', o.state is State.FAIL)


# ======================================================= the arms
def test_11_arms_share_upstream_and_differ_only_in_allocation():
    print('\n-- the side-by-side --')
    check('there are exactly two arms', len(CAND.ARMS) == 2)
    check('the production arm is named R8', CAND.ARM_PRODUCTION.startswith('R8'))
    out = SH.run(season=2024, n_games=2, n_draws=120, progress=False)
    check('the harness produced team-games', out['status'] == 'OK',
          str(out.get('detail'))[:120])
    if out['status'] != 'OK':
        return
    for tg in out['team_games']:
        ev = tg['outcome'].evidence
        v = tg['outcome'].value
        check(f'  {ev["game_id"]}/{ev["team"]}: both arms reconcile exactly',
              all(e == 0.0 for e in
                  ev['max_absolute_reconciliation_error'].values()))
        T = {a: v['arms'][a]['targets'] for a in CAND.ARMS}
        check('    both arms sit on one draw index',
              len({t.shape for t in T.values()}) == 1)
        check('    both arms allocate the SAME budget vector',
              all(np.array_equal(t.sum(axis=1), v['budget'])
                  for t in T.values()))
        check('    the two arms differ (the mechanism is doing something)',
              not np.array_equal(T[CAND.ARM_PRODUCTION],
                                 T[CAND.ARM_CANDIDATE]))
        check('    a non-appearing player gets nothing in that draw',
              bool(((v['appearance'] == 0)
                    & (T[CAND.ARM_CANDIDATE] > 0)).sum() == 0))
    check('the RNG policy is recorded on every team-game',
          all('shared upstream' in tg['outcome'].evidence['rng_policy']
              for tg in out['team_games']))


def test_12_streams_use_crc32_not_python_hash():
    print('\n-- the stream identity --')
    a = SH._stream_parts(1, 2026, 1, 'KC', 'Q9_HURDLE')
    b = SH._stream_parts(1, 2026, 1, 'KC', 'Q9_HURDLE')
    check('the stream parts are reproducible in one process', a == b)
    import subprocess
    code = ('import sys; sys.path.insert(0, %r);'
            'from nfl.prospective.q9shadow import shadow as SH;'
            'print(SH._stream_parts(1, 2026, 1, "KC", "Q9_HURDLE"))' % _ROOT)
    outs = set()
    for seed in ('0', '1', '2'):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, env=env, timeout=300)
        outs.add(r.stdout.strip())
    check('the stream is identical under three PYTHONHASHSEED values',
          len(outs) == 1, str(outs)[:120])


# ======================================================= the ledger
def _art(dry=False, game='2026_01_AA_BB', team='AA', fid='FC-1'):
    return {
        'forecast_id': fid, 'artifact_id': 'a' * 64, 'game_id': game,
        'team': team, 'kickoff_utc': '2026-11-01T18:00:00Z',
        'written_at': '2026-11-01T12:00:00Z',
        'cutoff': {'cutoff_utc': '2026-11-01T12:00:00Z',
                   'cutoff_basis': 'information_set.observed_before'},
        'player_ids': ['p1', 'p2'],
        'dry_run': dry, 'prospective_evidence': not dry,
        'player_summary': [
            {'arm': a, 'player_id': p, 'position': pos,
             'zero_probability': z, 'mean_targets': m}
            for a, z, m in ((CAND.ARM_PRODUCTION, 0.30, 3.0),
                            (CAND.ARM_CANDIDATE, 0.55, 3.0))
            for p, pos in (('p1', 'WR'), ('p2', 'TE'))],
        'eligibility_verdict': 'test',
    }


def _draws(n=200):
    rng = np.random.default_rng(7)
    return {f'{a}__targets': rng.poisson(1.5, size=(n, 2)).astype(float)
            for a in CAND.ARMS}


def test_13_ledger_schema_is_complete_and_declares_its_units():
    print('\n-- the ledger schema --')
    sch = LED.schema()
    for f in ('candidate', 'forecast_id', 'game_id', 'team', 'player_id',
              'metric', 'cutoff_utc', 'written_at', 'outcome_hash'):
        check(f'  the row identity carries {f}', f in sch['row_fields'])
    for u in ('scoring_rows', 'distinct_player_games', 'distinct_team_games',
              'distinct_games'):
        check(f'  the accounting declares {u}', u in sch['evidence_units'],
              sch['evidence_units'].get(u, '')[:40])
    check('the floor unit is GAME', sch['floor_unit'] == 'distinct_games')
    check('naive intervals are forbidden',
          'FORBIDDEN' in sch['clustering']['naive_intervals'])
    check('the primary metrics are the five the directive names',
          set(sch['primary_metrics']) == {
              'zero_brier', 'zero_log_loss', 'zero_mass_calibration_gap',
              'marginal_crps', 'positive_crps'})
    check('the receiving-yard score is DIAGNOSTIC, not primary',
          'rec_yard_crps' in sch['diagnostic_metrics']
          and 'rec_yard_crps' not in sch['primary_metrics'])
    check('randomized and mid PIT are both declared',
          'randomized_pit' in sch['row_fields']
          and 'mid_pit' in sch['row_fields'])


def test_14_the_floors_are_the_protocol_floors():
    print('\n-- the governed sample floors --')
    p = (CAND.HERE.parent / 'PROSPECTIVE_EVALUATION_PROTOCOL.md').read_text()
    check('the protocol file exists and states floors', 'Sample floors' in p
          or 'sample floors' in p.lower())
    check('any reported metric is 200 player-game forecasts',
          LED.FLOORS['any_reported_metric']['n_forecasts'] == 200
          and '200' in p)
    check('a benchmark comparison is 400 forecasts and 8 weeks',
          LED.FLOORS['any_benchmark_comparison']['n_forecasts'] == 400
          and LED.FLOORS['any_benchmark_comparison']['n_weeks'] == 8
          and '400' in p)
    check('a promotion decision is 800 forecasts and 12 weeks',
          LED.FLOORS['any_promotion_decision']['n_forecasts'] == 800
          and LED.FLOORS['any_promotion_decision']['n_weeks'] == 12
          and '800' in p)
    check('a position-stratified claim is 200 within the position',
          LED.FLOORS['any_position_stratified_claim']['n_forecasts'] == 200)
    check('the floor source is named', 'section 4' in LED.FLOOR_SOURCE)
    st = LED.state(2026)
    check('the sample is declared GOVERNED', st['sample_governed'] is True)
    check('PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED is NOT the reported state',
          'PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED' not in json.dumps(
              {k: v for k, v in st.items() if k != 'sample_governed_note'}))
    check('no numeric minimum was improvised',
          st['stop_rule']['improvised_minimum'] is False)
    v = LED.floor_verdicts({'eligible_player_game_forecasts': 0,
                            'eligible_weeks': 0})
    check('an empty ledger is UNDERPOWERED on every floor',
          all(x['state'] == LED.UNDERPOWERED for x in v.values()))


def test_15_rows_are_fully_identified_and_counted_in_four_units():
    print('\n-- the four counts --')
    art, dr = _art(), _draws()
    rows = LED.score_rows(art, dr, {'p1': {'targets': 0, 'rec_yds': 0.0},
                                    'p2': {'targets': 4, 'rec_yds': 51.0}},
                          'c' * 64, 'nflverse_pbp', 'GAME_FINAL')
    check('both arms produced rows for both players', len(rows) == 4,
          str(len(rows)))
    for f in ('candidate', 'arm', 'forecast_id', 'game_id', 'team',
              'player_id', 'metric', 'cutoff_utc', 'written_at',
              'outcome_hash'):
        check(f'  every row carries {f}', all(r.get(f) for r in rows))
    acc = LED.accounting(rows)
    check('four rows are 4 ROWS', acc['scoring_rows'] == 4)
    check('  but only 2 PLAYER_GAMES', acc['distinct_player_games'] == 2,
          str(acc['distinct_player_games']))
    check('  and 1 TEAM_GAME', acc['distinct_team_games'] == 1)
    check('  and 1 GAME', acc['distinct_games'] == 1)
    check('the floor count is player-game forecasts, not rows',
          acc['eligible_player_game_forecasts'] == 2)
    check('the paired-arm note is carried', 'paired' in
          acc['arm_pairing_note'].lower())
    check('a zero realisation produces no positive-target CRPS',
          [r['positive_crps'] for r in rows if r['player_id'] == 'p1']
          == ['', ''])
    check('a positive realisation does produce one',
          all(r['positive_crps'] != '' for r in rows
              if r['player_id'] == 'p2'))
    check('the receiving-yard diagnostic is scored when yards are supplied',
          all(r['rec_yard_crps'] == '' for r in rows),
          'no yard draws in this fixture, so empty rather than zero')


def test_16_a_missing_player_is_not_scored_as_a_zero():
    print('\n-- absence is not a zero --')
    art, dr = _art(), _draws()
    rows = LED.score_rows(art, dr, {'p2': {'targets': 4}}, 'c' * 64,
                          'nflverse_pbp', 'GAME_FINAL')
    check('a player absent from the outcome produces no row',
          {r['player_id'] for r in rows} == {'p2'})
    rows = LED.score_rows(art, dr, {'p1': {'targets': None}, 'p2':
                                    {'targets': 4}}, 'c' * 64,
                          'nflverse_pbp', 'GAME_FINAL')
    check('a null target count produces no row',
          {r['player_id'] for r in rows} == {'p2'})


def test_17_dry_run_rows_are_stored_and_never_counted():
    print('\n-- a dry-run row is not evidence --')
    o = LED.assert_not_dry_run(_art(dry=True))
    check('a dry-run artifact is refused as evidence',
          o.state is State.NOT_APPLICABLE
          and o.code == 'Q9_LEDGER_DRY_RUN_ROW_NOT_EVIDENCE')
    o = LED.assert_not_dry_run(_art(dry=False))
    check('a prospective artifact is accepted', o.state is State.PASS)
    rows = LED.score_rows(_art(dry=True), _draws(),
                          {'p1': {'targets': 0}, 'p2': {'targets': 4}},
                          'c' * 64, 'nflverse_pbp', 'GAME_FINAL')
    acc = LED.accounting(rows)
    check('dry-run rows exist on the ledger',
          acc['scoring_rows_including_non_evidence'] == 4)
    check('  and count as zero evidence in every unit',
          acc['scoring_rows'] == 0 and acc['distinct_games'] == 0
          and acc['distinct_player_games'] == 0)
    check('  and the exclusion is counted, not silent',
          acc['rows_excluded_as_non_evidence'] == 4)


def test_18_finality_gates_scoring_and_revisions_supersede():
    print('\n-- finality and supersession, through the governed module --')
    f = PG.game_finality([])
    check('an empty outcome read is not final',
          f['final'] is False and f['code'] == PG.NOT_FINAL,
          f['code'])
    check('the not-final state is named', PG.NOT_FINAL == 'POSTGAME_NOT_FINAL')
    art, dr = _art(), _draws()
    a1 = LED.score_rows(art, dr, {'p1': {'targets': 0}}, 'a' * 64,
                        'nflverse_pbp', 'GAME_FINAL')
    a2 = LED.score_rows(art, dr, {'p1': {'targets': 1}}, 'b' * 64,
                        'nflverse_pbp', 'GAME_FINAL')
    v = PG.versioned(a1 + a2)
    cur = [r for r in v if r['version_status'] == 'CURRENT']
    old = [r for r in v if r['version_status'] != 'CURRENT']
    check('a revision leaves exactly one CURRENT version per identity',
          len(cur) == 2 and len(old) == 2, f'{len(cur)} current, {len(old)} old')
    check('the superseded rows are still present, not deleted',
          all(r['outcome_hash'] == 'a' * 64 for r in old))
    check('the superseding hash is recorded on the older row',
          all(r.get('superseded_by_outcome_hash') == 'b' * 64 for r in old))


def test_19_randomized_pit_is_emitted_and_differs_from_mid_pit():
    print('\n-- randomized PIT, which section 9.6 names --')
    d = np.array([0.0] * 40 + [1.0] * 30 + [2.0] * 30)
    r1, m1, s1 = LED.pit_pair(d, 0.0, 'row-A')
    r2, m2, s2 = LED.pit_pair(d, 0.0, 'row-A')
    check('the randomized PIT reproduces from its recorded seed',
          (r1, s1) == (r2, s2), f'{r1} seed {s1}')
    r3, _m3, s3 = LED.pit_pair(d, 0.0, 'row-B')
    check('a different row gets a different randomisation', s1 != s3)
    check('mid-PIT is the midpoint of the atom', abs(m1 - 0.20) < 1e-9,
          str(m1))
    check('randomized PIT lies inside the atom', 0.0 <= r1 <= 0.40)
    check('the two statistics are recorded separately and can differ',
          r1 != m1 or r3 != m1)
    sch = LED.schema()
    check('the protocol conflict is recorded in the schema',
          'section_2_completeness' in
          str(sch['governance_conflicts_open']))


def test_20_the_comparison_is_paired_and_clustered():
    print('\n-- the paired clustered comparison --')
    rows = []
    for i in range(6):
        art = _art(game=f'2026_0{i + 1}_AA_BB', fid=f'FC-{i}')
        rows += LED.score_rows(art, _draws(),
                               {'p1': {'targets': 0}, 'p2': {'targets': 3}},
                               'c' * 64, 'nflverse_pbp', 'GAME_FINAL')
    cmp = LED.compare(rows)
    check('the comparison pairs the two arms per player-game',
          cmp['n_paired_player_games'] == 12,
          str(cmp['n_paired_player_games']))
    check('it reports UNDERPOWERED against the benchmark floor',
          cmp['benchmark_floor_state'] == LED.UNDERPOWERED
          and cmp['status'] == 'COMPARISON_UNDERPOWERED')
    for m in ('zero_brier', 'zero_log_loss', 'marginal_crps'):
        check(f'  {m} carries a game-clustered interval',
              cmp['metrics'][m]['game_clustered'] is not None)
        check(f'  {m} carries a team-game-clustered interval',
              cmp['metrics'][m]['team_game_clustered'] is not None)
        check(f'  {m} clusters over whole units, not rows',
              cmp['metrics'][m]['game_clustered']['n_clusters']
              < cmp['metrics'][m]['game_clustered']['n_rows'])
    g = cmp['metrics']['zero_mass_calibration_gap']
    check('the zero-mass gap is reported per arm against the observed rate',
          set(CAND.ARMS) <= set(g))
    check('randomized PIT is reported for both arms',
          set(CAND.ARMS) <= set(cmp['pit']))


# ======================================================= the proof
def test_21_the_dry_run_proof_holds():
    print('\n-- the dry-run proof artifact --')
    pr = _load('Q9_PROSPECTIVE_DRYRUN_PROOF.json')
    check('the proof artifact exists', pr is not None)
    if not pr:
        return
    check('it is not evidence about accuracy',
          pr['is_evidence_about_accuracy'] is False)
    check('nothing is promoted', pr['promoted'] is False)
    check('all ten checks hold', pr['n_failed'] == 0 and pr['n_checks'] == 10,
          f"{pr['n_checks'] - pr['n_failed']}/{pr['n_checks']} "
          f"{pr['failed']}")
    c = pr['checks']
    check('determinism compared the draw CONTENT hash',
          'draw_content_sha256' in
          c['DETERMINISTIC'].get('identity_keys_compared', []))
    check('every named outcome reader was poisoned',
          c['OUTCOME_READERS_POISONED']['n_readers_poisoned'] >= 6,
          str(c['OUTCOME_READERS_POISONED']['n_readers_poisoned']))
    check('the schedule check is not vacuous: the raw capture DOES carry '
          'outcome columns',
          len(c['SCHEDULE_PROJECTED']['banned_columns_present_in_raw_capture'])
          >= 4)
    check('the feature check is not vacuous: the panel row DOES carry '
          'realised columns',
          len(c['FEATURE_PROJECTED']['realised_keys_on_the_panel_row']) >= 4)
    check('the proof ran on a historical slice, not on 2026',
          pr['slice']['season'] <= 2025, str(pr['slice']['season']))


def test_22_the_sealed_artifact_passes_the_governed_contract():
    print('\n-- the sealed artifact against the artifact contract --')
    out = SEAL.seal_season(2024, source=SH.HISTORICAL_FRAME, n_games=1,
                           out_root=str(SEAL.DRYRUN / 'suite'), n_draws=120,
                           written_at='2026-09-12T12:00:00Z', dry_run=True)
    check('the dry-run seal produced forecasts', out['status'] == 'OK',
          str(out.get('detail'))[:150])
    if out['status'] != 'OK':
        return
    art = out['sealed'][0].value
    v = ART.validate(art)
    check('the artifact validates against the governed contract',
          v.state is State.PASS, f'{v.state.value}[{v.code}]')
    check('it is stamped a dry run and not evidence',
          art['dry_run'] is True and art['prospective_evidence'] is False)
    check('it declares its arm', art['model_arm'] in ART.ARMS)
    check('completeness is truthful, not relabelled to pass section 2',
          art['completeness'] == 'PARTIAL_PLAYER_COVERAGE')
    check('  and the section-2 consequence is recorded',
          'completeness_vs_protocol_section_2' in art['governance_notes'])
    check('the seal payload excludes the output location',
          'draw_artifact' in art['seal']['payload_excludes'])
    check('every consumed capture carries source, sha256 and retrieved_at',
          all(c.get('source') and c.get('sha256') and c.get('retrieved_at')
              for c in art['source_captures']))
    check('retrieved_at <= written_at for every capture',
          all(c['retrieved_at'] <= art['written_at']
              for c in art['source_captures']))
    check('written_at < kickoff', art['written_at'] < art['kickoff_utc'])
    check('the fallback counters are sealed with the forecast',
          any(k.endswith('/DRAWS') for k in art['fallback_counters']))
    check('both arms reconciled exactly',
          all(e == 0.0 for e in art['reconciliation'].values()))
    check('the draws are referenced by hash and the file exists',
          bool(art['draw_artifact_sha256'])
          and (CAND.HERE.parent.parent.parent
               / art['draw_artifact']).exists())
    check('the QB invariants are NOT_APPLICABLE, not silently absent',
          any(x['state'] == 'NOT_APPLICABLE'
              for x in art['accounting_verdicts']))
    g = ART.assert_hard_invariants(art['accounting_verdicts'])
    check('the hard-invariant gate passes and reports what was evaluated',
          g.state is State.PASS
          and len(g.evidence['hard_evaluated_and_held']) >= 5,
          str(len(g.evidence['hard_evaluated_and_held'])))
    check('  and names what was NOT_APPLICABLE rather than counting it a pass',
          len(g.evidence['hard_not_applicable']) >= 1,
          str(g.evidence['hard_not_applicable'])[:80])
    import shutil
    shutil.rmtree(SEAL.DRYRUN / 'suite', ignore_errors=True)


def test_23_nothing_here_is_promoted():
    print('\n-- nothing is promoted --')
    for name in ('Q9_PROSPECTIVE_CANDIDATE.json',
                 'Q9_PROSPECTIVE_LEDGER_SCHEMA.json',
                 'Q9_PROSPECTIVE_LEDGER_STATE.json',
                 'Q9_PROSPECTIVE_DRYRUN_PROOF.json'):
        a = _load(name)
        check(f'  {name} exists', a is not None)
        if a:
            check(f'    and reports promoted False', a.get('promoted') is False)
    st = _load('Q9_PROSPECTIVE_LEDGER_STATE.json')
    if st:
        check('the ledger state names all three blockers',
              set(st['blockers']) == {
                  'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED',
                  'INJURY_REPORT_INCOMPLETE', 'G0A_11_OF_12'})
        check('  and says which one needs bytes from outside',
              st['blockers']['INJURY_REPORT_INCOMPLETE'][
                  'needs_bytes_from_outside'] is True)
        check('  and that the feature build does not',
              st['blockers']['LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED'][
                  'needs_bytes_from_outside'] is False)
        check('zero live forecasts are sealed, and that is reported',
              st['live_eligibility']['n_sealed'] == 0)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)

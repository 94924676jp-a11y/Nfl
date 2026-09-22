"""Stage 6 consumes the current season, and cannot consume the future.

WHAT THIS SUITE IS FOR

`load_panel()` spans 202001-202518 with zero 2026 rows, so a 2026 week-2
forecast set every player's opportunity centre from 2025-and-older football.
These cases pin the repair and, more importantly, pin the ways it could go
wrong: leaking forward, erasing history on one game, breaking rookies, or
letting a depth listing manufacture a workload the governor refused.

ALL EVIDENCE IS PRE-KICKOFF. The live cases read the sealed 2026-09-21
captures. No NYG@LAR result is admitted anywhere, and no assertion below is
about a carry count -- only about ordering and provenance, as the directive
requires.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import current_season_evidence as CSE    # noqa: E402
from nfl.production.nonqb import opportunity_centre as OC          # noqa: E402
from nfl.production import candidate_mode as CM                    # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T23:05:00Z'
_C = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def params(target='carries'):
    if target not in _C:
        o = OC.load_params(target)
        assert o.state.name == 'PASS', (o.code, o.detail)
        _C[target] = o.value
    return _C[target]


def obs(season, week, team, share, opp=10.0, source='historical_panel'):
    return OC.Observation(season=season, week=week, team=team, share=share,
                          opportunity=opp, source=source)


def C(observations, **kw):
    kw.setdefault('position', 'RB')
    kw.setdefault('team', 'NYG')
    kw.setdefault('target', 'carries')
    kw.setdefault('target_season', 2026)
    kw.setdefault('params', params())
    kw.setdefault('shrinkage_k', 0.74)
    kw.setdefault('positional_mean', 0.12)
    return OC.centre('P', observations=observations, **kw)


# -- 1. the PIT contract ----------------------------------------------------
def test_week_n_cannot_read_week_n_or_later():
    leak = CSE.assert_pit([(2, 'NYG', 'X'), (1, 'NYG', 'Y')], before_week=2)
    ok(leak.state.name == 'FAIL' and
       leak.code == 'CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD',
       'a week-2 row inside a week-2 forecast is refused by name')
    clean = CSE.assert_pit([(1, 'NYG', 'Y')], before_week=2)
    ok(clean.state.name == 'PASS' and clean.value['max_week_used'] == 1,
       'and weeks strictly before pass, reporting the newest used')
    fut = CSE.assert_pit([(5, 'NYG', 'Z')], before_week=2)
    ok(fut.state.name == 'FAIL', 'a future week is refused too')


def test_week_2_of_2026_actually_reads_week_1_of_2026():
    o = CSE.collect(2026, 2, CUT)
    ok(o.state.name == 'PASS' and o.code == CSE.PRESENT,
       f'current-season evidence is present: {o.code}')
    ok(o.value['weeks_present'] == [1],
       f'it is week 1 and only week 1: {o.value["weeks_present"]}')
    sk = o.value['by_player'].get('00-0040715') or []
    ok(bool(sk) and sk[0]['carries'] == 18.0,
       f'Skattebo\'s measured 18 carries are in it: {sk}')
    ok(o.value['sources']['usage']['n_games'] == 16,
       f'from the widest lawful capture, 16 games, not the accepted panel\'s '
       f'{o.value["sources"]["usage"]["accepted_panel_sees_n_games"]}')
    ok('2026_01_DAL_NYG' in
       (o.value['sources']['usage']['games_the_accepted_panel_cannot_see']
        or []),
       'including the Giants game the narrower source cannot see -- the very '
       'game the repair needed')


def test_week_1_has_no_prior_week_and_that_is_a_state_not_a_failure():
    o = CSE.collect(2026, 1, CUT)
    ok(o.state.name == 'PASS' and o.code == CSE.ABSENT,
       f'week 1 reports ABSENT_NO_PRIOR_WEEK: {o.code}')
    f = CSE.assert_fresh(o, season=2026, week=1)
    ok(f.state.name == 'PASS',
       'and freshness passes: nothing is stale about evidence that cannot '
       'exist yet')


def test_stale_current_season_input_refuses_before_simulation():
    o = CSE.collect(2026, 2, CUT)
    f = CSE.assert_fresh(o, season=2026, week=8)
    ok(f.state.name == 'BLOCKED' and f.code == CSE.STALE,
       f'week-1 evidence for a week-8 forecast is {f.code}')
    na = CSE.assert_fresh(o, season=2026, week=8,
                          claims_current_season=False)
    ok(na.state.name == 'NOT_APPLICABLE',
       'a run that does not claim current-season opportunity is not held to it')


# -- 2. the weighting -------------------------------------------------------
def test_current_season_evidence_dominates_a_stale_prior():
    hist = [obs(2025, w, 'NYG', 0.50) for w in range(1, 18)]
    now = [obs(2026, 1, 'NYG', 0.05, source='current_season')]
    a_old = C(hist)
    a_new = C(hist + now)
    ok(a_new.centre < a_old.centre,
       f'one current-season game at 0.05 pulls a 0.50 prior down: '
       f'{a_old.centre:.4f} -> {a_new.centre:.4f}')
    ok(a_new.evidence_grade == OC.E_CURRENT_SEASON,
       'and the row is graded on its current-season evidence')
    ok(a_new.contributions.get(OC.E_CURRENT_SEASON, 0) > 0,
       'with a named current-season contribution in the decomposition')


def test_one_game_does_not_erase_all_historical_evidence():
    hist = [obs(2025, w, 'NYG', 0.50) for w in range(1, 18)]
    now = [obs(2026, 1, 'NYG', 0.05, source='current_season')]
    a = C(hist + now)
    ok(a.centre > 0.05,
       f'the centre is not dragged to the single observation: {a.centre:.4f}')
    ok(a.contributions.get(OC.E_PRIOR_SEASON, 0) > 0,
       'prior-season evidence still contributes, by name')
    ok(a.n_observations.get(OC.E_CURRENT_SEASON) == 1 and
       a.n_observations.get(OC.E_PRIOR_SEASON) == 17,
       f'and both counts are reported: {a.n_observations}')


def test_more_current_season_games_move_the_centre_further():
    hist = [obs(2025, w, 'NYG', 0.50) for w in range(1, 18)]
    one = C(hist + [obs(2026, 1, 'NYG', 0.05, source='current_season')])
    four = C(hist + [obs(2026, w, 'NYG', 0.05, source='current_season')
                     for w in range(1, 5)])
    ok(four.centre < one.centre,
       f'four current-season games move further than one: {one.centre:.4f} '
       f'-> {four.centre:.4f}, with no "latest game wins" rule anywhere')


def test_there_is_no_current_season_special_case_in_the_weight():
    """The repair is arithmetic, not a branch. A 2026 row and a 2025 row with
    the same recency rank and the same season differ in nothing."""
    a = C([obs(2026, 1, 'NYG', 0.30, source='current_season')])
    b = C([obs(2026, 1, 'NYG', 0.30, source='historical_panel')])
    ok(abs(a.centre - b.centre) < 1e-12,
       f'same season, same week, same share: identical centre '
       f'({a.centre:.8f} vs {b.centre:.8f}) -- the source label changes the '
       f'GRADE, never the arithmetic')
    ok(a.evidence_grade == OC.E_CURRENT_SEASON and
       b.evidence_grade != OC.E_CURRENT_SEASON,
       'while the reported grade does differ, which is the point of the label')


# -- 3. team change ---------------------------------------------------------
def test_team_change_discounts_stale_context():
    same = C([obs(2025, w, 'NYG', 0.40) for w in range(1, 18)])
    moved = C([obs(2025, w, 'PIT', 0.40) for w in range(1, 18)])
    ok(moved.retention < same.retention,
       f'a full team change retains less evidence weight: '
       f'{same.retention:.4f} -> {moved.retention:.4f}')
    ok(moved.shrinkage_weight < same.shrinkage_weight,
       f'so it shrinks harder toward the prior: '
       f'{same.shrinkage_weight:.4f} -> {moved.shrinkage_weight:.4f}')
    ok(moved.team_changed and any('another club' in n for n in moved.notes),
       'and the row says so')


def test_a_uniform_discount_alone_would_have_changed_nothing():
    """The defect this caught: n_eff and the weighted mean are both
    scale-invariant, so halving every observation of a full team-changer left
    the centre identical. Retention is what makes the discount bite."""
    moved = C([obs(2025, w, 'PIT', 0.40) for w in range(1, 18)])
    ok(abs(moved.weighted_evidence_mean - 0.40) < 1e-9,
       f'the weighted MEAN is unchanged by a uniform discount '
       f'({moved.weighted_evidence_mean:.6f}) -- as it must be')
    ok(moved.n_effective_adjusted < moved.n_effective,
       f'so the discount acts through the effective sample size instead: '
       f'{moved.n_effective:.3f} -> {moved.n_effective_adjusted:.3f}')


# -- 4. rookies and cold starts ---------------------------------------------
def test_rookie_with_one_measured_game_uses_it():
    a = C([obs(2026, 1, 'NYG', 0.45, source='current_season')])
    ok(a.basis == OC.B_EVIDENCE_SUPPORTED,
       f'a rookie with one 2026 game is evidence-supported: {a.basis}')
    ok(a.centre > 0.12,
       f'his measured share moves him above the positional mean: '
       f'{a.centre:.4f}')
    ok(a.n_observations.get(OC.E_CURRENT_SEASON) == 1,
       'on exactly one observation, reported as such')


def test_rookie_with_several_games_is_trusted_further():
    one = C([obs(2026, 1, 'NYG', 0.45, source='current_season')])
    four = C([obs(2026, w, 'NYG', 0.45, source='current_season')
              for w in range(1, 5)])
    ok(four.shrinkage_weight > one.shrinkage_weight,
       f'four games shrink less than one: {one.shrinkage_weight:.4f} -> '
       f'{four.shrinkage_weight:.4f}')
    ok(four.centre > one.centre,
       f'so the centre sits closer to what he has actually done: '
       f'{one.centre:.4f} -> {four.centre:.4f}')


def test_no_observations_anywhere_falls_to_a_measured_floor():
    a = C([], depth_anchor=None)
    ok(a.basis == OC.B_COLD_START_FLOOR,
       f'a player with nothing anywhere reads {a.basis}')
    ok(a.centre > 0.0,
       f'on the MEASURED median first-game share, not zero and not invented: '
       f'{a.centre:.4f}')
    ok(any('MEDIAN share taken by a player in his first appeared game' in n
           for n in a.notes),
       'and the row states where the floor came from')


def test_a_listed_player_with_no_history_still_gets_his_depth_anchor():
    a = C([], depth_anchor=0.33, governed_role_support='ROLE_SUPPORTED')
    ok(a.basis == OC.B_DEPTH_PRIOR and abs(a.centre - 0.33) < 1e-9,
       f'a supported role with a listing and no measurement anchors on the '
       f'listing: {a.basis} {a.centre:.4f}')


def test_veteran_with_zero_current_season_snaps_reads_historical():
    a = C([obs(2025, w, 'NYG', 0.40) for w in range(1, 18)],
          governed_role_support='ROLE_SUPPORTED')
    ok(a.basis == OC.B_HISTORICAL_SUPPORTED,
       f'no 2026 evidence and a supported role reads {a.basis}')
    ok(a.evidence_grade == OC.E_PRIOR_SEASON,
       'graded on prior-season evidence, so a reader knows what it rests on')


def test_declared_starter_with_no_measured_history_is_named_not_promoted():
    a = C([obs(2025, w, 'PIT', 0.40) for w in range(1, 6)],
          governed_role_support='ROLE_SUPPORTED', declared_starter=True)
    ok(a.basis == OC.B_DECLARED_STARTER_THIN,
       f'the thin-history starter is named: {a.basis}')
    ok(any('declaration is not itself treated as measurement' in n
           for n in a.notes),
       'and the declaration is explicitly not counted as evidence')


# -- 5. the governor reaches the generator ----------------------------------
def test_governed_refusal_withholds_the_depth_anchor():
    supported = C([], depth_anchor=0.33,
                  governed_role_support='ROLE_SUPPORTED')
    refused = C([], depth_anchor=0.33,
                governed_role_support='ROLE_UNSUPPORTED')
    ok(supported.centre > refused.centre,
       f'a refused role cannot use the listing: {supported.centre:.4f} -> '
       f'{refused.centre:.4f}')
    ok(refused.depth_anchor_available is False and
       refused.basis == OC.B_GOVERNED_ROLE_REFUSED,
       f'the anchor is marked unavailable and the basis says why: '
       f'{refused.basis}')
    ok(any('may not manufacture a workload' in n for n in refused.notes),
       'with the reason on the row')


def test_role_uncertain_is_treated_as_a_refusal():
    a = C([], depth_anchor=0.33, governed_role='ROLE_UNCERTAIN',
          governed_role_support='ROLE_SUPPORTED')
    ok(a.depth_anchor_available is False,
       'ROLE_UNCERTAIN also withholds the depth anchor, not just '
       'ROLE_UNSUPPORTED')


def test_a_refused_role_with_history_still_shrinks_toward_no_listing():
    hist = [obs(2025, w, 'PIT', 0.40) for w in range(1, 18)]
    sup = C(hist, depth_anchor=0.45, governed_role_support='ROLE_SUPPORTED')
    ref = C(hist, depth_anchor=0.45, governed_role_support='ROLE_UNSUPPORTED')
    ok(ref.shrinkage_target_name == 'positional_mean' and
       sup.shrinkage_target_name == 'depth_tier_mean',
       f'the refused row shrinks toward the positional mean rather than the '
       f'tier: {ref.shrinkage_target_name} vs {sup.shrinkage_target_name}')
    ok(ref.centre < sup.centre,
       f'which lowers it: {sup.centre:.4f} -> {ref.centre:.4f}')


# -- 6. governance ----------------------------------------------------------
def test_stage6_refuses_without_estimated_parameters():
    o = OC.load_params('carries', fit_path='/nonexistent/fit.json')
    ok(o.state.name == 'BLOCKED' and o.code == 'STAGE2_FIT_ABSENT',
       'no fit means no centre: Stage 6 refuses rather than defaulting')


def test_the_parameters_came_from_a_predeclared_fit():
    p = params()
    ok(p.get('preregistration', '').endswith('PREREGISTRATION_STAGE2.md'),
       f'the loaded parameters name their preregistration: '
       f'{p.get("preregistration")}')
    for k in ('half_life', 'season_decay', 'team_discount', 'opp_exponent'):
        ok(k in p['grid'], f'{k} is an estimated parameter, not a literal')


def test_the_new_candidate_mode_is_a_new_identity():
    new = CM.resolve(CM.V1_CANDIDATE_R9_W1P_GSVUCYS)
    old = CM.resolve(CM.V1_CANDIDATE_R9_W1P_GSVUCY)
    ok(new.state.name == 'PASS' and
       new.value['flags'].get('current_season_opportunity') is True,
       'CS6 is its own mode with its own flag')
    ok('current_season_opportunity' not in old.value['flags'],
       'and the baseline mode is untouched, so it stays reproducible')
    ok(len(new.value['components']) == len(old.value['components']) + 1,
       'exactly one component separates them')


def test_deterministic_replay():
    hist = [obs(2025, w, 'NYG', 0.4 + w / 100) for w in range(1, 18)]
    now = [obs(2026, 1, 'NYG', 0.22, source='current_season')]
    runs = {json.dumps(C(hist + now).as_dict(), sort_keys=True, default=str)
            for _ in range(8)}
    ok(len(runs) == 1,
       f'eight identical calls give one result, not {len(runs)}')
    shuffled = C(list(reversed(hist)) + now)
    ok(json.dumps(shuffled.as_dict(), sort_keys=True, default=str) ==
       json.dumps(C(hist + now).as_dict(), sort_keys=True, default=str),
       'and input order does not change it: ordering is by (season, week), '
       'never by arrival')


def main():
    for t in (test_week_n_cannot_read_week_n_or_later,
              test_week_2_of_2026_actually_reads_week_1_of_2026,
              test_week_1_has_no_prior_week_and_that_is_a_state_not_a_failure,
              test_stale_current_season_input_refuses_before_simulation,
              test_current_season_evidence_dominates_a_stale_prior,
              test_one_game_does_not_erase_all_historical_evidence,
              test_more_current_season_games_move_the_centre_further,
              test_there_is_no_current_season_special_case_in_the_weight,
              test_team_change_discounts_stale_context,
              test_a_uniform_discount_alone_would_have_changed_nothing,
              test_rookie_with_one_measured_game_uses_it,
              test_rookie_with_several_games_is_trusted_further,
              test_no_observations_anywhere_falls_to_a_measured_floor,
              test_a_listed_player_with_no_history_still_gets_his_depth_anchor,
              test_veteran_with_zero_current_season_snaps_reads_historical,
              test_declared_starter_with_no_measured_history_is_named_not_promoted,
              test_governed_refusal_withholds_the_depth_anchor,
              test_role_uncertain_is_treated_as_a_refusal,
              test_a_refused_role_with_history_still_shrinks_toward_no_listing,
              test_stage6_refuses_without_estimated_parameters,
              test_the_parameters_came_from_a_predeclared_fit,
              test_the_new_candidate_mode_is_a_new_identity,
              test_deterministic_replay):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())

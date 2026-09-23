"""The rule that decides whether a dependence number is admissible at all.

This suite exists because a number reached three documents as a verified
computation without one, and the artifacts that could have produced it say in
their own manifests that reading them that way measures the generator.

The suite therefore checks the GUARD, and it checks the guard against the
REAL artifacts in this repository rather than against fixtures alone: a rule
that refuses a synthetic manifest and would have waved through the 351 sealed
files sitting on disk is not a rule.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import dependence as D                            # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def man(across_rows):
    return {} if across_rows is None else {
        'draw_index_semantics': {'across_rows': across_rows}}


# -- 1. eligibility --------------------------------------------------------
def test_independently_seeded_rows_are_ineligible():
    o = D.assert_cross_player_eligible(man(D.INDEPENDENT_STREAMS),
                                       artifact='fixture')
    ok(o.state.name == 'FAIL' and o.code == D.INELIGIBLE,
       f'an independently-seeded artifact refuses a cross-player '
       f'correlation: {o.code}')
    ok('measures the generator' in o.detail,
       'and says what such a number would actually measure')
    ok(o.evidence['declared_semantics'] == D.INDEPENDENT_STREAMS,
       'naming the semantics the artifact itself declared')


def test_a_shared_football_world_is_eligible():
    o = D.assert_cross_player_eligible(man(D.SHARED_FOOTBALL_WORLD),
                                       artifact='hypothetical')
    ok(o.state.name == 'PASS' and o.code == D.ELIGIBLE,
       f'only a declared shared football world is admissible: {o.code}')


def test_silence_is_not_a_verdict():
    """UNDECLARED is a third answer. An artifact that never said how its
    rows relate has not said they are independent, and has not said they are
    coupled; reading silence either way is the defect."""
    for m, label in ((man(None), 'no semantics block at all'),
                     (man('COLUMN_ALIGNED'), 'an unknown semantics value')):
        o = D.assert_cross_player_eligible(m, artifact='fixture')
        ok(o.state.name == 'BLOCKED' and o.code == D.UNDECLARED,
           f'{label} is UNDECLARED, not eligible and not ineligible: '
           f'{o.code}')
        ok(o.evidence.get('cause') == 'GOVERNANCE',
           'and it is a governance refusal, not a data problem')


def test_column_alignment_alone_is_not_a_shared_world():
    ok(D.SHARED_FOOTBALL_WORLD != D.INDEPENDENT_STREAMS,
       'the two declarations are different strings, on purpose')
    ok(D.cross_player_eligibility(man('COLUMN_ALIGNED'))['verdict']
       == D.UNDECLARED,
       'and "COLUMN_ALIGNED" on its own does not buy eligibility: every '
       'player having a 17th draw is not world 17 meaning one football '
       'scenario')
    ok(len(D.REQUIRED_SHARED_LATENTS) >= 8
       and 'team_opportunity_allocation' in D.REQUIRED_SHARED_LATENTS,
       f'the latents a shared world must carry are enumerated, not left to '
       f'judgement: {len(D.REQUIRED_SHARED_LATENTS)} of them')


# -- 2. the rule against the artifacts actually on disk --------------------
def test_every_sealed_artifact_in_this_repo_is_ineligible_today():
    """The finding that produced this module, asserted rather than recalled.

    If a coupled generator ever ships, this test starts failing -- which is
    the correct moment for a human to look, because it means an artifact has
    begun claiming a shared world and somebody must check it earned it."""
    seen = {}
    for p in sorted(_REPO.glob('nfl/research/**/player_draws_manifest.json')):
        try:
            m = json.loads(p.read_text())
        except Exception:                                     # noqa: BLE001
            continue
        v = D.cross_player_eligibility(m)
        seen.setdefault(v['verdict'], []).append(p.name)
    ok(seen, f'sealed draw manifests were found and classified: '
             f'{sum(len(v) for v in seen.values())}')
    ok(set(seen) == {D.INELIGIBLE},
       f'and every one of them is INELIGIBLE for cross-player dependence: '
       f'{ {k: len(v) for k, v in seen.items()} }')


# -- 3. estimands ----------------------------------------------------------
def test_an_estimand_cannot_be_built_incomplete():
    try:
        D.Estimand(name='x', population='', conditioning='c',
                   random_dimension=D.ACROSS_GAMES, outcome='o',
                   aggregation='a')
        ok(False, 'an estimand missing its population should be refused')
    except AssertionError as e:
        ok('population' in str(e) and 'bare correlation' in str(e),
           'an estimand missing a field is refused by name: a bare '
           'correlation is not a measurement')
    try:
        D.Estimand(name='x', population='p', conditioning='c',
                   random_dimension='ACROSS_VIBES', outcome='o',
                   aggregation='a')
        ok(False, 'an undeclared random dimension should be refused')
    except AssertionError as e:
        ok('is not one of' in str(e),
           'and an undeclared random dimension is refused by name')


def test_the_two_team_opponent_estimands_are_not_comparable():
    same, why = D.OBSERVED_TEAM_VS_OPPONENT.comparable_to(
        D.SIMULATED_TEAM_VS_OPPONENT)
    ok(not same,
       'the observed and simulated team-vs-opponent numbers are NOT '
       'measuring the same thing')
    for f in ('conditioning', 'random_dimension'):
        ok(f in why, f'and the reason names {f!r}')
    ok(D.OBSERVED_TEAM_VS_OPPONENT.random_dimension == D.ACROSS_GAMES
       and D.SIMULATED_TEAM_VS_OPPONENT.random_dimension == D.ACROSS_WORLDS,
       'one varies the game, the other varies the world at a fixed game')
    ok(D.OBSERVED_TEAM_VS_OPPONENT.comparable_to(
        D.OBSERVED_TEAM_VS_OPPONENT)[0],
       'while an estimand is of course comparable with itself, so the check '
       'is not simply refusing everything')


# -- 4. the retraction, recorded where it can be found ---------------------
def test_the_minus_0_128_is_recorded_as_unverified():
    k = 'simulated_team_vs_opponent_offense_dk = -0.128'
    ok(k in D.UNVERIFIED, 'the retracted value is recorded, not deleted')
    r = D.UNVERIFIED[k]
    ok(r['status'] == 'UNVERIFIED',
       f'with status {r["status"]}, against the packet\'s '
       f'{r["claimed_as"][:24]}...')
    ok('no script, no artifact, no JSON' in r['why_unverified'],
       'saying exactly where the citation chain ends')
    ok('INELIGIBLE' in r['why_it_would_be_inadmissible_anyway'],
       'and that it would be inadmissible even if it were reproducible')
    ok('not a calibration target' in r['ruling'],
       'with the ruling stated, so it is not re-quoted from the document '
       'that overstated it')


def test_the_rederived_observed_values_are_kept_with_their_caveat():
    r = D.REDERIVED_OBSERVED
    ok(abs(r['values']['2024_REG'] - 0.1471) < 1e-9
       and abs(r['values']['2025_REG'] - 0.2068) < 1e-9,
       f'the re-derived observed values are carried: {r["values"]}')
    ok(r['n_games']['2024_REG'] == 272,
       'with the sample they came from')
    ok('+0.1201' in r['not_canonical'],
       'and the packet figure that did NOT reproduce is named rather than '
       'quietly dropped')
    ok(r['estimand'] == D.OBSERVED_TEAM_VS_OPPONENT.name,
       'tied to the estimand they measure, so they cannot be read as a '
       'within-world target')


def test_the_candidate_targets_are_labelled_candidates():
    for k, v in D.CANDIDATE_TARGETS.items():
        ok('why_a_candidate_not_a_target' in v,
           f'{k} says why it is not yet a target')
        ok('INELIGIBLE' in v['why_a_candidate_not_a_target'],
           f'and names the eligibility problem on its simulated side')
        ok('NOT re-derived' in v['observed_source'],
           f'and marks its observed side as not re-derived here')


# -- 5. replay evidence states ---------------------------------------------
def test_a_cut_is_as_replayable_as_its_weakest_requirement():
    s = D.for_cut('W3-FRI', {'pbp': D.PIT_SAFE, 'snaps': D.PIT_SAFE})
    ok(s.status == D.PIT_SAFE, f'all vintages present: {s.status}')
    s = D.for_cut('W3-FRI', {'pbp': D.PIT_SAFE,
                             'depth': D.HISTORICAL_RECONSTRUCTION_ONLY})
    ok(s.status == D.HISTORICAL_RECONSTRUCTION_ONLY,
       f'one rebuilt-after-the-fact capability downgrades the cut: '
       f'{s.status}')
    ok(s.may_be_called_a_backtest,
       'that is usable, and it is still not point-in-time')
    s = D.for_cut('W1-2023', {'pbp': D.PIT_SAFE,
                              'rosters': D.UNRECOVERABLE_FOR_CUT})
    ok(s.status == D.UNRECOVERABLE_FOR_CUT,
       f'one unrecoverable capability makes the whole cut unrecoverable: '
       f'{s.status}')
    ok(s.missing_capabilities == ('rosters',),
       f'naming it: {s.missing_capabilities}')
    ok(not s.may_be_called_a_backtest,
       'and a run over that cut may NOT be presented as a backtest -- '
       'overwritten daily rosters are not a weaker reconstruction, they '
       'are gone')


def test_pit_safe_cannot_be_asserted_over_a_gap():
    try:
        D.ReplayEvidenceStatus(status=D.PIT_SAFE, reason='looks fine',
                               missing_capabilities=('rosters',))
        ok(False, 'PIT_SAFE over a missing capability should be refused')
    except AssertionError as e:
        ok('PIT_SAFE is refused' in str(e),
           'PIT_SAFE cannot be asserted directly while a capability is '
           'missing, so the verdict cannot be talked up past its evidence')
    try:
        D.ReplayEvidenceStatus(status=D.UNRECOVERABLE_FOR_CUT, reason='no')
        ok(False, 'an unnamed unrecoverable should be refused')
    except AssertionError as e:
        ok('unfalsifiable' in str(e),
           'and UNRECOVERABLE_FOR_CUT must name what is missing')
    ok(D.for_cut('empty', {}).status == D.UNRECOVERABLE_FOR_CUT,
       'a cut declaring no requirements is UNRECOVERABLE, not PIT_SAFE: it '
       'has not been examined')


def main():
    for t in (test_independently_seeded_rows_are_ineligible,
              test_a_shared_football_world_is_eligible,
              test_silence_is_not_a_verdict,
              test_column_alignment_alone_is_not_a_shared_world,
              test_every_sealed_artifact_in_this_repo_is_ineligible_today,
              test_an_estimand_cannot_be_built_incomplete,
              test_the_two_team_opponent_estimands_are_not_comparable,
              test_the_minus_0_128_is_recorded_as_unverified,
              test_the_rederived_observed_values_are_kept_with_their_caveat,
              test_the_candidate_targets_are_labelled_candidates,
              test_a_cut_is_as_replayable_as_its_weakest_requirement,
              test_pit_safe_cannot_be_asserted_over_a_gap):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())

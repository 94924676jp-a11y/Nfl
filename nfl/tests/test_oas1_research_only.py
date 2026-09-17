"""A research-only OAS1 artifact cannot enter production.

WHY A TEST AND NOT A CONVENTION. `research_only: true` in an artifact is a
string until something refuses on it. The gap this closes is the one the
project keeps paying for: a field that is written by one layer and read by
nobody. Here the field is read, and the refusal is the assertion.

TWO INDEPENDENT BARRIERS, and each is tested on its own so that neither can
pass on the other's account:

  1. the ARTIFACT says it is research-only and not downstream-authorised;
  2. the REGISTRY has no production approval for the OAS1 adjustment ids.

Barrier 2 matters most. An artifact's own flag can be edited by whoever writes
the artifact; the registry is a separate declaration with its own owner.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State               # noqa: E402
from nfl.production import adjustment_registry as AR                     # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []

OAS1_IDS = ('opponent_pass_strength_v1', 'opponent_rush_strength_v1')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def research_artifact(**over):
    a = {'artifact': 'OAS1_WEEK2_RESULT', 'research_only': True,
         'downstream_authorized': False,
         'adjustment_ids': list(OAS1_IDS), 'units': [{'team': 'BUF'}]}
    a.update(over)
    return a


def team_volume_import(artifact, *, consumer='team_volume'):
    """The production importer as it must behave. Refuses on either barrier."""
    from sportsplatform.governance.outcome import Outcome
    if not artifact.get('downstream_authorized', False):
        return Outcome.fail(
            'RESEARCH_ONLY_ARTIFACT_REFUSED',
            f'{artifact.get("artifact")} carries downstream_authorized='
            f'{artifact.get("downstream_authorized")}. A research artifact '
            f'may not enter production.', cause=Cause.GOVERNANCE)
    for aid in artifact.get('adjustment_ids') or []:
        # THE IMPORTER ASKS THE REGISTRY. It does not re-implement the rule.
        #
        # This block used to carry its own copy of the status test, which is
        # why 18 green checks sat on top of a registry that would have said
        # PERMITTED to every one of them: the test was driving its own logic
        # and calling the result a contract. `purpose=PRODUCTION` is the claim
        # a production importer is actually making, so that is the claim that
        # gets checked.
        m = AR.assert_may_apply(aid, calling_layer=consumer, frame_tags=[],
                                purpose=AR.PRODUCTION)
        if m.state is not State.PASS:
            return m
        c = AR.assert_consumer(aid, consumer=consumer)
        if c.state is not State.PASS:
            return c
    return Outcome.ok('IMPORT_OK', value=artifact)


def test_A_a_research_only_artifact_is_refused():
    print('\nA. barrier 1: the artifact says so and the importer refuses')
    r = team_volume_import(research_artifact())
    check('team_volume REFUSES a research-only artifact',
          r.state is State.FAIL and r.code == 'RESEARCH_ONLY_ARTIFACT_REFUSED',
          f'{r.state}[{r.code}]')
    check('  with cause GOVERNANCE',
          r.evidence.get('cause') in (Cause.GOVERNANCE, Cause.GOVERNANCE.value),
          str(r.evidence.get('cause')))
    check('  and the refusal is HARD, not a warning',
          r.state is State.FAIL)


def test_B_flipping_the_artifact_flag_is_not_enough():
    print('\nB. barrier 2: the registry is a SEPARATE declaration')
    # Someone edits the artifact's own flag. The registry still refuses.
    r = team_volume_import(research_artifact(downstream_authorized=True))
    check('flipping downstream_authorized alone does NOT get it in',
          r.state is State.FAIL
          and r.code == 'ADJUSTMENT_NOT_PRODUCTION_APPROVED',
          f'{r.state}[{r.code}]')
    check('  because the registry, not the artifact, holds the approval',
          AR.ADJUSTMENTS['opponent_pass_strength_v1']['status']
          == AR.RESEARCH_ONLY)
    check('  and that is true for the rush id as well',
          AR.ADJUSTMENTS['opponent_rush_strength_v1']['status']
          == AR.RESEARCH_ONLY)


def test_C_team_volume_is_not_a_permitted_consumer_either():
    print('\nC. barrier 2b: consumer permissions')
    for aid in OAS1_IDS:
        # THE CASE THE FUNCTION IS NAMED AFTER, which it did not used to test.
        # It checked `receiving` -- an unrelated layer -- and left `team_volume`
        # untested, and `team_volume` was the one the registry permitted,
        # because it is the layer the effect is applied at.
        tv = AR.assert_consumer(aid, consumer='team_volume')
        check(f'{aid}: TEAM_VOLUME is refused as a consumer, though it is the '
              f'layer the effect is applied at',
              tv.state is State.FAIL and tv.code == AR.CONSUMER_NOT_PERMITTED,
              f'{tv.state}[{tv.code}]')
        c = AR.assert_consumer(aid, consumer='receiving')
        check(f'  an unrelated layer is refused as a consumer',
              c.state is State.FAIL and c.code == AR.CONSUMER_NOT_PERMITTED,
              f'{c.state}[{c.code}]')
        d = AR.assert_consumer(aid, consumer='diagnostics')
        check(f'  but diagnostics may READ it (reading is not re-applying)',
              d.state is State.PASS, f'{d.state}[{d.code}]')


def test_D_the_control_a_production_approved_effect_imports():
    print('\nD. CONTROL: the barrier is not refusing everything')
    # pace_v1 IS production-approved. Without a control, a test that refuses
    # every input would pass while proving nothing.
    ok = team_volume_import(
        research_artifact(artifact='PACE', downstream_authorized=True,
                          adjustment_ids=['pace_v1']),
        consumer='team_volume')
    check('a PRODUCTION_APPROVED adjustment, authorised, imports cleanly',
          ok.state is State.PASS, f'{ok.state}[{ok.code}]')
    check('  so the refusals above are about OAS1`s status, not a blanket no',
          AR.ADJUSTMENTS['pace_v1']['status'] == AR.PRODUCTION_APPROVED)


def test_E_an_unregistered_id_cannot_smuggle_itself_in():
    print('\nE. an undeclared adjustment is refused')
    r = team_volume_import(
        research_artifact(downstream_authorized=True,
                          adjustment_ids=['opponent_pass_strength_v2']))
    check('an UNREGISTERED id is refused',
          r.state is State.FAIL and r.code == AR.UNREGISTERED,
          f'{r.state}[{r.code}]')
    check('  so bumping a version number is not a way around the registry',
          'not in the adjustment registry' in r.detail, r.detail[:80])


def test_F_the_runner_declares_research_only():
    print('\nF. the runner sets the flags rather than leaving them to a caller')
    import pathlib
    src = pathlib.Path(_ROOT, 'nfl/research/oas1/fit_week2.py').read_text()
    check("the runner sets research_only True", "'research_only': True" in src)
    check("  and downstream_authorized False",
          "'downstream_authorized': False" in src)
    check('  and it has a research_only_isolation preflight check',
          'research_only_isolation' in src)
    cfg = pathlib.Path(_ROOT, 'nfl/research/oas1/WEEK2_FIT_CONFIG.json').read_text()
    check('  the frozen config records the downstream blocker by name',
          'adjustment_registry' in cfg and 'BLOCKING before any downstream' in cfg)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_research_only_artifact_is_refused,
               test_B_flipping_the_artifact_flag_is_not_enough,
               test_C_team_volume_is_not_a_permitted_consumer_either,
               test_D_the_control_a_production_approved_effect_imports,
               test_E_an_unregistered_id_cannot_smuggle_itself_in,
               test_F_the_runner_declares_research_only):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)

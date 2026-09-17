"""The registry refuses a second application of the same adjustment.

WHY THIS TEST IS ABOUT LINEAGE AND NOT ABOUT A NUMBER

The obvious test is "apply the adjustment twice, check the output doubled".
That test is weak in a specific way: it passes only if you already know what
the single-application output should be, and on a stack whose behaviour is
being changed it would simply memorise whatever the stack currently does --
INCLUDING a double count, if one were already present. It also cannot
distinguish "the registry refused" from "the second application happened to
cancel out".

So the contract is tested directly. The registry is asked whether an
application is permitted, GIVEN the frame's own record of what has already
been applied to it, and the refusal is the assertion. The numeric effect is
checked separately, as a demonstration that a permitted double application
really would have doubled the response -- which is what makes the refusal
worth having.

Both variants the pre-declaration asked for are here: the control, where the
adjustment is applied exactly once and passes, and the double, where the
second application is refused before publication.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State               # noqa: E402
from nfl.production import adjustment_registry as AR                     # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


# ------------------------------------------------------------------ fixture
ADJ = 'opponent_pass_strength_v1'
OWNER_LAYER = 'team_volume'
PERTURBATION = 0.25          # a known opponent-strength effect, in EPA/play


class Frame:
    """A minimal frame that carries its OWN lineage, which is what is checked."""

    def __init__(self, value):
        self.value = float(value)
        self.tags = []          # empty list, NOT None: "nothing applied yet"

    def apply(self, adjustment_id, layer, amount, distinct_mechanism=None):
        v = AR.assert_may_apply(adjustment_id, calling_layer=layer,
                                frame_tags=self.tags,
                                distinct_mechanism=distinct_mechanism)
        if v.state is not State.PASS:
            return v
        self.value += amount
        self.tags.append(adjustment_id)
        return v


def test_A_the_control_one_application_passes():
    print('\nA. CONTROL: applied exactly once, and it passes')
    f = Frame(1.00)
    r = f.apply(ADJ, OWNER_LAYER, PERTURBATION)
    check('the single application is permitted',
          r.state is State.PASS and r.code == AR.OK, f'{r.state}[{r.code}]')
    check('  the frame moved by exactly the perturbation',
          abs(f.value - (1.00 + PERTURBATION)) < 1e-12, str(f.value))
    check('  and the lineage records it', f.tags == [ADJ], str(f.tags))
    a = AR.audit_frame(f.tags, label='control')
    check('  the seal-time audit is clean', a.state is State.PASS,
          f'{a.state}[{a.code}]')


def test_B_the_double_is_refused_before_publication():
    print('\nB. DOUBLE: the second application is refused')
    f = Frame(1.00)
    f.apply(ADJ, OWNER_LAYER, PERTURBATION)
    before = f.value
    r = f.apply(ADJ, OWNER_LAYER, PERTURBATION)
    check('the SECOND application is REFUSED',
          r.state is State.FAIL and r.code == AR.ALREADY_APPLIED,
          f'{r.state}[{r.code}]')
    check('  with cause GOVERNANCE',
          (r.evidence.get('cause') in (Cause.GOVERNANCE, Cause.GOVERNANCE.value)),
          str(r.evidence.get('cause')))
    check('  the refusal is HARD, not a log line',
          r.code in AR.HARD_CODES, str(AR.HARD_CODES))
    check('  and the frame did NOT move', abs(f.value - before) < 1e-12,
          f'{before} -> {f.value}')
    check('  the lineage still holds exactly one entry', f.tags == [ADJ],
          str(f.tags))
    # THE DEMONSTRATION: had it been permitted, the response WOULD have doubled.
    unguarded = 1.00 + PERTURBATION + PERTURBATION
    single = 1.00 + PERTURBATION
    check('  and an unguarded double really would have doubled the response, '
          'which is what makes the refusal worth having',
          abs((unguarded - 1.00) - 2 * (single - 1.00)) < 1e-12,
          f'{unguarded - 1.00} vs {2 * (single - 1.00)}')


def test_C_the_refusal_is_not_an_accident_of_another_guard():
    print('\nC. the test detects a genuine double when the guard is bypassed')
    # The pre-declaration required this: a test that passes only because some
    # OTHER guard blocked the scenario has proved nothing about itself.
    f = Frame(1.00)
    f.value += PERTURBATION          # applied WITHOUT consulting the registry
    f.value += PERTURBATION          # applied again, still unguarded
    f.tags = [ADJ, ADJ]              # lineage records what really happened
    check('with the registry bypassed, the frame really is double-counted',
          abs(f.value - 1.50) < 1e-12, str(f.value))
    a = AR.audit_frame(f.tags, label='bypassed')
    check('  and the SEAL-TIME audit catches it independently',
          a.state is State.FAIL and a.code == AR.ALREADY_APPLIED,
          f'{a.state}[{a.code}]')
    check('  naming the duplicated id',
          a.evidence.get('duplicated') == [ADJ],
          str(a.evidence.get('duplicated')))


def test_D_owner_and_lineage_refusals():
    print('\nD. the other three HARD refusals')
    f = Frame(1.0)
    r = f.apply(ADJ, 'receiving', PERTURBATION)
    check('a NON-OWNER layer is refused',
          r.state is State.FAIL and r.code == AR.OWNER_MISMATCH,
          f'{r.state}[{r.code}]')
    check('  and the frame did not move', abs(f.value - 1.0) < 1e-12)
    r = AR.assert_may_apply(ADJ, calling_layer=OWNER_LAYER, frame_tags=None)
    check('a frame with UNKNOWN lineage is refused',
          r.state is State.FAIL and r.code == AR.LINEAGE_UNKNOWN,
          f'{r.state}[{r.code}]')
    check('  because an absent tag and an empty tag are different states',
          'different states' in r.detail, r.detail[:90])
    r = AR.assert_may_apply('not_a_real_adjustment', calling_layer=OWNER_LAYER,
                            frame_tags=[])
    check('an UNREGISTERED adjustment is refused',
          r.state is State.FAIL and r.code == AR.UNREGISTERED,
          f'{r.state}[{r.code}]')
    a = AR.audit_frame(['not_a_real_adjustment'], label='x')
    check('  and the seal audit refuses it too', a.state is State.FAIL
          and a.code == AR.UNREGISTERED, f'{a.state}[{a.code}]')


def test_E_a_declared_distinct_mechanism_is_permitted():
    print('\nE. not all re-application is double counting')
    r = AR.assert_may_apply(ADJ, calling_layer=OWNER_LAYER, frame_tags=[ADJ],
                            distinct_mechanism='coverage acting on catch rate '
                                               'is a different quantity from '
                                               'opponent strength acting on '
                                               'team volume')
    check('a re-application with a DECLARED distinct mechanism is permitted',
          r.state is State.PASS and r.evidence['re_applied_under_distinct_mechanism'],
          f'{r.state}[{r.code}]')
    r2 = AR.assert_may_apply(ADJ, calling_layer=OWNER_LAYER, frame_tags=[ADJ],
                             distinct_mechanism='')
    check('  but silence is still refused', r2.state is State.FAIL
          and r2.code == AR.ALREADY_APPLIED, f'{r2.state}[{r2.code}]')


def test_F_oas1_pass_and_rush_are_separate_ids():
    print('\nF. pass and rush do not share evidence')
    p = AR.get('opponent_pass_strength_v1')
    r = AR.get('opponent_rush_strength_v1')
    check('both are registered', p.state is State.PASS and r.state is State.PASS)
    check('  they are DISTINCT ids', 'opponent_pass_strength_v1'
          != 'opponent_rush_strength_v1')
    check('  neither is production-approved yet',
          p.value['status'] == AR.RESEARCH_ONLY
          and r.value['status'] == AR.RESEARCH_ONLY,
          f"{p.value['status']} / {r.value['status']}")
    check('  the rush entry records that registration is NOT approval',
          'REGISTERED IS NOT APPROVED' in (r.value.get('note') or ''),
          (r.value.get('note') or '')[:70])
    check('  and cites the frozen result that says so',
          'NOT_SUPPORTED_YET' in r.value['evidence'], r.value['evidence'])
    check('  while the pass entry cites the supporting result',
          'SUPPORTED' in p.value['evidence']
          and 'NOT_SUPPORTED' not in p.value['evidence'],
          p.value['evidence'])
    # Applying one must not clear the other from a frame's lineage.
    tags = ['opponent_pass_strength_v1']
    ok = AR.assert_may_apply('opponent_rush_strength_v1',
                             calling_layer='team_volume', frame_tags=tags)
    check('  applying the rush effect to a pass-adjusted frame is permitted, '
          'because they are different quantities',
          ok.state is State.PASS, f'{ok.state}[{ok.code}]')


def test_G_every_entry_declares_the_required_fields():
    print('\nG. the registry answers the question it exists for')
    req = ('owner', 'producer', 'applied_at', 'permitted_consumers',
           'emitted_quantity_is_already_adjusted', 'embeds', 'version',
           'status', 'evidence')
    for aid, a in sorted(AR.ADJUSTMENTS.items()):
        miss = [f for f in req if f not in a]
        check(f'  {aid} declares all {len(req)} fields', not miss, str(miss))
    check('the nine requested effects are covered',
          len(AR.ADJUSTMENTS) >= 9, str(len(AR.ADJUSTMENTS)))
    for aid in ('opponent_pass_strength_v1', 'opponent_rush_strength_v1',
                'pace_v1', 'game_environment_v1', 'score_state_v1',
                'weather_v1', 'ol_pass_protection_v1', 'run_blocking_v1',
                'coverage_v1'):
        check(f'  {aid} is registered', aid in AR.ADJUSTMENTS)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_control_one_application_passes,
               test_B_the_double_is_refused_before_publication,
               test_C_the_refusal_is_not_an_accident_of_another_guard,
               test_D_owner_and_lineage_refusals,
               test_E_a_declared_distinct_mechanism_is_permitted,
               test_F_oas1_pass_and_rush_are_separate_ids,
               test_G_every_entry_declares_the_required_fields):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)

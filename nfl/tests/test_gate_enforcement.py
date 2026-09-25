"""Enforcement: a fired gate stops the consumer, and NOT_CHECKED is not a pass.

The regression in section F replays the gate state as it actually stood for
ATL/GB on 2026-09-24, when a selector consumed a state the board had already
refused with NFL1_NOT_AUTHORIZED.

Written to `run_suite.py`'s convention -- module-level PASSED/FAILED and
`test_*` names -- because the first draft used `t_*` and its own list, and the
suite reported the whole module as `0 fn, NO TALLY`. Every check in it was
invisible: had all of them failed, the suite would still have said PASS.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs import gate_enforcement as GE                     # noqa: E402
from nfl.dfs import player_universe as PU                      # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    """(did_raise_with_needle, detail)."""
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                      # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def _all_hard_pass():
    return {g: GE.PASSED for g, s in GE.SEVERITY.items() if s == GE.HARD}


def test_A_a_failed_hard_gate_stops_a_product():
    print('\nA. detection was never the missing piece')
    v = dict(_all_hard_pass(), board_authorization=GE.FAILED)
    ok, d = raised(GE.ConsumptionRefused,
                   lambda: GE.assert_may_consume(v, 'dfs.showdown.selector'),
                   'HARD gate(s) FAILED')
    check('the selector is refused', ok, d)
    ok2, d2 = raised(GE.ConsumptionRefused,
                     lambda: GE.assert_may_consume(v, 'someone.new'))
    check('an unclassified consumer gets the same refusal', ok2, d2)


def test_B_not_checked_is_not_a_pass():
    print('\nB. the state that gets read as a pass')
    v = _all_hard_pass()
    del v['pregame_readiness.execution']
    ok, d = raised(GE.ConsumptionRefused,
                   lambda: GE.assert_may_consume(v, 'dfs.showdown.selector'),
                   'NOT_CHECKED (not the same as passed)')
    check('a HARD gate nobody evaluated blocks', ok, d)


def test_C_severity_is_declared_not_inferred():
    print('\nC. a diagnostic reports and does not block')
    v = dict(_all_hard_pass(), unavailable_owns_nothing=GE.FAILED)
    rec = GE.assert_may_consume(v, 'dfs.showdown.selector')
    check('a failed DIAGNOSTIC does not stop the build',
          rec['may_consume'] is True, rec)
    check('but it is still reported by name',
          rec['failed_diagnostic'] == ['unavailable_owns_nothing'],
          rec['failed_diagnostic'])
    ok, d = raised(GE.GateUnknown,
                   lambda: GE.decide(dict(_all_hard_pass(),
                                          invented_gate=GE.PASSED),
                                     'dfs.showdown.selector'),
                   'no declared severity')
    check('an unclassified gate is an error, not a default', ok, d)


def test_D_a_diagnostic_may_run_against_a_broken_state():
    print('\nD. refusing the auditor makes a failing game unauditable')
    v = dict(_all_hard_pass(), board_authorization=GE.FAILED)
    rec = GE.assert_may_consume(v, 'tools.pool_audit')
    check('a consumer that stakes nothing proceeds',
          rec['may_consume'] is True, rec)
    check('and still SEES the failure it ran against',
          rec['failed_hard'] == ['board_authorization'], rec['failed_hard'])


def test_E_not_exercised_is_not_evidence():
    print('\nE. nothing to catch is not proof the catching works')
    v = dict(_all_hard_pass(), unavailable_owns_nothing=GE.NOT_EXERCISED)
    rec = GE.assert_may_consume(v, 'dfs.showdown.selector')
    check('it proceeds', rec['may_consume'] is True, rec)
    check('and is marked not citable as mechanism evidence',
          rec['citable_as_mechanism_evidence'] is False, rec)
    clean = GE.decide(_all_hard_pass(), 'dfs.showdown.selector')
    check('a fully exercised pass IS citable',
          clean['may_consume'] and clean['citable_as_mechanism_evidence'],
          clean)
    check('NOT_APPLICABLE maps to NOT_EXERCISED',
          GE.classify_unavailable_owns_nothing(
              {'state': 'NOT_APPLICABLE'}) == GE.NOT_EXERCISED)
    check('an absent verdict maps to NOT_CHECKED',
          GE.classify_unavailable_owns_nothing(None) == GE.NOT_CHECKED)
    check('FAIL maps to FAILED',
          GE.classify_unavailable_owns_nothing({'state': 'FAIL'}) == GE.FAILED)
    check('an UNKNOWN readiness layer is NOT_CHECKED, not ELIGIBLE',
          GE.classify_readiness({'execution_verdict': 'ELIGIBLE',
                                 'unknown_layers': ['depth']})
          == GE.NOT_CHECKED)
    check('a clean readiness matrix passes',
          GE.classify_readiness({'execution_verdict': 'ELIGIBLE',
                                 'unknown_layers': []}) == GE.PASSED)
    check('a refused matrix fails',
          GE.classify_readiness({'execution_verdict': 'REFUSED'}) == GE.FAILED)
    check('no matrix at all is NOT_CHECKED',
          GE.classify_readiness(None) == GE.NOT_CHECKED)


def test_F_20260924_atl_gb_would_have_been_stopped():
    print('\nF. the gate state as it actually stood that night')
    actual = {
        'board_authorization': GE.FAILED,
        'healthy_qb1_zero_opportunity_anomaly': GE.FAILED,
        'authoritative_inactive_nonzero_opportunity': GE.NOT_CHECKED,
        'unavailable_owns_nothing': GE.FAILED,
    }
    rec = GE.decide(actual, 'dfs.showdown.selector')
    check('the selector may NOT consume it', rec['may_consume'] is False, rec)
    check('board_authorization is named',
          'board_authorization' in rec['failed_hard'], rec['failed_hard'])
    check('the QB1 anomaly is named',
          'healthy_qb1_zero_opportunity_anomaly' in rec['failed_hard'],
          rec['failed_hard'])
    check('the never-evaluated inactive gate is named separately',
          'authoritative_inactive_nonzero_opportunity' in rec['unchecked_hard'],
          rec['unchecked_hard'])


def test_G_the_universe_builder_cannot_skip_the_gates():
    print('\nG. omitting the verdicts must not read as "they passed"')
    ok, d = raised(GE.ConsumptionRefused,
                   lambda: PU.build('/nonexistent.json', '/nonexistent.npz',
                                    '/nonexistent.csv', {},
                                    'dfs.showdown.selector', eligible=set()),
                   'NOT_CHECKED')
    check('a strict build with no gate verdicts is refused', ok, d)

"""Enforcement: a fired gate stops the consumer, and NOT_CHECKED is not a pass.

The regression at the bottom replays the gate state as it actually stood for
ATL/GB on 2026-09-24, when a selector consumed a state the board had already
refused. The test asserts it would now be stopped.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs import gate_enforcement as GE                     # noqa: E402
from nfl.dfs import player_universe as PU                      # noqa: E402
from nfl.production.contracts import completeness as CC        # noqa: E402

FAIL = []


def check(label, fn):
    try:
        fn()
        print(f'  ok    {label}')
    except AssertionError as e:
        FAIL.append(f'{label}: {e}')
        print(f'  FAIL  {label}: {e}')
    except Exception as e:                                      # noqa: BLE001
        FAIL.append(f'{label}: unexpected {type(e).__name__}: {e}')
        print(f'  ERROR {label}: {type(e).__name__}: {e}')


def raises(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        assert needle is None or needle in str(e), \
            f'raised without {needle!r}: {e}'
        return
    raise AssertionError(f'did not raise {exc.__name__}')


_ALL_HARD_PASS = {g: GE.PASSED for g, s in GE.SEVERITY.items() if s == GE.HARD}


def t_failed_hard_gate_refuses_a_product():
    v = dict(_ALL_HARD_PASS, board_authorization=GE.FAILED)
    raises(GE.ConsumptionRefused,
           lambda: GE.assert_may_consume(v, 'dfs.showdown.selector'),
           'HARD gate(s) FAILED')


def t_not_checked_is_not_a_pass():
    v = {g: GE.PASSED for g in _ALL_HARD_PASS}
    del v['pregame_readiness.execution']
    raises(GE.ConsumptionRefused,
           lambda: GE.assert_may_consume(v, 'dfs.showdown.selector'),
           'NOT_CHECKED (not the same as passed)')


def t_failed_diagnostic_does_not_block():
    v = dict(_ALL_HARD_PASS, unavailable_owns_nothing=GE.FAILED)
    rec = GE.assert_may_consume(v, 'dfs.showdown.selector')
    assert rec['may_consume'] is True
    assert rec['failed_diagnostic'] == ['unavailable_owns_nothing'], \
        'a diagnostic failure must still be reported, just not blocking'


def t_unclassified_gate_is_an_error_not_a_default():
    raises(GE.GateUnknown,
           lambda: GE.decide(dict(_ALL_HARD_PASS, invented_gate=GE.PASSED),
                             'dfs.showdown.selector'),
           'no declared severity')


def t_diagnostic_may_run_against_a_broken_state():
    """Refusing the auditor on a failing game makes it unauditable."""
    v = dict(_ALL_HARD_PASS, board_authorization=GE.FAILED)
    rec = GE.assert_may_consume(v, 'tools.pool_audit')
    assert rec['may_consume'] is True
    assert rec['failed_hard'] == ['board_authorization'], \
        'it must still SEE the failure it is allowed to run against'


def t_unknown_consumer_gets_the_safe_behaviour():
    v = dict(_ALL_HARD_PASS, board_authorization=GE.FAILED)
    raises(GE.ConsumptionRefused,
           lambda: GE.assert_may_consume(v, 'someone.new'))


def t_not_exercised_proceeds_but_is_not_evidence():
    v = dict(_ALL_HARD_PASS, unavailable_owns_nothing=GE.NOT_EXERCISED)
    rec = GE.assert_may_consume(v, 'dfs.showdown.selector')
    assert rec['may_consume'] is True
    assert rec['citable_as_mechanism_evidence'] is False, \
        'nothing to catch is not proof the catching works'


def t_all_pass_is_citable():
    rec = GE.decide(dict(_ALL_HARD_PASS), 'dfs.showdown.selector')
    assert rec['may_consume'] and rec['citable_as_mechanism_evidence']


def t_classifier_keeps_not_applicable_and_absent_apart():
    assert GE.classify_unavailable_owns_nothing(
        {'state': 'NOT_APPLICABLE'}) == GE.NOT_EXERCISED
    assert GE.classify_unavailable_owns_nothing(None) == GE.NOT_CHECKED
    assert GE.classify_unavailable_owns_nothing({'state': 'FAIL'}) == GE.FAILED


def t_readiness_unknown_layer_is_not_checked():
    assert GE.classify_readiness(
        {'execution_verdict': 'ELIGIBLE', 'unknown_layers': ['depth']}) \
        == GE.NOT_CHECKED
    assert GE.classify_readiness(
        {'execution_verdict': 'ELIGIBLE', 'unknown_layers': []}) == GE.PASSED
    assert GE.classify_readiness({'execution_verdict': 'REFUSED'}) == GE.FAILED
    assert GE.classify_readiness(None) == GE.NOT_CHECKED


def t_universe_build_refuses_without_gates():
    """Omitting gate_verdicts must not read as "the gates passed"."""
    raises(GE.ConsumptionRefused,
           lambda: PU.build('/nonexistent.json', '/nonexistent.npz',
                            '/nonexistent.csv', {}, 'dfs.showdown.selector',
                            eligible=set()),
           'NOT_CHECKED')


def t_20260924_atl_gb_state_would_have_been_stopped():
    """The actual gate state that night, replayed."""
    actual = {
        'board_authorization': GE.FAILED,
        'healthy_qb1_zero_opportunity_anomaly': GE.FAILED,
        'authoritative_inactive_nonzero_opportunity': GE.NOT_CHECKED,
        'unavailable_owns_nothing': GE.FAILED,
    }
    rec = GE.decide(actual, 'dfs.showdown.selector')
    assert rec['may_consume'] is False
    assert 'board_authorization' in rec['failed_hard']
    assert 'healthy_qb1_zero_opportunity_anomaly' in rec['failed_hard']
    assert 'authoritative_inactive_nonzero_opportunity' in rec['unchecked_hard']


if __name__ == '__main__':
    print('gate enforcement')
    for name, fn in sorted(globals().items()):
        if name.startswith('t_') and callable(fn):
            check(name[2:], fn)
    print()
    if FAIL:
        print(f'{len(FAIL)} failure(s)')
        raise SystemExit(1)
    print('all pass')

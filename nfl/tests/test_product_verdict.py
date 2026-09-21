"""Minimum P0-C: the three answers, and the distinction that makes them worth having.

WHAT THIS PINS, AND WHY EACH ONE IS A REAL FAILURE MODE

1. RESEARCH_ONLY and NO_SUPPORTED_EDGE are different claims. Collapsing them
   lets a broken model hide behind "we looked and found nothing", which is the
   most flattering possible description of a system that never worked. A scope
   reaches NO_SUPPORTED_EDGE only once every readiness gate has passed.
2. An ABSENT required gate is NOT_EVALUATED, never PASS. The failure mode is
   the whole reason the file exists: a gate nobody ran reading as a gate that
   passed is exactly how "DEPLOYABLE" gets printed over an unmeasured board.
3. Scopes are cumulative and the direction matters. A football failure blocks
   the DFS product; a DFS-only failure says nothing about the football
   simulation beneath it. This is the same inversion the owner caught in the
   artifact contract, pinned here so it cannot come back in a second file.
4. `render_status_line` takes no prose argument. A signature that accepts a
   human note will eventually be passed one, and the first line stops being
   generated.
5. The status line survives a blocked Outcome. The payload of a blocked
   governance Outcome lives in `.evidence`, not `.value`; a renderer that
   reads only `.value` crashes on precisely the boards that most need a first
   line, which is a silent-failure-as-success in the delivery layer itself.
"""
from __future__ import annotations

import inspect
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import verdict as V                          # noqa: E402
from sportsplatform.governance.outcome import (                  # noqa: E402
    Cause, Outcome, State)

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _all_pass(scope):
    return {g: V.PASS for g in V.required_gates(scope)}


def test_scope_chain_is_cumulative_and_directed():
    ok(V.ancestors('football') == ('football',),
       'football is the root and inherits nothing')
    ok(V.ancestors('dfs_product') == ('football', 'dfs_product'),
       f'dfs inherits football: {V.ancestors("dfs_product")}')
    ok(V.ancestors('prop_product') == ('football', 'prop_product'),
       f'props inherit football: {V.ancestors("prop_product")}')

    fb = set(V.required_gates('football'))
    dfs = set(V.required_gates('dfs_product'))
    prop = set(V.required_gates('prop_product'))
    ok(fb < dfs and fb < prop,
       f'every football gate is required downstream: |fb|={len(fb)} '
       f'|dfs|={len(dfs)} |prop|={len(prop)}')
    ok(not (dfs & prop) - fb,
       'the two product scopes share nothing but their football parent')
    ok(len(fb) >= 10, f'the football scope is not a stub: {len(fb)} gates')

    try:
        V.required_gates('no_such_scope')
        ok(False, 'an unknown scope must raise, not resolve to an empty set')
    except KeyError:
        ok(True, 'an unknown scope raises rather than requiring zero gates')


def test_all_gates_passing_is_the_only_deployable():
    for scope in ('football', 'prop_product', 'dfs_product'):
        o = V.assess(_all_pass(scope), scope=scope)
        v = o.value
        ok(v['VERDICT'] == V.DEPLOYABLE, f'{scope} all-pass is DEPLOYABLE')
        ok(o.state is State.PASS,
           f'{scope} deployable carries a PASS state: {o.state}')
        ok(v['n_passed'] == v['n_required'] and not v['blocking_gates'],
           f'{scope} counts {v["n_passed"]}/{v["n_required"]} with no blocker')
        ok(v['first_blocking_gate'] is None,
           f'{scope} names no blocking gate when nothing blocks')


def test_an_absent_required_gate_is_not_a_passing_gate():
    # The single most dangerous default in the file.
    gates = _all_pass('football')
    gates.pop('PLAYER_COVERAGE')
    o = V.assess(gates, scope='football')
    v = o.value or o.evidence['value']
    ok(v['VERDICT'] == V.RESEARCH_ONLY,
       f'a missing gate blocks rather than clears: {v["VERDICT"]}')
    ok(v['gates']['PLAYER_COVERAGE'] == V.NOT_EVALUATED,
       f'the missing gate reads NOT_EVALUATED: {v["gates"]["PLAYER_COVERAGE"]}')
    ok(v['first_blocking_gate'] == 'PLAYER_COVERAGE',
       'the missing gate is named as the blocker')

    o2 = V.assess({}, scope='dfs_product')
    v2 = o2.value or o2.evidence['value']
    ok(v2['VERDICT'] == V.RESEARCH_ONLY and v2['n_passed'] == 0,
       f'an empty result dict clears nothing: {v2["VERDICT"]} '
       f'{v2["n_passed"]} passed')

    # A junk value is not a pass either.
    g3 = _all_pass('football')
    g3['ROLE_PLAUSIBILITY'] = 'probably fine'
    v3 = (V.assess(g3, scope='football').evidence or {})['value']
    ok(v3['gates']['ROLE_PLAUSIBILITY'] == V.NOT_EVALUATED,
       'an unrecognised gate result degrades to NOT_EVALUATED, not to PASS')


def test_readiness_failure_and_no_edge_are_never_the_same_answer():
    # Readiness fails -> RESEARCH_ONLY even though the edge gate also fails.
    g = _all_pass('prop_product')
    g['PER_CLUB_LAYER_COVERAGE'] = V.FAIL
    g['PROP_CALIBRATION_STATUS'] = V.UNSUPPORTED
    v = (V.assess(g, scope='prop_product').evidence or {})['value']
    ok(v['VERDICT'] == V.RESEARCH_ONLY,
       f'a broken football layer cannot report "no edge found": {v["VERDICT"]}')
    ok(v['first_blocking_gate'] == 'PER_CLUB_LAYER_COVERAGE',
       f'the readiness gate is the blocker, not the calibrator: '
       f'{v["first_blocking_gate"]}')

    # Readiness all passes, edge gate does not -> NO_SUPPORTED_EDGE.
    g2 = _all_pass('prop_product')
    g2['PROP_CALIBRATION_STATUS'] = V.UNSUPPORTED
    v2 = (V.assess(g2, scope='prop_product').evidence or {})['value']
    ok(v2['VERDICT'] == V.NO_SUPPORTED_EDGE,
       f'a ready system with no validated calibration finds no edge: '
       f'{v2["VERDICT"]}')
    ok(v2['first_blocking_gate'] == 'PROP_CALIBRATION_STATUS',
       'the edge gate is named')
    ok('IS ready' in v2['why'],
       'the NO_SUPPORTED_EDGE reason says the system was ready')

    g3 = _all_pass('dfs_product')
    g3['DFS_FIELD_MODEL_STATUS'] = V.UNSUPPORTED
    v3 = (V.assess(g3, scope='dfs_product').evidence or {})['value']
    ok(v3['VERDICT'] == V.NO_SUPPORTED_EDGE,
       f'the same holds for DFS: {v3["VERDICT"]}')

    # And a DFS readiness gate failing is RESEARCH_ONLY, not no-edge.
    g4 = _all_pass('dfs_product')
    g4['DK_SCORING_PRESENT'] = V.FAIL
    v4 = (V.assess(g4, scope='dfs_product').evidence or {})['value']
    ok(v4['VERDICT'] == V.RESEARCH_ONLY,
       f'a missing scoring layer is unreadiness, not absence of edge: '
       f'{v4["VERDICT"]}')


def test_upstream_invalidity_flows_down_and_never_up():
    g = _all_pass('dfs_product')
    g['PER_CLUB_POSITION_COVERAGE'] = V.FAIL
    v = (V.assess(g, scope='dfs_product').evidence or {})['value']
    ok(v['VERDICT'] == V.RESEARCH_ONLY, 'a football failure blocks the product')
    ok(v['blocked_by_upstream_scopes'] == ['football'],
       f'the blocking scope is attributed upstream: '
       f'{v["blocked_by_upstream_scopes"]}')
    ok(v['blocking_gates'][0]['is_upstream'] is True,
       'the blocking gate is marked as not belonging to this scope')

    # The same result dict read at football scope must ALSO fail: downstream
    # scopes cannot rescue an upstream one.
    vf = (V.assess(g, scope='football').evidence or {})['value']
    ok(vf['VERDICT'] == V.RESEARCH_ONLY,
       'the football scope fails on its own gate too')

    # The inversion the owner caught: a DFS-only failure must not touch
    # football.
    g2 = _all_pass('dfs_product')
    g2['DST_SUPPORT_STATUS'] = V.UNSUPPORTED
    v2d = (V.assess(g2, scope='dfs_product').evidence or {})['value']
    v2f = V.assess(g2, scope='football').value
    ok(v2d['VERDICT'] == V.RESEARCH_ONLY,
       'the DFS product is blocked by its own gate')
    ok(v2f is not None and v2f['VERDICT'] == V.DEPLOYABLE,
       'an unvalidated DFS field model says nothing about the football sim')
    ok(v2d['blocked_by_upstream_scopes'] == [],
       f'a same-scope failure is not attributed upstream: '
       f'{v2d["blocked_by_upstream_scopes"]}')


def test_every_non_pass_state_blocks():
    for bad in (V.FAIL, V.BLOCKED, V.UNSUPPORTED, V.NOT_EVALUATED):
        g = _all_pass('football')
        g['DATA_FRESHNESS'] = bad
        o = V.assess(g, scope='football')
        v = (o.evidence or {})['value']
        ok(v['VERDICT'] == V.RESEARCH_ONLY,
           f'gate result {bad} does not clear: {v["VERDICT"]}')
        ok(o.state is State.BLOCKED,
           f'a non-deployable verdict carries a BLOCKED state for {bad}: '
           f'{o.state}')
    ok(V.CLEARING == (V.PASS,), f'PASS is the only clearing result: {V.CLEARING}')


def test_governance_outcomes_map_onto_gate_results():
    pairs = [
        (Outcome.ok('FINE', value={'n': 1}), V.PASS),
        (Outcome.fail('BROKEN', 'because'), V.FAIL),
        (Outcome.blocked('STUCK', 'because', cause=Cause.DATA), V.BLOCKED),
        (Outcome.not_applicable('NOT_BUILT', 'no such model'), V.UNSUPPORTED),
        (Outcome.deferred('LATER', 'awaiting inactives'), V.NOT_EVALUATED),
        (None, V.NOT_EVALUATED),
    ]
    for o, want in pairs:
        got = V.from_outcome(o)
        ok(got == want, f'{getattr(o, "code", None)!r} -> {got} (want {want})')

    # And the mapping is usable end to end: a real Outcome in the dict.
    g = _all_pass('football')
    g['INACTIVE_APPLICATION'] = Outcome.blocked(
        'NO_OFFICIAL_INACTIVE_EVIDENCE', 'no declarations', cause=Cause.DATA)
    v = (V.assess(g, scope='football').evidence or {})['value']
    ok(v['gates']['INACTIVE_APPLICATION'] == V.BLOCKED,
       'a blocked coverage Outcome blocks the verdict directly')
    ok(v['VERDICT'] == V.RESEARCH_ONLY,
       'a board with no inactive evidence is not deployable')


def test_the_status_line_is_generated_and_takes_no_prose():
    sig = inspect.signature(V.render_status_line)
    ok(len(sig.parameters) == 1,
       f'the renderer takes exactly the verdict: {list(sig.parameters)}')

    dep = V.render_status_line(V.assess(_all_pass('football'), scope='football'))
    ok(dep.startswith('FOOTBALL: DEPLOYABLE'), f'deployable line: {dep}')
    ok('gates passed' in dep, f'the line carries the count: {dep}')

    g = _all_pass('dfs_product')
    g['PER_CLUB_LAYER_COVERAGE'] = V.FAIL
    blocked = V.render_status_line(V.assess(g, scope='dfs_product'))
    ok(blocked.startswith('DFS_PRODUCT: RESEARCH_ONLY'),
       f'blocked line: {blocked}')
    ok('PER_CLUB_LAYER_COVERAGE = FAIL' in blocked,
       f'the blocking gate and its result are both on the line: {blocked}')

    g2 = _all_pass('prop_product')
    g2['PROP_CALIBRATION_STATUS'] = V.UNSUPPORTED
    noedge = V.render_status_line(V.assess(g2, scope='prop_product'))
    ok(noedge.startswith('PROP_PRODUCT: NO_SUPPORTED_EDGE'),
       f'no-edge line: {noedge}')

    # Regression: the payload of a blocked Outcome is in .evidence, not
    # .value. A renderer reading only .value crashed here.
    o = V.assess(g, scope='dfs_product')
    ok(o.value is None or isinstance(o.value, dict),
       'the blocked Outcome keeps value where the governance type puts it')
    ok(V.render_status_line(o) == blocked,
       'the line renders identically however the payload is carried')

    for line in (dep, blocked, noedge):
        ok(line.split(':')[1].strip().split()[0] in V.VERDICTS,
           f'the second token is always one of the three answers: {line}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_scope_chain_is_cumulative_and_directed,
              test_all_gates_passing_is_the_only_deployable,
              test_an_absent_required_gate_is_not_a_passing_gate,
              test_readiness_failure_and_no_edge_are_never_the_same_answer,
              test_upstream_invalidity_flows_down_and_never_up,
              test_every_non_pass_state_blocks,
              test_governance_outcomes_map_onto_gate_results,
              test_the_status_line_is_generated_and_takes_no_prose):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())

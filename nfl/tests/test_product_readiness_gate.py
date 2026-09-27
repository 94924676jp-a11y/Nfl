#!/usr/bin/env python3.12
"""The requirement-driven gate must be unable to stay silent about a missing component.

The old gate's defect was structural: one row per DECLARED layer, so a component nobody
wrote produced no row and could not be RED. These checks assert the new gate cannot do that.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import product_readiness as PR  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('every required stage produces a row, on every run')
def t_every_stage():
    m = PR.build()
    stages = {r['stage'] for r in m['rows']}
    missing = [s for s, _ in PR.REQUIRED_STAGES if s not in stages]
    assert not missing, f'required stages with no row: {missing}'
    assert m['n_rows'] >= len(PR.REQUIRED_STAGES), (m['n_rows'], len(PR.REQUIRED_STAGES))
    for r in m['rows']:
        assert r['state'] in (PR.GREEN, PR.AMBER, PR.RED), r
        assert r['detail'], f'{r["stage"]} has no detail'
        assert r['requirement'], f'{r["stage"]} has no stated requirement'
    return f'{m["n_rows"]} rows for {len(PR.REQUIRED_STAGES)} required stages, none silent'


@check('every required position produces a row even with zero coverage')
def t_every_position():
    m = PR.build()
    got = {p['position'] for p in m['positions']}
    for pos in PR.REQUIRED_POSITIONS + PR.OPTIONAL_POSITIONS:
        assert pos in got, f'{pos} produced no row'
    dst = next(p for p in m['positions'] if p['position'] == 'DST')
    assert dst['proprietary'] == 0, dst
    assert dst['state'] != PR.GREEN, (
        'DST has no proprietary component and must not read GREEN')
    k = next(p for p in m['positions'] if p['position'] == 'K')
    assert k['state'] == 'NOT_REQUIRED_BY_THIS_SURFACE', k
    return (f'{len(got)} position rows; DST proprietary=0 state={dst["state"]}; '
            f'K declared not discovered')


@check('the gate is RED today and names what blocks')
def t_red_today():
    m = PR.build()
    assert m['overall'] == PR.RED, m['overall']
    assert m['blocking_stages'], 'RED with nothing named as blocking'
    for s in ('player_prior', 'role_consumed_by_projection', 'td_allocation',
              'joint_simulation', 'historical_validation'):
        assert s in m['blocking_stages'], f'{s} should block and does not'
    assert 'NOT_PROPRIETARY_READY' in m['product_verdict']
    return (f'{m["overall"]}, {len(m["blocking_stages"])} blocking: '
            f'{m["blocking_stages"]}')


@check('the universe requirement catches a scope mismatch')
def t_universe():
    m = PR.build()
    r = next(x for x in m['rows'] if x['stage'] == 'universe_identity')
    assert r['evidence']['expected'] == 457, r
    assert r['evidence']['n'] == 457 and r['state'] == PR.GREEN, r
    assert PR.EXPECTED_UNIVERSE == 457, (
        'the expected universe must be the PRODUCT universe. The old board validated 156 '
        'while the product needed 457, and nothing compared them')
    return 'universe requirement is the product universe (457), not the engine universe'


@check('role CONSUMED is a separate row from role EXISTS')
def t_role_two_rows():
    m = PR.build()
    exists = next(x for x in m['rows'] if x['stage'] == 'current_role')
    consumed = next(x for x in m['rows'] if x['stage'] == 'role_consumed_by_projection')
    assert exists['state'] == PR.GREEN, exists
    assert consumed['state'] == PR.RED, consumed
    return ('role exists GREEN while role consumed RED -- exactly the distinction that '
            'let Drew Lock keep a starter projection')


@check('STOP-WORK RULE 8 fires: assurance has outgrown what it assures')
def t_assurance_ratio():
    r = PR.assurance_ratio()
    assert r.state is State.FAIL, f'the ratio rule did not fire: {r}'
    assert r.code == 'ASSURANCE_OUTGREW_WHAT_IT_ASSURES'
    assert r.evidence['ratio'] > PR.MAX_RATIO, r.evidence
    return (f"{r.evidence['n_assurance']} assurance vs "
            f"{r.evidence['n_projection']} projection test files, ratio "
            f"{r.evidence['ratio']} over max {r.evidence['max_ratio']}")


@check('the postmortem exists and carries all fourteen required sections')
def t_postmortem():
    p = _REPO / 'nfl/research/audit/2026-09-27_WEEK3_POSTMORTEM.md'
    assert p.exists(), 'postmortem missing'
    txt = p.read_text()
    for i, head in enumerate((
            'Executive summary', 'Timeline of failures', 'Root-cause matrix',
            'Wasted-effort', 'Load-bearing pieces still missing',
            'Why this recurred', 'Regression-guard failure analysis',
            'Permanent architecture changes', 'Weekly operating cadence',
            'Stop-work rules', 'V1 acceptance criteria',
            'Work to delete', 'Work to accelerate', 'Shortest path'), 1):
        assert head in txt, f'section {i} ({head}) missing from the postmortem'
    return f'{len(txt.splitlines())} lines, all 14 sections present'


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())

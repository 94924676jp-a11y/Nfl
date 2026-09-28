#!/usr/bin/env python3.12
"""The studies must keep their distinctions, and must not leak into the model.

Two failure modes are worth guarding. A study that reports a lift of 1.07 with an interval spanning
1.0 is not a finding, and collapsing it with one at 2.03 whose interval clears 1.0 by a wide margin
is how "stack everything" becomes received wisdom. And the instruction was explicit that these
conclusions must not be hard-coded, so the import graph is checked, not the intention.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.dfs import studies  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _art():
    if studies.OUT.exists():
        return json.loads(studies.OUT.read_text())
    o = studies.build()
    assert o.state is State.PASS, o
    return o.value


@check('the quarterback-to-receiver stack shows a lift whose interval clears independence')
def t_stack():
    s = _art()['stack_studies']['QB1+WR1_same_club']
    assert s['state'] == 'MEASURED', s
    lift = s['joint_top20_lift_over_independence']
    ci = s['ci95_game_blocked']
    assert lift > 1.5, lift
    assert ci and ci[0] > 1.0, (
        f'the interval {ci} includes independence, so the lift is not established')
    return f'lift {lift} with interval {ci} over {s["n_pairs"]} pairs'


@check('LOAD-BEARING: a lift whose interval spans 1.0 is not reported as established')
def t_not_established():
    art = _art()
    rb = art['stack_studies']['QB1+RB1_same_club']
    assert rb['state'] == 'MEASURED', rb
    ci = rb['ci95_game_blocked']
    assert ci and ci[0] < 1.0 < ci[1], (
        f'the quarterback-and-back interval is {ci}. If this stopped spanning 1.0 the measurement '
        f'changed; it must not be quietly upgraded to a finding, because that is how "stack '
        f'everything" gets asserted')
    wr = art['stack_studies']['QB1+WR1_same_club']
    assert wr['ci95_game_blocked'][0] > rb['ci95_game_blocked'][1], (
        'the receiver stack and the back stack intervals overlap, so they can no longer be '
        'distinguished')
    return (f"quarterback+back lift {rb['joint_top20_lift_over_independence']} interval {ci} spans "
            f"independence; the receiver stack does not, and the two do not overlap")


@check('the same-club stack and the bring-back move OPPOSITE ways with the game total')
def t_crossover():
    c = _art()['conditional_correlation']
    same = c['QB1~WR1_by_total']
    back = c['bring_back_by_total']
    for d in (same, back):
        assert all(v.get('r') is not None for v in d.values()), d
    assert same['49_plus']['r'] < same['under_44']['r'], same
    assert back['49_plus']['r'] > back['under_44']['r'], back
    return (f"same club {same['under_44']['r']} -> {same['49_plus']['r']} as the total rises, "
            f"bring-back {back['under_44']['r']} -> {back['49_plus']['r']} the other way")


@check('stack correlation is strongest for underdogs, which is the game script showing up')
def t_spread():
    c = _art()['conditional_correlation']['QB1~WR1_by_spread']
    assert all(v.get('r') is not None for v in c.values()), c
    assert c['underdog_by_4+']['r'] > c['favoured_by_4+']['r'], c
    rb = _art()['conditional_correlation']['QB1~RB1_by_spread']
    assert rb['underdog_by_4+']['r'] > rb['favoured_by_4+']['r'], rb
    return (f"receiver stack {c['underdog_by_4+']['r']} as an underdog against "
            f"{c['favoured_by_4+']['r']} as a favourite")


@check('the market anchoring result is stated, with what it does and does not mean')
def t_anchor():
    a = _art()['market_anchoring']
    assert a['state'] == 'MEASURED', a
    m = a['market_implied_total_vs_actual']
    assert m['sd_of_implied'] < m['sd_of_actual'], m
    assert 0 < m['r2'] < 1
    assert 'ALLOCATION' in a['WHAT_THIS_MEANS_FOR_US']
    assert 'not evidence the market is unbiased' in a['WHAT_IT_DOES_NOT_MEAN']
    return (f"implied vs actual r2 {m['r2']}, MAE {m['mae']}, spread of implied "
            f"{m['sd_of_implied']} against actual {m['sd_of_actual']} over {a['n_club_games']} "
            f"club-games")


@check('duplication and chalk failure stay BLOCKED rather than approximated')
def t_blocked():
    b = _art()['blocked_studies']
    for k in ('duplication_rates', 'chalk_failure_rates'):
        assert b[k]['state'] == 'BLOCKED', b[k]
        assert b[k]['request'] == 'OUT-040'
        assert b[k]['why_not_approximated']
    return 'both blocked studies name the data they need and why a proxy would measure the proxy'


@check('LOAD-BEARING: no model or optimiser module imports the studies')
def t_no_leak():
    bad = []
    for d in ('nfl/tools', 'nfl/sim', 'nfl/opt', 'nfl/field', 'nfl/warehouse'):
        for f in (_REPO / d).rglob('*.py'):
            txt = f.read_text(errors='ignore')
            if 'research.dfs' in txt or 'DFS_STUDIES' in txt:
                bad.append(str(f.relative_to(_REPO)))
    assert not bad, (
        f'{bad} reads the studies. The instruction was not to hard-code these conclusions: the '
        f'simulator must reproduce these structures or fail to, never import them as constants.')
    return 'nothing under tools, sim, opt, field or warehouse reads the studies'


# EXPOSE EVERY CHECK TO run_suite, the authoritative execution path. Before this the runner
# reported `0 fn, NO TALLY` for this module and executed NONE of its checks, while a direct run of
# the file printed a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())

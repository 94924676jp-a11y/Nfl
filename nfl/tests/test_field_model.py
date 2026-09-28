#!/usr/bin/env python3.12
"""The field model must obey arithmetic, reproduce its own target, and stay downstream.

Ownership is the easiest place in a DFS system to emit a confident number that is not a
measurement, so these checks are about the three things that can be held true regardless of
whether the parameters are right:

  ARITHMETIC. Shares sum to exactly nine slots per entry and no player exceeds 100%. A plain
  normalisation satisfies the first and violates the second, so the check that matters is
  whether the second is actually enforced -- verified here by breaking the capped solve and
  requiring a refusal.

  SELF-CONSISTENCY. The generated field must reproduce the marginals it was given. Otherwise
  it is a pile of legal lineups, and every contest-level number computed from it is noise.

  DIRECTION OF DEPENDENCE. No projection may read the field. That is a structural rule, so
  it is checked structurally, over the import graph, not by intention.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import opponent, ownership as own  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def synth(n_per=12, seed=5):
    import random
    rng = random.Random(seed)
    pool = []
    for pos, n in (('QB', n_per), ('RB', n_per * 2), ('WR', n_per * 3), ('TE', n_per),
                   ('DST', n_per)):
        for i in range(n):
            sal = rng.randrange(30, 90) * 100
            pool.append({'id': f'{pos}{i}', 'position': pos, 'salary': sal,
                         'value': max(0.5, rng.gauss(sal / 1000.0 * 2.2, 3.0))})
    return pool


@check('expected slots sum to exactly nine for any shape mix')
def t_slots():
    for mix in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1 / 3, 1 / 3, 1 / 3), (0.06, 0.13, 0.81)):
        s = own.expected_slots(mix)
        assert abs(sum(s.values()) - 9) < 1e-9, (mix, s)
    # and FLEX really does move the per-position counts
    a, b = own.expected_slots((1, 0, 0)), own.expected_slots((0, 0, 1))
    assert a['RB'] != b['RB'] and a['TE'] != b['TE']
    return 'nine slots under every mix; RB and TE counts move with the FLEX split'


@check('ownership obeys the accounting identity and the 100% ceiling')
def t_identity():
    o = own.ownership(synth(), mix=own.DECLARED_SHAPE_MIX)
    assert o.state is State.PASS, o
    v = o.value
    assert abs(v['sum_of_shares'] - 9) < 1e-6, v['sum_of_shares']
    assert max(v['ownership'].values()) <= 1.0 + 1e-9
    assert v['CALIBRATION_STATE'].startswith('NOT_CALIBRATED')
    return f"shares sum to {v['sum_of_shares']}, max share {max(v['ownership'].values()):.3f}"


@check('LOAD-BEARING: the ceiling is enforced, not assumed -- a plain normalisation is refused')
def t_ceiling_enforced():
    real = own._waterfill

    def normalise(weights, target, cap):
        tot = sum(weights) or 1.0
        return [w / tot * target for w in weights], target / tot
    try:
        own._waterfill = normalise
        o = own.ownership(synth(n_per=2), mix=own.DECLARED_SHAPE_MIX)
        assert o.state is State.FAIL and o.code == 'OWNERSHIP_EXCEEDS_CEILING', (
            f'a plain normalisation was accepted ({o.state}/{o.code}). With only two players '
            f'per position the QB slot forces shares above 100%, which is impossible, so the '
            f'ceiling check is not actually doing anything')
    finally:
        own._waterfill = real
    return 'scaling past 100% ownership is caught and refused'


@check('a pool too thin to fill the slate BLOCKS instead of returning a normalised vector')
def t_infeasible():
    pool = [{'id': 'q', 'position': 'QB', 'salary': 5000, 'value': 20.0}]
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX)
    assert o.state is State.BLOCKED and o.code == 'OWNERSHIP_INFEASIBLE_NOT_ENOUGH_PLAYERS', o
    return 'a one-player pool blocks; the field cannot fill nine slots from it'


@check('the generated field reproduces the target marginals it was given')
def t_field_marginals():
    pool = synth()
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX)
    assert o.state is State.PASS
    g = opponent.generate(pool, o.value['ownership'], mix=own.DECLARED_SHAPE_MIX,
                          n_entries=4000, seed=7, salary_floor=0, ipf_rounds=14)
    assert g.state is State.PASS, g
    r = g.value['realised_vs_target']
    assert r['CONVERGED'], r
    assert g.value['n_entries'] == 4000
    f = g.value['JOINT_FEASIBILITY_FINDING']
    # the residual must be the known arithmetic one, concentrated at minimum salary, and in
    # the direction the cap forces -- if that flipped, something else is wrong
    assert f['mean_signed_gap_at_minimum_salary'] > f['mean_signed_gap_everyone_else'], f
    assert f['mean_signed_gap_at_minimum_salary'] > 0, f
    return (f"mean gap {r['mean_abs_deviation']} within tolerance; residual concentrated at "
            f"minimum salary ({f['mean_signed_gap_at_minimum_salary']:+.4f} against "
            f"{f['mean_signed_gap_everyone_else']:+.4f} elsewhere)")


@check('LOAD-BEARING: an unsatisfiable salary band FAILS rather than returning a short field')
def t_short_field_refused():
    # a pool of minimum-priced players cannot spend the cap, which is a real defect shape:
    # a stale or truncated player file that has lost every expensive player.
    pool = [dict(r, salary=3000) for r in synth()]
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX, budget=27000)
    assert o.state is State.PASS, o
    g = opponent.generate(pool, o.value['ownership'], mix=own.DECLARED_SHAPE_MIX,
                          n_entries=50, seed=3, salary_floor=44000, ipf_rounds=1)
    assert g.state is State.FAIL and g.code == 'FIELD_SAMPLER_CANNOT_MEET_CONSTRAINTS', (
        f'got {g.state}/{g.code}: a field that silently comes back short changes the field '
        f'size that every duplication and win-probability number divides by')
    return ('a pool that cannot reach the salary band is refused, with the accepted count as '
            'evidence')


@check('LOAD-BEARING: a field that does not reproduce its target marginals FAILS')
def t_marginals_enforced():
    pool = synth()
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX)
    # one fitting round from a flat start cannot reach the target, and must not be reported
    # as a field with the residual noted in a corner
    flat = {i: v for i, v in o.value['ownership'].items()}
    flat[max(flat, key=flat.get)] = 0.99
    g = opponent.generate(pool, flat, mix=own.DECLARED_SHAPE_MIX, n_entries=300, seed=4,
                          salary_floor=0, ipf_rounds=1)
    assert g.state is State.FAIL and g.code == 'FIELD_MARGINALS_NOT_REPRODUCED', (
        f'got {g.state}/{g.code}: an unreproduced marginal makes every contest-level number '
        f'downstream noise, so it cannot be a PASS')
    assert 'contradict' in (g.evidence.get('note') or ''), 'the refusal should name the likely cause'
    return (f"mean gap {g.evidence['mean_abs_deviation']} against tolerance "
            f"{opponent.GEN_PARAMETERS['mean_marginal_tolerance']['value']} is refused")


@check('the budget identity is enforced: expected entry salary equals the declared spend')
def t_budget():
    pool = synth()
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX, budget=44000)
    assert o.state is State.PASS, o
    assert abs(o.value['expected_entry_salary'] - 44000) <= 50, o.value['expected_entry_salary']
    cheap = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX, budget=40000)
    assert cheap.value['salary_tilt_solved'] < o.value['salary_tilt_solved'], (
        'a cheaper field must solve to a lower salary tilt; the tilt is derived from the '
        'budget, not declared')
    out = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX, budget=200000)
    assert out.state is State.BLOCKED and out.code == 'OWNERSHIP_BUDGET_UNREACHABLE', out
    return (f"tilt {o.value['salary_tilt_solved']} hits 44,000; a cheaper field solves lower; "
            f"an unreachable budget blocks rather than taking the nearest value")


@check('duplication reports an upper bound when a lineup is unseen, never zero')
def t_dup():
    pool = synth()
    o = own.ownership(pool, mix=own.DECLARED_SHAPE_MIX)
    g = opponent.generate(pool, o.value['ownership'], mix=own.DECLARED_SHAPE_MIX,
                          n_entries=4000, seed=9, salary_floor=0, ipf_rounds=14)
    assert g.state is State.PASS, g
    field = g.value['_field']
    d = opponent.duplication(field, ['QB0', 'RB0', 'RB1', 'WR0', 'WR1', 'WR2', 'TE0', 'TE1',
                                     'DST0'], 100000)
    assert d.state is State.PASS
    assert 'NOT zero duplication' in d.value['ZERO_MEANS']
    assert d.value['expected_other_entries_identical'] >= 0
    seen = opponent.duplication(field, list(field[0]), 100000)
    assert seen.value['field_sample_hits'] >= 1
    return (f"unseen lineup reports an upper bound; a lineup taken from the field reports "
            f"{seen.value['field_sample_hits']} hits")


@check('sensitivity declares its threshold before running and reaches a verdict')
def t_sens():
    s = own.sensitivity(synth(), top_n=20)
    assert s.state is State.PASS, s
    v = s.value
    assert v['threshold']['declared_before_running'] is True
    assert v['n_settings'] == 60, v['n_settings']
    assert v['VERDICT'] in ('LEVERAGE_SET_STABLE_ACROSS_UNCALIBRATED_RANGE',
                            'DECISION_SENSITIVE_TO_UNCALIBRATED_PARAMETERS')
    assert (v['VERDICT'] == 'LEVERAGE_SET_STABLE_ACROSS_UNCALIBRATED_RANGE') == (
        v['worst_top_leverage_overlap'] >= 0.80), 'verdict disagrees with its own threshold'
    return (f"{v['n_settings']} settings, worst overlap {v['worst_top_leverage_overlap']}, "
            f"verdict {v['VERDICT']}")


@check('LOAD-BEARING: no projection or warehouse module imports the field')
def t_no_upstream_import():
    bad = []
    for d in ('nfl/tools', 'nfl/warehouse', 'nfl/eval'):
        for f in (_REPO / d).rglob('*.py'):
            txt = f.read_text(errors='ignore')
            if 'nfl.field' in txt or 'from nfl import field' in txt:
                bad.append(str(f.relative_to(_REPO)))
    assert not bad, (
        f'{bad} reads the field model. Ownership is downstream of football: a projection that '
        f'sees ownership is being fitted to the crowd, which is the one thing this layer must '
        f'never do.')
    return 'no module under tools, warehouse or eval reads nfl.field'


@check('the shape mix decision records both failed identifications rather than one number')
def t_mix_decision():
    d = own.shape_mix_decision([0.06, 0.0, 0.94], [0.06, 0.1333, 0.8067], [0.0, 0.0, 1.0])
    v = d.value
    assert v['state'] == 'DECLARED_PRIOR_NOT_IDENTIFIED'
    assert v['candidate_1_tool_lineups']['rejected_as_field_mix'] is True
    assert v['candidate_1_tool_lineups']['verdict'] == 'DEGENERATE_SINGLE_SHAPE'
    assert v['candidate_2_value_frontier']['verdict'] == 'DEPTH_DEPENDENT_NOT_AN_IDENTIFICATION'
    assert v['candidate_2_value_frontier']['leading_shape_drift_between_depths'] > 0.1
    return ('the degenerate tool mix is rejected and the frontier drift of '
            f"{v['candidate_2_value_frontier']['leading_shape_drift_between_depths']} recorded")


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

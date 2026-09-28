#!/usr/bin/env python3.12
"""Prove the exact optimiser exact, by brute force. Without this, PROVEN_OPTIMAL is just a string.

A dynamic program that is nearly right returns a number that looks fine and is not the maximum. The
only way to know is to enumerate every legal lineup on a pool small enough to enumerate, and check
that the optimiser's value and its reconstructed lineup agree with the brute-force winner -- not just
the value, because a correct value with a wrong roster means the reconstruction is broken and the
lineup that gets uploaded is illegal.

Also checked: that the returned lineup is LEGAL under DK rules, that it is within the cap, and that
k_best returns strictly descending distinct lineups whose top entry equals the single-lineup optimum.
"""
from __future__ import annotations

import itertools
import random
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import exact  # noqa: E402
from sportsplatform.governance.outcome import Outcome  # noqa: E402


def random_pool(rng, n_qb=4, n_rb=6, n_wr=7, n_te=4, n_dst=3, cap_scale=1.0):
    pool = []
    plan = (('QB', n_qb, 4000, 9000), ('RB', n_rb, 3000, 9000), ('WR', n_wr, 3000, 9000),
            ('TE', n_te, 2500, 7000), ('DST', n_dst, 2000, 4000))
    for pos, n, lo, hi in plan:
        for i in range(n):
            sal = rng.randrange(lo, hi + 1, 100)
            pool.append({'id': f'{pos}{i}', 'position': pos, 'salary': sal,
                         'value': round(rng.uniform(0.5, 30.0), 3)})
    return pool


def brute_force(pool, cap):
    """Every legal DK classic lineup, enumerated. The ground truth."""
    by = {}
    for p in pool:
        by.setdefault(p['position'], []).append(p)
    best = None
    for shape in exact.SHAPES:
        groups = []
        ok = True
        for pos, k in shape.items():
            items = by.get(pos) or []
            if len(items) < k:
                ok = False
                break
            groups.append(list(itertools.combinations(items, k)))
        if not ok:
            continue
        for combo in itertools.product(*groups):
            flat = [p for grp in combo for p in grp]
            sal = sum(p['salary'] for p in flat)
            if sal > cap:
                continue
            val = sum(p['value'] for p in flat)
            if best is None or val > best[0]:
                best = (val, tuple(sorted(p['id'] for p in flat)), sal)
    return best


def legal(ids, pool):
    by = {p['id']: p for p in pool}
    counts = {}
    for i in ids:
        counts[by[i]['position']] = counts.get(by[i]['position'], 0) + 1
    return any(counts == dict(sh) for sh in exact.SHAPES)


def run(trials=40, cap=50000, seed=0):
    rng = random.Random(seed)
    fails, checked = [], 0
    for t in range(trials):
        pool = random_pool(rng)
        bf = brute_force(pool, cap)
        o = exact.solve(pool, cap)
        if bf is None:
            if o.state.name == 'PASS':
                fails.append({'trial': t, 'why': 'solver found a lineup where brute force found none'})
            continue
        if o.state.name != 'PASS':
            fails.append({'trial': t, 'why': f'solver failed where brute force succeeded: {o.code}'})
            continue
        checked += 1
        v = o.value
        if abs(v['value'] - bf[0]) > 1e-6:
            fails.append({'trial': t, 'why': 'VALUE_DISAGREES', 'solver': v['value'],
                          'brute_force': round(bf[0], 6)})
            continue
        if v['salary'] > cap:
            fails.append({'trial': t, 'why': 'OVER_CAP', 'salary': v['salary']})
            continue
        if not legal(v['ids'], pool):
            fails.append({'trial': t, 'why': 'ILLEGAL_ROSTER_SHAPE', 'ids': v['ids']})
            continue
        # the reconstructed roster must actually add up to the reported value and salary
        by = {p['id']: p for p in pool}
        rv = sum(by[i]['value'] for i in v['ids'])
        rs = sum(by[i]['salary'] for i in v['ids'])
        if abs(rv - v['value']) > 1e-6 or rs != v['salary']:
            fails.append({'trial': t, 'why': 'RECONSTRUCTION_DOES_NOT_ADD_UP',
                          'reported': [v['value'], v['salary']], 'recomputed': [rv, rs]})
    # a tighter cap, where the knapsack actually binds
    tight_fails = []
    for t in range(trials // 2):
        pool = random_pool(rng)
        tight = 38000
        bf = brute_force(pool, tight)
        o = exact.solve(pool, tight)
        if bf is None:
            continue
        if o.state.name != 'PASS' or abs(o.value['value'] - bf[0]) > 1e-6:
            tight_fails.append({'trial': t, 'cap': tight,
                                'solver': (o.value.get('value') if o.state.name == 'PASS'
                                           else o.code),
                                'brute_force': round(bf[0], 6)})
    # k_best must be strictly descending, distinct, and start at the optimum
    kb_fails = []
    pool = random_pool(rng)
    kb = exact.k_best(pool, 6)
    if kb:
        o = exact.solve(pool)
        if o.state.name == 'PASS' and abs(kb[0]['value'] - o.value['value']) > 1e-6:
            kb_fails.append('k_best top entry is not the single-lineup optimum')
        vals = [x['value'] for x in kb]
        if any(vals[i] < vals[i + 1] - 1e-9 for i in range(len(vals) - 1)):
            kb_fails.append(f'k_best not descending: {vals}')
        sets = [frozenset(x['ids']) for x in kb]
        if len(set(sets)) != len(sets):
            kb_fails.append('k_best returned a duplicate lineup')
        for x in kb:
            if not legal(x['ids'], pool):
                kb_fails.append(f"k_best produced an illegal roster: {x['ids']}")
    ev = {'trials_vs_brute_force': checked, 'failures': fails,
          'tight_cap_trials': trials // 2, 'tight_cap_failures': tight_fails,
          'k_best_values': [x['value'] for x in kb] if kb else [],
          'k_best_failures': kb_fails}
    if fails or tight_fails or kb_fails:
        return Outcome.fail('OPTIMISER_NOT_EXACT',
                            f'{len(fails)} value/legality failures, {len(tight_fails)} at a tight '
                            f'cap, {len(kb_fails)} in k_best', **ev)
    return Outcome.ok('OPTIMISER_PROVEN_EXACT', ev,
                      f'{checked} random slates matched brute force exactly, '
                      f'{trials // 2} more at a binding cap')


def main() -> int:
    o = run()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    ev = getattr(o, 'evidence', {}) or o.value
    for k in ('trials_vs_brute_force', 'tight_cap_trials', 'k_best_values'):
        print(f'  {k}: {ev.get(k)}')
    for k in ('failures', 'tight_cap_failures', 'k_best_failures'):
        v = ev.get(k)
        if v:
            print(f'  {k}: {v[:3]}')
    return 0 if o.state.name == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3.12
"""Archetype-first SHADOW field generator: hard guarantees (no data, synthetic pool).

    python3.12 nfl/tests/test_archetype_field.py
"""
from __future__ import annotations

import collections
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.field import showdown_archetype_field as AF  # noqa: E402

P = F = 0


def check(ok, msg):
    global P, F
    P, F = P + int(bool(ok)), F + int(not ok)
    print(('  ok   ' if ok else '  FAIL ') + msg)


def synthetic():
    rng = np.random.default_rng(0)
    players = {}
    spec = [('A', 'QB', 11000), ('A', 'RB', 10000), ('A', 'WR', 9000), ('A', 'WR', 6000), ('A', 'TE', 3000),
            ('A', 'K', 4000), ('A', 'DST', 3800), ('A', 'WR', 1000),
            ('H', 'QB', 10500), ('H', 'RB', 8000), ('H', 'WR', 10800), ('H', 'WR', 5000), ('H', 'TE', 7000),
            ('H', 'K', 4200), ('H', 'DST', 4000), ('H', 'TE', 200)]
    for i, (t, pos, sal) in enumerate(spec):
        players[f'p{i}|{t}'] = {'name': f'p{i}', 'dk_team': t, 'position': pos, 'flex': {'salary': sal},
                                'cpt': {'salary': int(sal * 1.5)}}
    slate = {'away': 'A', 'home': 'H', 'players': players}
    keys = list(players)
    w = rng.random(len(keys)) + 0.2
    arche = {(3, 1, 0): 0.4, (2, 1, 1): 0.3, (4, 2, 0): 0.2, (1, 1, 1): 0.1}
    # targets that are REACHABLE: the realised ownership of a field the generator itself produces from weights w
    seed_own = {k: {'cpt': 100 * w[i] / w.sum(), 'flex': 500 * w[i] / w.sum(), 'total': 1.0} for i, k in enumerate(keys)}
    pool = AF.Pool(slate, seed_own)
    L, _ = AF.generate(pool, arche, pool.tc, pool.tf, 6000, 1e6, np.random.default_rng(9))
    rc, rf = AF.realised(pool, L)
    own = {k: {'cpt': 100 * rc[i], 'flex': 100 * rf[i], 'total': 100 * (rc[i] + rf[i])} for i, k in enumerate(pool.keys)}
    return slate, own, arche


def test_guarantees():
    slate, own, arche = synthetic()
    pool = AF.Pool(slate, own)
    rng = np.random.default_rng(1)
    L, rej = AF.generate(pool, arche, pool.tc, pool.tf, 4000, 200.0, rng)
    check(len(L) == 4000, f'fills exactly k lineups ({len(L)}; rejected {rej})')
    bad_cap = bad_dist = bad_arch = 0
    seen = collections.Counter()
    for c, f in L:
        seats = [c] + list(f)
        if len(set(seats)) != 6:
            bad_dist += 1
        if pool.csal[c] + pool.sal[list(f)].sum() > AF.CAP:
            bad_cap += 1
        a = (int(sum(pool.team[x] for x in seats)), int(sum(pool.cat[x] == 'QB' for x in seats)),
             int(sum(pool.cat[x] == 'KD' for x in seats)))
        if a not in arche:
            bad_arch += 1
        seen[a] += 1
    check(bad_dist == 0, 'every lineup has six distinct players')
    check(bad_cap == 0, 'every lineup is under the salary cap')
    check(bad_arch == 0, 'every lineup matches an archetype in the prior exactly')
    share = {a: seen[a] / len(L) for a in arche}
    check(all(abs(share[a] - arche[a]) < 0.02 for a in arche), f'archetype rates equal the prior (stratified) {share}')
    rng = np.random.default_rng(2)
    AF.CAL_ROUNDS, AF.CAL_K = 12, 4000
    wc, wf, hist = AF.calibrate(pool, arche, 200.0, rng)
    check(hist[-1]['flex_rmse_pts'] <= hist[0]['flex_rmse_pts'],
          f"calibration does not worsen FLEX residual ({hist[0]['flex_rmse_pts']} -> {hist[-1]['flex_rmse_pts']})")


def test_stack_flags():
    slate, own, arche = synthetic()
    pool = AF.Pool(slate, own)
    kidx = {k: i for i, k in enumerate(pool.keys)}
    # CPT p2 (A WR) with p0 (A QB) in FLEX: the own-QB stack
    lineup = ('p2|A', tuple(sorted(['p0|A', 'p1|A', 'p9|H', 'p10|H', 'p13|H'])))
    gk = (kidx[lineup[0]], tuple(sorted(kidx[x] for x in lineup[1])))
    rows = AF.stack([lineup], kidx, pool, {}, 1000, {}, 1000, own, slate, 100000)
    r = rows[0]
    check('CPT_WR_WITH_OWN_QB x2.0' in r['E2_factors'] and abs(r['E2_adjusted_product'] - 2 * r['E1_independent_product']) < 0.02,
          'E2 applies the ETR-seeded own-QB factor')
    check(isinstance(r['E3_archetype_field'], str) and r['E3_archetype_field'].startswith('<'),
          'a lineup absent from the generated field is reported below resolution, never as 0')
    rows = AF.stack([lineup], kidx, pool, {gk: 50}, 1000, {}, 1000, own, slate, 100000)
    e1, e3 = rows[0]['E1_independent_product'], rows[0]['E3_archetype_field']
    want = 'E1_E3_DISAGREE_GT_2X' if max(e1, e3) / max(min(e1, e3), 1e-12) > 2 else None
    check(rows[0]['FLAG'] == want, f'the >2x disagreement flag follows its definition (E1 {e1}, E3 {e3}, flag {rows[0]["FLAG"]})')


if __name__ == '__main__':
    for t in (test_guarantees, test_stack_flags):
        print('##', t.__name__)
        t()
    print(f'\nPASSED {P} FAILED {F}')
    sys.exit(1 if F else 0)

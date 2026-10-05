#!/usr/bin/env python3.12
"""OWN-05 (Cycle 1 ledger): a CPT's score is exactly 1.5 x the same player's FLEX score IN THE SAME WORLD.

    python3.12 nfl/tests/test_cycle1_checks.py

Checked on a synthetic pool and, when a staged scenario exists, on tonight's real candidates and sealed draws.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import showdown_portfolio as SP  # noqa: E402

P = F = 0


def check(ok, msg):
    global P, F
    P, F = P + ok, F + (not ok)
    print(('  ok   ' if ok else '  FAIL ') + msg)


def test_synthetic():
    rng = np.random.default_rng(0)
    by = {f'p{i}': {'draws': rng.gamma(2.0, 4.0, 500)} for i in range(8)}
    cands = [('p0', ('p1', 'p2', 'p3', 'p4', 'p5')), ('p6', ('p0', 'p1', 'p2', 'p3', 'p7'))]
    M = SP.score_matrix(cands, by)
    for i, (c, f) in enumerate(cands):
        resid = M[i] - sum(by[k]['draws'] for k in f) - 1.5 * by[c]['draws']
        check(float(np.max(np.abs(resid))) < 1e-9, f'candidate {i}: CPT = 1.5 x same-world FLEX draw (max residual {np.max(np.abs(resid)):.2e})')


def test_tonight():
    sd = _REPO / 'nfl/dfs/salaries/showdown_atl_no/BASE'
    if not (sd / 'SCENARIO.json').exists():
        print('  skip no staged scenario')
        return
    from nfl.tools import showdown_portfolio_audit as PA
    export = _REPO / json.loads((sd / 'SCENARIO.json').read_text())['export']
    R = PA.rebuild(export, sd)
    by, cands, M = R['by'], R['cands'], R['M']
    worst = 0.0
    for i, (c, f) in enumerate(cands):
        worst = max(worst, float(np.max(np.abs(M[i] - sum(by[k]['draws'] for k in f) - 1.5 * by[c]['draws']))))
    check(worst < 1e-9, f'all {len(cands)} BASE candidates: CPT = 1.5 x same-world FLEX (max residual {worst:.2e})')
    rows = list(csv.DictReader(open(next(sd.glob('SHOWDOWN_*_PROJECTIONS.csv')))))
    bad = [r['player'] for r in rows if r['sim_mean'] and r['cpt_mean'] and abs(float(r['cpt_mean']) - 1.5 * float(r['sim_mean'])) > 0.011]
    check(not bad, f'board cpt_mean = 1.5 x sim_mean for every player (rounding 0.01) {bad[:5]}')


for t in (test_synthetic, test_tonight):
    print('##', t.__name__)
    t()
print(f'\nPASSED {P} FAILED {F}')
sys.exit(1 if F else 0)

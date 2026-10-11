#!/usr/bin/env python3.12
"""ECW-2 structural acceptance (PREREG_ECW2 section 2) on a Classic arm folder's published worlds. Read-only.

    python3.12 nfl/research/accounting_repair/ecw2_acceptance.py ARM_DIR [SLATE]

  accounting   nfl/tools/world_accounting_check on the arm's STATE, DRAWS and WORLDS: 0 violations required
  ties         share of game-worlds whose two club scores are equal: <= 0.6% (twice the historical 0.29%)
  receivers    median over receivers with mean > 2 catches of (simulated single-game receiving-yards CV / 0.451, the
               2021-2025 benchmark in ECW2_INPUTS.json): within [0.85, 1.15]
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TIE_MAX = 0.006
CV_BAND = (0.85, 1.15)


def evaluate(arm_dir, slate='2026W5') -> dict:
    import numpy as np
    from nfl.tools import classic_slate_run as CR, world_accounting_check as WAC
    d = pathlib.Path(arm_dir)
    b = f'DK_{slate}_EARLY'
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        for src, nm in ((d / f'{b}_STATE.json', 'X_STATE.json'), (d / f'{b}_DRAWS.json', 'X_DRAWS.json'),
                        (d / f'{b}_WORLDS.npz', 'X_WORLDS.npz')):
            (t / nm).symlink_to(src.resolve())
        wac = WAC.check(t)['VIOLATED']
    S, pts, M = CR.load_worlds(d / f'{b}_WORLDS.npz')
    ties = [float((pts[g, :, 0] == pts[g, :, 1]).mean()) for g in range(pts.shape[0])]
    F = {f: i for i, f in enumerate(M['fields'])}
    bench = json.loads((_REPO / 'nfl/research/accounting_repair/ECW2_INPUTS.json').read_text())[
        'benchmark_receiving_yards_cv_gt2_catches']['median_cv']
    ratios = []
    for i, k in enumerate(M['keys']):
        rec = S[i, :, F['receptions']].astype(float)
        if rec.mean() <= 2:
            continue
        y = S[i, :, F['rec_yards']].astype(float) / M['yard_scale']
        if y.mean() > 0:
            ratios.append(float(y.std() / y.mean()) / bench)
    med = statistics.median(ratios) if ratios else None
    out = {'accounting_violations': wac, 'accounting_ok': wac == {},
           'tie_share_by_game': [round(x, 4) for x in ties], 'tie_share_max': round(max(ties), 4),
           'ties_ok': max(ties) <= TIE_MAX,
           'receivers_n': len(ratios), 'receiver_cv_ratio_median': round(med, 4) if med is not None else None,
           'receivers_ok': med is not None and CV_BAND[0] <= med <= CV_BAND[1], 'benchmark_cv': bench}
    out['ALL_OK'] = out['accounting_ok'] and out['ties_ok'] and out['receivers_ok']
    return out


if __name__ == '__main__':
    r = evaluate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '2026W5')
    print(json.dumps(r, indent=1))
    sys.exit(0 if r['ALL_OK'] else 1)

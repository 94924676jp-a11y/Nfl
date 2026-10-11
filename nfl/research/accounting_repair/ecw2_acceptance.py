#!/usr/bin/env python3.12
"""ECW-2 structural acceptance (PREREG_ECW2 section 2) on a Classic arm folder's published worlds. Read-only.

    python3.12 nfl/research/accounting_repair/ecw2_acceptance.py ARM_DIR [SLATE]

  accounting   nfl/tools/world_accounting_check on the arm's STATE, DRAWS and WORLDS: 0 violations required
  ties         share of game-worlds whose two club scores are equal: <= 0.6% (twice the historical 0.29%)
  receivers    median over receivers with mean > 2 catches of (simulated single-game receiving-yards CV / 0.451, the
               2021-2025 benchmark in ECW2_INPUTS.json): within [0.85, 1.15]. PREREG_ECW3 C2: the benchmark is the CV
               over games with > 2 catches, so the simulated CV is taken over the worlds where he has > 2 catches; that
               like-for-like ratio decides. The all-worlds ratio ECW-2 used is still printed, labelled, and decides
               nothing.
               ECW3_ACCEPTANCE_MEASURE.md C3 (registered 2026-10-11 ~20:12 UTC, AFTER the W5 ECW-3 result was seen; decides
               for builds after that registration, never re-scores W5): the benchmark is a population SD over a median of
               10 games per player-season, which is biased low, so the simulated CV is computed with the same estimator
               at the same sample sizes (k worlds, k drawn from history's game counts, pstdev, median over 400 draws).
"""
from __future__ import annotations

import collections
import json
import random
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
    ks = json.loads((_REPO / 'nfl/research/accounting_repair/ECW2_INPUTS.json').read_text())[
        'benchmark_receiving_yards_cv_gt2_catches'].get('games_per_player_season')
    rng = random.Random(20261011)
    ratios, ratios_all, ratios_c3 = [], [], []
    for i, k in enumerate(M['keys']):
        rec = S[i, :, F['receptions']].astype(float)
        if rec.mean() <= 2:
            continue
        y = S[i, :, F['rec_yards']].astype(float) / M['yard_scale']
        if y.mean() > 0:
            ratios_all.append(float(y.std() / y.mean()) / bench)
        yc = y[rec > 2]
        if len(yc) >= 2 and yc.mean() > 0:
            ratios.append(float(yc.std() / yc.mean()) / bench)
            if ks and len(yc) >= 20:
                cv = []
                for _ in range(400):
                    smp = [float(yc[rng.randrange(len(yc))]) for _ in range(rng.choice(ks))]
                    m_ = statistics.mean(smp)
                    if m_ > 0:
                        cv.append(statistics.pstdev(smp) / m_)
                ratios_c3.append(statistics.median(cv) / bench)
    med = statistics.median(ratios) if ratios else None
    med_all = statistics.median(ratios_all) if ratios_all else None
    out = {'accounting_violations': wac, 'accounting_ok': wac == {},
           'tie_share_by_game': [round(x, 4) for x in ties], 'tie_share_max': round(max(ties), 4),
           'ties_ok': max(ties) <= TIE_MAX,
           'receivers_n': len(ratios), 'receiver_cv_ratio_median': round(med, 4) if med is not None else None,
           'receiver_cv_ratio_median_all_worlds_ecw2_measure': round(med_all, 4) if med_all is not None else None,
           'receiver_cv_measure': 'PREREG_ECW3 C2: worlds with > 2 catches',
           'receiver_cv_ratio_median_c3_history_sample_size': (round(statistics.median(ratios_c3), 4)
                                                               if ratios_c3 else None),
           'receivers_ok_c3': bool(ratios_c3) and CV_BAND[0] <= statistics.median(ratios_c3) <= CV_BAND[1],
           'c3_note': 'C3 registered after the W5 ECW-3 result; it decides only for later builds',
           'receivers_ok': med is not None and CV_BAND[0] <= med <= CV_BAND[1], 'benchmark_cv': bench}
    out['ALL_OK'] = out['accounting_ok'] and out['ties_ok'] and out['receivers_ok']
    return out


if __name__ == '__main__':
    r = evaluate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '2026W5')
    print(json.dumps(r, indent=1))
    sys.exit(0 if r['ALL_OK'] else 1)

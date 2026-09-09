"""A3G supplementary: is the marginal MOVING, or is that Monte Carlo?

WHY THIS EXISTS. Clause 5 of predeclaration_a3g.md asked that no per-team
marginal statistic move by more than 1% relative between the incumbent and a
candidate. That clause is DEFECTIVE AS WRITTEN and this script is the proof,
not an excuse: it re-runs the INCUMBENT AGAINST ITSELF under different seeds
and applies the same clause. If the incumbent fails its own clause against
itself, the clause is measuring Monte Carlo noise on integer-ish low-count
quantiles, not a moved marginal. Clause 6 (zero-floor draw count, strict
inequality on a noisy count) is tested the same way.

This is a POST-HOC diagnostic. It was written after seeing the A3G result and
it carries none of the pre-registration's standing. It does not change
a3g_results.json and it does not change the verdict recorded there.

    python3.12 nfl/research/a3g/run_a3g_marginal_noise.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
for _q in (_ROOT, _HERE):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import a3g_lib as A                                              # noqa: E402
from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production import team_volume_v1 as TV                  # noqa: E402

SEASON, WEEK, M = 2026, 1, 4000
SEEDS = (11, 22, 33, 44, 55, 66)
ARMS = ('none', 'off_snaps')
STATS = ('mean', 'sd', 'p05', 'p50', 'p95')
OUT_FILE = os.path.join(_HERE, 'a3g_marginal_noise.json')


def main():
    t0 = time.time()
    sl = A.slate(SEASON, WEEK)
    if sl.state is not State.PASS:
        print(sl); return 1
    pairs = sl.value
    TV.cache_clear()
    marg, zero = {}, {}
    for arm in ARMS:
        for s in SEEDS:
            d = A.draw_slate(SEASON, WEEK, pairs, arm, M, s, per_game=True)
            if d.state is not State.PASS:
                print(f'{arm}/{s}: {d}'); return 1
            marg[(arm, s)] = A.marginal_summary(d.value)
            zero[(arm, s)] = A.zero_floor_count(d.value)
            print(f'  {arm} seed {s}: {time.time() - t0:.0f}s', flush=True)

    OUT = {'artifact': 'A3G_MARGINAL_NOISE',
           'label': 'POST-HOC DIAGNOSTIC. Written after the A3G result was '
                    'seen; carries none of the pre-registration standing and '
                    'changes no verdict in a3g_results.json.',
           'seeds': list(SEEDS), 'draws_per_team': M, 'arms': list(ARMS)}

    # 1. the incumbent judged against ITSELF by clause 5 as written
    self_pairs = [(SEEDS[i], SEEDS[j]) for i in range(len(SEEDS))
                  for j in range(i + 1, len(SEEDS))]
    inc_self = [A.marginal_max_move(marg[('none', a)], marg[('none', b)])
                for a, b in self_pairs]
    OUT['clause5_incumbent_against_itself'] = {
        'n_seed_pairs': len(self_pairs),
        'max_abs_relative_move_min': min(x['max_abs_relative_move']
                                         for x in inc_self),
        'max_abs_relative_move_max': max(x['max_abs_relative_move']
                                         for x in inc_self),
        'seed_pairs_failing_the_1pct_clause': int(sum(
            x['max_abs_relative_move'] > 0.01 for x in inc_self)),
        'worst_example': max(inc_self,
                             key=lambda x: x['max_abs_relative_move'])}

    # 2. candidate vs incumbent, same clause, same footing
    cross = [A.marginal_max_move(marg[('none', a)], marg[('off_snaps', b)])
             for a in SEEDS for b in SEEDS]
    OUT['clause5_candidate_against_incumbent'] = {
        'n_seed_pairs': len(cross),
        'max_abs_relative_move_min': min(x['max_abs_relative_move']
                                         for x in cross),
        'max_abs_relative_move_max': max(x['max_abs_relative_move']
                                         for x in cross),
        'seed_pairs_failing_the_1pct_clause': int(sum(
            x['max_abs_relative_move'] > 0.01 for x in cross))}

    # 3. the corrected statistic: across-seed means, with a seed-noise SE
    keys = sorted(set(marg[('none', SEEDS[0])]))
    worst = {'z': 0.0, 'at': None, 'stat': None}
    per_stat = {}
    for st in STATS:
        zs = []
        for k in keys:
            a = np.array([marg[('none', s)][k][st] for s in SEEDS], float)
            b = np.array([marg[('off_snaps', s)][k][st] for s in SEEDS], float)
            se = np.sqrt(a.var(ddof=1) / len(SEEDS) + b.var(ddof=1) / len(SEEDS))
            if se <= 0:
                z = 0.0 if abs(a.mean() - b.mean()) < 1e-12 else float('inf')
            else:
                z = abs(a.mean() - b.mean()) / se
            zs.append(z)
            if z > worst['z']:
                worst = {'z': float(z), 'at': k, 'stat': st,
                         'incumbent_mean': float(a.mean()),
                         'candidate_mean': float(b.mean()),
                         'seed_se': float(se)}
        zs = np.array(zs, float)
        per_stat[st] = {'n': int(zs.size), 'max_z': float(np.nanmax(zs)),
                        'share_above_2': float(np.mean(zs > 2)),
                        'share_above_3': float(np.mean(zs > 3))}
    OUT['across_seed_z_test'] = {
        'note': 'across-seed mean of each per-team marginal statistic, '
                'candidate vs incumbent, standardised by the seed-to-seed SE. '
                'Under an unmoved marginal roughly 5% should exceed 2.',
        'per_statistic': per_stat, 'worst': worst,
        'n_team_metric_cells': len(keys)}

    # 4. clause 6, the zero-floor count, on the same footing
    z_none = [zero[('none', s)] for s in SEEDS]
    z_cand = [zero[('off_snaps', s)] for s in SEEDS]
    OUT['clause6_zero_floor_draws'] = {
        'incumbent_by_seed': z_none, 'candidate_by_seed': z_cand,
        'incumbent_range': [min(z_none), max(z_none)],
        'candidate_range': [min(z_cand), max(z_cand)],
        'incumbent_seed_pairs_where_a_later_seed_exceeds_an_earlier_one':
            int(sum(z_none[j] > z_none[i] for i in range(len(SEEDS))
                    for j in range(i + 1, len(SEEDS)))),
        'n_incumbent_seed_pairs': len(self_pairs),
        'candidate_mean_minus_incumbent_mean':
            float(np.mean(z_cand) - np.mean(z_none)),
        'seed_se_of_the_difference': float(np.sqrt(
            np.var(z_none, ddof=1) / len(SEEDS)
            + np.var(z_cand, ddof=1) / len(SEEDS)))}

    OUT['runtime_seconds'] = round(time.time() - t0, 1)
    with open(OUT_FILE, 'w') as fh:
        json.dump(OUT, fh, indent=1)
    print(f'\nwrote {OUT_FILE} ({OUT["runtime_seconds"]}s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

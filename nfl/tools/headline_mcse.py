"""What the draw count actually buys on the numbers a reader reads.

SEPARATE FROM THE CONVERGENCE DECISION AND DELIBERATELY SO. `draw_convergence`
applies the predeclared pass/fail criterion and is not permitted to move it.
This module answers a different question and makes no pass/fail claim at all:
for the headline quantities on the displayed board -- a player's mean DK
points, carries, rushing yards, targets, receptions and receiving yards --
how large is the Monte Carlo error at each draw count, in the units the
reader is reading?

That is the number a person needs to decide whether 1,000 draws is enough for
what they are doing, and it is not the same as whether every published
quantity on the whole artifact clears a predeclared tolerance. Conflating the
two is how a criterion gets quietly relaxed: "the headline numbers are fine"
becomes "it converged". It did not converge; the headline numbers are fine,
which is a smaller claim and the only one this file makes.

MCSE by batch means, for the same reason as the decision tool: the draws are
not independent across players.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
N_BATCHES = 20

HEADLINE = (('dk_scoring', 'dk_points'), ('kicking', 'dk_points'),
            ('rushing', 'carries'), ('rushing', 'rushing_yards'),
            ('receiving', 'targets'), ('receiving', 'receptions'),
            ('receiving', 'receiving_yards'),
            ('qb', 'pyds'), ('qb', 'att'), ('qb', 'ryds'))


def mcse(x, n_batches=N_BATCHES):
    x = np.asarray(x, float)
    b = x.shape[0] // n_batches
    if b < 2:
        return float('nan')
    v = np.array([x[i * b:(i + 1) * b].mean() for i in range(n_batches)])
    return float(v.std(ddof=1) / np.sqrt(n_batches))


def main(argv=None):
    dirs = argv or sys.argv[1:]
    if not dirs:
        print('usage: headline_mcse.py <run_dir> [<run_dir> ...]')
        return 2
    out = {}
    for d in dirs:
        m = json.load(open(os.path.join(d, 'player_draws_manifest.json')))
        z = np.load(os.path.join(d, 'player_draws.npz'), allow_pickle=True)
        n = int(m['n_draws'])
        rows = []
        for layer, metric in HEADLINE:
            key = f'{layer}__{metric}'
            if key not in z.files:
                continue
            arr = z[key]
            for r in range(arr.shape[0]):
                v = arr[r]
                mu = float(v.mean())
                # A ROW THAT NEVER MOVES IS NOT A CONVERGENCE QUESTION.
                if float(v.std()) == 0.0:
                    continue
                rows.append({'metric': f'{layer}/{metric}', 'mean': mu,
                             'mcse': mcse(v)})
        # Reported at the quantiles of the ROWS, not averaged: one badly
        # behaved fringe player should be visible, not diluted.
        by = {}
        for metric in sorted({r['metric'] for r in rows}):
            g = [r for r in rows if r['metric'] == metric]
            e = np.array([r['mcse'] for r in g])
            mus = np.array([r['mean'] for r in g])
            top = sorted(g, key=lambda r: -r['mean'])[:8]
            by[metric] = {
                'n_rows': len(g),
                'mcse_median': round(float(np.median(e)), 4),
                'mcse_max': round(float(e.max()), 4),
                'mcse_median_top8_by_mean': round(
                    float(np.median([r['mcse'] for r in top])), 4),
                'mean_of_top8': round(float(np.median(
                    [r['mean'] for r in top])), 3),
                'worst_row_mean': round(float(mus[int(e.argmax())]), 3),
            }
        out[n] = by
        print(f'\n=== {n} draws ===')
        print(f"{'quantity':26s} {'rows':>5s} {'MCSE med':>9s} "
              f"{'MCSE max':>9s} {'MCSE med (top 8)':>17s} {'their mean':>11s}")
        for k, v in by.items():
            print(f"{k:26s} {v['n_rows']:5d} {v['mcse_median']:9.4f} "
                  f"{v['mcse_max']:9.4f} {v['mcse_median_top8_by_mean']:17.4f} "
                  f"{v['mean_of_top8']:11.3f}")
    print()
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

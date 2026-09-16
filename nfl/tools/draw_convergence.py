"""Monte Carlo standard error across a draw-count sweep, by batch means.

Applies DRAW_COUNT_PREDECLARATION.md, which was written before any of these
runs existed. The tolerances are not arguments to this script and cannot be
passed in: a convergence tool whose threshold is a flag is a tool for finding
the threshold that passes.

WHY BATCH MEANS AND NOT sd/sqrt(n). The draws are not independent across
players. They share one team carry budget, one integerised rush partition and
one game script, so a quantity summed or compared across players inherits
that dependence, and the i.i.d. formula understates its error. Batch means
assume only that the batches are exchangeable, which the per-row seeding
protocol delivers by construction.

WHY THE QUANTILES AND PROBABILITIES MATTER MORE THAN THE MEANS. A mean
converges as 1/sqrt(n) with the smallest constant of anything on the board. A
p90 and a small threshold probability converge more slowly, so a draw count
chosen on the means alone would declare convergence while a rushing tail was
still moving. Every published quantity is checked and the binding one is
named in the output.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]

#: From the predeclaration. Changing these here is changing the criterion
#: after seeing the data, which is the failure mode the file exists against.
TOL_MEAN_REL = 0.01
TOL_MEAN_ABS = 0.05
TOL_QUANTILE_REL_IQR = 0.02
TOL_PROB_ABS = 0.01
N_BATCHES = 20

#: A quantile of a variable taking at most this many distinct integer values
#: is flagged as a step function. It is NOT exempted -- see the note at the
#: flag site and the secondary analysis at the end of `main`.
DISCRETE_SUPPORT_MAX = 12

QUANTILES = (10, 25, 75, 90)


def mcse_batch(x, f, n_batches=N_BATCHES):
    """MCSE of statistic `f` by non-overlapping batch means."""
    x = np.asarray(x, float)
    n = x.shape[0]
    b = n // n_batches
    if b < 2:
        return float('nan')
    vals = np.array([f(x[i * b:(i + 1) * b]) for i in range(n_batches)])
    return float(vals.std(ddof=1) / np.sqrt(n_batches))


def audit_run(run_dir):
    """Every published quantity of every row, with its MCSE."""
    m = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    n = int(m['n_draws'])
    out = []
    for layer, spec in sorted(m['layers'].items()):
        for metric in spec['metrics']:
            arr = z[f'{layer}__{metric}']
            for r, row_id in enumerate(spec['row_ids']):
                v = arr[r]
                mu = float(v.mean())
                iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
                key = f'{layer}/{metric}@{row_id}'
                se = mcse_batch(v, np.mean)
                tol = max(TOL_MEAN_REL * abs(mu), TOL_MEAN_ABS)
                out.append({'key': key, 'kind': 'mean', 'value': mu,
                            'mcse': se, 'tol': tol, 'ok': se <= tol})
                for q in QUANTILES:
                    se = mcse_batch(v, lambda a, q=q: np.percentile(a, q))
                    # A DEGENERATE ROW HAS NO SPREAD AND NO TOLERANCE. A row
                    # that is zero in every draw has iqr 0, and 2% of zero is
                    # zero -- which would fail a quantity that cannot move.
                    # Those are recorded as NOT_APPLICABLE, never as pass and
                    # never as fail.
                    if iqr <= 0:
                        out.append({'key': f'{key}.p{q}', 'kind': 'quantile',
                                    'value': float(np.percentile(v, q)),
                                    'mcse': se, 'tol': None, 'ok': None,
                                    'why': 'IQR is zero; the row is '
                                           'degenerate and has no spread to '
                                           'converge'})
                        continue
                    tol = TOL_QUANTILE_REL_IQR * iqr
                    # SMALL-SUPPORT INTEGER QUANTILES ARE FLAGGED, NOT
                    # EXCUSED. A quantile of a variable supported on a handful
                    # of integers is a STEP function: when the requested
                    # quantile falls on a jump, its batch-to-batch variability
                    # is a fraction of 1 and does NOT decay with n, because it
                    # is a property of the discrete distribution rather than
                    # Monte Carlo noise. Measured case: kicking/made_FG50+ p75
                    # over support {0,1,2,3} with 75% mass at 0 -- IQR 0.25,
                    # tolerance 0.005, MCSE 0.115 at every draw count tried.
                    #
                    # The predeclaration did not distinguish these from
                    # continuous quantities, so they are still CHECKED and
                    # still count against the decision. Excusing them here
                    # would be relaxing a tolerance after seeing the data,
                    # which the predeclaration forbids. The flag exists so the
                    # NEXT predeclaration can be written correctly.
                    disc = (len(np.unique(v)) <= DISCRETE_SUPPORT_MAX
                            and np.allclose(v, np.rint(v)))
                    out.append({'key': f'{key}.p{q}', 'kind': 'quantile',
                                'value': float(np.percentile(v, q)),
                                'mcse': se, 'tol': tol, 'ok': se <= tol,
                                'small_support_integer': bool(disc),
                                'n_distinct': int(len(np.unique(v)))})
                # P(zero) is published on every count metric.
                se = mcse_batch(v, lambda a: float((a == 0).mean()))
                out.append({'key': f'{key}.p_zero', 'kind': 'probability',
                            'value': float((v == 0).mean()), 'mcse': se,
                            'tol': TOL_PROB_ABS, 'ok': se <= TOL_PROB_ABS})
    return n, out


def main(argv=None):
    dirs = (argv or sys.argv[1:])
    if not dirs:
        print('usage: draw_convergence.py <run_dir> [<run_dir> ...]')
        return 2
    report = {}
    for d in dirs:
        n, rows = audit_run(d)
        checked = [r for r in rows if r['ok'] is not None]
        bad = [r for r in checked if not r['ok']]
        na = [r for r in rows if r['ok'] is None]
        worst = max(bad, key=lambda r: r['mcse'] / r['tol']) if bad else None
        report[n] = {
            'run_dir': os.path.relpath(d, REPO), 'n_draws': n,
            'n_quantities_checked': len(checked),
            'n_not_applicable_degenerate': len(na),
            'n_failing': len(bad),
            'clears': not bad,
            'binding_quantity': (
                {'key': worst['key'], 'kind': worst['kind'],
                 'value': round(worst['value'], 6),
                 'mcse': round(worst['mcse'], 6),
                 'tolerance': round(worst['tol'], 6),
                 'mcse_over_tolerance': round(worst['mcse'] / worst['tol'], 3)}
                if worst else None),
            'failing_by_kind': {
                k: sum(1 for r in bad if r['kind'] == k)
                for k in ('mean', 'quantile', 'probability')},
        }
        # SECONDARY, AND IT IS NOT THE DECISION. Restricting to quantities
        # the criterion was designed for -- means, probabilities, and
        # quantiles of variables with enough support for a quantile to be a
        # continuous thing -- says what a CORRECTED predeclaration would
        # choose. It is reported beside the decision, never in place of it.
        cont = [r for r in checked
                if not (r['kind'] == 'quantile'
                        and r.get('small_support_integer'))]
        cbad = [r for r in cont if not r['ok']]
        cworst = max(cbad, key=lambda r: r['mcse'] / r['tol']) if cbad else None
        report[n]['secondary_excluding_small_support_integer_quantiles'] = {
            'is_not_the_decision': 'the predeclared criterion does not carve '
                                   'these out. This says what a CORRECTED '
                                   'predeclaration would choose, for the next '
                                   'one to be written against.',
            'n_checked': len(cont), 'n_failing': len(cbad),
            'clears': not cbad,
            'binding': ({'key': cworst['key'], 'mcse': round(cworst['mcse'], 6),
                         'tolerance': round(cworst['tol'], 6)}
                        if cworst else None)}
        print(f"n={n:6d}  checked {len(checked):5d}  failing {len(bad):5d}  "
              f"degenerate {len(na):4d}  "
              + (f"binding {worst['key']} "
                 f"({worst['mcse']:.4f} vs {worst['tol']:.4f})"
                 if worst else 'CLEARS'))
    ok = sorted(k for k, v in report.items() if v['clears'])
    sec = sorted(k for k, v in report.items() if isinstance(v, dict)
                 and v.get('secondary_excluding_small_support_integer_'
                           'quantiles', {}).get('clears'))
    print()
    if ok:
        print(f'SMALLEST DRAW COUNT MEETING EVERY PREDECLARED TOLERANCE: '
              f'{ok[0]}')
        report['chosen'] = ok[0]
    else:
        # NOT A FAILURE OF THE SCRIPT. The predeclaration says to report that
        # nothing clears and name the binding quantity, NOT to extend the grid
        # until something passes.
        print('NO DRAW COUNT ON THIS GRID MEETS EVERY PREDECLARED TOLERANCE.')
        print('The predeclaration forbids extending the grid or relaxing a '
              'tolerance to make the last point work. The binding quantity at '
              'the largest n is named above.')
        report['chosen'] = None
    print()
    print('SECONDARY (NOT THE DECISION) -- excluding quantiles of variables '
          'with at most '
          f'{DISCRETE_SUPPORT_MAX} distinct integer values, whose quantiles '
          'are step functions whose variability does not decay with n:')
    print(f'  smallest clearing n: {sec[0] if sec else "none on this grid"}')
    report['secondary_chosen'] = sec[0] if sec else None
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

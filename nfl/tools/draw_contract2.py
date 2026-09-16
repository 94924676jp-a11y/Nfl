"""Apply draw-count contract 2. The thresholds are constants, not flags.

`draw_convergence.py` applies CONTRACT 1 and is left exactly as it was: its
result stands as a recorded failure and this module does not amend it. A
convergence tool whose threshold is an argument is a tool for finding the
threshold that passes, so both tools hard-code their own.

The four classes and why each gets a different instrument are argued in
DRAW_COUNT_CONTRACT_2.md. In short: a mean is judged against its own
dispersion rather than its level, a probability against an absolute bar, a
DISCRETE quantile against batch AGREEMENT because MCSE is the wrong
instrument for a step function, and a continuous quantile against its IQR.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]

#: From the contract. Changing these here is amending a criterion after
#: seeing the data, which is what the contract exists to prevent.
TOL_MEAN_REL_SD = 0.02
TOL_PROB_ABS = 0.01
TOL_CONT_QUANTILE_REL_IQR = 0.02
DISCRETE_MAX = 12
BATCH_AGREEMENT = 19          # of N_BATCHES
N_BATCHES = 20
QUANTILES = (10, 25, 75, 90)


def _batches(x, n=N_BATCHES):
    b = len(x) // n
    return [x[i * b:(i + 1) * b] for i in range(n)] if b >= 2 else []


def mcse(x, f):
    bs = _batches(np.asarray(x, float))
    if not bs:
        return float('nan')
    v = np.array([f(b) for b in bs])
    return float(v.std(ddof=1) / np.sqrt(len(bs)))


def audit_run(run_dir):
    m = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    out = []
    for layer, spec in sorted(m['layers'].items()):
        for metric in spec['metrics']:
            arr = z[f'{layer}__{metric}']
            for r, row_id in enumerate(spec['row_ids']):
                v = arr[r]
                key = f'{layer}/{metric}@{row_id}'
                uniq = len(np.unique(v))
                if float(v.std()) == 0.0:
                    out.append({'key': key, 'cls': 'DEGENERATE', 'ok': None,
                                'why': 'identically constant in every draw; '
                                       'no dispersion to converge'})
                    continue
                discrete = uniq <= DISCRETE_MAX and np.allclose(v, np.rint(v))
                # Class A -- continuous mean (a discrete COUNT still has a
                # mean, and its mean is continuous; the class is about the
                # STATISTIC, not the raw support).
                se = mcse(v, np.mean)
                tol = TOL_MEAN_REL_SD * float(v.std())
                out.append({'key': key, 'cls': 'A_mean', 'value': float(v.mean()),
                            'mcse': se, 'tol': tol, 'ok': se <= tol})
                # Class B -- p_zero is published for every count metric.
                se = mcse(v, lambda a: float((a == 0).mean()))
                out.append({'key': f'{key}.p_zero', 'cls': 'B_prob',
                            'value': float((v == 0).mean()), 'mcse': se,
                            'tol': TOL_PROB_ABS, 'ok': se <= TOL_PROB_ABS})
                for q in QUANTILES:
                    if discrete:
                        # Class C -- AGREEMENT, not MCSE.
                        bs = _batches(v)
                        vals = [float(np.percentile(b, q)) for b in bs]
                        mode, n_mode = collections.Counter(vals).most_common(1)[0]
                        out.append({
                            'key': f'{key}.p{q}', 'cls': 'C_discrete_quantile',
                            'value': float(np.percentile(v, q)),
                            'agree': n_mode, 'need': BATCH_AGREEMENT,
                            'mode': mode, 'ok': n_mode >= BATCH_AGREEMENT})
                    else:
                        iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
                        se = mcse(v, lambda a, q=q: np.percentile(a, q))
                        if iqr <= 0:
                            out.append({'key': f'{key}.p{q}',
                                        'cls': 'DEGENERATE', 'ok': None,
                                        'why': 'IQR is zero'})
                            continue
                        tol = TOL_CONT_QUANTILE_REL_IQR * iqr
                        out.append({'key': f'{key}.p{q}',
                                    'cls': 'D_cont_quantile',
                                    'value': float(np.percentile(v, q)),
                                    'mcse': se, 'tol': tol, 'ok': se <= tol})
    return int(m['n_draws']), out


def main(argv=None):
    dirs = argv or sys.argv[1:]
    if not dirs:
        print('usage: draw_contract2.py <run_dir> [<run_dir> ...]')
        return 2
    report, clears = {}, []
    for d in dirs:
        n, rows = audit_run(d)
        checked = [r for r in rows if r['ok'] is not None]
        bad = [r for r in checked if not r['ok']]
        by_cls = collections.Counter(r['cls'] for r in bad)

        def sev(r):
            if r['cls'] == 'C_discrete_quantile':
                return (r['need'] - r['agree']) / r['need']
            return r['mcse'] / r['tol'] - 1.0
        worst = max(bad, key=sev) if bad else None
        report[n] = {
            'run_dir': os.path.relpath(d, REPO), 'n_draws': n,
            'n_checked': len(checked),
            'n_degenerate': len(rows) - len(checked),
            'n_failing': len(bad), 'failing_by_class': dict(by_cls),
            'clears': not bad,
            'binding': ({'key': worst['key'], 'class': worst['cls'],
                         **({'agree': worst['agree'], 'need': worst['need']}
                            if worst['cls'] == 'C_discrete_quantile' else
                            {'mcse': round(worst['mcse'], 6),
                             'tolerance': round(worst['tol'], 6)})}
                        if worst else None)}
        if not bad:
            clears.append(n)
        print(f'n={n:6d}  checked {len(checked):5d}  failing {len(bad):5d}  '
              f'{dict(by_cls)}  '
              + (f"binding {worst['key']} [{worst['cls']}]" if worst
                 else 'CLEARS'))
    print()
    if clears:
        print(f'PRODUCTION DRAW COUNT UNDER CONTRACT 2: {min(clears)}')
        report['chosen'] = min(clears)
    else:
        print('NO DRAW COUNT ON THIS GRID CLEARS CONTRACT 2.')
        print('The contract forbids extending the grid or amending itself. '
              'The binding quantity and its class are named above.')
        report['chosen'] = None
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

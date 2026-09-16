"""Apply contract 3: bootstrap stability of the empirical quantile itself.

Contracts 1 and 2 judged a quantile by an MCSE against a BORROWED scale --
the IQR -- and both failed the same way, because a low-usage player's IQR
collapses for the same reason his mean does. Replacing the divisor would have
been the third instance of one move. This measures the estimator directly:
resample the sealed draws, recompute the quantile, and report how far it
moves. That is the question a reader is actually asking.

Thresholds are constants here, as in both earlier tools, and for the same
reason: a convergence checker whose threshold is a flag is a tool for finding
the threshold that passes.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]

R_BOOT = 400
N_BATCHES = 20
BATCH_AGREEMENT = 19
DISCRETE_MAX = 12
QUANTILES = (10, 25, 50, 75, 90)

#: Native-unit thresholds from the contract: the smallest difference a reader
#: would act on. Absolute, so they cannot collapse on a low-usage player.
THRESH_YARDS = 1.0
THRESH_DK = 0.25
THRESH_COUNT = 0.25
THRESH_PROB = 0.01

#: Intrinsic-instability constants. The most arguable numbers in the
#: contract, named there as such.
UNSTABLE_RANGE_FRAC = 0.20
UNSTABLE_DENSITY_FRAC = 0.25

_YARD = ('yards', 'yds', 'pyds', 'ryds')
_DK = ('dk_points',)


def family(metric: str) -> tuple:
    m = metric.lower()
    if any(k in m for k in _DK):
        return 'dk', THRESH_DK
    if any(k in m for k in _YARD):
        return 'yards', THRESH_YARDS
    return 'count', THRESH_COUNT


def boot_quantiles(v, q, rng, r=R_BOOT):
    n = len(v)
    idx = rng.integers(0, n, size=(r, n))
    return np.percentile(v[idx], q, axis=1)


def intrinsic_instability(v, reps, sd):
    """Is this quantile unstable for a reason no draw count fixes?"""
    rng_span = float(v.max() - v.min())
    if rng_span > 0 and float(reps.max() - reps.min()) > \
            UNSTABLE_RANGE_FRAC * rng_span:
        return ('SPAN', f'bootstrap replicates span '
                        f'{float(reps.max() - reps.min()):.3g} of a '
                        f'{rng_span:.3g} range -- the quantile is not '
                        f'localised')
    if sd > 0:
        centre = float(np.median(reps))
        near = float(((v >= centre - sd) & (v <= centre + sd)).mean())
        hist, edges = np.histogram(v, bins=min(40, max(5, len(np.unique(v)))))
        w = edges[1] - edges[0]
        peak = float(hist.max() / len(v)) * (2 * sd / w) if w > 0 else 0.0
        if peak > 0 and near < UNSTABLE_DENSITY_FRAC * peak:
            return ('SPARSE', f'density within +/-1 bootstrap sd is '
                              f'{near:.3g} against a modal {peak:.3g} -- the '
                              f'quantile sits in a sparse region')
    return None


def audit_run(run_dir, seed=20260916):
    m = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    rng = np.random.default_rng(seed)
    out = []
    for layer, spec in sorted(m['layers'].items()):
        for metric in spec['metrics']:
            arr = z[f'{layer}__{metric}']
            fam, thr = family(metric)
            for r, row_id in enumerate(spec['row_ids']):
                v = np.asarray(arr[r], float)
                key = f'{layer}/{metric}@{row_id}'
                if float(v.std()) == 0.0:
                    out.append({'key': key, 'cls': 'DEGENERATE', 'ok': None,
                                'why': 'constant in every draw'})
                    continue
                uniq = np.unique(v)
                discrete = len(uniq) <= DISCRETE_MAX and \
                    np.allclose(v, np.rint(v))
                # Probabilities are published for every count metric.
                bs = [v[i * (len(v) // N_BATCHES):
                        (i + 1) * (len(v) // N_BATCHES)]
                      for i in range(N_BATCHES)]
                pz = np.array([float((b == 0).mean()) for b in bs])
                se = float(pz.std(ddof=1) / np.sqrt(N_BATCHES))
                out.append({'key': f'{key}.p_zero', 'cls': 'prob',
                            'value': float((v == 0).mean()), 'stat': se,
                            'thr': THRESH_PROB, 'ok': se <= THRESH_PROB})
                reps_all = boot_quantiles(v, list(QUANTILES), rng)
                for qi, q in enumerate(QUANTILES):
                    reps = reps_all[qi]
                    sd = float(reps.std(ddof=1))
                    point = float(np.percentile(v, q))
                    if discrete:
                        vals = [float(np.percentile(b, q)) for b in bs]
                        mode, n_mode = collections.Counter(
                            vals).most_common(1)[0]
                        modal_boot = float((reps == mode).mean())
                        out.append({
                            'key': f'{key}.p{q}', 'cls': 'discrete_quantile',
                            'value': point, 'agree': n_mode,
                            'need': BATCH_AGREEMENT, 'mode': mode,
                            # REPORTED WHETHER IT PASSES OR FAILS.
                            'boot_modal_fraction': round(modal_boot, 4),
                            'ok': n_mode >= BATCH_AGREEMENT})
                        continue
                    unst = intrinsic_instability(v, reps, sd)
                    if unst:
                        out.append({'key': f'{key}.p{q}',
                                    'cls': 'INTRINSICALLY_UNSTABLE',
                                    'value': point, 'stat': sd, 'thr': thr,
                                    'reason': unst[0], 'why': unst[1],
                                    'ok': None})
                        continue
                    out.append({'key': f'{key}.p{q}', 'cls': 'cont_quantile',
                                'family': fam, 'value': point, 'stat': sd,
                                'thr': thr, 'ok': sd <= thr})
    return int(m['n_draws']), out


def main(argv=None):
    dirs = argv or sys.argv[1:]
    if not dirs:
        print('usage: draw_contract3.py <run_dir> [...]')
        return 2
    report, clears = {}, []
    for d in dirs:
        n, rows = audit_run(d)
        checked = [r for r in rows if r['ok'] is not None]
        bad = [r for r in checked if not r['ok']]
        unstable = [r for r in rows if r['cls'] == 'INTRINSICALLY_UNSTABLE']

        def sev(r):
            if r['cls'] == 'discrete_quantile':
                return (r['need'] - r['agree']) / r['need']
            return r['stat'] / r['thr'] - 1.0
        worst = max(bad, key=sev) if bad else None
        report[n] = {
            'run_dir': os.path.relpath(d, REPO), 'n_draws': n,
            'n_checked': len(checked), 'n_failing': len(bad),
            'n_intrinsically_unstable': len(unstable),
            'n_degenerate': sum(1 for r in rows if r['cls'] == 'DEGENERATE'),
            'failing_by_class': dict(collections.Counter(
                r['cls'] for r in bad)),
            'clears': not bad,
            'binding': ({'key': worst['key'], 'class': worst['cls'],
                         **({'agree': worst['agree'], 'need': worst['need'],
                             'boot_modal_fraction':
                                 worst['boot_modal_fraction']}
                            if worst['cls'] == 'discrete_quantile'
                            else {'boot_sd': round(worst['stat'], 4),
                                  'threshold': worst['thr'],
                                  'family': worst.get('family')})}
                        if worst else None),
            'unstable_examples': [
                {'key': r['key'], 'reason': r['reason'],
                 'boot_sd': round(r['stat'], 4), 'why': r['why']}
                for r in unstable[:6]]}
        if not bad:
            clears.append(n)
        print(f'n={n:6d}  checked {len(checked):5d}  failing {len(bad):5d}  '
              f'unstable {len(unstable):4d}  '
              f'{dict(collections.Counter(r["cls"] for r in bad))}  '
              + (f"binding {worst['key']} [{worst['cls']}]" if worst
                 else 'CLEARS'))
    print()
    if clears:
        print(f'PRODUCTION DRAW COUNT UNDER CONTRACT 3: {min(clears)}')
        report['chosen'] = min(clears)
    else:
        print('NO DRAW COUNT ON THIS GRID CLEARS CONTRACT 3.')
        report['chosen'] = None
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
